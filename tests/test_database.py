import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.db.models import Document, DocumentChunk, Tenant
from enterprise_knowledge_engine.db.session import build_engine
from enterprise_knowledge_engine.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1 with a migrated test database"
    ),
]


def test_real_readiness():
    with TestClient(create_app(Settings())) as client:
        assert client.get("/ready").status_code == 200


def test_tenant_integrity_and_cascade():
    engine = build_engine(Settings())
    try:
        with engine.connect() as connection, connection.begin() as transaction:
            with Session(connection, join_transaction_mode="create_savepoint") as session:
                first, second = (
                    Tenant(name="First", slug="first"),
                    Tenant(name="Second", slug="second"),
                )
                session.add_all([first, second])
                session.flush()
                doc = Document(tenant_id=first.id, title="Example")
                session.add(doc)
                session.flush()
                with pytest.raises(IntegrityError), session.begin_nested():
                    session.add(
                        DocumentChunk(
                            tenant_id=second.id, document_id=doc.id, position=0, content="Invalid"
                        )
                    )
                    session.flush()
                session.add(
                    DocumentChunk(
                        tenant_id=first.id, document_id=doc.id, position=0, content="Valid"
                    )
                )
                session.flush()
                session.delete(first)
                session.flush()
                assert (
                    session.scalar(
                        text("SELECT count(*) FROM document_chunks WHERE tenant_id = :tenant_id"),
                        {"tenant_id": first.id},
                    )
                    == 0
                )
            transaction.rollback()
    finally:
        engine.dispose()
