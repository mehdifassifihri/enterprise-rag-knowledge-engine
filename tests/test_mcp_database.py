import asyncio
import os
import sys
from contextlib import contextmanager
from datetime import timedelta
from uuid import uuid4

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.memory import create_connected_server_and_client_session
from pydantic import SecretStr
from sqlalchemy import delete, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.db.models import Document, DocumentChunk, Tenant
from enterprise_knowledge_engine.db.session import build_engine
from enterprise_knowledge_engine.mcp.runtime import open_runtime
from enterprise_knowledge_engine.mcp.server import create_server

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1", reason="Requires migrated disposable PostgreSQL"
    ),
]


@pytest.fixture
def mcp_database():
    config = Settings()
    a, b = uuid4(), uuid4()
    key_a, key_b = (
        "mcp-a-test-only-key-with-32-characters",
        "mcp-b-test-only-key-with-32-characters",
    )
    config = config.model_copy(
        update={
            "api_key": SecretStr(key_a),
            "api_key_tenant_id": a,
            "tenant_api_keys": {b: SecretStr(key_b)},
            "mcp_api_key": SecretStr(key_a),
            "embedding_provider": "fake",
            "llm_provider": "fake",
            "reranker_provider": "none",
        }
    )
    engine = build_engine(config)
    docs = []
    try:
        with Session(engine) as session, session.begin():
            session.add_all([Tenant(id=t, name="MCP fixture", slug=str(t)) for t in (a, b)])
            session.flush()
            for tenant, marker in [(a, "ALPHA"), (b, "PRIVATE_BETA")]:
                doc = Document(
                    tenant_id=tenant,
                    title=marker,
                    filename=marker + ".md",
                    status="ready",
                    chunk_count=1,
                    embedding_model="deterministic-fake-v1",
                    embedding_dimensions=1536,
                )
                session.add(doc)
                session.flush()
                session.add(
                    DocumentChunk(
                        tenant_id=tenant,
                        document_id=doc.id,
                        position=0,
                        content=f"Shared refund policy {marker}.",
                        embedding=[1.0] + [0.0] * 1535,
                    )
                )
                docs.append(doc.id)
        yield config, docs
    finally:
        with Session(engine) as session, session.begin():
            session.execute(delete(Tenant).where(Tenant.id.in_([a, b])))
        engine.dispose()


@pytest.mark.parametrize("mode", ["keyword", "vector", "hybrid"])
@pytest.mark.parametrize("identity", ["a", "b"])
def test_tenant_isolation_all_tools(mcp_database, mode, identity):
    config, docs = mcp_database
    if identity == "b":
        config = config.model_copy(
            update={"mcp_api_key": next(iter(config.tenant_api_keys.values()))}
        )
        docs = list(reversed(docs))
    # Read the configured provider model rather than assume fixture naming.
    from enterprise_knowledge_engine.ingestion.embeddings import build_embedding_provider

    engine = build_engine(config)
    with Session(engine) as session, session.begin():
        for doc_id in docs:
            session.get(Document, doc_id).embedding_model = build_embedding_provider(config).model
    engine.dispose()

    async def run():
        async with create_connected_server_and_client_session(create_server(config)) as client:
            listing = await client.call_tool("list_documents", {})
            assert [d["id"] for d in listing.structuredContent["items"]] == [str(docs[0])]
            own = await client.call_tool("get_document", {"document_id": str(docs[0])})
            assert not own.isError
            chunks = await client.call_tool("get_document_chunks", {"document_id": str(docs[0])})
            assert len(chunks.structuredContent["items"]) == 1
            for tool in ("get_document", "get_document_chunks"):
                denied = await client.call_tool(tool, {"document_id": str(docs[1])})
                assert denied.isError
                assert denied.structuredContent["error"]["code"] == "document_not_found"
            search = await client.call_tool("search_knowledge", {"query": "refund", "mode": mode})
            assert not search.isError, search
            assert search.structuredContent["results"]
            assert all(
                r["document_id"] == str(docs[0]) for r in search.structuredContent["results"]
            )
            answer = await client.call_tool(
                "ask_knowledge", {"question": "refund", "search_mode": mode}
            )
            assert not answer.isError
            assert answer.structuredContent["status"] == "insufficient_evidence"
            assert "PRIVATE_BETA" not in answer.model_dump_json()

    asyncio.run(run())


def test_read_only_and_cleanup(mcp_database):
    config, _ = mcp_database
    with open_runtime(config) as runtime:
        with Session(runtime.engine) as session:
            assert session.scalar(text("SHOW transaction_read_only")) == "on"
            with pytest.raises(DBAPIError):
                session.execute(text("DELETE FROM tenants WHERE false"))
    assert runtime.engine.pool.checkedout() == 0


def test_real_stdio_process(mcp_database):
    config, docs = mcp_database
    env = {
        **os.environ,
        "DATABASE_URL": str(config.database_url),
        "API_KEY": config.api_key.get_secret_value(),
        "API_KEY_TENANT_ID": str(config.api_key_tenant_id),
        "TENANT_API_KEYS": "{}",
        "MCP_API_KEY": config.api_key.get_secret_value(),
        "EMBEDDING_PROVIDER": "fake",
        "LLM_PROVIDER": "fake",
        "RERANKER_PROVIDER": "none",
    }

    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "enterprise_knowledge_engine.mcp", "--env-file", "/dev/null"],
            env=env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=15)
            ) as client:
                await client.initialize()
                assert len((await client.list_tools()).tools) == 5
                for name, args in [
                    ("list_documents", {}),
                    ("get_document", {"document_id": str(docs[0])}),
                    ("get_document_chunks", {"document_id": str(docs[0])}),
                    ("search_knowledge", {"query": "refund", "mode": "keyword"}),
                    ("ask_knowledge", {"question": "refund", "search_mode": "keyword"}),
                ]:
                    response = await client.call_tool(name, args)
                    assert not response.isError, response

    asyncio.run(run())


@pytest.mark.parametrize("source,status", [("S1", "answered"), ("S99", "error")])
def test_grounded_citations_through_protocol(mcp_database, source, status):
    import json

    from enterprise_knowledge_engine.qa.providers import FakeLLMProvider

    config, docs = mcp_database
    quote = "Shared refund policy ALPHA."

    @contextmanager
    def factory(settings):
        with open_runtime(settings) as runtime:
            runtime.llm = FakeLLMProvider(
                json.dumps(
                    {
                        "status": "answered",
                        "reason": None,
                        "claims": [
                            {"text": quote, "evidence": [{"source_id": source, "quote": quote}]}
                        ],
                    }
                )
            )
            yield runtime

    async def run():
        async with create_connected_server_and_client_session(
            create_server(config, factory)
        ) as client:
            response = await client.call_tool(
                "ask_knowledge", {"question": "refund", "search_mode": "keyword"}
            )
            assert response.isError == (status == "error")
            if status == "answered":
                payload = response.structuredContent
                assert payload["status"] == "answered"
                assert "[S1]" in payload["answer"]
                assert payload["citations"][0]["document_id"] == str(docs[0])
                assert payload["citations"][0]["excerpt"] == quote
            else:
                assert "S99" not in response.model_dump_json()

    asyncio.run(run())


@pytest.mark.parametrize("provider", ["embedding", "llm"])
def test_provider_failures_are_mcp_errors(mcp_database, provider):
    from enterprise_knowledge_engine.qa.errors import QAError

    config, docs = mcp_database

    class BrokenEmbeddings:
        model = "deterministic-fake-v1"
        dimensions = 1536

        def embed(self, texts):
            raise RuntimeError("SECRET API KEY must never be exposed")

    class BrokenLLM:
        model = "fixture"

        def generate(self, messages):
            raise QAError("llm_timeout", "Answer provider timed out", 504)

    @contextmanager
    def factory(settings):
        with open_runtime(settings) as runtime:
            runtime.embeddings = BrokenEmbeddings()
            runtime.llm = BrokenLLM()
            yield runtime

    async def run():
        async with create_connected_server_and_client_session(
            create_server(config, factory)
        ) as client:
            name = "search_knowledge" if provider == "embedding" else "ask_knowledge"
            args = (
                {"query": "refund", "mode": "vector"}
                if provider == "embedding"
                else {"question": "refund", "search_mode": "keyword"}
            )
            response = await client.call_tool(name, args)
            assert response.isError
            expected = "query_embedding_failed" if provider == "embedding" else "llm_timeout"
            assert response.structuredContent["error"]["code"] == expected
            assert "SECRET" not in response.model_dump_json()

    asyncio.run(run())


def test_empty_retrieval_and_pagination(mcp_database):
    config, docs = mcp_database

    async def run():
        async with create_connected_server_and_client_session(create_server(config)) as client:
            for tool, args in [
                ("search_knowledge", {"query": "zxqnonexistent", "mode": "keyword"}),
                ("list_documents", {"offset": 999}),
                ("get_document_chunks", {"document_id": str(docs[0]), "offset": 999}),
            ]:
                response = await client.call_tool(tool, args)
                assert not response.isError
                assert not response.structuredContent.get(
                    "results", response.structuredContent.get("items")
                )
            response = await client.call_tool(
                "ask_knowledge", {"question": "zxqnonexistent", "search_mode": "keyword"}
            )
            assert response.structuredContent["status"] == "insufficient_evidence"
            assert response.structuredContent["citations"] == []

    asyncio.run(run())


def test_chunk_clipping_is_explicit(mcp_database):
    config, docs = mcp_database
    engine = build_engine(config)
    try:
        with Session(engine) as session, session.begin():
            from sqlalchemy import select

            chunk = session.scalar(
                select(DocumentChunk).where(DocumentChunk.document_id == docs[0])
            )
            chunk.content = "x" * 2500
    finally:
        engine.dispose()

    async def run():
        async with create_connected_server_and_client_session(create_server(config)) as client:
            response = await client.call_tool("get_document_chunks", {"document_id": str(docs[0])})
            item = response.structuredContent["items"][0]
            assert item["truncated"] is True
            assert len(item["content"]) == 2000

    asyncio.run(run())
