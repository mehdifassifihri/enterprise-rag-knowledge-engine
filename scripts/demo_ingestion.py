"""Exercise the running API with fake embeddings and verify real pgvector persistence."""

import argparse
import json
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.db.models import DocumentChunk
from enterprise_knowledge_engine.db.session import build_engine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    config = Settings()
    if config.embedding_provider != "fake" or config.api_key_tenant_id is None:
        parser.error(
            "Set EMBEDDING_PROVIDER=fake and bind API_KEY_TENANT_ID before running this demo"
        )
    sample = Path(__file__).resolve().parents[1] / "examples" / "handbook.md"
    with httpx.Client(
        base_url=args.base_url, headers={"X-API-Key": config.api_key.get_secret_value()}, timeout=60
    ) as client:
        with sample.open("rb") as source:
            response = client.post(
                "/api/v1/documents/upload", files={"file": (sample.name, source)}
            )
        if response.status_code == 409:
            doc_id = response.json()["detail"]["document_id"]
            response = client.get(f"/api/v1/documents/{doc_id}")
        response.raise_for_status()
        doc = response.json()
        assert doc["status"] == "ready"
        assert doc["embedding_model"] == "fake-sha256-v1", "Demo server must use fake embeddings"
        print(json.dumps(doc, indent=2))
        assert client.get(f"/api/v1/documents/{doc['id']}").status_code == 200
        assert client.get("/api/v1/documents").status_code == 200
        with sample.open("rb") as source:
            duplicate = client.post(
                "/api/v1/documents/upload", files={"file": (sample.name, source)}
            )
        assert duplicate.status_code == 409
        print("Duplicate upload: 409 duplicate_document")
    engine = build_engine(config)
    try:
        with Session(engine) as session:
            count = session.scalar(
                select(func.count())
                .select_from(DocumentChunk)
                .where(
                    DocumentChunk.tenant_id == config.api_key_tenant_id,
                    DocumentChunk.document_id == UUID(doc["id"]),
                    func.vector_dims(DocumentChunk.embedding) == config.embedding_dimensions,
                )
            )
            assert count == doc["chunk_count"] > 0
            print(f"PostgreSQL verification: {count} persisted VECTOR(1536) chunks")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
