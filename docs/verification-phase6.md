# Phase 6 verification — 2026-11-08

Phase 6 implements a synthetic evaluation framework, optional structured judge, security regression/hardening work, content-free observability, pinned dependency/CI checks and a lightweight HTTP load harness. No push or commit was performed. No schema changes or migrations were added; the schema head remains `0003_retrieval`.

## Actual checks and results

| Check | Result |
|---|---|
| Baseline before changes | 248 tests passed; Ruff passed |
| Final Python 3.13.9, clean locked environment | **307 passed, 0 failed, 0 skipped**, one warning |
| Final Python 3.12.2, separate clean locked environment | **307 passed, 0 failed, 0 skipped**, one warning |
| Unit selection | 242 passed; 65 integration tests deselected by `make test` |
| PostgreSQL integration coverage in full runs | 65 passed per interpreter |
| Focused answer recording/judge tests after type/fixture refinement | 11 passed |
| Ruff check and format check | Passed |
| Dependency compatibility (`uv pip check`) | Passed, 83 installed packages including editable project |
| Dataset validation | 34 questions, 12 documents, two tenants; passed |
| Common-format secret guard | Passed; limited pattern scan, not a complete secret/history review |
| pip-audit 2.10.1 | 82 applicable locked packages audited, zero skipped, **zero known vulnerabilities** reported |
| Migration upgrade / schema comparison | Passed; no new upgrade operations detected |
| Migration downgrade to base / upgrade to head / comparison | Passed in disposable database |
| Actual MCP protocol regressions | Passed as part of each full suite, including separate stdio subprocess |
| Keyword benchmark | Completed: 34 queries, zero query errors |
| Actual local HTTP load demo | 40 listing + 40 keyword requests, concurrency four, zero failures |

The warning is `StarletteDeprecationWarning`: the locked Starlette TestClient supports the existing `httpx` fallback but recommends `httpx2` for future use. It is recorded rather than hidden. Unused `httpx2`, `httpcore2`, `mcp-types` and `truststore` packages left by the earlier SDK v2 investigation were removed before the final Python 3.13 run so the tests match the dependency lock. Existing suppression of both HTTP client logger families is retained as defense in depth. Updating the test-client dependency path is future maintenance, not a claimed failure of these passing tests.

Docker is not installed here, so container build/Compose and remote GitHub Actions execution were **not** tested. CI configuration retains both Python versions, a pgvector PostgreSQL service, all tests, migration checks and Docker build. The local matrix ran on macOS, not CI's Linux host. There were no paid OpenAI/Cohere/judge calls.

The previous temporary PostgreSQL installation disappeared during the session. A separate PostgreSQL **16.11** + pgvector **0.8.1** instance was rebuilt in `/tmp`, on loopback port **55432**, leaving the installed PostgreSQL 14 service on port 5432 untouched. The first recreated SQL_ASCII cluster caused setup failures (4 failed, 228 passed, 61 errors); it was replaced with a fresh **UTF-8** cluster, after which migrations and all final tests passed. The failed setup run is not included as successful coverage. The temporary cluster uses trust authentication for disposable local testing only and is stopped after verification. Database/OS/base-image vulnerability assessment is outside the Python dependency scan.

## Exact verification commands

These local connection settings name disposable test resources and a public test-only application key, not deployment credentials:

```sh
make lint
make test
.venv/bin/python -m enterprise_knowledge_engine.evaluation.runner --validate-only
.venv/bin/python scripts/check_secrets.py
UV_CACHE_DIR=/tmp/eke-uv-cache uv pip check --python .venv/bin/python

.venv/bin/pip-audit -r requirements-dev.lock --disable-pip --no-deps \
  --cache-dir /tmp/eke-audit-cache --progress-spinner off \
  --format json --output /tmp/eke-phase6-audit-universal.json

API_KEY=test-only-api-key-with-at-least-32-characters \
DATABASE_URL=postgresql+psycopg://MEHDI@127.0.0.1:55432/eke_phase6 \
RUN_DB_TESTS=1 .venv/bin/pytest -q

API_KEY=test-only-api-key-with-at-least-32-characters \
DATABASE_URL=postgresql+psycopg://MEHDI@127.0.0.1:55432/eke_phase6 \
RUN_DB_TESTS=1 /tmp/eke-phase6-py312/bin/python -m pytest -q
```

The separate Python 3.12 environment was created and populated with:

```sh
UV_CACHE_DIR=/tmp/eke-uv-cache uv venv \
  --python /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 /tmp/eke-phase6-py312
UV_CACHE_DIR=/tmp/eke-uv-cache uv pip install --python /tmp/eke-phase6-py312/bin/python -r requirements-dev.lock
UV_CACHE_DIR=/tmp/eke-uv-cache uv pip install --python /tmp/eke-phase6-py312/bin/python --no-deps -e .
```

The main environment was synchronized with `uv pip sync --python .venv/bin/python requirements-dev.lock` and the project reinstalled using `uv pip install --python .venv/bin/python --no-deps -e .`. Both commands used the same temporary UV cache.

Migration commands were executed in order, stopping on any failed return code, with the disposable API_KEY/DATABASE_URL above:

```sh
.venv/bin/alembic upgrade head
.venv/bin/alembic check
.venv/bin/alembic downgrade base
.venv/bin/alembic upgrade head
.venv/bin/alembic check
```

Measured artifact commands used those same disposable API_KEY/DATABASE_URL values:

```sh
.venv/bin/python -m enterprise_knowledge_engine.evaluation.runner \
  --output evaluation/reports/local-keyword
.venv/bin/python scripts/demo_performance.py \
  --output evaluation/reports/local-keyword/performance.json
```

For ordinary local use, configure your protected `.env` using the root README rather than copying these machine-specific paths/database settings.

## Dataset, metrics and tested strategies

The versioned dataset has 34 questions across semantic, exact-identifier, technical, paraphrase, multiple-document, ambiguous, missing-information, conflicting-evidence, tenant-isolation and injection categories. Twenty-six questions have positive document judgments; eight have no authorized relevant documents. Corpus and judgments are synthetic, manually authored and documented. The final SHA-256 fingerprint is:

`42bdb2da2b3e46868b61fad519f8cb66c8e9ce53ea0b363a341be14deb736ba1`

Document labels are benchmark truth; indexed UUIDs are mapped dynamically. Benchmark-only chunk UUIDs are deterministic for stable ties. Integration tests compare two complete keyword runs and verify identical metric aggregates and cleanup. Keyword-only fixtures contain NULL vectors; **no fake embeddings were used to publish retrieval quality**.

Definitions: Recall@K is hits divided by relevant labels; Precision@K is hits divided by K even for short result lists; MRR is the macro mean of reciprocal first-relevant rank (also truncated at each K); nDCG@K uses `(2^grade−1)/log2(rank+1)` normalized by ideal order; Hit Rate@K is whether any relevant label appears. All five cutoff metrics exclude zero-relevance queries, return null for them and expose denominators. Failed positive-relevance searches count as zeros. Negative successful-query counts/nonempty results are reported separately. See [EVALUATION.md](EVALUATION.md) for complete policy, category aggregates and limitations.

Measured PostgreSQL keyword baseline:

| K | Recall | Precision | MRR@K | nDCG | Hit rate |
|---|---|---|---|---|---|
| 1 | 0.1474 | 0.1923 | 0.1923 | 0.1923 | 0.1923 |
| 3 | 0.1667 | 0.0769 | 0.1923 | 0.1719 | 0.1923 |
| 5 | 0.1667 | 0.0462 | 0.1923 | 0.1719 | 0.1923 |
| 10 | 0.1667 | 0.0231 | 0.1923 | 0.1719 | 0.1923 |

Pool MRR is 0.1923. Every relevance-metric denominator is 26. Eight successful negative queries returned no passages; that is not a claim that real semantic retrieval or LLM abstention is solved. This is a **weak lexical baseline**, exposing conjunctive PostgreSQL web-search behavior on natural-language paraphrases. These results are not presented as adequate enterprise retrieval quality, and questions/algorithms were not tuned to conceal the misses.

Vector, hybrid, hybrid-plus-real-reranker, live-answer and live-judge quality results remain **pending** because no authorized real-provider configuration was available. The runner creates explicit pending entries with no scores. It rejects fake answer-quality evaluation and reports real-reranker fallback as an error. Optional answer/judge adapters, structured schema/evidence checks, budgets and failure states were tested with controlled unit providers; those tests are not live model quality results.

Artifacts:

- `evaluation/reports/local-keyword/metrics.json`
- `evaluation/reports/local-keyword/metrics.csv`
- `evaluation/reports/local-keyword/comparison.md`
- `evaluation/reports/local-keyword/per_question.jsonl`
- `evaluation/reports/local-keyword/performance.json`
- `evaluation/reports/local-keyword/dependency-audit.json`

The dependency audit snapshot wraps actual pip-audit output. It covers the 82 packages applicable on macOS; Windows-only marker dependencies were not scanned on this host. A clean advisory scan is not a complete vulnerability or supply-chain assessment.

## Actual measured HTTP performance

The final snapshot ran on Python 3.13.9 against a real, single-process loopback Uvicorn API and PostgreSQL 16.11/pgvector 0.8.1. It indexed the synthetic dataset with NULL vectors, used one trusted tenant credential, exercised real HTTP/authentication/SQL/serialization, and cleaned up its process and fixture tenants. No paid providers were used. Scenarios run sequentially; no warm-up samples were removed.

| Scenario | Requests | Concurrency | Average ms | P50 ms | P95 ms | Failures | Attempts/sec |
|---|---|---|---|---|---|---|---|
| Listing | 40 | 4 | 5.384 | 4.347 | 15.297 | 0 | 723.632 |
| Keyword search | 40 | 4 | 6.760 | 6.293 | 11.405 | 0 | 577.659 |

Latency includes failed calls (there were none); throughput counts all attempts. Percentiles use linear interpolation. The run is extremely short, its data is tiny, caches/connections affect timing, and there is no representative workload or confidence interval. **Do not infer production capacity or enterprise scale from this table.** Vector/hybrid/answer load scenarios are implemented but unmeasured here; they require a real corpus, explicit paid authorization and bounded calls/rate limits.

## Verified controls and reliability

New and retained regressions verify:

- HTTP and MCP authentication, tenant-bound credentials, revocation/removal, and stale MCP principal rejection against refreshed in-memory configuration.
- Caller-supplied tenant fields/headers do not move ingested records; other tenants' valid document IDs return the same missing-document result as absent IDs.
- All search modes, document metadata/chunks, source citations and five official SDK MCP tools enforce tenant isolation in database access.
- Invalid/oversized/unreadable files and parser timeout paths fail safely; duplicate hashes and partial-ingestion failures do not create false-ready documents.
- Invalid input values and private exception contents are omitted from errors/logs; request IDs cannot be spoofed. Timing context resets after errors, and generated IDs propagate into worker events.
- Citation IDs/document/chunk identities match actual supplied sources; quote membership and canaries are checked. Valid citations do not prove entailment.
- SDK transient retry classification, bounded exponential backoff/jitter and exhaustion are tested with mock HTTP transport and no sleeps/paid calls. Provider authorization/bad-request errors are classified separately from rate-limit/timeouts and remain sanitized.
- Health/readiness, pool/session/client cleanup, bounded candidates/context/MCP outputs, rejected MCP writes and explicit reranking fallback remain tested.

## File inventory

Created application/evaluation code:

- `src/enterprise_knowledge_engine/evaluation/{__init__,dataset,metrics,answers,runner,performance}.py`
- `src/enterprise_knowledge_engine/core/telemetry.py`
- `scripts/check_secrets.py`, `scripts/demo_performance.py`
- `tests/test_evaluation_metrics.py`, `tests/test_evaluation_answers.py`, `tests/test_evaluation_database.py`
- `tests/test_provider_reliability.py`, `tests/test_security_hardening.py`

Created data, documentation and reproducibility files:

- `evaluation/README.md`
- `evaluation/datasets/v1/{README.md,manifest.json,questions.jsonl}`
- `evaluation/datasets/v1/documents/{refunds,portal,sla,sso,retention,billing,limits,export,maintenance-a,maintenance-b,malicious,private-refunds}.md`
- The six measured/audit artifacts listed above.
- `docs/EVALUATION.md`, `docs/SECURITY.md`, `docs/verification-phase6.md`
- `requirements.lock`, `requirements-dev.lock`, `.gitattributes`

Modified existing files:

- `src/enterprise_knowledge_engine/core/{config,security,logging}.py`
- `src/enterprise_knowledge_engine/main.py`
- `src/enterprise_knowledge_engine/mcp/{runtime,server}.py`
- `src/enterprise_knowledge_engine/ingestion/{embeddings,service}.py`
- `src/enterprise_knowledge_engine/retrieval/service.py`
- `src/enterprise_knowledge_engine/qa/providers.py`
- `tests/test_ingestion_database.py`, `tests/test_qa_providers.py`
- `pyproject.toml`, `Makefile`, `Dockerfile`, `.github/workflows/ci.yml`
- `.gitignore`, `.env.example`, `README.md`, `docs/ARCHITECTURE.md`

## Remaining risks and portfolio assessment

**Appropriate as a transparent technical portfolio demonstration, not approved for production deployment.** The repo now has reproducible fixtures/metrics, actual published lexical/load measurements and security/tenant regression evidence. The poor keyword baseline and absent real-provider comparisons are clearly visible. Publication still requires the owner's normal review of files/history, intended license, examples and metadata; nothing was pushed automatically.

Remaining work includes actual vector/hybrid/reranker and LLM/judge evaluation, human-reviewed judge calibration/entailment checks, larger held-out/multilingual/long-document datasets, representative load and real-model adversarial testing. No evidence supports a claim that hallucinations or prompt injection are eliminated.

Remote MCP authentication/TLS/host-origin validation is not implemented; only trusted local stdio is supported. Live identity/revocation, RLS/per-document roles, distributed rate/admission limits, dollar budgets, durable audit/alerts, provider privacy agreements, backups/restore and incident procedures remain deployment requirements. Environment revocation changes require restarting/reloading every worker. DB/OS/image/CPython patching, complete secret/history scanning, artifact hashes/signing, production Linux behavior and remote CI results were not security-verified here. See [SECURITY.md](SECURITY.md) for the threat model and exact boundaries.
