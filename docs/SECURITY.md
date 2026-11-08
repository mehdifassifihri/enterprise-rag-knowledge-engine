# Security model and operational limits

This is a production-minded portfolio service, not a security certification or a production deployment approval. Controls below are separated from incomplete mitigations. Use only synthetic/public documents until an authorized security and privacy review approves real data and provider handling.

## Trust boundaries and threats

| Boundary / threat | Implemented control and regression evidence | Remaining limitation |
|---|---|---|
| REST caller impersonates a tenant | Constant-time API-key comparison; trusted key-to-tenant mapping; client tenant fields/headers cannot override identity. HTTP integration tests verify stored tenant ownership. | Static environment configuration, no identity provider, user roles or per-document ACLs. |
| Key is removed or revoked | `REVOKED_API_KEY_HASHES` denies listed SHA-256 key digests in the shared resolver; removed mapping rejects old keys. MCP revalidates its bound credential against its in-memory config on each tool call. | **All processes must restart/reload configuration** after `.env`/environment changes. No live revocation database or automatic file watcher. A running process retains its old config until refreshed. |
| Document UUID enumeration / cross-tenant reads | SQL tenant predicates on document, chunks and parent documents; absent and unauthorized UUIDs return the same document-not-found response. Tests cover ingestion, all search modes, QA citations and all five MCP tools. | UUIDs are identifiers, not access grants. No rate limiter or proof against timing/volume side channels; no RLS. |
| Untrusted MCP client | Stdio startup requires an existing tenant-bound credential and provisioned tenant; strict tool schemas reject tenant arguments. Tests use actual SDK/stdin protocol and verify invalid credential startup failure. | Stdio assumes trusted local clients and OS. Any client controlling the process can read its tenant's knowledge. No remote HTTP/OAuth/authenticated multi-client endpoint exists. |
| Prompt injection in documents/history/questions | Data-only JSON context, narrow system instruction, no generation tools, bounded source context; server validates supplied citation IDs/metadata and exact supporting quotes. Scripted malicious-source tests prove the data path and reject fabricated citations. | Prompt instructions and quote membership cannot guarantee factual support, safe client behavior or resistance from a real model. Real-model attack evaluation remains pending. |
| SQL injection | SQLAlchemy bound expressions and parameters; user queries go to safe PostgreSQL full-text functions; no user SQL interpolation. | App database role may access all tenants. A compromised service/DB credential can bypass app predicates. Use a least-privilege role; evaluate RLS before remote production use. |
| Unsafe uploads / parser exhaustion | Extension/content/UTF-8/empty-file checks, exact file limit, whole-body bound, PDF page/extracted-text/time bounds and isolated worker; image-only/unreadable PDFs rejected. Existing tests cover malformed, oversized and timed-out files. | No OCR, antivirus/content-disarm pipeline, global admission control or proven parser sandbox escape resistance. Linux container resource isolation is stronger than macOS. Slow-client/network limits require a proxy. |
| Raw data or credentials in errors/logs | Safe service/database/unexpected error envelopes, input-free 422 validation responses, protected settings repr, JSON allowlist logging and suppressed SDK/HTTP payload logs. Security tests check input/exception/credential redaction and request-ID spoofing. | Returned authorized passages are private data by design. Access controls/retention for logs, backups and evaluation output remain operator responsibilities. |
| Accidental writes through MCP | Five read-only tools only; PostgreSQL transaction-read-only option; tests verify rejected DELETE and resource cleanup. | Use a SELECT-only database role as defense in depth. Read-only hints alone do not enforce authorization. |
| Dependency and repository leakage | Version locks; pip-audit CI gate; small common-format credential guard; ignored `.env` and local evaluation outputs. | Advisory coverage is incomplete and point-in-time. Locks lack artifact hashes; build/base-image signing and full secret/history scanning are not implemented. |
| Denial of service / provider billing | Upload/query/top_k/context/candidate/output bounds; connection/statement/provider timeouts; bounded per-process MCP work and benchmark/load budgets. | No tenant quotas, global rate limit, distributed admission, hard total deadline or dollar-based provider budget. Multiple processes can multiply load/cost. |

## Credential configuration and revocation

Generate strong random credentials; do not reuse portfolio examples. `.env` and `.env.*` are ignored, except `.env.example`. Protect local `.env` permissions (`chmod 600 .env`). Use a real secret manager and TLS at deployment. Never put actual keys in repository files, command examples, MCP client JSON or screenshots. `API_KEY` can be an unbound service-only key, but knowledge operations require a tenant binding. Duplicate key bindings are rejected. Database URLs are hidden from settings repr, yet a full settings dump can still expose credentials: do not log configuration objects.

To revoke a known key without publishing the raw key, compute its digest in a trusted shell/tool and store it in JSON `REVOKED_API_KEY_HASHES`. This local snippet reads the existing key from protected configuration, so it does not put the credential in command history:

```sh
.venv/bin/python - <<'PY'
import hashlib
from enterprise_knowledge_engine.core.config import Settings
settings = Settings()
print(hashlib.sha256(settings.api_key.get_secret_value().encode()).hexdigest())
PY
# In your protected .env: REVOKED_API_KEY_HASHES=["<64-character lowercase digest>"]
# Restart every API/MCP worker; rotate/remove the old binding and update trusted clients.
```

Do not rely on a key's hash being secret; weak keys remain vulnerable to offline guessing. There is no administrative revocation endpoint, expiry, per-user identity or granular role management. Rotation requires a coordinated configuration rollout; test both old-key rejection and new-key access before exposing service traffic. MCP's current principal must still match the configured key on each invocation, preventing stale identity after an intentional in-process configuration update. Editing a file alone does not update that object.

## Logging and correlation

HTTP request IDs are server-generated UUIDs returned in `X-Request-ID`; arbitrary caller request IDs are not trusted or reflected. MCP generates its own tool IDs and passes them to QA and worker timing context. HTTP logs include tenant identity after successful authentication. Health/readiness and unauthenticated requests have no authenticated tenant.

JSON events include request/tool identity, duration, known route/tool, status/error category and source count. `retrieval_completed` measures whole search service time; `embedding_generation_completed` measures embedding generation in query and ingestion paths; `embedding_usage` records actual provider-reported tokens. Existing QA events measure retrieval/model time and returned token usage. Missing usage remains absent/null; fake providers do not manufacture tokens. `request_completed` times application processing through response construction, not complete network streaming/transfer. `mcp_tool_completed` includes active-call limiter wait.

Do not enable raw SDK/HTTP access logs or add prompt/document contents to diagnostic events. DEBUG keeps SDK and HTTP payload loggers suppressed. No OpenTelemetry instrumentation/exporter was added; request IDs and structured events serve this local phase. The SDK dependency graph may include the OpenTelemetry API transitively. Metrics collection, tracing propagation across trusted gateways, durable audit trails, log access policies and alerts remain deployment work. A request ID aids correlation, not authorization.

## Reliability policy

- Database connections use pre-ping, bounded pool/overflow, connect/pool waits and a 3-second statement timeout. PostgreSQL 16 + pgvector >=0.8 and **UTF-8 encoding** are required.
- `/health` is liveness without DB/provider access. `/ready` checks DB connectivity, vector extension and migration head. It does not spend tokens or promise that external providers are healthy.
- OpenAI embeddings use `EMBEDDING_MAX_RETRIES` (default 1, range 0–3); chat uses `LLM_MAX_RETRIES` (default 1, range 0–3). The installed SDK supplies exponential backoff with jitter, transient connection/timeouts and 408/409/429/5xx retry policy, honoring provider retry directives. Mock-transport tests exercise ordinary permanent 400/401/403 failures without retries, transient retry behavior, backoff ranges and exhaustion.
- SDK server-directed Retry-After may lengthen wall time (the inspected SDK caps accepted delay at 120 seconds). A request timeout is not a hard total tool deadline. Model/provider package changes can alter policy; keep regression tests passing when updating locks.
- Embedding/chat operations do not execute business actions; chat uses `store=false`. Retrying inference can still duplicate billed work after ambiguous failures. There is no blind retry of ingestion database transactions or other non-idempotent mutations.
- Tenant/content-hash locking detects concurrent duplicates. Savepoints remove partial chunks; failures retain a failed document state, never false readiness. Reprocess/delete behavior and cleanup are integration-tested. This is synchronous ingestion, not a durable job queue.
- Optional reranking uses one bounded attempt, with explicit retrieval-order fallback in the app. The evaluation runner treats failed/no-op requested real reranking as an error rather than reporting fabricated reranker quality.
- HTTP database/provider failures return safe status/error categories; QA provider failure is `status=error`, not an abstention success. MCP provider failure is `isError=true`.
- Engines/sessions, per-operation provider clients, PDF workers, demo processes and temporary fixture tenants are closed in normal/error paths. Abrupt process kills can leave synthetic fixture rows; no claim of crash-proof automatic recovery is made.

## CI and public portfolio review

CI runs Ruff, compatibility checks, the common-format credential guard, pip-audit, dataset validation, unit/metric/security tests, PostgreSQL/pgvector integration tests, migration checks/downgrade-upgrade and Docker build. Network advisory outages can fail the security job; do not silence them or treat a missing scan as clean. Automated tests mock paid APIs. The local guard detects common OpenAI/GitHub/AWS/private-key formats and prints locations only. It deliberately skips protected env files, local results, binary/oversized files and build directories, and is **not** a full credential/history scanner.

Before publication, review repository and Git history, synthetic evaluation artifacts, licenses and configuration examples. No actual credentials belong in this project. Before deployment with business data, add operational secret management, TLS/proxy controls, least-privilege migrations/runtime DB roles, permission/identity review, RLS or independently verified tenant controls, live revocation, rate/admission controls, backup/restore drills, provider retention agreements, incident procedures and real workload/adversarial evaluation. Passing the local suite does not establish production readiness, guaranteed hallucination prevention or enterprise certification.

Provider error codes distinguish final timeout/rate-limit/network failures (`embedding_timeout`, `embedding_rate_limited`, `embedding_unavailable`, corresponding LLM categories) from permanent authorization/request problems (`embedding_not_authorized`, `embedding_request_rejected`, `llm_not_authorized`, `llm_request_rejected`). Operator configuration fixes may be needed even when the application maps an upstream authorization failure to 503; do not blindly retry every 5xx response. Upstream credentials and rejection details are never returned to clients.

## Phase 7 review

The current offline security/unit run passes within 242 total unit tests; the common-format secret guard and ignored-env checks pass. Prior PostgreSQL authorization/read-only/ingestion tests remain documented evidence, but the current database rerun and new unified demo were blocked by approval-review availability. Docker is unavailable. No newly demonstrated serious security defect required a production code change. This review does not replace penetration testing or a deployment assessment.

License declarations are inventoried in [DEPENDENCY_LICENSES.md](DEPENDENCY_LICENSES.md); owner licensing remains pending. All source files remain untracked locally, with no commits/staged files and no configured remote. Review the intended staged snapshot and full imported history with a dedicated secret scanner before publication. No files, credentials, customer data or logs have been pushed. The dependency advisory snapshot is retained from Phase 6, not refreshed here.

Publication verification update: approval review became available and the complete 307-test PostgreSQL suite plus synthetic API/MCP demos passed; Alembic upgrade/check passed. Earlier Phase 7 blocked-attempt notes remain historical. Real-model, deployment and advisory-refresh limitations are unchanged.


## Phase 8 browser boundary

Next.js adds a server-only, allowlisted BFF using one configured tenant-bound API key. The browser receives an HTTP-only signed demo cookie, not backend credentials, and cannot choose a tenant or upstream URL. All writes require the exact configured origin. Actual request-byte limits, strict search/ask schemas, no-store responses, React text rendering and sanitized upstream errors limit specific attack paths. The backend still enforces authentication and SQL ownership for the new aggregate/chunk endpoints. Controlled browser tests verify upload/search/citation behavior, forbidden cross-origin writes, unauthenticated BFF rejection and credential separation; they do not prove real-model security.

This is a shared local demo, not user identity/role management. Protect remote deployment with proper authentication, user-to-tenant authorization, TLS and gateway rate/admission controls. No distributed login limiter, per-session revocation or strict nonce CSP was added. Provider configuration flags are not live connectivity probes. Only reviewed synthetic evaluation artifacts should be mounted into the frontend. See [FRONTEND.md](FRONTEND.md) for the exact security and operating boundaries.
