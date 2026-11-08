"""Start an isolated real local API and measure free listing/keyword requests."""

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
from pathlib import Path
from time import monotonic, sleep

import httpx

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.evaluation.dataset import Dataset
from enterprise_knowledge_engine.evaluation.performance import run_load
from enterprise_knowledge_engine.evaluation.runner import indexed_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("evaluation/results/performance-demo.json")
    )
    args = parser.parse_args()
    config = Settings()
    dataset = Dataset(Path("evaluation/datasets/v1"))
    with indexed_dataset(dataset, config, semantic=False) as (_, tenants, _):
        key = secrets.token_urlsafe(40)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        env = {
            **os.environ,
            "DATABASE_URL": str(config.database_url),
            "API_KEY": key,
            "API_KEY_TENANT_ID": str(tenants["a"]),
            "TENANT_API_KEYS": "{}",
            "REVOKED_API_KEY_HASHES": "[]",
            "EMBEDDING_PROVIDER": "openai",
            "LLM_PROVIDER": "openai",
            "DOCS_ENABLED": "false",
        }
        child = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "enterprise_knowledge_engine.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            base = f"http://127.0.0.1:{port}"
            deadline = monotonic() + 15
            with httpx.Client(timeout=1, trust_env=False) as client:
                while True:
                    try:
                        if client.get(base + "/ready").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if monotonic() > deadline or child.poll() is not None:
                        raise RuntimeError("Demo API did not become ready")
                    sleep(0.05)
            result = run_load(base, key, ["list", "keyword"], requests=40, concurrency=4)
            result["dataset_sha256"] = dataset.sha256
            output = args.output
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result, indent=2))
            assert all(s["failure_count"] == 0 for s in result["scenarios"].values())
        finally:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
