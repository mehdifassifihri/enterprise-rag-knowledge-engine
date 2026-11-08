import hashlib
import logging
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr

from enterprise_knowledge_engine.core.errors import ServiceError
from enterprise_knowledge_engine.core.security import authenticate_api_key
from enterprise_knowledge_engine.core.telemetry import measured, trace_context
from enterprise_knowledge_engine.mcp.runtime import KnowledgeRuntime, open_runtime


def test_revoked_key_rejected_by_http_and_resolver(client):
    config = client.app.state.settings
    key = config.api_key.get_secret_value()
    assert authenticate_api_key(config, key) is not None
    config.revoked_api_key_hashes = {hashlib.sha256(key.encode()).hexdigest()}
    assert authenticate_api_key(config, key) is None
    response = client.get("/api/v1/info", headers={"X-API-Key": key})
    assert response.status_code == 401
    assert key not in response.text


def test_revocation_rejects_mcp_startup_and_existing_runtime(settings):
    settings.api_key_tenant_id = uuid4()
    settings.mcp_api_key = settings.api_key
    settings.embedding_provider = "fake"
    settings.llm_provider = "fake"
    runtime = KnowledgeRuntime(settings, None, settings.api_key_tenant_id)
    settings.revoked_api_key_hashes = {
        hashlib.sha256(settings.api_key.get_secret_value().encode()).hexdigest()
    }
    with pytest.raises(ValueError, match="tenant-bound"):
        with open_runtime(settings):
            pytest.fail("Revoked credential accepted")
    with pytest.raises(ServiceError, match="no longer authorized"):
        runtime.invoke("list_documents", {}, "fixture")


def test_removed_tenant_binding_cannot_override_current_identity(settings):
    tenant = uuid4()
    key = "removed-test-key-with-at-least-32-characters"
    settings.tenant_api_keys = {tenant: SecretStr(key)}
    assert authenticate_api_key(settings, key).tenant_id == tenant
    settings.tenant_api_keys = {}
    assert authenticate_api_key(settings, key) is None


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "CONFIDENTIAL_QUESTION" * 100},
        {"query": "policy", "top_k": "CONFIDENTIAL_VALUE"},
        {"query": "policy", "CONFIDENTIAL_FIELD": "private"},
    ],
)
def test_validation_does_not_echo_private_inputs(client, payload, caplog):
    client.app.state.settings.api_key_tenant_id = uuid4()
    key = client.app.state.settings.api_key.get_secret_value()
    response = client.post("/api/v1/search", headers={"X-API-Key": key}, json=payload)
    assert response.status_code == 422
    assert "CONFIDENTIAL" not in response.text
    assert "private" not in response.text
    assert "input" not in response.text
    assert "CONFIDENTIAL" not in caplog.text


def test_request_id_cannot_be_spoofed(client):
    response = client.get("/health", headers={"X-Request-ID": "PRIVATE_PROMPT"})
    assert UUID(response.headers["X-Request-ID"])
    assert response.headers["X-Request-ID"] != "PRIVATE_PROMPT"


def test_timing_context_is_cleaned_up_and_errors_are_safe(caplog):
    token = trace_context.set({"request_id": "safe-fixture"})
    try:
        with caplog.at_level(logging.INFO), pytest.raises(RuntimeError):
            with measured("fixture_timing", tenant_id="tenant-fixture"):
                raise RuntimeError("SECRET PRIVATE DOCUMENT")
        assert trace_context.get() == {"request_id": "safe-fixture"}
        record = next(r for r in caplog.records if r.message == "fixture_timing")
        assert record.duration_ms >= 0
        assert record.request_id == "safe-fixture"
        assert record.error_category == "unexpected_error"
        assert "SECRET" not in caplog.text
    finally:
        trace_context.reset(token)


def test_secret_guard_reports_locations_without_values(tmp_path):
    import runpy
    from pathlib import Path

    scanner = runpy.run_path(str(Path("scripts/check_secrets.py")))
    secret = "sk-" + "A" * 30
    (tmp_path / "public.py").write_text(secret)
    (tmp_path / ".env").write_text(secret)
    assert scanner["scan"](tmp_path) == ["public.py:1"]
