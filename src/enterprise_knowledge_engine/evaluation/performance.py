"""Small HTTP load harness. All timings are local measurements, not capacity claims."""

import argparse
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from platform import python_version
from statistics import fmean
from time import perf_counter
from urllib.parse import urlparse

import httpx

from enterprise_knowledge_engine.core.config import Settings

SCENARIOS = {"list", "keyword", "vector", "hybrid", "ask"}


def percentile(values: list[float], percent: float) -> float | None:
    if not 0 <= percent <= 100:
        raise ValueError("Percentile must be 0–100")
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def latency_summary(values: list[float]) -> dict:
    return {
        "requests": len(values),
        "average_ms": fmean(values) if values else None,
        "p50_ms": percentile(values, 50),
        "p95_ms": percentile(values, 95),
    }


def run_load(
    base_url: str,
    key: str,
    scenarios: list[str],
    requests: int = 20,
    concurrency: int = 4,
    allow_paid: bool = False,
) -> dict:
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("This demo harness supports loopback HTTP only")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Do not place credentials or query strings in base URL")
    if not 1 <= requests <= 500 or not 1 <= concurrency <= 16:
        raise ValueError("Requests must be 1–500 and concurrency 1–16")
    if not scenarios or any(s not in SCENARIOS for s in scenarios):
        raise ValueError("Unknown load scenario")
    if any(s in {"vector", "hybrid", "ask"} for s in scenarios) and not allow_paid:
        raise ValueError("Provider scenarios require explicit --allow-paid")
    if "ask" in scenarios and requests > 10:
        raise ValueError("Answer load is limited to ten calls per run")
    output = {
        "started_at": datetime.now(UTC).isoformat(),
        "python": python_version(),
        "scope": "loopback synthetic demonstration, not representative production load",
        "concurrency": concurrency,
        "scenarios": {},
    }
    with httpx.Client(
        base_url=base_url,
        headers={"X-API-Key": key},
        timeout=60,
        follow_redirects=False,
        trust_env=False,
    ) as client:

        def call(scenario: str) -> tuple[float, str | None]:
            started = perf_counter()
            error = None
            try:
                if scenario == "list":
                    response = client.get("/api/v1/documents", params={"limit": 10})
                elif scenario == "ask":
                    response = client.post(
                        "/api/v1/ask",
                        json={
                            "question": "What is RMA-204?",
                            "top_k": 5,
                            "search_mode": "hybrid",
                            "rerank": False,
                        },
                    )
                else:
                    response = client.post(
                        "/api/v1/search",
                        json={
                            "query": "RMA-204 returns",
                            "mode": scenario,
                            "top_k": 5,
                            "rerank": False,
                        },
                    )
                if not 200 <= response.status_code < 300:
                    error = f"http_{response.status_code}"
            except httpx.HTTPError:
                error = "network_error"
            return (perf_counter() - started) * 1000, error

        for scenario in scenarios:
            started = perf_counter()
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                samples = list(executor.map(call, [scenario] * requests))
            elapsed = perf_counter() - started
            failures = [error for _, error in samples if error]
            output["scenarios"][scenario] = {
                **latency_summary([ms for ms, _ in samples]),
                "failure_count": len(failures),
                "errors": {e: failures.count(e) for e in sorted(set(failures))},
                "elapsed_seconds": elapsed,
                "throughput_requests_per_second": requests / elapsed,
                "samples_ms": [ms for ms, _ in samples],
            }
    output["finished_at"] = datetime.now(UTC).isoformat()
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--scenarios", default="list,keyword")
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/performance.json"))
    args = parser.parse_args()
    try:
        config = Settings()
        result = run_load(
            args.base_url,
            config.api_key.get_secret_value(),
            args.scenarios.split(","),
            args.requests,
            args.concurrency,
            args.allow_paid,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    except Exception:
        parser.exit(
            1,
            "Load run failed; check bounds, server, credentials and paid authorization.\n",
        )


if __name__ == "__main__":
    main()
