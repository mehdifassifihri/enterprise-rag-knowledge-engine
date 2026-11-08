"""Run against a migrated disposable PostgreSQL database, never SQLite."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from test_ingestion_units import pdf_bytes

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.db.models import Document, DocumentChunk, Tenant
from enterprise_knowledge_engine.db.session import build_engine
from enterprise_knowledge_engine.ingestion.embeddings import (
    FakeEmbeddingProvider,
    get_embedding_provider,
)
from enterprise_knowledge_engine.ingestion.errors import IngestionError
from enterprise_knowledge_engine.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1", reason="Requires RUN_DB_TESTS=1 and migrated PostgreSQL"
    ),
]

KEY_A = "tenant-a-test-key-at-least-32-characters"
KEY_B = "tenant-b-test-key-at-least-32-characters"


@pytest.fixture
def ingestion_context():
    config = Settings()
    tenant_a, tenant_b = uuid4(), uuid4()
    config.api_key = SecretStr(KEY_A)
    config.api_key_tenant_id = tenant_a
    config.tenant_api_keys = {tenant_b: SecretStr(KEY_B)}
    config.embedding_provider = "fake"
    engine = build_engine(config)
    with Session(engine) as session, session.begin():
        session.add_all(
            [
                Tenant(id=tenant_a, name="A", slug=str(tenant_a)),
                Tenant(id=tenant_b, name="B", slug=str(tenant_b)),
            ]
        )
    try:
        with TestClient(create_app(config)) as client:
            yield client, engine, tenant_a, tenant_b
    finally:
        with Session(engine) as session, session.begin():
            session.execute(delete(Tenant).where(Tenant.id.in_([tenant_a, tenant_b])))
        engine.dispose()


def upload(
    client, data=b"# Handbook\n\nTenant private knowledge.", key=KEY_A, suffix="md", retry=False
):
    return client.post(
        "/api/v1/documents/upload",
        params={"reprocess": retry},
        files={"file": (f"handbook.{suffix}", data)},
        headers={"X-API-Key": key},
    )


def test_upload_persistence_and_delete(ingestion_context):
    client, engine, tenant_a, _ = ingestion_context
    result = upload(client)
    assert result.status_code == 201, result.text
    doc = result.json()
    assert doc["status"] == "ready"
    assert doc["chunk_count"] > 0
    assert doc["embedding_model"] == "fake-sha256-v1"
    assert doc["embedding_dimensions"] == 1536
    with Session(engine) as session:
        chunks = session.scalars(
            select(DocumentChunk).where(DocumentChunk.tenant_id == tenant_a)
        ).all()
        assert len(chunks) == doc["chunk_count"]
        assert all(len(c.embedding) == 1536 for c in chunks)
        assert chunks[0].content.startswith("# Handbook")
        assert chunks[0].start_offset == 0
    headers = {"X-API-Key": KEY_A}
    assert client.get(f"/api/v1/documents/{doc['id']}", headers=headers).json() == doc
    listing = client.get("/api/v1/documents?limit=1&offset=0", headers=headers).json()
    assert [item["id"] for item in listing["items"]] == [doc["id"]]
    assert client.delete(f"/api/v1/documents/{doc['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/documents/{doc['id']}", headers=headers).status_code == 404
    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(DocumentChunk)
                .where(DocumentChunk.tenant_id == tenant_a)
            )
            == 0
        )


def test_duplicates_are_tenant_scoped(ingestion_context):
    client, _, _, _ = ingestion_context
    first = upload(client)
    duplicate = upload(client)
    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["document_id"] == first.json()["id"]
    other = upload(client, key=KEY_B)
    assert other.status_code == 201
    assert other.json()["id"] != first.json()["id"]
    assert other.json()["content_hash"] == first.json()["content_hash"]


def test_cross_tenant_access_is_hidden(ingestion_context):
    client, _, tenant_a, _ = ingestion_context
    doc = upload(client).json()
    headers = {"X-API-Key": KEY_B, "X-Tenant-ID": str(tenant_a)}
    assert client.get("/api/v1/documents", headers=headers).json()["items"] == []
    for method in ("get", "delete"):
        response = getattr(client, method)(f"/api/v1/documents/{doc['id']}", headers=headers)
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "document_not_found"
    own = client.get(f"/api/v1/documents/{doc['id']}", headers={"X-API-Key": KEY_A})
    assert own.status_code == 200


class FailingProvider(FakeEmbeddingProvider):
    def embed(self, texts):
        raise IngestionError("embedding_unavailable", "Embedding provider request failed", 502)


def test_failure_and_retry_are_atomic(ingestion_context):
    client, engine, tenant_a, _ = ingestion_context
    original = upload(client).json()
    client.app.dependency_overrides[get_embedding_provider] = FailingProvider
    failure = upload(client, retry=True)
    assert failure.status_code == 502
    assert failure.json()["detail"]["document_id"] == original["id"]
    with Session(engine) as session:
        doc = session.get(Document, UUID(original["id"]))
        assert doc.status == "failed"
        assert doc.chunk_count == 0
        assert doc.error_code == "embedding_unavailable"
        assert (
            session.scalar(
                select(func.count())
                .select_from(DocumentChunk)
                .where(DocumentChunk.tenant_id == tenant_a)
            )
            == 0
        )
    client.app.dependency_overrides.clear()
    retry = upload(client)
    assert retry.status_code == 201
    assert retry.json()["id"] == original["id"]
    assert retry.json()["status"] == "ready"
    assert upload(client).status_code == 409


def test_invalid_vectors_never_mark_ready(ingestion_context):
    client, engine, tenant_a, _ = ingestion_context

    class InvalidProvider(FakeEmbeddingProvider):
        def embed(self, texts):
            return [[0.1]]

    client.app.dependency_overrides[get_embedding_provider] = InvalidProvider
    result = upload(client)
    assert result.status_code == 502
    with Session(engine) as session:
        doc = session.scalar(select(Document).where(Document.tenant_id == tenant_a))
        assert doc.status == "failed"
        assert doc.chunk_count == 0


def test_pdf_page_provenance(ingestion_context):
    client, engine, tenant_a, _ = ingestion_context
    result = upload(client, pdf_bytes("PDF ingestion example."), suffix="pdf")
    assert result.status_code == 201
    assert result.json()["page_count"] == 1
    with Session(engine) as session:
        chunk = session.scalar(select(DocumentChunk).where(DocumentChunk.tenant_id == tenant_a))
        assert chunk.page_number == 1
        assert "PDF ingestion example." in chunk.content


def test_concurrent_duplicate_does_not_call_provider_twice(ingestion_context):
    client, _, _, _ = ingestion_context
    entered, finish = Event(), Event()

    class BlockingProvider(FakeEmbeddingProvider):
        def embed(self, texts):
            entered.set()
            if not finish.wait(10):
                raise RuntimeError("Timed out waiting for duplicate test")
            return super().embed(texts)

    client.app.dependency_overrides[get_embedding_provider] = BlockingProvider
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(upload, client)
        try:
            assert entered.wait(5)
            duplicate = upload(client)
            assert duplicate.status_code == 409
            assert duplicate.json()["detail"]["code"] == "document_busy"
        finally:
            finish.set()
        assert first.result().status_code == 201


def test_untrusted_tenant_fields_cannot_move_uploaded_records(ingestion_context):
    client, engine, tenant_a, tenant_b = ingestion_context
    response = client.post(
        "/api/v1/documents/upload",
        params={"tenant_id": str(tenant_b)},
        headers={"X-API-Key": KEY_A, "X-Tenant-ID": str(tenant_b)},
        data={"tenant_id": str(tenant_b)},
        files={"file": ("policy.md", b"Authorized tenant A fact.")},
    )
    assert response.status_code == 201
    id_ = UUID(response.json()["id"])
    with Session(engine) as session:
        assert session.get(Document, id_).tenant_id == tenant_a
        assert all(
            c.tenant_id == tenant_a
            for c in session.scalars(select(DocumentChunk).where(DocumentChunk.document_id == id_))
        )
    denied = client.get(f"/api/v1/documents/{id_}", headers={"X-API-Key": KEY_B})
    absent = client.get(f"/api/v1/documents/{uuid4()}", headers={"X-API-Key": KEY_B})
    assert denied.status_code == absent.status_code == 404
    assert denied.json() == absent.json()
