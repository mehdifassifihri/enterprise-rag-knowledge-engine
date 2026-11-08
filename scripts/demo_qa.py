"""Exercise grounded QA against real PostgreSQL using explicit, controlled fixture providers."""

import argparse
import json
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
from enterprise_knowledge_engine.qa.prompts import ChatMessage
from enterprise_knowledge_engine.qa.providers import LLMCompletion, get_llm_provider

SAMPLE_ROOT = Path(__file__).resolve().parents[1] / "examples" / "qa"


class DemoEmbeddings:
    """Identical synthetic vectors expose all fixture sources; no semantic ranking claim."""

    model = "controlled-qa-demo-embedding-v1"
    dimensions = 1536

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * 1535 for _ in texts]


class DemoLLM:
    """Scripted source-quote fixture, not a real language model or an injection defense."""

    model = "controlled-qa-demo-v1"

    def generate(self, messages: Sequence[ChatMessage]) -> LLMCompletion:
        payload = json.loads(messages[1]["content"])
        scenarios = json.loads((SAMPLE_ROOT / "scenarios.json").read_text())
        selectors = next(
            (
                s["fixture_fact_selectors"]
                for s in scenarios
                if s["question"] == payload["question"]
            ),
            [],
        )
        claims = []
        for source in payload["sources"]:
            for line in source["content"].splitlines():
                if line.startswith("FACT: "):
                    fact = line.removeprefix("FACT: ")
                    if any(selector in fact.lower() for selector in selectors):
                        claims.append(
                            {
                                "text": fact,
                                "evidence": [{"source_id": source["source_id"], "quote": fact}],
                            }
                        )
        output = {
            "status": "answered" if claims else "insufficient_evidence",
            "claims": claims,
            "reason": None if claims else "insufficient_support",
        }
        return LLMCompletion(content=json.dumps(output), model=self.model)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paid-openai",
        action="store_true",
        help="Explicitly use paid OpenAI embeddings/chat instead of scripted providers",
    )
    args = parser.parse_args()
    config = Settings()
    if args.paid_openai and (
        not config.openai_api_key
        or config.embedding_provider != "openai"
        or config.llm_provider != "openai"
    ):
        parser.error("Paid demo requires OpenAI embedding/chat providers and OPENAI_API_KEY")
    tenant = uuid4()
    config = config.model_copy(
        update={
            "api_key": SecretStr(secrets.token_urlsafe(40)),
            "api_key_tenant_id": tenant,
            "tenant_api_keys": {},
            "reranker_provider": "none",
            "qa_rerank": False,
            "search_vector_strategy": "exact",
            "qa_search_mode": "hybrid",
        }
    )
    engine = build_engine(config)
    with Session(engine) as session, session.begin():
        session.add(Tenant(id=tenant, name="Temporary grounded QA demo", slug=str(tenant)))
    try:
        app = create_app(config)
        if not args.paid_openai:
            app.dependency_overrides[get_embedding_provider] = DemoEmbeddings
            app.dependency_overrides[get_llm_provider] = DemoLLM
        print(
            "Provider: "
            + (
                "OpenAI (paid; outputs require review)"
                if args.paid_openai
                else "SCRIPTED FIXTURES; not semantic quality or real-model injection evaluation"
            )
        )
        with TestClient(app) as client:
            headers = {"X-API-Key": config.api_key.get_secret_value()}
            for path in sorted(SAMPLE_ROOT.glob("*.md")):
                response = client.post(
                    "/api/v1/documents/upload",
                    headers=headers,
                    files={"file": (path.name, path.read_bytes())},
                )
                response.raise_for_status()
            for scenario in json.loads((SAMPLE_ROOT / "scenarios.json").read_text()):
                payload = {
                    "question": scenario["question"],
                    "top_k": 5,
                    "search_mode": "hybrid",
                    "rerank": False,
                }
                response = client.post("/api/v1/ask", headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
                if not args.paid_openai:
                    assert body["status"] == scenario["expected_status"]
                    assert body["retrieval"]["sources_used"] == scenario["expected_sources"]
                    assert "INJECTION_CANARY_EXECUTED" not in body["answer"]
                    assert "[S99]" not in body["answer"]
                print("\nCase " + scenario["case"] + " request: " + json.dumps(payload))
                print(json.dumps(body, indent=2))
    finally:
        with Session(engine) as session, session.begin():
            session.execute(delete(Tenant).where(Tenant.id == tenant))
        engine.dispose()
        print("\nTemporary QA demo tenant and documents removed")


if __name__ == "__main__":
    main()
