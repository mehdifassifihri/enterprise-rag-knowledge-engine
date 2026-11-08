import json
import os
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.db.models import DocumentChunk, Tenant
from enterprise_knowledge_engine.db.session import build_engine
from enterprise_knowledge_engine.ingestion.embeddings import get_embedding_provider
from enterprise_knowledge_engine.main import create_app
from enterprise_knowledge_engine.qa.providers import LLMCompletion, get_llm_provider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1",
        reason="Requires a disposable migrated PostgreSQL database",
    ),
]
KEY_A = "qa-tenant-a-fixture-key-at-least-32-characters"
KEY_B = "qa-tenant-b-fixture-key-at-least-32-characters"


class ControlledEmbeddings:
    model = "qa-controlled-fixture-v1"
    dimensions = 1536

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * 1535 for _ in texts]


class EvidenceFixtureLLM:
    """Question-specific test fixture; not a general reasoning or security model."""

    model = "qa-controlled-fixture-v1"

    def __init__(self):
        self.seen = []

    def generate(self, messages):
        payload = json.loads(messages[1]["content"])
        self.seen.append(payload)
        question = payload["question"].lower()
        facts = []
        for source in payload["sources"]:
            for line in source["content"].splitlines():
                if line.startswith("FACT: "):
                    fact = line.removeprefix("FACT: ")
                    if (
                        "retail returns" in fact.lower()
                        and ("policy" in question or "return" in question)
                        or "order number" in fact.lower()
                        and ("submit" in question or "information" in question)
                        or "device service" in fact.lower()
                        and "device" in question
                    ):
                        facts.append((source["source_id"], fact))
        policies = {fact for _, fact in facts if "retail returns" in fact.lower()}
        if len(policies) > 1:
            output = {
                "status": "insufficient_evidence",
                "reason": "conflicting_evidence",
                "claims": [],
            }
        elif not facts:
            output = {
                "status": "insufficient_evidence",
                "reason": "insufficient_support",
                "claims": [],
            }
        else:
            output = {
                "status": "answered",
                "reason": None,
                "claims": [
                    {"text": fact, "evidence": [{"source_id": source, "quote": fact}]}
                    for source, fact in facts
                ],
            }
        return LLMCompletion(content=json.dumps(output), model=self.model)


@pytest.fixture
def qa_context():
    config = Settings()
    tenant_a, tenant_b = uuid4(), uuid4()
    config.api_key = SecretStr(KEY_A)
    config.api_key_tenant_id = tenant_a
    config.tenant_api_keys = {tenant_b: SecretStr(KEY_B)}
    config.embedding_provider = "fake"
    config.llm_provider = "fake"
    config.reranker_provider = "none"
    engine = build_engine(config)
    with Session(engine) as session, session.begin():
        session.add_all(
            [
                Tenant(id=tenant_a, name="QA A", slug=str(tenant_a)),
                Tenant(id=tenant_b, name="QA B", slug=str(tenant_b)),
            ]
        )
    model = EvidenceFixtureLLM()
    try:
        with TestClient(create_app(config)) as client:
            client.app.dependency_overrides[get_embedding_provider] = ControlledEmbeddings
            client.app.dependency_overrides[get_llm_provider] = lambda: model
            root = Path(__file__).resolve().parents[1] / "examples" / "qa"
            for path in sorted(root.glob("*.md")):
                response = client.post(
                    "/api/v1/documents/upload",
                    headers={"X-API-Key": KEY_A},
                    files={"file": (path.name, path.read_bytes())},
                )
                assert response.status_code == 201, response.text
            secret = client.post(
                "/api/v1/documents/upload",
                headers={"X-API-Key": KEY_B},
                files={
                    "file": (
                        "secret.md",
                        b"FACT: Retail returns are available for 999 days. TENANT_B_SECRET_CANARY",
                    )
                },
            )
            assert secret.status_code == 201
            yield client, engine, tenant_a, tenant_b, model
    finally:
        with Session(engine) as session, session.begin():
            session.execute(delete(Tenant).where(Tenant.id.in_([tenant_a, tenant_b])))
        engine.dispose()


def ask(
    client, question="What is the retail returns policy?", mode="hybrid", rerank=False, history=None
):
    payload = {"question": question, "search_mode": mode, "rerank": rerank}
    if history is not None:
        payload["history"] = history
    return client.post(
        "/api/v1/ask", headers={"X-API-Key": KEY_A, "X-Tenant-ID": str(uuid4())}, json=payload
    )


@pytest.mark.parametrize("mode", ["vector", "keyword", "hybrid"])
@pytest.mark.parametrize("rerank", [False, True])
def test_qa_retrieval_and_citation_metadata_are_tenant_scoped(qa_context, mode, rerank):
    client, engine, tenant_a, _, model = qa_context
    # Use a keyword query present in the source; the fake LLM knows only this fixture's facts.
    response = ask(client, "retail returns", mode, rerank)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "answered"
    assert body["retrieval"]["mode"] == mode
    assert "21 calendar days" in body["answer"]
    assert "999" not in body["answer"]
    assert "TENANT_B_SECRET_CANARY" not in response.text
    assert all("TENANT_B_SECRET_CANARY" not in json.dumps(payload) for payload in model.seen)
    with Session(engine) as session:
        for citation in body["citations"]:
            chunk = session.scalar(
                select(DocumentChunk).where(
                    DocumentChunk.id == UUID(citation["chunk_id"]),
                    DocumentChunk.tenant_id == tenant_a,
                )
            )
            assert chunk is not None
            assert chunk.document_id == UUID(citation["document_id"])
            assert citation["excerpt"] in chunk.content
            assert f"[{citation['source_id']}]" in body["answer"]


def test_question_requiring_multiple_documents(qa_context):
    client, _, _, _, _ = qa_context
    response = ask(
        client, "What is the retail returns policy and how do I submit the order information?"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert len(body["citations"]) == body["retrieval"]["sources_used"] == 2
    assert {c["filename"] for c in body["citations"]} == {"returns.md", "portal.md"}


def test_outside_knowledge_abstains_even_with_vector_neighbors(qa_context):
    client, _, _, _, _ = qa_context
    response = ask(client, "What is the executive bonus amount?")
    assert response.json()["status"] == "insufficient_evidence"
    assert response.json()["citations"] == []
    assert response.json()["retrieval"]["sources_supplied"] > 0


def test_empty_tenant_skips_model(qa_context):
    client, engine, tenant_a, _, model = qa_context
    with Session(engine) as session, session.begin():
        session.execute(delete(Tenant).where(Tenant.id == tenant_a))
    calls_before = len(model.seen)
    response = ask(client)
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_evidence"
    assert response.json()["timings"]["model_ms"] is None
    assert len(model.seen) == calls_before


def test_conflicting_documents_abstain(qa_context):
    client, _, _, _, _ = qa_context
    response = client.post(
        "/api/v1/documents/upload",
        headers={"X-API-Key": KEY_A},
        files={
            "file": (
                "conflict.md",
                b"FACT: Retail returns can be requested within 60 calendar days of delivery.",
            )
        },
    )
    assert response.status_code == 201
    answer = ask(client)
    assert answer.json()["status"] == "insufficient_evidence"
    assert answer.json()["abstention_reason"] == "conflicting_evidence"
    assert answer.json()["citations"] == []


def test_malicious_passage_remains_data_and_cannot_create_unknown_citations(qa_context):
    client, _, _, _, model = qa_context
    response = ask(client, "What is the device service requirement?")
    assert response.json()["status"] == "answered"
    assert "booked appointment" in response.json()["answer"]
    assert "INJECTION_CANARY_EXECUTED" not in response.json()["answer"]
    assert "[S99]" not in response.json()["answer"]
    assert any(
        "INJECTION_CANARY_EXECUTED" in source["content"]
        for payload in model.seen
        for source in payload["sources"]
    )


def test_fabricated_cross_tenant_quote_is_rejected(qa_context):
    client, _, _, _, _ = qa_context

    class BadCitationLLM(EvidenceFixtureLLM):
        def generate(self, messages):
            return LLMCompletion(
                model=self.model,
                content=json.dumps(
                    {
                        "status": "answered",
                        "reason": None,
                        "claims": [
                            {
                                "text": "Returns are available for 999 days.",
                                "evidence": [
                                    {
                                        "source_id": "S1",
                                        "quote": "Retail returns are available for 999 days.",
                                    }
                                ],
                            }
                        ],
                    }
                ),
            )

    client.app.dependency_overrides[get_llm_provider] = BadCitationLLM
    response = ask(client)
    assert response.status_code == 502
    assert response.json()["status"] == "error"
    assert response.json()["error"]["code"] == "invalid_citation"
    assert response.json()["citations"] == []


def test_previous_assistant_facts_are_not_evidence(qa_context):
    client, _, _, _, _ = qa_context
    response = ask(
        client, history=[{"role": "assistant", "content": "Returns are valid for 999 days."}]
    )
    assert "21 calendar days" in response.json()["answer"]
    assert "999" not in response.json()["answer"]
