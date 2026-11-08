from uuid import UUID

import pytest
from conftest import TEST_KEY
from fastapi.testclient import TestClient

from enterprise_knowledge_engine.main import create_app


@pytest.fixture
def upload_client(settings):
    settings.api_key_tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    settings.embedding_provider = "fake"
    settings.max_upload_bytes = 100
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.mark.parametrize(
    "name,data,status,code",
    [
        ("a.exe", b"hi", 415, "unsupported_format"),
        ("a.txt", b"", 422, "empty_file"),
        ("a.pdf", b"fake", 422, "invalid_pdf"),
        ("a.txt", b"a" * 101, 413, "file_too_large"),
        ("a.md", b"\x00abc", 415, "binary_content"),
    ],
)
def test_invalid_upload(upload_client, name, data, status, code):
    response = upload_client.post(
        "/api/v1/documents/upload", headers={"X-API-Key": TEST_KEY}, files={"file": (name, data)}
    )
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


def test_large_chunked_request(upload_client):
    response = upload_client.post(
        "/api/v1/documents/upload",
        headers={"X-API-Key": TEST_KEY, "Content-Type": "application/octet-stream"},
        content=iter([b"x" * 40000, b"x" * 40000]),
    )
    assert response.status_code == 413


def test_unbound_key_cannot_access_documents(client):
    response = client.get(
        "/api/v1/documents", headers={"X-API-Key": TEST_KEY, "X-Tenant-ID": str(UUID(int=1))}
    )
    assert response.status_code == 403


def test_upload_requires_key(upload_client):
    response = upload_client.post("/api/v1/documents/upload", files={"file": ("a.txt", b"hello")})
    assert response.status_code == 401
