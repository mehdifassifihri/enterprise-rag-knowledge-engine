import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.core.errors import ServiceError
from enterprise_knowledge_engine.core.telemetry import measured
from enterprise_knowledge_engine.ingestion.embeddings import EmbeddingProvider, validate_vectors
from enterprise_knowledge_engine.retrieval import repository
from enterprise_knowledge_engine.retrieval.errors import RetrievalError
from enterprise_knowledge_engine.retrieval.ranking import (
    RankedCandidate,
    cosine_scores,
    rank_candidates,
    reciprocal_rank_fusion,
)
from enterprise_knowledge_engine.retrieval.reranking import Reranker, validate_reranking
from enterprise_knowledge_engine.retrieval.schemas import (
    SearchRequest,
    SearchResponse,
    SearchResult,
)

logger = logging.getLogger(__name__)


def query_vector(provider: EmbeddingProvider, query: str, dimensions: int) -> list[float]:
    try:
        with measured("embedding_generation_completed"):
            vectors = provider.embed([query])
        validate_vectors(vectors, 1, dimensions)
        if provider.dimensions != dimensions:
            raise ValueError("Dimension mismatch")
        return vectors[0]
    except ServiceError as error:
        raise RetrievalError(error.code, error.message, error.status_code) from None
    except Exception:
        raise RetrievalError(
            "query_embedding_failed", "Query embedding generation failed", 502
        ) from None


def search(
    session: Session,
    tenant_id: UUID,
    request: SearchRequest,
    config: Settings,
    provider: EmbeddingProvider,
    reranker: Reranker,
) -> SearchResponse:
    with measured("retrieval_completed", tenant_id=str(tenant_id)):
        vectors, keywords = [], []
        strategy = None
        warnings: list[str] = []
        with session.begin():
            # Both candidate sets see one snapshot during concurrent document changes.
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            if request.mode in {"vector", "hybrid"}:
                if repository.has_vector_candidates(
                    session, tenant_id, provider.model, config.embedding_dimensions
                ):
                    vector = query_vector(provider, request.query, config.embedding_dimensions)
                    candidates, strategy = repository.vector_candidates(
                        session,
                        tenant_id,
                        vector,
                        provider.model,
                        config.embedding_dimensions,
                        config.search_candidate_limit,
                        config.search_vector_strategy,
                        config.search_hnsw_ef_search,
                    )
                    vectors = rank_candidates(candidates, "vector")
                    if strategy == "hnsw":
                        warnings.append("approximate_vector_candidates")
                else:
                    strategy = config.search_vector_strategy
                    warnings.append("no_compatible_vector_documents")
            if request.mode in {"keyword", "hybrid"}:
                keywords = rank_candidates(
                    repository.keyword_candidates(
                        session,
                        tenant_id,
                        request.query,
                        config.search_candidate_limit,
                    ),
                    "keyword",
                )
        if request.mode == "hybrid":
            ranked = reciprocal_rank_fusion(vectors, keywords, config.search_rrf_k)
            score_type = "rrf"
        elif request.mode == "vector":
            ranked, score_type = vectors, "normalized_cosine"
        else:
            ranked, score_type = keywords, "keyword_rank"
        status = "not_requested"
        rerank_scores: dict[UUID, float] = {}
        if request.rerank:
            if not ranked:
                status = "empty"
            elif reranker.model is None:
                reranker.rerank(
                    request.query,
                    [item.candidate.content for item in ranked[: config.reranker_max_candidates]],
                )
                status = "noop"
            else:
                pool = ranked[: config.reranker_max_candidates]
                try:
                    items = reranker.rerank(
                        request.query, [item.candidate.content for item in pool]
                    )
                    validate_reranking(items, len(pool))
                    rerank_scores = {
                        pool[item.index].candidate.chunk_id: item.score for item in items
                    }
                    ranked = sorted(
                        pool,
                        key=lambda item: (
                            -rerank_scores[item.candidate.chunk_id],
                            item.candidate.chunk_id,
                        ),
                    )
                    score_type, status = "reranker_relevance", "applied"
                except Exception:
                    # Fail open only for this optional stage, without claiming reranking succeeded.
                    logger.warning("reranker_fallback")
                    warnings.append("reranker_failed_using_retrieval_order")
                    rerank_scores = {}
                    status = "fallback"
        results = [
            make_result(item, i, rerank_scores.get(item.candidate.chunk_id))
            for i, item in enumerate(ranked[: request.top_k], 1)
        ]
        logger.info(
            "retrieval_sources", extra={"tenant_id": str(tenant_id), "sources_count": len(results)}
        )
        return SearchResponse(
            query=request.query,
            mode=request.mode,
            results=results,
            score_type=score_type,
            rrf_k=config.search_rrf_k if request.mode == "hybrid" else None,
            candidate_limit_per_source=config.search_candidate_limit,
            vector_strategy=strategy,
            reranking_status=status,
            reranker_model=reranker.model if request.rerank else None,
            warnings=warnings,
        )


def make_result(item: RankedCandidate, rank: int, rerank_score: float | None) -> SearchResult:
    c = item.candidate
    cosine, normalized = (
        cosine_scores(c.vector_distance) if c.vector_distance is not None else (None, None)
    )
    return SearchResult(
        chunk_id=c.chunk_id,
        document_id=c.document_id,
        filename=c.filename,
        content=c.content,
        page=c.page,
        chunk_position=c.chunk_position,
        start_offset=c.start_offset,
        end_offset=c.end_offset,
        rank=rank,
        score=rerank_score if rerank_score is not None else item.score,
        score_type="reranker_relevance" if rerank_score is not None else item.score_type,
        retrieval_score=item.score,
        vector_rank=item.vector_rank,
        keyword_rank=item.keyword_rank,
        sources=(["vector"] if item.vector_rank else [])
        + (["keyword"] if item.keyword_rank else []),
        vector_distance=c.vector_distance,
        cosine_similarity=cosine,
        normalized_similarity=normalized,
        keyword_score=c.keyword_score,
        rrf_score=item.rrf_score,
        rerank_score=rerank_score,
    )
