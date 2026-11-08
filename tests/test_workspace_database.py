"""Frontend aggregate/preview reads retain the existing SQL authorization boundary."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.db.models import Document, DocumentChunk, Tenant
from enterprise_knowledge_engine.db.session import build_engine
from enterprise_knowledge_engine.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires PostgreSQL"),
]


def test_workspace_totals_and_chunk_previews_are_tenant_scoped():
    tenants = [uuid4(), uuid4()]
    doc_ids = [uuid4(), uuid4()]
    config = Settings().model_copy(
        update={
            "api_key": SecretStr("workspace-test-only-key-at-least-32-characters"),
            "api_key_tenant_id": tenants[0],
            "tenant_api_keys": {},
        }
    )
    engine = build_engine(config)
    try:
        with Session(engine) as session, session.begin():
            for tenant, document in zip(tenants, doc_ids, strict=True):
                session.add(Tenant(id=tenant, name="Workspace fixture", slug=str(tenant)))
                session.flush()
                session.add(
                    Document(
                        id=document,
                        tenant_id=tenant,
                        title="Fixture",
                        status="ready",
                        chunk_count=1,
                    )
                )
                session.flush()
                session.add(
                    DocumentChunk(
                        tenant_id=tenant, document_id=document, position=0, content="x" * 2100
                    )
                )
        with TestClient(create_app(config)) as client:
            headers = {"X-API-Key": config.api_key.get_secret_value()}
            assert client.get("/api/v1/documents/stats").status_code == 401
            stats = client.get("/api/v1/documents/stats", headers=headers)
            assert stats.json() == {"documents": 1, "ready": 1, "failed": 0, "chunks": 1}
            own = client.get(f"/api/v1/documents/{doc_ids[0]}/chunks", headers=headers)
            assert own.status_code == 200
            assert len(own.json()["items"][0]["content"]) == 2000
            assert own.json()["items"][0]["truncated"] is True
            assert (
                client.get(f"/api/v1/documents/{doc_ids[1]}/chunks", headers=headers).status_code
                == 404
            )
            assert (
                client.get(
                    f"/api/v1/documents/{doc_ids[0]}/chunks?limit=21", headers=headers
                ).status_code
                == 422
            )
            capabilities = client.get("/api/v1/capabilities", headers=headers).json()
            assert capabilities["embedding_dimensions"] == 1536
            assert capabilities["mcp_transport"] == "stdio"
            assert "api_key" not in capabilities and "database_url" not in capabilities
    finally:
        with Session(engine) as session, session.begin():
            session.execute(delete(Tenant).where(Tenant.id.in_(tenants)))
        engine.dispose()
