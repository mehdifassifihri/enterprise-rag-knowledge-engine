# Final capability audit — Phase 7, 2026-11-08

Historical Phase 7 snapshot. Phase 8 now implements and verifies the frontend; see [Phase 8 verification](verification-phase8.md) for the current UI, additional endpoints and 308-test backend result.

Evidence is scoped: publication verification now passes all 307 PostgreSQL-backed tests and both demo scripts; earlier blocked attempts are retained in FINAL_VERIFICATION. “Verified working” below identifies the executed scope, not deployment readiness. No serious code defect was demonstrated by current offline checks; README length, stale dependency wording and architecture naming were documentation defects corrected here.

| Capability | Status | Evidence / boundary |
|---|---|---|
| src layout, app factory, configuration and DI | Verified working | Imports exercised by 307 current tests; `pyproject.toml` requires Python >=3.12 |
| Health/auth/OpenAPI routing | Verified working | `test_api.py`, search/ask API tests in current unit run; DB readiness covered historically |
| Extraction, validation, normalization, chunking | Verified working | `test_ingestion_units.py`, `test_upload_validation.py`; PDF bounds/malformed files exercised |
| Embedding adapter and failure handling | Verified working | Mocked provider/reliability tests; real OpenAI access not included |
| DB schema, vector dimension and migrations | Verified working | Models/migrations inspected: VECTOR(1536), composite tenant FK, tenant/hash/position indexes, GIN/HNSW; Phase 6 migration upgrade/check/roundtrip report |
| Persisted ingestion, duplicates, reprocessing cleanup | Verified working | Phase 6 real PostgreSQL integration evidence in verification-phase6; current full suite passes |
| Vector, FTS, RRF and ranking provenance | Verified working | Current ranking/query unit tests plus retained PostgreSQL retrieval integration results; controlled vectors do not prove semantic quality |
| Optional Cohere reranking | Implemented but not verified | Adapter, mock validation/fallback tests exist; no paid real-model relevance comparison |
| Structured Q&A and citation identity/quote checks | Verified working | Current parser/context/citation/provider tests; retained DB multi-document/isolation tests |
| Actual model factual support / attack resistance | Partially implemented | Prompt boundaries and deterministic checks exist; real semantic judge/human calibration pending |
| Tenant auth, safe errors and logging | Verified working | Current security regression tests; historical SQL isolation tests all search modes/QA/MCP; no RLS or deployment penetration review |
| MCP stdio/read-only tools | Verified working | Current schema/unit tests; Phase 5/6 official SDK subprocess and PostgreSQL tests in retained reports |
| Evaluation dataset, formulas and CLI validation | Verified working | Current evaluation unit tests and dataset validation; 34-question real keyword report retained |
| Vector/hybrid/rerank quality comparison | Implemented but not verified | Explicit pending strategies, no fake semantic benchmark |
| Content-free timings, IDs, usage when reported | Verified working | Current telemetry/security tests; no exporter/alerting deployment |
| Docker/Compose and remote CI | Implemented but not verified | Files inspected; Docker unavailable, no remote CI run |
| Phase 7 unified demo | Verified working | API/database assertions and official MCP stdio subprocess completed successfully during publication verification |
| Cloud deployment, graph, OCR, durable jobs, frontend | Not implemented | No corresponding services/deployments claimed |
| Production readiness / certification | Not implemented | Operational, workload and security work remains |

Reviewed boundaries include API/core/db/ingestion/documents/retrieval/QA/MCP/evaluation modules, migration history, all test modules, Compose/Docker/CI, locks and retained reports. No LangChain, hidden agent actions or fake fallback to generated success was introduced. Detailed evidence: [current verification](FINAL_VERIFICATION.md), [Phase 6](verification-phase6.md), [security](SECURITY.md).
