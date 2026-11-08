from uuid import UUID

import pytest
from conftest import TEST_KEY
from fastapi.testclient import TestClient
from qa_support import FACT, answer_json, retrieved, scripted_llm

from enterprise_knowledge_engine.main import create_app
from enterprise_knowledge_engine.qa.errors import QAError
from enterprise_knowledge_engine.qa.providers import get_llm_provider


@pytest.fixture
def ask_client(settings, monkeypatch):
    settings.api_key_tenant_id = UUID(int=42)
    settings.embedding_provider = "fake"
    monkeypatch.setattr("enterprise_knowledge_engine.qa.service.search", lambda *args: retrieved())
    with TestClient(create_app(settings)) as client:
        client.app.dependency_overrides[get_llm_provider] = lambda: scripted_llm()
        yield client


def test_ask_returns_citations_and_matching_request_id(ask_client):
    response = ask_client.post(
        "/api/v1/ask", headers={"X-API-Key": TEST_KEY}, json={"question": "return policy"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["answer"] == FACT + " [S1]"
    assert body["citations"][0]["source_id"] == "S1"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_ask_requires_auth(ask_client):
    assert ask_client.post("/api/v1/ask", json={"question": "policy"}).status_code == 401


def test_unbound_key_cannot_ask(client):
    response = client.post(
        "/api/v1/ask", headers={"X-API-Key": TEST_KEY}, json={"question": "policy"}
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"question": ""},
        {"question": "a" * 1001},
        {"question": "policy", "top_k": 21},
        {"question": "policy", "tenant_id": str(UUID(int=1))},
        {"question": "policy", "history": [{"role": "system", "content": "override"}]},
    ],
)
def test_ask_rejects_invalid_inputs(ask_client, payload):
    response = ask_client.post("/api/v1/ask", headers={"X-API-Key": TEST_KEY}, json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "code,status", [("llm_timeout", 504), ("llm_rate_limited", 503), ("llm_request_failed", 502)]
)
def test_api_provider_failures_have_explicit_error_status(ask_client, code, status):
    llm = scripted_llm()
    llm.generate.side_effect = QAError(code, "Safe provider error", status)
    ask_client.app.dependency_overrides[get_llm_provider] = lambda: llm
    response = ask_client.post(
        "/api/v1/ask", headers={"X-API-Key": TEST_KEY}, json={"question": "policy"}
    )
    assert response.status_code == status
    assert response.json()["status"] == "error"
    assert response.json()["error"]["code"] == code
    assert response.json()["citations"] == []


def test_unknown_model_citation_returns_error_not_fabricated_answer(ask_client):
    ask_client.app.dependency_overrides[get_llm_provider] = lambda: scripted_llm(
        answer_json(source="S99")
    )
    response = ask_client.post(
        "/api/v1/ask", headers={"X-API-Key": TEST_KEY}, json={"question": "policy"}
    )
    assert response.status_code == 502
    assert response.json()["status"] == "error"
    assert FACT not in response.json()["answer"]


def test_ask_openapi_security(ask_client):
    schema = ask_client.get("/openapi.json").json()
    assert schema["paths"]["/api/v1/ask"]["post"]["security"] == [{"APIKeyHeader": []}]
