# Phase 5 verification

Verification performed locally on Python 3.13.9, PostgreSQL 16.11, pgvector 0.8.1 and official MCP SDK 1.30.0. No GitHub push or commit was made. No database schema changes were necessary: `0003_retrieval` remains the migration head.

## Executed checks

Baseline before MCP work: `make test` passed 167 unit tests; `make lint` passed. The first full suite after SDK installation exposed a verbose `httpx2` URL logging leak (214 passed, 1 failed). Logging suppression now covers both HTTP client logger families and MCP SDK payload logs; the final suite includes the passing logging regression. SDK 2.3.0 was inspected first, then replaced with pinned 1.30.0 because v2 renamed FastMCP to MCPServer.

Final commands (the database/user below are disposable loopback test resources, not application credentials):

```sh
make test
make lint
UV_CACHE_DIR=/tmp/eke-uv-cache uv pip check --python .venv/bin/python

API_KEY=test-only-api-key-with-at-least-32-characters \
DATABASE_URL=postgresql+psycopg://MEHDI@localhost:55432/eke_test \
RUN_DB_TESTS=1 .venv/bin/pytest -q

API_KEY=test-only-api-key-with-at-least-32-characters \
DATABASE_URL=postgresql+psycopg://MEHDI@localhost:55432/eke_test \
.venv/bin/alembic check

API_KEY=test-only-api-key-with-at-least-32-characters \
DATABASE_URL=postgresql+psycopg://MEHDI@localhost:55432/eke_test \
.venv/bin/python scripts/demo_mcp.py
```

- Unit selection: **186 passed**, 62 integration tests intentionally deselected by `make test`.
- Full PostgreSQL suite: **248 passed**, zero failed or skipped, comprising 186 unit/protocol and 62 integration tests.
- Ruff check and format check: passed.
- Installed dependency compatibility: passed (`uv pip check`).
- Alembic check: `No new upgrade operations detected.`
- CLI `python -m enterprise_knowledge_engine.mcp --help`: passed.

The test database was started from the previously built temporary PostgreSQL installation because Docker is unavailable in this environment. Docker build/Compose and CI's Python 3.12 matrix were not run locally. Existing CI will execute all new tests with migrated PostgreSQL on Python 3.12/3.13. This is configuration, not a claim that remote CI has passed.

## Protocol and authorization evidence

Official SDK in-memory protocol tests initialize ClientSession, discover all five tool schemas, and invoke every tool. A real stdio subprocess test also initializes, discovers, and calls all five tools against PostgreSQL. A separate subprocess test verifies invalid credentials exit nonzero, emit no stdout data, and expose neither the secret nor traceback on stderr.

The 33 added tests cover discovery/input descriptions and bounds, unknown tenant arguments, invalid UUIDs, string booleans, empty/oversized arguments, pagination, safe exceptions, embedding and LLM failures, output byte budgets, engine cleanup, explicit SQL chunk clipping, denied SQL writes, and transport restrictions. PostgreSQL tests exercise both authenticated tenant identities in vector, keyword and hybrid retrieval, plus metadata/chunk ownership, grounded citations, nonexistent citation rejection, empty results and abstention. Another tenant's valid UUID produces `document_not_found` in both document tools. Metadata lists and search results contain only the bound tenant's records. The default fake LLM abstains; a scripted valid quote returns citations for the tenant's actual chunk.

Read-only transaction enforcement is verified by `SHOW transaction_read_only` returning `on` and a SQL DELETE being rejected by PostgreSQL. This is defense in depth, not an implementation of database RLS or per-tenant database roles.

## Reproducible demonstration

`scripts/demo_mcp.py` ingested three sample Markdown files into a temporary tenant, launched a separate stdio server, discovered the five tools and executed hybrid search plus four grounded QA scenarios through the official SDK client. Temporary records were cleaned up afterward. The demo reused the existing Phase 4 sample documents and controlled providers; no paid API calls were made.

Observed cases:

- Supported retail-policy question: `answered`, one actual cited source, exact supporting quote.
- Portal submission plus policy: `answered`, two sources.
- Unsupported question: `insufficient_evidence`, zero sources used.
- Malicious-document fixture: legitimate device-service fact cited; injection canary absent from the scripted answer.

The actual supported response excerpt and client configuration are in [the MCP guide](mcp.md). The script prints complete structured search and QA responses including IDs, score provenance, excerpts and timings. Run-specific UUIDs and durations change. Scripted vectors do not prove semantic quality; scripted claims do not prove a real model resists malicious documents. Existing server-side citation ID and exact-quote validation remains in force.

## File inventory

Created:

- `src/enterprise_knowledge_engine/mcp/__init__.py`
- `src/enterprise_knowledge_engine/mcp/__main__.py`
- `src/enterprise_knowledge_engine/mcp/schemas.py`
- `src/enterprise_knowledge_engine/mcp/server.py`
- `src/enterprise_knowledge_engine/mcp/runtime.py`
- `src/enterprise_knowledge_engine/documents/__init__.py`
- `src/enterprise_knowledge_engine/documents/schemas.py`
- `src/enterprise_knowledge_engine/documents/service.py`
- `tests/test_mcp.py`
- `tests/test_mcp_database.py`
- `scripts/demo_mcp.py`
- `examples/mcp/claude_desktop_config.json`
- `docs/mcp.md`
- `docs/verification-phase5.md`

Modified:

- `pyproject.toml`: pinned official SDK and explicit AnyIO dependency.
- `core/config.py`, `core/security.py`, `core/logging.py` under the existing package: MCP settings, shared pure credential resolver, sanitized logging.
- `ingestion/embeddings.py`, `retrieval/reranking.py`, `qa/providers.py`: reusable provider builders; existing FastAPI dependency wrappers preserved.
- `api/v1/documents.py`: reused shared document DTOs/list read service; public REST behavior preserved.
- `Makefile`, `.env.example`, `README.md`, `docs/ARCHITECTURE.md`: commands, settings, architecture and security documentation.

No migrations, FastAPI MCP mounts, frontend, remote authentication, agent framework, persistent memory or destructive MCP tools were added.

## Remaining limits

Only trusted local stdio is supported by this app. Official SDK 1.30.0 supports stdio, Streamable HTTP and legacy SSE; its HTTP interfaces are deliberately disabled here. OAuth, remote bearer-token validation, TLS/origin/host protections, revocation, rate limits, distributed admission/scaling, persistent audit logs, RLS and real-model injection/relevance evaluation remain future work. No production-readiness or certification claim is made.

Provider timeouts and SQL statement timeouts bound individual operations; there is no hard overall tool deadline. Active concurrency is limited per process, queued calls are not a rate limiter, and cancellation waits for worker cleanup. Local clients can exfiltrate the bound tenant's returned knowledge; local OS/environment access is trusted. Citation IDs and substring quote checks do not establish factual entailment. GUI desktop client and Inspector interactions, paid providers, container execution, multi-process load and production authorization were not verified.
