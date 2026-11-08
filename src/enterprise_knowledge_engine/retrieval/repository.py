from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, exists, func, select
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.db.models import Document, DocumentChunk
from enterprise_knowledge_engine.retrieval.ranking import Candidate

C = DocumentChunk
D = Document


def eligible_statement(tenant_id: UUID) -> Select:
    return (
        select(
            C.id.label("chunk_id"),
            C.document_id,
            D.filename,
            C.content,
            C.page_number.label("page"),
            C.position.label("chunk_position"),
            C.start_offset,
            C.end_offset,
        )
        .join(D, and_(D.id == C.document_id, D.tenant_id == C.tenant_id))
        .where(
            C.tenant_id == tenant_id,
            D.tenant_id == tenant_id,
            D.status == "ready",
        )
    )


def vector_eligibility(model: str, dimensions: int) -> tuple:
    return (
        D.embedding_model == model,
        D.embedding_dimensions == dimensions,
        C.embedding.is_not(None),
        func.vector_norm(C.embedding) > 0,
    )


def has_vector_candidates(session: Session, tenant_id: UUID, model: str, dimensions: int) -> bool:
    statement = eligible_statement(tenant_id).where(*vector_eligibility(model, dimensions))
    return bool(session.scalar(select(exists(statement))))


def vector_statement(
    tenant_id: UUID,
    vector: list[float],
    model: str,
    dimensions: int,
    limit: int,
    strategy: str = "exact",
) -> Select:
    if strategy not in {"exact", "hnsw"} or not 1 <= limit <= 200:
        raise ValueError("Require a known vector strategy and a limit between 1 and 200")
    base = eligible_statement(tenant_id).where(*vector_eligibility(model, dimensions))
    if strategy == "exact":
        # Materialization prevents the planner from substituting an approximate global ANN scan.
        eligible = base.add_columns(C.embedding).cte("eligible_chunks").prefix_with("MATERIALIZED")
        distance = eligible.c.embedding.cosine_distance(vector).label("vector_distance")
        return (
            select(*[col for col in eligible.c if col.key != "embedding"], distance)
            .order_by(
                distance,
                eligible.c.chunk_id,
            )
            .limit(limit)
        )
    distance = C.embedding.cosine_distance(vector).label("vector_distance")
    # pgvector requires ORDER BY the direct distance operator and LIMIT for ANN index eligibility.
    return base.add_columns(distance).order_by(distance).limit(limit)


def keyword_statement(tenant_id: UUID, query: str, limit: int) -> Select:
    if not 1 <= limit <= 200:
        raise ValueError("Candidate limit must be between 1 and 200")
    english = func.websearch_to_tsquery("english", query)
    simple = func.websearch_to_tsquery("simple", query)
    score = func.greatest(
        func.ts_rank_cd(C.search_english, english, 32), func.ts_rank_cd(C.search_simple, simple, 32)
    ).label("keyword_score")
    return (
        eligible_statement(tenant_id)
        .add_columns(score)
        .where(C.search_english.bool_op("@@")(english) | C.search_simple.bool_op("@@")(simple))
        .order_by(score.desc(), C.id)
        .limit(limit)
    )


def candidate_from_row(row: Mapping[str, Any]) -> Candidate:
    return Candidate(**row)


def vector_candidates(
    session: Session,
    tenant_id: UUID,
    vector: list[float],
    model: str,
    dimensions: int,
    limit: int,
    strategy: str = "exact",
    ef_search: int = 100,
) -> tuple[list[Candidate], str]:
    if strategy == "hnsw":
        session.execute(select(func.set_config("hnsw.iterative_scan", "strict_order", True)))
        session.execute(select(func.set_config("hnsw.ef_search", str(max(limit, ef_search)), True)))
    rows = (
        session.execute(vector_statement(tenant_id, vector, model, dimensions, limit, strategy))
        .mappings()
        .all()
    )
    actual_strategy = strategy
    if strategy == "hnsw" and len(rows) < limit:
        # Small tenants can be starved by global ANN filters. Recover with an exact tenant scan.
        rows = (
            session.execute(vector_statement(tenant_id, vector, model, dimensions, limit, "exact"))
            .mappings()
            .all()
        )
        actual_strategy = "exact_fallback"
    return [candidate_from_row(row) for row in rows], actual_strategy


def keyword_candidates(
    session: Session, tenant_id: UUID, query: str, limit: int
) -> list[Candidate]:
    rows = session.execute(keyword_statement(tenant_id, query, limit)).mappings().all()
    return [candidate_from_row(row) for row in rows]
