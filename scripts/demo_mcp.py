"""Real stdio protocol + PostgreSQL demo with scripted providers; never paid AI calls."""

import argparse
import asyncio
import json
import os
import secrets
import sys
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from demo_qa import SAMPLE_ROOT, DemoEmbeddings, DemoLLM
from fastapi.testclient import TestClient
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import SecretStr
from sqlalchemy import delete
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.db.models import Tenant
from enterprise_knowledge_engine.db.session import build_engine
from enterprise_knowledge_engine.ingestion.embeddings import get_embedding_provider
from enterprise_knowledge_engine.main import create_app
from enterprise_knowledge_engine.mcp.runtime import open_runtime
from enterprise_knowledge_engine.mcp.server import create_server


@contextmanager
def fixture_runtime(config: Settings):
    with open_runtime(config) as runtime:
        runtime.embeddings, runtime.llm = DemoEmbeddings(), DemoLLM()
        yield runtime


async def interact(config: Settings) -> None:
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
    params = StdioServerParameters(
        command=sys.executable, args=[str(Path(__file__).resolve()), "--serve-fixtures"], env=env
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=30)) as client:
            initialized = await client.initialize()
            print("Server: " + initialized.serverInfo.name)
            print("Tools: " + ", ".join(t.name for t in (await client.list_tools()).tools))
            scenarios = json.loads((SAMPLE_ROOT / "scenarios.json").read_text())
            calls = [("search_knowledge", {"query": "retail returns", "mode": "hybrid"})]
            calls += [
                ("ask_knowledge", {"question": s["question"], "search_mode": "hybrid"})
                for s in scenarios
            ]
            for name, args in calls:
                response = await client.call_tool(name, args)
                assert not response.isError, response
                payload = response.structuredContent
                if name == "ask_knowledge":
                    scenario = next(s for s in scenarios if s["question"] == args["question"])
                    assert payload["status"] == scenario["expected_status"]
                    assert payload["retrieval"]["sources_used"] == scenario["expected_sources"]
                    assert "INJECTION_CANARY_EXECUTED" not in payload["answer"]
                else:
                    assert payload["results"]
                print(json.dumps({"tool": name, "arguments": args, "result": payload}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve-fixtures", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.serve_fixtures:
        create_server(Settings(_env_file=None), fixture_runtime).run()
        return
    config = Settings()
    tenant, key = uuid4(), secrets.token_urlsafe(40)
    config = config.model_copy(
        update={
            "api_key": SecretStr(key),
            "api_key_tenant_id": tenant,
            "tenant_api_keys": {},
            "embedding_provider": "fake",
            "llm_provider": "fake",
            "reranker_provider": "none",
            "search_vector_strategy": "exact",
        }
    )
    engine = build_engine(config)
    try:
        with Session(engine) as session, session.begin():
            session.add(Tenant(id=tenant, name="Temporary MCP fixture demo", slug=str(tenant)))
        app = create_app(config)
        app.dependency_overrides[get_embedding_provider] = DemoEmbeddings
        with TestClient(app) as client:
            for path in sorted(SAMPLE_ROOT.glob("*.md")):
                response = client.post(
                    "/api/v1/documents/upload",
                    headers={"X-API-Key": key},
                    files={"file": (path.name, path.read_bytes())},
                )
                response.raise_for_status()
        print("SCRIPTED FIXTURES: verifies protocol and source plumbing, not real-model security.")
        asyncio.run(interact(config))
    finally:
        with Session(engine) as session, session.begin():
            session.execute(delete(Tenant).where(Tenant.id == tenant))
        engine.dispose()


if __name__ == "__main__":
    main()
