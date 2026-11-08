from uuid import UUID

import pytest
from conftest import TEST_KEY
from fastapi.testclient import TestClient

from enterprise_knowledge_engine.main import create_app
from enterprise_knowledge_engine.retrieval.schemas import SearchResponse


@pytest.fixture
def search_client(settings):
    settings.api_key_tenant_id = UUID(int=42)
    settings.embedding_provider = "fake"
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.mark.parametrize(
    "payload",
    [
        {"query": ""},
        {"query": "  "},
        {"query": "a" * 1001},
        {"query": "hello\x00world"},
        {"query": "hello", "top_k": 0},
        {"query": "hello", "top_k": 51},
        {"query": "hello", "top_k": True},
        {"query": "hello", "top_k": "5"},
        {"query": "hello", "mode": "sql"},
        {"query": "hello", "rerank": "true"},
        {"query": "hello", "tenant_id": str(UUID(int=100))},
    ],
)
def test_invalid_search_request(search_client, payload):
    response = search_client.post("/api/v1/search", headers={"X-API-Key": TEST_KEY}, json=payload)
    assert response.status_code == 422


def test_search_requires_auth(search_client):
    assert search_client.post("/api/v1/search", json={"query": "refund"}).status_code == 401


def test_search_requires_tenant_binding(client):
    assert (
        client.post(
            "/api/v1/search", headers={"X-API-Key": TEST_KEY}, json={"query": "refund"}
        ).status_code
        == 403
    )


def test_tenant_is_derived_from_key_not_header(search_client, monkeypatch):
    seen = []

    def stub(session, tenant_id, payload, config, provider, reranker):
        seen.append(tenant_id)
        return SearchResponse(
            query=payload.query,
            mode=payload.mode,
            results=[],
            score_type="rrf",
            rrf_k=60,
            candidate_limit_per_source=50,
            vector_strategy="exact",
            reranking_status="not_requested",
            reranker_model=None,
            warnings=[],
        )

    monkeypatch.setattr("enterprise_knowledge_engine.api.v1.search.search", stub)
    response = search_client.post(
        "/api/v1/search",
        json={"query": " refund policy "},
        headers={"X-API-Key": TEST_KEY, "X-Tenant-ID": str(UUID(int=99))},
    )
    assert response.status_code == 200
    assert response.json()["query"] == "refund policy"
    assert seen == [UUID(int=42)]


def test_openapi_search_has_api_key_security(search_client):
    schema = search_client.get("/openapi.json").json()
    assert schema["paths"]["/api/v1/search"]["post"]["security"] == [{"APIKeyHeader": []}]
