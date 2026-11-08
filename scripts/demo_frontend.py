"""Run real browser/BFF/FastAPI/PostgreSQL integration using isolated controlled fixtures.

Requires a migrated disposable DATABASE_URL and installed frontend/Playwright Chromium.
No paid providers. Does not change .env files or leave fixture tenants on normal exit.
"""

import argparse
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
from demo_qa import DemoEmbeddings, DemoLLM
from pydantic import SecretStr
from sqlalchemy import delete
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.db.models import Tenant
from enterprise_knowledge_engine.db.session import build_engine
from enterprise_knowledge_engine.ingestion.embeddings import get_embedding_provider
from enterprise_knowledge_engine.main import create_app
from enterprise_knowledge_engine.qa.providers import get_llm_provider

ROOT = Path(__file__).resolve().parents[1]


def fixture_app():
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_embedding_provider] = DemoEmbeddings
    app.dependency_overrides[get_llm_provider] = DemoLLM
    return app


def wait_ready(url: str, process: subprocess.Popen) -> None:
    with httpx.Client(trust_env=False, timeout=2) as client:
        for _ in range(150):
            if process.poll() is not None:
                raise RuntimeError("Demo process exited; inspect /tmp/eke-frontend-*.log")
            try:
                if client.get(url).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
    raise RuntimeError("Demo startup timed out")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help="Internal fixture backend")
    parser.add_argument("--interactive", action="store_true", help="Keep demo open until Enter")
    parser.add_argument(
        "--screenshots",
        action="store_true",
        help="Capture the README RAG gallery with isolated public fixtures",
    )
    args = parser.parse_args()
    if args.serve:
        import uvicorn

        uvicorn.run(fixture_app(), host="127.0.0.1", port=8018, access_log=False)
        return
    config = Settings()
    tenant = uuid4()
    key = secrets.token_urlsafe(40)
    config = config.model_copy(
        update={
            "api_key": SecretStr(key),
            "api_key_tenant_id": tenant,
            "tenant_api_keys": {},
        }
    )
    engine = build_engine(config)
    processes: list[subprocess.Popen] = []
    logs = []
    try:
        with Session(engine) as session, session.begin():
            session.add(Tenant(id=tenant, name="Synthetic browser demo", slug=str(tenant)))
        env = {
            **os.environ,
            "DATABASE_URL": str(config.database_url),
            "API_KEY": key,
            "API_KEY_TENANT_ID": str(tenant),
            "TENANT_API_KEYS": "{}",
            "REVOKED_API_KEY_HASHES": "[]",
            "EMBEDDING_PROVIDER": "fake",
            "LLM_PROVIDER": "fake",
            "RERANKER_PROVIDER": "none",
            "QA_RERANK": "false",
            "SEARCH_VECTOR_STRATEGY": "exact",
            "BACKEND_URL": "http://127.0.0.1:8018",
            "BACKEND_API_KEY": key,
            "APP_ORIGIN": "http://localhost:3008",
            "SESSION_SECRET": secrets.token_urlsafe(48),
            "DEMO_PASSWORD": secrets.token_urlsafe(24),
            "EVALUATION_REPORT_DIR": str(ROOT / "evaluation/reports/local-keyword"),
            "E2E_BASE_URL": "http://localhost:3008",
            "NEXT_TELEMETRY_DISABLED": "1",
            "PORT": "3008",
            "HOSTNAME": "127.0.0.1",
        }
        for name, command, cwd in [
            ("backend", [sys.executable, str(Path(__file__).resolve()), "--serve"], ROOT),
            (
                "next",
                [
                    "node",
                    "scripts/start.mjs",
                ],
                ROOT / "frontend",
            ),
        ]:
            log = open(f"/tmp/eke-frontend-{name}.log", "w")
            logs.append(log)
            processes.append(
                subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
            )
        wait_ready("http://127.0.0.1:8018/ready", processes[0])
        wait_ready("http://localhost:3008/login", processes[1])
        # Runtime-only backend credentials must never appear in browser JS assets.
        for bundle in (ROOT / "frontend/.next/static").rglob("*.js"):
            if key.encode() in bundle.read_bytes():
                raise RuntimeError("Backend key leaked into a client asset")
        print("CONTROLLED PROVIDERS: real browser/proxy/SQL, not semantic-quality evidence.")
        if args.screenshots:
            subprocess.run(
                ["node", "scripts/capture-showcase.mjs"], cwd=ROOT / "frontend", env=env, check=True
            )
        elif args.interactive:
            print("Open http://localhost:3008/login; this temporary password is NOT an API key:")
            print(env["DEMO_PASSWORD"])
            input("Press Enter to stop and remove the demo tenant. ")
        else:
            subprocess.run(["npm", "run", "test:e2e"], cwd=ROOT / "frontend", env=env, check=True)
    finally:
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for log in logs:
            log.close()
        with Session(engine) as session, session.begin():
            session.execute(delete(Tenant).where(Tenant.id == tenant))
        engine.dispose()


if __name__ == "__main__":
    main()
