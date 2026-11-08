from unittest.mock import MagicMock

import pytest
from conftest import TEST_KEY
from sqlalchemy.exc import OperationalError

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.db.session import get_session
from enterprise_knowledge_engine.main import create_app


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


@pytest.mark.parametrize("key", [None, "wrong", "é" * 40])
def test_auth_rejects(client, key):
    headers = {"X-API-Key": key} if key else {}
    # httpx restricts header strings to ASCII; raw bytes exercise non-ASCII input.
    if key and not key.isascii():
        headers = {b"X-API-Key": key.encode()}
    response = client.get("/api/v1/info", headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"


def test_auth_accepts(client):
    response = client.get("/api/v1/info", headers={"X-API-Key": TEST_KEY})
    assert response.status_code == 200
    assert response.json()["version"] == "0.1.0"


@pytest.mark.parametrize(
    "extension,revision,expected",
    [
        (1, "0003_retrieval", 200),
        (None, "0003_retrieval", 503),
        (1, "old", 503),
    ],
)
def test_readiness(client, extension, revision, expected):
    session = MagicMock()
    session.scalar.side_effect = [extension, revision]
    client.app.dependency_overrides[get_session] = lambda: session
    response = client.get("/ready")
    assert response.status_code == expected


def test_readiness_database_failure(client):
    session = MagicMock()
    session.execute.side_effect = OperationalError("private SQL", {}, Exception("secret"))
    client.app.dependency_overrides[get_session] = lambda: session
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service not ready"}


def test_openapi_security(client):
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/api/v1/info"]["get"]["security"] == [{"APIKeyHeader": []}]
    assert "security" not in schema["paths"]["/health"]["get"]


def test_docs_disabled(settings):
    from fastapi.testclient import TestClient

    settings.docs_enabled = False
    with TestClient(create_app(settings)) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


@pytest.mark.parametrize("key", ["short", "REPLACE_WITH_GENERATED_API_KEY_12345"])
def test_config_rejects_unsafe_key(key):
    with pytest.raises(ValueError):
        Settings(_env_file=None, database_url="postgresql+psycopg://u:p@localhost/db", api_key=key)


def test_unexpected_error_is_sanitized(client):
    def fail():
        raise RuntimeError("private-database-password")

    client.app.dependency_overrides[get_session] = fail
    response = client.get("/ready")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "private-database-password" not in response.text


def test_logs_do_not_include_request_secrets(client, caplog):
    from enterprise_knowledge_engine.core.logging import JsonFormatter

    client.get(
        "/api/v1/info?token=private-query-value",
        headers={"X-API-Key": TEST_KEY},
    )
    logs = "\n".join(JsonFormatter().format(record) for record in caplog.records)
    assert "request_completed" in logs
    assert "private-query-value" not in logs
    assert TEST_KEY not in logs
