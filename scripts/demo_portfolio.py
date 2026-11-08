"""Synthetic API/database walkthrough; controlled providers, never semantic-quality evidence."""

import json
import secrets
from pathlib import Path
from typing import Any
from uuid import uuid4

import demo_qa
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.db.models import Tenant
from enterprise_knowledge_engine.db.session import build_engine
from enterprise_knowledge_engine.ingestion.embeddings import get_embedding_provider
from enterprise_knowledge_engine.main import create_app
from enterprise_knowledge_engine.qa.providers import get_llm_provider


def main() -> None:
    config = Settings()
    tenants = [uuid4(), uuid4()]
    keys = [secrets.token_urlsafe(40), secrets.token_urlsafe(40)]
    config = config.model_copy(
        update={
            "api_key": SecretStr(keys[0]),
            "api_key_tenant_id": tenants[0],
            "tenant_api_keys": {tenants[1]: SecretStr(keys[1])},
            "reranker_provider": "none",
            "qa_rerank": False,
            "search_vector_strategy": "exact",
        }
    )
    engine = build_engine(config)
    try:
        with Session(engine) as session, session.begin():
            session.add_all(
                Tenant(id=t, name="Synthetic portfolio demo", slug=str(t)) for t in tenants
            )
        app = create_app(config)
        app.dependency_overrides[get_embedding_provider] = demo_qa.DemoEmbeddings
        app.dependency_overrides[get_llm_provider] = demo_qa.DemoLLM
        headers = [{"X-API-Key": key} for key in keys]
        sample_root = Path(__file__).resolve().parents[1] / "demo" / "sample_documents"
        print("CONTROLLED PROVIDERS: SQL/API correctness, not semantic or LLM quality")
        with TestClient(app) as client:

            def request(method: str, path: str, tenant: int = 0, **kwargs: Any) -> dict[str, Any]:
                response = client.request(
                    method, "/api/v1" + path, headers=headers[tenant], **kwargs
                )
                response.raise_for_status()
                return response.json()

            documents = []
            for path in sorted(sample_root.glob("*.md")):
                assert path.read_bytes() == (demo_qa.SAMPLE_ROOT / path.name).read_bytes()
                files = {"file": (path.name, path.read_bytes())}
                body = request("POST", "/documents/upload", files=files)
                assert body["status"] == "ready" and body["chunk_count"] > 0
                assert (
                    request("GET", "/documents/" + body["id"])["chunk_count"] == body["chunk_count"]
                )
                documents.append(body["id"])
                print(json.dumps({"scenario": "upload", "response": body}))
                assert (
                    client.post(
                        "/api/v1/documents/upload", headers=headers[0], files=files
                    ).status_code
                    == 409
                )
            assert {d["id"] for d in request("GET", "/documents")["items"]} == set(documents)
            private = request(
                "POST",
                "/documents/upload",
                tenant=1,
                files={"file": ("private.txt", b"Private B ONLY-B-991 policy.")},
            )
            for mode in ("keyword", "vector", "hybrid"):
                result = request(
                    "POST", "/search", json={"query": "retail", "mode": mode, "top_k": 5}
                )
                assert result["results"]
                assert all(r["document_id"] in documents for r in result["results"])
                isolated = request(
                    "POST", "/search", tenant=1, json={"query": "retail", "mode": mode, "top_k": 5}
                )
                assert all(r["document_id"] == private["id"] for r in isolated["results"])
                print(json.dumps({"scenario": mode, "response": result}))
            for scenario in json.loads((demo_qa.SAMPLE_ROOT / "scenarios.json").read_text()):
                payload = {
                    "question": scenario["question"],
                    "top_k": 5,
                    "search_mode": "hybrid",
                    "rerank": False,
                }
                body = request("POST", "/ask", json=payload)
                assert body["status"] == scenario["expected_status"]
                assert len(body["citations"]) == scenario["expected_sources"]
                assert all(c["document_id"] in documents for c in body["citations"])
                assert "INJECTION_CANARY_EXECUTED" not in body["answer"]
                print(
                    json.dumps({"scenario": scenario["case"], "request": payload, "response": body})
                )
            isolated_answer = request(
                "POST", "/ask", tenant=1, json={"question": "What is the retail returns policy?"}
            )
            assert isolated_answer["status"] == "insufficient_evidence"
            assert not isolated_answer["citations"]
            for method in ("GET", "DELETE"):
                assert (
                    client.request(
                        method, "/api/v1/documents/" + documents[0], headers=headers[1]
                    ).status_code
                    == 404
                )
            assert request("GET", "/documents/" + documents[0])["status"] == "ready"
            print(
                "PASS: upload, duplicates, metadata, all search modes, "
                "citations, abstention, tenant isolation"
            )
    finally:
        with Session(engine) as session, session.begin():
            session.execute(delete(Tenant).where(Tenant.id.in_(tenants)))
        engine.dispose()


if __name__ == "__main__":
    main()
