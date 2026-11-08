import json
import os
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.db.models import DocumentChunk, Tenant
from enterprise_knowledge_engine.evaluation.dataset import Dataset
from enterprise_knowledge_engine.evaluation.runner import indexed_dataset, run

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1", reason="Requires disposable migrated PostgreSQL"
    ),
]


def test_keyword_corpus_has_no_fake_vectors_and_cleans_up():
    config, dataset = Settings(), Dataset(Path("evaluation/datasets/v1"))
    with indexed_dataset(dataset, config, False) as (engine, tenants, mapping):
        assert len(mapping) == 12
        with Session(engine) as session:
            count = session.scalar(
                select(func.count())
                .select_from(DocumentChunk)
                .where(
                    DocumentChunk.tenant_id.in_(tenants.values()),
                    DocumentChunk.embedding.is_not(None),
                )
            )
            assert count == 0
    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count()).select_from(Tenant).where(Tenant.id.in_(tenants.values()))
            )
            == 0
        )
    engine.dispose()


def test_reproducible_keyword_reports_and_pending_strategies(tmp_path):
    config, dataset = Settings(), Dataset(Path("evaluation/datasets/v1"))
    first = run(
        dataset,
        config,
        tmp_path / "one",
        [1, 3, 5, 10],
        ["vector", "keyword", "hybrid", "hybrid_rerank"],
    )
    second = run(dataset, config, tmp_path / "two", [1, 3, 5, 10], ["keyword"])
    assert first["metrics"]["keyword"] == second["metrics"]["keyword"]
    assert first["strategies"]["keyword"]["status"] == "completed"
    assert first["strategies"]["hybrid"]["status"] == "pending"
    assert first["configuration"]["embedding_provider"] == "none_keyword_only"
    eligible = sum(bool(q.relevance) for q in dataset.questions)
    assert first["metrics"]["keyword"]["overall"]["at_k"]["1"]["recall"]["denominator"] == eligible
    assert all(
        (tmp_path / "one" / p).is_file()
        for p in ["metrics.json", "metrics.csv", "comparison.md", "per_question.jsonl"]
    )
    rows = [
        json.loads(line) for line in (tmp_path / "one/per_question.jsonl").read_text().splitlines()
    ]
    assert len(rows) == 34
    assert not any(r["error"] for r in rows)
    for row in rows:
        allowed = {d.label for d in dataset.manifest.documents if d.tenant == row["tenant_label"]}
        assert set(row["ranked_labels"]) <= allowed
