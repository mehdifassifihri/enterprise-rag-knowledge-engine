import asyncio
from contextlib import contextmanager
from uuid import uuid4

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from pydantic import SecretStr

from enterprise_knowledge_engine.core.errors import ServiceError
from enterprise_knowledge_engine.mcp.runtime import open_runtime
from enterprise_knowledge_engine.mcp.server import ARGUMENTS, create_server


class StubRuntime:
    def __init__(self):
        self.calls = []
        self.failure = None
        self.payload = {"items": []}
        self.closed = False

    def invoke(self, name, args, request_id):
        self.calls.append((name, args, request_id))
        if self.failure:
            raise self.failure
        return self.payload


def make_server(settings, runtime):
    @contextmanager
    def factory(config):
        try:
            yield runtime
        finally:
            runtime.closed = True

    return create_server(settings, factory)


def test_discovery_and_all_calls(settings):
    runtime = StubRuntime()

    async def run():
        async with create_connected_server_and_client_session(
            make_server(settings, runtime)
        ) as client:
            tools = (await client.list_tools()).tools
            assert {t.name for t in tools} == set(ARGUMENTS)
            for tool in tools:
                assert tool.annotations.readOnlyHint
                assert not tool.annotations.destructiveHint
                assert tool.inputSchema["additionalProperties"] is False
                assert "tenant_id" not in tool.inputSchema["properties"]
                assert all(
                    field.get("description") for field in tool.inputSchema["properties"].values()
                )
            args = [
                {"query": "policy"},
                {"question": "policy"},
                {},
                {"document_id": str(uuid4())},
                {"document_id": str(uuid4())},
            ]
            for name, payload in zip(ARGUMENTS, args, strict=True):
                response = await client.call_tool(name, payload)
                assert not response.isError
                assert response.structuredContent == {"items": []}

    asyncio.run(run())
    assert len(runtime.calls) == 5
    assert runtime.closed


@pytest.mark.parametrize(
    "name,args",
    [
        ("search_knowledge", {"query": " "}),
        ("search_knowledge", {"query": "x", "tenant_id": str(uuid4())}),
        ("search_knowledge", {"query": "x", "top_k": 21}),
        ("search_knowledge", {"query": "x", "rerank": "false"}),
        ("ask_knowledge", {"question": "x", "top_k": True}),
        ("ask_knowledge", {"question": "x", "search_mode": "unsafe"}),
        ("list_documents", {"limit": 21}),
        ("list_documents", {"offset": -1}),
        ("get_document", {"document_id": "invalid"}),
        ("get_document_chunks", {"document_id": str(uuid4()), "tenant_id": "evil"}),
    ],
)
def test_invalid_arguments_never_reach_runtime(settings, name, args):
    runtime = StubRuntime()

    async def run():
        async with create_connected_server_and_client_session(
            make_server(settings, runtime)
        ) as client:
            response = await client.call_tool(name, args)
            assert response.isError
            assert response.structuredContent["error"]["code"] == "invalid_arguments"

    asyncio.run(run())
    assert not runtime.calls


@pytest.mark.parametrize(
    "failure,code",
    [
        (RuntimeError("SECRET PRIVATE DOCUMENT"), "tool_failed"),
        (
            ServiceError("embedding_unavailable", "Embedding provider request failed"),
            "embedding_unavailable",
        ),
    ],
)
def test_safe_errors(settings, failure, code):
    runtime = StubRuntime()
    runtime.failure = failure

    async def run():
        async with create_connected_server_and_client_session(
            make_server(settings, runtime)
        ) as client:
            response = await client.call_tool("search_knowledge", {"query": "x"})
            assert response.isError
            assert response.structuredContent["error"]["code"] == code
            assert "SECRET" not in response.model_dump_json()

    asyncio.run(run())


def test_output_budget(settings):
    settings.mcp_max_output_bytes = 4096
    runtime = StubRuntime()
    runtime.payload = {"content": "x" * 5000}

    async def run():
        async with create_connected_server_and_client_session(
            make_server(settings, runtime)
        ) as client:
            response = await client.call_tool("list_documents", {})
            assert response.isError
            assert response.structuredContent["error"]["code"] == "output_too_large"

    asyncio.run(run())


def test_stdio_only(settings):
    server = create_server(settings)
    with pytest.raises(ValueError):
        server.run("streamable-http")
    with pytest.raises(NotImplementedError):
        server.streamable_http_app()
    with pytest.raises(NotImplementedError):
        server.sse_app()


@pytest.mark.parametrize("key", [None, "wrong", "test-api-key-with-at-least-32-characters"])
def test_startup_requires_tenant_bound_credential(settings, key):
    settings.mcp_api_key = SecretStr(key) if key else None
    with pytest.raises(ValueError, match="tenant-bound"):
        with open_runtime(settings):
            pytest.fail("Unbound or invalid credential accepted")


def test_stdio_authentication_failure_does_not_leak(settings):
    import os
    import subprocess
    import sys

    env = {
        **os.environ,
        "API_KEY": settings.api_key.get_secret_value(),
        "API_KEY_TENANT_ID": str(uuid4()),
        "TENANT_API_KEYS": "{}",
        "MCP_API_KEY": "SECRET-invalid-credential",
        "DATABASE_URL": str(settings.database_url),
    }
    completed = subprocess.run(
        [sys.executable, "-m", "enterprise_knowledge_engine.mcp", "--env-file", "/dev/null"],
        input="",
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert "SECRET" not in completed.stderr
    assert "Traceback" not in completed.stderr
    assert "MCP startup failed" in completed.stderr
