"""Real PostgreSQL/pgvector retrieval checks; all provider behavior is controlled and free."""

import os
from collections.abc import Sequence
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.db.models import Document, DocumentChunk, Tenant
from enterprise_knowledge_engine.db.session import build_engine
from enterprise_knowledge_engine.ingestion.embeddings import get_embedding_provider
from enterprise_knowledge_engine.main import create_app
from enterprise_knowledge_engine.retrieval.reranking import RerankItem, get_reranker

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1",
        reason="Requires a migrated disposable PostgreSQL database",
    ),
]

KEY_A = "retrieval-a-test-key-at-least-32-characters"
KEY_B = "retrieval-b-test-key-at-least-32-characters"


def vector(x, y=0):
    return [x, y] + [0.0] * 1534


class FixtureEmbeddings:
    model = "controlled-retrieval-fixture-v1"
    dimensions = 1536

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [vector(1) for _ in texts]


class FixtureReranker:
    model = "controlled-reranker-v1"

    def __init__(self):
        self.seen = []

    def rerank(self, query, documents):
        self.seen.extend(documents)
        return [RerankItem(i, 1 / (i + 1)) for i in range(len(documents))]


@pytest.fixture
def retrieval_context():
    config = Settings()
    tenant_a, tenant_b = uuid4(), uuid4()
    config.api_key = SecretStr(KEY_A)
    config.api_key_tenant_id = tenant_a
    config.tenant_api_keys = {tenant_b: SecretStr(KEY_B)}
    config.embedding_provider = "fake"
    engine = build_engine(config)
    chunks = {}
    with Session(engine) as session, session.begin():
        session.add_all(
            [
                Tenant(id=tenant_a, name="Retrieval A", slug=str(tenant_a)),
                Tenant(id=tenant_b, name="Retrieval B", slug=str(tenant_b)),
            ]
        )
        session.flush()
        for name, tenant, content, embedding in [
            (
                "refunds.md",
                tenant_a,
                "Customers may obtain their money back within thirty days.",
                vector(1),
            ),
            (
                "qx9000.md",
                tenant_a,
                "QX-9000 connector refund policy covers defective hardware.",
                vector(0.8, 0.6),
            ),
            (
                "qx9001.md",
                tenant_a,
                "QX-9001 connector setup and installation guide.",
                vector(0, 1),
            ),
            ("secret.md", tenant_b, "TENANT-B-ONLY QX-9000 refund policy money back.", vector(1)),
        ]:
            doc = Document(
                tenant_id=tenant,
                title=name,
                filename=name,
                status="ready",
                chunk_count=1,
                embedding_model=FixtureEmbeddings.model,
                embedding_dimensions=1536,
            )
            session.add(doc)
            session.flush()
            chunk = DocumentChunk(
                tenant_id=tenant,
                document_id=doc.id,
                position=0,
                content=content,
                embedding=embedding,
                page_number=2,
                start_offset=0,
                end_offset=len(content),
            )
            session.add(chunk)
            session.flush()
            chunks[name] = chunk.id
    try:
        with TestClient(create_app(config)) as client:
            client.app.dependency_overrides[get_embedding_provider] = FixtureEmbeddings
            yield client, engine, tenant_a, tenant_b, chunks
    finally:
        with Session(engine) as session, session.begin():
            session.execute(delete(Tenant).where(Tenant.id.in_([tenant_a, tenant_b])))
        engine.dispose()


def run_search(client, query="refund policy", mode="hybrid", rerank=False, key=KEY_A, top_k=5):
    return client.post(
        "/api/v1/search",
        json={
            "query": query,
            "mode": mode,
            "rerank": rerank,
            "top_k": top_k,
        },
        headers={"X-API-Key": key, "X-Tenant-ID": str(uuid4())},
    )


def test_vector_cosine_ranking_and_source_fields(retrieval_context):
    client, _, _, _, chunks = retrieval_context
    response = run_search(client, mode="vector")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [r["filename"] for r in body["results"]] == ["refunds.md", "qx9000.md", "qx9001.md"]
    first = body["results"][0]
    assert first["chunk_id"] == str(chunks["refunds.md"])
    assert first["page"] == 2 and first["chunk_position"] == 0
    assert first["vector_distance"] == pytest.approx(0)
    assert first["cosine_similarity"] == pytest.approx(1)
    assert first["normalized_similarity"] == pytest.approx(1)
    assert first["score_type"] == "normalized_cosine"
    assert body["results"][1]["vector_distance"] == pytest.approx(0.2, abs=1e-6)


def test_exact_identifier_and_english_stemming(retrieval_context):
    client, _, _, _, _ = retrieval_context
    identifier = run_search(client, query="QX-9000", mode="keyword")
    assert identifier.status_code == 200, identifier.text
    assert [r["filename"] for r in identifier.json()["results"]] == ["qx9000.md"]
    stemming = run_search(client, query="customer", mode="keyword")
    assert [r["filename"] for r in stemming.json()["results"]] == ["refunds.md"]
    phrases = run_search(client, query='"money back"', mode="keyword")
    assert [r["filename"] for r in phrases.json()["results"]] == ["refunds.md"]


def test_hybrid_fuses_independent_candidate_lists(retrieval_context):
    client, _, _, _, _ = retrieval_context
    response = run_search(client)
    assert response.status_code == 200, response.text
    body = response.json()
    first = body["results"][0]
    assert first["filename"] == "qx9000.md"
    assert first["sources"] == ["vector", "keyword"]
    assert first["vector_rank"] == 2 and first["keyword_rank"] == 1
    assert first["rrf_score"] == pytest.approx(1 / 62 + 1 / 61)
    assert body["score_type"] == "rrf"
    assert len({r["chunk_id"] for r in body["results"]}) == len(body["results"])


@pytest.mark.parametrize("mode", ["vector", "keyword", "hybrid"])
@pytest.mark.parametrize("rerank", [False, True])
@pytest.mark.parametrize("strategy", ["exact", "hnsw"])
def test_all_modes_and_rerankers_are_tenant_isolated(retrieval_context, mode, rerank, strategy):
    client, engine, tenant_a, _, chunks = retrieval_context
    client.app.state.settings.search_vector_strategy = strategy
    reranker = FixtureReranker()
    client.app.dependency_overrides[get_reranker] = lambda: reranker
    result = run_search(client, mode=mode, rerank=rerank)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["results"]
    assert str(chunks["secret.md"]) not in result.text
    assert "TENANT-B-ONLY" not in result.text
    assert all("TENANT-B-ONLY" not in doc for doc in reranker.seen)
    with Session(engine) as session:
        own = set(
            session.scalars(select(DocumentChunk.id).where(DocumentChunk.tenant_id == tenant_a))
        )
    assert all(r["chunk_id"] in {str(value) for value in own} for r in body["results"])
    if rerank:
        assert body["reranking_status"] == "applied"


@pytest.mark.parametrize(
    "query",
    [
        "' ; DROP TABLE tenants; --",
        '"unterminated',
        "!!!",
        "the",
        "QX-9000 OR QX-9001",
        "refund -installation",
    ],
)
def test_adversarial_queries_are_safe(retrieval_context, query):
    client, engine, _, _, _ = retrieval_context
    response = run_search(client, query=query, mode="keyword")
    assert response.status_code == 200, response.text
    with Session(engine) as session:
        assert session.scalar(text("SELECT count(*) FROM tenants")) >= 2


def test_generated_fts_updates_and_search_indexes_exist(retrieval_context):
    client, engine, _, _, chunks = retrieval_context
    with Session(engine) as session, session.begin():
        chunk = session.get(DocumentChunk, chunks["qx9000.md"])
        chunk.content = "UniqueUpdatedIdentifierABC"
    assert run_search(client, query="QX-9000", mode="keyword").json()["results"] == []
    results = run_search(client, query="UniqueUpdatedIdentifierABC", mode="keyword").json()[
        "results"
    ]
    assert results[0]["chunk_id"] == str(chunks["qx9000.md"])
    with Session(engine) as session:
        indexes = session.execute(
            text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename='document_chunks'")
        ).all()
        definitions = dict(indexes)
        assert "USING gin" in definitions["ix_chunks_fts_english"]
        assert "USING gin" in definitions["ix_chunks_fts_simple"]
        assert "USING hnsw" in definitions["ix_chunks_embedding_hnsw"]
        assert "vector_cosine_ops" in definitions["ix_chunks_embedding_hnsw"]


def test_incompatible_models_failed_documents_and_zero_vectors_are_not_semantic_matches(
    retrieval_context,
):
    client, engine, tenant_a, _, _ = retrieval_context
    with Session(engine) as session, session.begin():
        for name, status, model, embedding in [
            ("wrong-model.md", "ready", "other-model", vector(1)),
            ("failed.md", "failed", FixtureEmbeddings.model, vector(1)),
            ("zero.md", "ready", FixtureEmbeddings.model, vector(0)),
        ]:
            doc = Document(
                tenant_id=tenant_a,
                title=name,
                filename=name,
                status=status,
                chunk_count=1,
                embedding_model=model,
                embedding_dimensions=1536,
            )
            session.add(doc)
            session.flush()
            session.add(
                DocumentChunk(
                    tenant_id=tenant_a,
                    document_id=doc.id,
                    position=0,
                    content="refund policy",
                    embedding=embedding,
                )
            )
    vectors = run_search(client, mode="vector").json()["results"]
    assert {r["filename"] for r in vectors} == {"refunds.md", "qx9000.md", "qx9001.md"}
    keywords = run_search(client, mode="keyword").json()["results"]
    assert "failed.md" not in {r["filename"] for r in keywords}
    assert "wrong-model.md" in {r["filename"] for r in keywords}


def test_embedding_error_does_not_break_keyword_search(retrieval_context):
    client, _, _, _, _ = retrieval_context

    class BrokenEmbedding(FixtureEmbeddings):
        def embed(self, texts):
            raise RuntimeError("private-provider-token")

    client.app.dependency_overrides[get_embedding_provider] = BrokenEmbedding
    for mode in ("vector", "hybrid"):
        result = run_search(client, mode=mode)
        assert result.status_code == 502
        assert result.json()["detail"]["code"] == "query_embedding_failed"
        assert "private-provider-token" not in result.text
    assert run_search(client, mode="keyword").status_code == 200


def test_empty_tenant_and_unknown_keywords(retrieval_context):
    client, engine, _, tenant_b, _ = retrieval_context
    with Session(engine) as session, session.begin():
        session.execute(delete(Document).where(Document.tenant_id == tenant_b))
    for mode in ("vector", "keyword", "hybrid"):
        result = run_search(client, mode=mode, key=KEY_B)
        assert result.status_code == 200
        assert result.json()["results"] == []
    assert run_search(client, query="NonexistentLexemeZZZ", mode="keyword").json()["results"] == []


def test_search_limit_and_repeatable_tie_order(retrieval_context):
    client, _, _, _, _ = retrieval_context
    first = run_search(client, mode="vector", top_k=2).json()
    second = run_search(client, mode="vector", top_k=2).json()
    assert len(first["results"]) == 2
    assert first == second
