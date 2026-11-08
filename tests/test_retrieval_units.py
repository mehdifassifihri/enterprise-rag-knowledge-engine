import math
from dataclasses import replace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from enterprise_knowledge_engine.ingestion.embeddings import FakeEmbeddingProvider
from enterprise_knowledge_engine.ingestion.errors import IngestionError
from enterprise_knowledge_engine.retrieval import repository
from enterprise_knowledge_engine.retrieval.errors import RetrievalError
from enterprise_knowledge_engine.retrieval.ranking import (
    Candidate,
    cosine_scores,
    rank_candidates,
    reciprocal_rank_fusion,
)
from enterprise_knowledge_engine.retrieval.reranking import NoopReranker, RerankItem
from enterprise_knowledge_engine.retrieval.schemas import SearchRequest
from enterprise_knowledge_engine.retrieval.service import query_vector, search


def candidate(number=1, distance=0.2, keyword=0.1):
    return Candidate(
        chunk_id=UUID(int=number),
        document_id=UUID(int=1000 + number),
        filename=f"{number}.md",
        content=f"Sample content {number}",
        page=1,
        chunk_position=0,
        start_offset=0,
        end_offset=10,
        vector_distance=distance,
        keyword_score=keyword,
    )


def test_vector_ranking_and_ties():
    results = rank_candidates([candidate(3, 1), candidate(2, 0), candidate(1, 0)], "vector")
    assert [r.candidate.chunk_id.int for r in results] == [1, 2, 3]
    assert [r.vector_rank for r in results] == [1, 2, 3]
    assert [r.score for r in results] == [1, 1, 0.5]


def test_keyword_ranking_and_ties():
    results = rank_candidates(
        [candidate(3, keyword=0.2), candidate(2, keyword=0.8), candidate(1, keyword=0.8)], "keyword"
    )
    assert [r.candidate.chunk_id.int for r in results] == [1, 2, 3]
    assert [r.keyword_rank for r in results] == [1, 2, 3]


def test_rrf_fusion_scores_deduplication_and_provenance():
    a, b, c = candidate(1), candidate(2), candidate(3)
    vectors = rank_candidates([a, b], "vector")
    keywords = rank_candidates([b, c], "keyword")
    fused = reciprocal_rank_fusion(vectors, keywords, 60)
    assert [r.candidate.chunk_id.int for r in fused] == [2, 1, 3]
    assert math.isclose(fused[0].score, 1 / 62 + 1 / 61)
    assert fused[0].vector_rank == 2
    assert fused[0].keyword_rank == 1
    assert fused[0].candidate.vector_distance == b.vector_distance
    assert fused[0].candidate.keyword_score == b.keyword_score
    duplicated = reciprocal_rank_fusion([vectors[0], vectors[0]], [], 60)
    assert len(duplicated) == 1
    assert duplicated[0].score == 1 / 61


def test_rrf_empty_and_configured_k():
    assert reciprocal_rank_fusion([], []) == []
    assert rank_candidates([], "vector") == []
    result = reciprocal_rank_fusion(rank_candidates([candidate()], "vector"), [], k=10)
    assert result[0].score == 1 / 11
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([], [], k=0)


@pytest.mark.parametrize("distance,cosine,normalized", [(0, 1, 1), (1, 0, 0.5), (2, -1, 0)])
def test_similarity_semantics(distance, cosine, normalized):
    assert cosine_scores(distance) == (cosine, normalized)


@pytest.mark.parametrize("distance", [float("nan"), float("inf"), -0.1, 2.1])
def test_invalid_cosine_distance(distance):
    with pytest.raises(ValueError):
        cosine_scores(distance)


@pytest.mark.parametrize("mode", ["exact", "hnsw"])
def test_vector_sql_is_tenant_filtered_bounded_and_parameterized(mode):
    tenant = UUID(int=42)
    compiled = repository.vector_statement(
        tenant, [0.1] * 1536, "fixture-model", 1536, 50, mode
    ).compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "<=>" in sql
    assert "document_chunks.tenant_id =" in sql
    assert "documents.tenant_id =" in sql
    assert "documents.status =" in sql
    assert "documents.embedding_model =" in sql
    assert "LIMIT" in sql
    assert str(tenant) not in sql
    assert tenant in compiled.params.values()
    assert 50 in compiled.params.values()
    if mode == "exact":
        assert "MATERIALIZED" in sql


def test_keyword_sql_uses_safe_queries_indexes_and_tenant_filters():
    attack = "QX-9000' ); DROP TABLE tenants; --"
    compiled = repository.keyword_statement(UUID(int=42), attack, 50).compile(
        dialect=postgresql.dialect()
    )
    sql = str(compiled)
    assert "websearch_to_tsquery" in sql
    assert "ts_rank_cd" in sql
    assert "search_english @@" in sql and "search_simple @@" in sql
    assert "document_chunks.tenant_id =" in sql and "documents.tenant_id =" in sql
    assert "LIMIT" in sql
    assert attack not in sql
    assert attack in compiled.params.values()


def stub_repositories(monkeypatch, vector=None, keyword=None, exists=True):
    monkeypatch.setattr(repository, "has_vector_candidates", lambda *a: exists)
    monkeypatch.setattr(repository, "vector_candidates", lambda *a: (vector or [], "exact"))
    monkeypatch.setattr(repository, "keyword_candidates", lambda *a: keyword or [])


def test_keyword_mode_does_not_embed(settings, monkeypatch):
    stub_repositories(monkeypatch, keyword=[candidate()])
    provider = MagicMock()
    result = search(
        MagicMock(),
        UUID(int=1),
        SearchRequest(query="QX-9000", mode="keyword"),
        settings,
        provider,
        NoopReranker(),
    )
    provider.embed.assert_not_called()
    assert result.score_type == "keyword_rank"
    assert result.results[0].keyword_rank == 1


@pytest.mark.parametrize("mode", ["vector", "keyword", "hybrid"])
def test_empty_dataset_does_not_call_embedding_api(settings, monkeypatch, mode):
    stub_repositories(monkeypatch, exists=False)
    provider = MagicMock()
    result = search(
        MagicMock(),
        UUID(int=1),
        SearchRequest(query="hello", mode=mode, rerank=True),
        settings,
        provider,
        NoopReranker(),
    )
    assert result.results == []
    assert result.reranking_status == "empty"
    provider.embed.assert_not_called()


def test_query_embedding_failure_is_safe():
    provider = MagicMock()
    provider.embed.side_effect = RuntimeError("private-api-key")
    with pytest.raises(RetrievalError) as error:
        query_vector(provider, "hello", 1536)
    assert error.value.status_code == 502
    assert "private-api-key" not in str(error.value)


def test_zero_query_vector_is_rejected():
    provider = MagicMock()
    provider.embed.return_value = [[0.0] * 1536]
    with pytest.raises(RetrievalError) as error:
        query_vector(provider, "hello", 1536)
    assert error.value.code == "embedding_invalid_response"


def test_hybrid_embedding_failure_is_not_silently_keyword_only(settings, monkeypatch):
    stub_repositories(monkeypatch, keyword=[candidate()])
    provider = MagicMock()
    provider.embed.side_effect = IngestionError("embedding_unavailable", "Safe provider error", 502)
    with pytest.raises(RetrievalError) as error:
        search(
            MagicMock(),
            UUID(int=1),
            SearchRequest(query="hello"),
            settings,
            provider,
            NoopReranker(),
        )
    assert error.value.code == "embedding_unavailable"


class ReverseReranker:
    model = "deterministic-test-reranker"

    def rerank(self, query, documents):
        return [RerankItem(i, i / len(documents)) for i in reversed(range(len(documents)))]


def test_real_reranker_interface_changes_order_and_preserves_retrieval_scores(
    settings, monkeypatch
):
    stub_repositories(monkeypatch, keyword=[candidate(1, keyword=0.9), candidate(2, keyword=0.1)])
    result = search(
        MagicMock(),
        UUID(int=1),
        SearchRequest(query="policy", mode="keyword", rerank=True),
        settings,
        FakeEmbeddingProvider(),
        ReverseReranker(),
    )
    assert [r.chunk_id.int for r in result.results] == [2, 1]
    assert result.reranking_status == "applied"
    assert result.score_type == "reranker_relevance"
    assert result.results[0].retrieval_score == 0.1
    assert result.results[0].score == result.results[0].rerank_score == 0.5
    assert result.results[0].keyword_rank == 2


@pytest.mark.parametrize("bad", ["exception", "foreign_index", "nan", "duplicate"])
def test_reranker_failure_falls_back_without_partial_order(settings, monkeypatch, bad):
    stub_repositories(monkeypatch, keyword=[candidate(1, keyword=0.9), candidate(2, keyword=0.1)])
    reranker = MagicMock(model="test-reranker")
    if bad == "exception":
        reranker.rerank.side_effect = RuntimeError("private-provider-data")
    elif bad == "foreign_index":
        reranker.rerank.return_value = [RerankItem(0, 0.9), RerankItem(42, 0.8)]
    elif bad == "nan":
        reranker.rerank.return_value = [RerankItem(0, float("nan")), RerankItem(1, 0.8)]
    else:
        reranker.rerank.return_value = [RerankItem(0, 0.9), RerankItem(0, 0.8)]
    result = search(
        MagicMock(),
        UUID(int=1),
        SearchRequest(query="policy", mode="keyword", rerank=True),
        settings,
        FakeEmbeddingProvider(),
        reranker,
    )
    assert [r.chunk_id.int for r in result.results] == [1, 2]
    assert result.reranking_status == "fallback"
    assert result.score_type == "keyword_rank"
    assert result.warnings == ["reranker_failed_using_retrieval_order"]
    assert all(r.rerank_score is None for r in result.results)


def test_noop_preserves_order_and_scores(settings, monkeypatch):
    stub_repositories(monkeypatch, keyword=[candidate()])
    result = search(
        MagicMock(),
        UUID(int=1),
        SearchRequest(query="policy", mode="keyword", rerank=True),
        settings,
        FakeEmbeddingProvider(),
        NoopReranker(),
    )
    assert result.reranking_status == "noop"
    assert result.results[0].score == result.results[0].retrieval_score
    assert result.results[0].rerank_score is None


def test_reranker_candidate_cost_is_bounded(settings, monkeypatch):
    stub_repositories(
        monkeypatch,
        vector=[replace(candidate(i), keyword_score=None) for i in range(1, 51)],
        keyword=[replace(candidate(i), vector_distance=None) for i in range(51, 101)],
    )
    reranker = MagicMock(model="test-reranker")
    reranker.rerank.return_value = [RerankItem(i, 0.5) for i in range(50)]
    result = search(
        MagicMock(),
        UUID(int=1),
        SearchRequest(query="policy", rerank=True, top_k=50),
        settings,
        FakeEmbeddingProvider(),
        reranker,
    )
    assert len(reranker.rerank.call_args.args[1]) == 50
    assert len(result.results) == 50


def test_ann_underfill_uses_exact_fallback():
    session = MagicMock()
    row = candidate().__dict__.copy()
    row.pop("keyword_score")
    session.execute.return_value.mappings.return_value.all.side_effect = [[], [row]]
    candidates, strategy = repository.vector_candidates(
        session, UUID(int=1), [0.1] * 1536, "fixture", 1536, 50, "hnsw"
    )
    assert strategy == "exact_fallback"
    assert len(candidates) == 1
