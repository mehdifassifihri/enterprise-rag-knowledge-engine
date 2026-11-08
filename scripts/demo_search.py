"""Reproducible ingestion/search demo using real PostgreSQL and explicit provider selection."""

import argparse
import json
import math
import secrets
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.db.models import Tenant
from enterprise_knowledge_engine.db.session import build_engine
from enterprise_knowledge_engine.ingestion.embeddings import get_embedding_provider
from enterprise_knowledge_engine.main import create_app


class ControlledDemoEmbeddings:
    """Synthetic concept vectors to explain fusion mechanics; NOT a real semantic model."""

    model = "controlled-demo-v1"
    dimensions = 1536

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            value = text.lower()
            if "qx-9001" in value:
                pair = (0.0, 1.0)
            elif "qx-9000" in value:
                pair = (0.8, 0.6) if len(text) > 30 else (1.0, 0.0)
            elif any(word in value for word in ("subscription", "cancellation", "billing")):
                pair = (-1.0, 0.0)
            else:
                pair = (1.0, 0.0)
            norm = math.hypot(*pair)
            vectors.append([pair[0] / norm, pair[1] / norm] + [0.0] * 1534)
        return vectors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paid-openai",
        action="store_true",
        help="Explicitly permit paid OpenAI embedding requests instead of synthetic vectors",
    )
    args = parser.parse_args()
    config = Settings()
    if args.paid_openai and (config.embedding_provider != "openai" or not config.openai_api_key):
        parser.error("Paid demo requires EMBEDDING_PROVIDER=openai and OPENAI_API_KEY")
    tenant = uuid4()
    # Demo gets a fresh tenant/key; never edits an existing tenant's documents.
    config = config.model_copy(
        update={
            "api_key": SecretStr(secrets.token_urlsafe(40)),
            "api_key_tenant_id": tenant,
            "tenant_api_keys": {},
            "reranker_provider": "none",
            "search_vector_strategy": "exact",
        }
    )
    root = Path(__file__).resolve().parents[1] / "examples" / "search"
    engine = build_engine(config)
    with Session(engine) as session, session.begin():
        session.add(Tenant(id=tenant, name="Temporary retrieval demo", slug=str(tenant)))
    try:
        app = create_app(config)
        if not args.paid_openai:
            app.dependency_overrides[get_embedding_provider] = ControlledDemoEmbeddings
        print(
            "Provider: "
            + (
                "OpenAI (paid)"
                if args.paid_openai
                else "CONTROLLED SYNTHETIC VECTORS; mechanics only, not a relevance benchmark"
            )
        )
        with TestClient(app) as client:
            headers = {"X-API-Key": config.api_key.get_secret_value()}
            assert client.get("/ready").status_code == 200
            for source in sorted(root.glob("*.md")):
                response = client.post(
                    "/api/v1/documents/upload",
                    headers=headers,
                    files={"file": (source.name, source.read_bytes())},
                )
                response.raise_for_status()
                print(f"Ingested {source.name}: {response.json()['chunk_count']} chunks")
            for scenario in json.loads((root / "scenarios.json").read_text()):
                print("\nQuery: " + scenario["query"])
                for mode in ("vector", "keyword", "hybrid"):
                    response = client.post(
                        "/api/v1/search",
                        headers=headers,
                        json={
                            "query": scenario["query"],
                            "mode": mode,
                            "top_k": 3,
                            "rerank": False,
                        },
                    )
                    response.raise_for_status()
                    body = response.json()
                    summary = [
                        {
                            "filename": r["filename"],
                            "score": round(r["score"], 6),
                            "sources": r["sources"],
                        }
                        for r in body["results"]
                    ]
                    print(f"{mode} ({body['score_type']}): " + json.dumps(summary))
    finally:
        with Session(engine) as session, session.begin():
            session.execute(delete(Tenant).where(Tenant.id == tenant))
        engine.dispose()
        print("\nTemporary demo tenant and documents removed")


if __name__ == "__main__":
    main()
