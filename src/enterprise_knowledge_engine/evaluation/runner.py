"""Administrative, isolated synthetic benchmark; no fake quality results."""

import argparse
import csv
import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from platform import python_version
from time import perf_counter
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.core.errors import ServiceError
from enterprise_knowledge_engine.core.logging import configure_logging
from enterprise_knowledge_engine.db.models import Document, DocumentChunk, Tenant
from enterprise_knowledge_engine.db.session import build_engine
from enterprise_knowledge_engine.evaluation.answers import OpenAIJudge, RecordingLLM, check_answer
from enterprise_knowledge_engine.evaluation.dataset import Dataset
from enterprise_knowledge_engine.evaluation.metrics import METRICS, aggregate
from enterprise_knowledge_engine.evaluation.performance import latency_summary
from enterprise_knowledge_engine.ingestion.chunking import chunk_sections
from enterprise_knowledge_engine.ingestion.embeddings import OpenAIEmbeddingProvider
from enterprise_knowledge_engine.ingestion.extraction import extract
from enterprise_knowledge_engine.ingestion.service import ingest
from enterprise_knowledge_engine.qa.providers import build_llm_provider
from enterprise_knowledge_engine.qa.schemas import AskRequest
from enterprise_knowledge_engine.qa.service import answer_question
from enterprise_knowledge_engine.retrieval.reranking import build_reranker
from enterprise_knowledge_engine.retrieval.schemas import SearchRequest
from enterprise_knowledge_engine.retrieval.service import search

STRATEGIES = {
    "vector": ("vector", False),
    "keyword": ("keyword", False),
    "hybrid": ("hybrid", False),
    "hybrid_rerank": ("hybrid", True),
}


@contextmanager
def indexed_dataset(dataset: Dataset, config: Settings, semantic: bool) -> Iterator[tuple]:
    engine = build_engine(config)
    tenants = {label: uuid4() for label in sorted({d.tenant for d in dataset.manifest.documents})}
    mapping = {}
    try:
        with Session(engine) as session, session.begin():
            session.add_all(
                Tenant(id=id_, name="Synthetic evaluation", slug=str(id_))
                for id_ in tenants.values()
            )
        for source in dataset.manifest.documents:
            data = dataset.content(source)
            extracted = extract(data, source.label + ".md", config)
            with Session(engine) as session:
                if semantic:
                    doc = ingest(
                        session,
                        tenants[source.tenant],
                        data,
                        extracted,
                        config,
                        OpenAIEmbeddingProvider(config),
                    )
                else:
                    # An evaluation-only lexical corpus has NULL vectors, never fake embeddings.
                    chunks = chunk_sections(
                        extracted.sections,
                        config.chunk_size,
                        config.chunk_overlap,
                        config.max_chunks,
                    )
                    with session.begin():
                        doc = Document(
                            tenant_id=tenants[source.tenant],
                            title=source.label,
                            filename=source.label + ".md",
                            status="ready",
                            chunk_count=len(chunks),
                            size_bytes=len(data),
                            media_type="text/markdown",
                        )
                        session.add(doc)
                        session.flush()
                        session.add_all(
                            DocumentChunk(
                                tenant_id=tenants[source.tenant],
                                document_id=doc.id,
                                position=c.position,
                                content=c.content,
                                start_offset=c.start_offset,
                                end_offset=c.end_offset,
                                page_number=c.page_number,
                            )
                            for c in chunks
                        )
                session.commit()
                # Stable chunk UUIDs make score ties reproducible across isolated benchmark runs.
                # Run one benchmark for this dataset at a time; concurrent collisions fail safely.
                with session.begin():
                    for chunk in session.scalars(
                        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
                    ).all():
                        chunk.id = uuid5(
                            NAMESPACE_URL,
                            f"eke-eval:{dataset.sha256}:{source.label}:{chunk.position}",
                        )
                mapping[str(doc.id)] = source.label
        yield engine, tenants, mapping
    finally:
        try:
            with Session(engine) as session, session.begin():
                session.execute(delete(Tenant).where(Tenant.id.in_(tenants.values())))
        finally:
            engine.dispose()


def write_reports(output: Path, metadata: dict, rows: list[dict], ks: list[int]) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    summaries = {}
    for strategy in metadata["strategies"]:
        selected = [r for r in rows if r["strategy"] == strategy]
        if metadata["strategies"][strategy]["status"] == "pending":
            continue
        summaries[strategy] = aggregate(selected, ks)
    answer_metrics = {}
    for strategy in summaries:
        selected = [r for r in rows if r["strategy"] == strategy]
        answer_metrics[strategy] = {}
        for metric in [
            "abstention_correct",
            "reference_exact_match",
            "citation_validity",
            "quote_membership",
            "forbidden_output_detected",
        ]:
            values = [
                r["answer_evaluation"][metric]
                for r in selected
                if r.get("answer_evaluation", {}).get(metric) is not None
            ]
            answer_metrics[strategy][metric] = {
                "value": sum(values) / len(values) if values else None,
                "denominator": len(values),
            }
    report = {
        **metadata,
        "answer_metrics": answer_metrics,
        "latency": {
            s: latency_summary([r["latency_ms"] for r in rows if r["strategy"] == s])
            for s in summaries
        },
        "metrics": summaries,
        "policy": "Labels; macro mean over queries with relevance. Failures score zero, "
        "zero-relevance queries excluded. Precision denominator K; cutoff and pool MRR reported.",
    }
    (output / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    with (output / "per_question.jsonl").open("w") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
    with (output / "metrics.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["strategy", "category", "k", "denominator", "errors", *METRICS])
        for strategy, summary in summaries.items():
            for category, group in summary.items():
                for k, scores in group["at_k"].items():
                    writer.writerow(
                        [
                            strategy,
                            category,
                            k,
                            scores["recall"]["denominator"],
                            group["errors"],
                            *(scores[m]["value"] for m in METRICS),
                        ]
                    )
    lines = [
        "# Synthetic retrieval comparison",
        "",
        f"Dataset SHA-256: `{metadata['dataset_sha256']}`",
        "",
        "No fake embeddings. Pending strategies have no scores. Errors count as empty retrieval.",
        "",
        "| Strategy | State | K | Recall | Precision | MRR@K | nDCG | Hit rate |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for strategy, state in metadata["strategies"].items():
        if strategy not in summaries:
            lines.append(f"| {strategy} | pending: {state['reason']} | — | — | — | — | — | — |")
        else:
            for k, scores in summaries[strategy]["overall"]["at_k"].items():
                values = [
                    f"{scores[m]['value']:.4f}" if scores[m]["value"] is not None else "—"
                    for m in METRICS
                ]
                lines.append(
                    f"| {strategy} | {state['status']} | {k} | " + " | ".join(values) + " |"
                )
    lines += [
        "",
        "Latency is per serial service call including query embedding/reranking where applicable;",
        "Indexing excluded. This tiny corpus does not establish production performance.",
        "Documents deduplicated by first appearance within the first 50 retrieved chunks.",
    ]
    (output / "comparison.md").write_text("\n".join(lines) + "\n")
    return report


def run(
    dataset: Dataset,
    config: Settings,
    output: Path,
    ks: list[int],
    strategies: list[str],
    allow_paid: bool = False,
    answers: bool = False,
    judge_model: str | None = None,
    max_answer_calls: int = 10,
    max_judge_calls: int = 5,
) -> dict:
    started_at = datetime.now(UTC).isoformat()
    if not ks or any(type(k) is not int or not 1 <= k <= 10 for k in ks):
        raise ValueError("K must be in 1–10")
    if not strategies or any(s not in STRATEGIES for s in strategies):
        raise ValueError("Unknown strategy")
    if answers and not (allow_paid and config.llm_provider == "openai" and config.openai_api_key):
        raise ValueError(
            "Answer evaluation requires explicit paid authorization and real LLM credentials"
        )
    if judge_model and not answers:
        raise ValueError("Judge requires answer evaluation")
    if not 1 <= max_answer_calls <= 136 or not 1 <= max_judge_calls <= 20:
        raise ValueError("Invalid evaluation call budgets")
    semantic = bool(
        allow_paid
        and any(s != "keyword" for s in strategies)
        and config.embedding_provider == "openai"
        and config.openai_api_key
        and config.openai_api_key.get_secret_value()
    )
    real_reranker = bool(
        allow_paid
        and config.reranker_provider == "cohere"
        and config.cohere_api_key
        and config.cohere_api_key.get_secret_value()
    )
    states = {
        s: {
            "status": "pending",
            "reason": "real embeddings or explicit paid authorization unavailable",
        }
        if s != "keyword" and not semantic
        else (
            {
                "status": "pending",
                "reason": "real reranker or explicit paid authorization unavailable",
            }
            if s == "hybrid_rerank" and not real_reranker
            else {"status": "completed"}
        )
        for s in strategies
    }
    rows = []
    judge = OpenAIJudge(config, judge_model, max_judge_calls) if judge_model else None
    remaining_answers = max_answer_calls
    context = (
        indexed_dataset(dataset, config, semantic)
        if any(state["status"] != "pending" for state in states.values())
        else nullcontext((None, {}, {}))
    )
    environment = {"python": python_version(), "postgresql": None, "pgvector_extension": None}
    with context as (engine, tenants, mapping):
        if engine is not None:
            with Session(engine) as session:
                environment["postgresql"] = session.scalar(text("SHOW server_version"))
                environment["pgvector_extension"] = session.scalar(
                    text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
                )
        for strategy, state in states.items():
            if state["status"] == "pending":
                continue
            mode, rerank = STRATEGIES[strategy]
            for question in dataset.questions:
                started = perf_counter()
                row = {
                    "strategy": strategy,
                    "question_id": question.id,
                    "category": question.category,
                    "tenant_label": question.tenant,
                    "relevance": question.relevance,
                    "ranked_labels": [],
                    "error": None,
                    "results": [],
                }
                try:
                    with Session(engine) as session:
                        response = search(
                            session,
                            tenants[question.tenant],
                            SearchRequest(
                                query=question.question, mode=mode, top_k=50, rerank=rerank
                            ),
                            config,
                            OpenAIEmbeddingProvider(config),
                            build_reranker(config),
                        )
                    if rerank and response.results and response.reranking_status != "applied":
                        raise ServiceError(
                            "evaluation_reranking_failed", "Actual reranking did not apply"
                        )
                    row["ranked_labels"] = list(
                        dict.fromkeys(mapping[str(r.document_id)] for r in response.results)
                    )
                    row["results"] = [
                        {"label": mapping[str(r.document_id)], **r.model_dump(mode="json")}
                        for r in response.results
                    ]
                    if any(
                        label
                        not in {
                            d.label
                            for d in dataset.manifest.documents
                            if d.tenant == question.tenant
                        }
                        for label in row["ranked_labels"]
                    ):
                        raise ServiceError(
                            "evaluation_tenant_violation", "Tenant isolation check failed"
                        )
                except Exception as error:
                    row["error"] = getattr(error, "code", "evaluation_search_failed")
                    row["ranked_labels"] = []
                    row["results"] = []
                    state["status"] = "completed_with_errors"
                row["latency_ms"] = round((perf_counter() - started) * 1000, 3)
                if answers and remaining_answers > 0 and not row["error"]:
                    remaining_answers -= 1
                    recorder = RecordingLLM(build_llm_provider(config))
                    with Session(engine) as session:
                        outcome = answer_question(
                            session,
                            tenants[question.tenant],
                            AskRequest(
                                question=question.question,
                                search_mode=mode,
                                top_k=min(max(ks), 20),
                                rerank=rerank,
                            ),
                            config,
                            OpenAIEmbeddingProvider(config),
                            build_reranker(config),
                            recorder,
                        )
                    row["answer"] = outcome.response.model_dump(mode="json")
                    row["answer_evaluation"] = check_answer(
                        question, outcome.response, recorder.sources
                    )
                    if judge and outcome.response.status != "error":
                        row["judge"] = judge.evaluate(question, outcome.response, recorder.sources)
                else:
                    row["answer_evaluation"] = {"status": "not_run", "reason": "disabled_or_budget"}
                rows.append(row)
        mapping_record = mapping.copy()
    return write_reports(
        output,
        {
            "run_started_at": started_at,
            "run_finished_at": datetime.now(UTC).isoformat(),
            "environment": environment,
            "dataset_version": dataset.manifest.version,
            "dataset_sha256": dataset.sha256,
            "question_count": len(dataset.questions),
            "strategies": states,
            "document_id_to_label": mapping_record,
            "configuration": {
                "embedding_provider": "openai" if semantic else "none_keyword_only",
                "embedding_model": config.embedding_model if semantic else None,
                "embedding_dimensions": config.embedding_dimensions if semantic else None,
                "chunk_size": config.chunk_size,
                "chunk_overlap": config.chunk_overlap,
                "candidate_limit": config.search_candidate_limit,
                "rrf_k": config.search_rrf_k,
                "vector_strategy": config.search_vector_strategy,
                "reranker_model": config.reranker_model if real_reranker else None,
                "answer_calls": max_answer_calls - remaining_answers if answers else 0,
                "judge_model": judge_model,
                "max_answer_calls": max_answer_calls,
                "max_judge_calls": max_judge_calls,
                "answer_model": config.llm_model if answers else None,
                "provider_and_context_settings": {
                    name: getattr(config, name)
                    for name in (
                        "embedding_batch_size",
                        "embedding_timeout_seconds",
                        "embedding_max_retries",
                        "llm_timeout_seconds",
                        "llm_max_retries",
                        "llm_max_output_tokens",
                        "qa_max_sources",
                        "qa_context_char_budget",
                        "qa_max_passage_chars",
                        "qa_min_cosine_similarity",
                        "qa_min_keyword_score",
                        "search_hnsw_ef_search",
                        "reranker_max_candidates",
                        "reranker_timeout_seconds",
                    )
                },
            },
            "runtime_versions": {
                p: version(p) for p in ["sqlalchemy", "pgvector", "openai", "mcp"]
            },
        },
        rows,
        ks,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("evaluation/datasets/v1"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/local"))
    parser.add_argument("--ks", default="1,3,5,10")
    parser.add_argument("--strategies", default=",".join(STRATEGIES))
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--answers", action="store_true")
    parser.add_argument("--judge-provider", choices=["none", "openai"], default="none")
    parser.add_argument("--judge-model", default="gpt-4.1-mini")
    parser.add_argument("--max-answer-calls", type=int, default=10)
    parser.add_argument("--max-judge-calls", type=int, default=5)
    args = parser.parse_args()
    try:
        dataset = Dataset(args.dataset)
        if args.validate_only:
            print(json.dumps({"questions": len(dataset.questions), "sha256": dataset.sha256}))
            return
        config = Settings()
        configure_logging(config.log_level)
        report = run(
            dataset,
            config,
            args.output,
            sorted(set(map(int, args.ks.split(",")))),
            args.strategies.split(","),
            args.allow_paid,
            args.answers,
            args.judge_model if args.judge_provider == "openai" else None,
            args.max_answer_calls,
            args.max_judge_calls,
        )
        print(json.dumps({"strategies": report["strategies"], "artifacts": str(args.output)}))
        if any(s["status"] == "completed_with_errors" for s in report["strategies"].values()):
            raise SystemExit(1)
    except Exception:
        logging.getLogger(__name__).error("evaluation_failed")
        print(
            "Evaluation failed; check dataset, configuration and database.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
