# Phase 3 verification — 2026-11-07

## Review and baseline

Inspected the actual src package, models, both existing migrations, ingestion services, API routes, tenant authentication, settings, logging, tests, Docker/Compose and CI. Before changes, `make test` passed **58 unit tests** and Ruff passed. The repository did not contain search routes, full-text columns or retrieval indexes. Embeddings were already `VECTOR(1536)`, with document provider/model metadata and tenant-prefix indexes.

The existing temporary PostgreSQL 16 environment from Phase 2 was reused, without modifying the system PostgreSQL installation. SQL inspection confirmed **PostgreSQL 16.11**, **pgvector 0.8.1**, `vector(1536)`, the document tenant/created index and composite tenant/document unique indexes. Search indexes were added by the new migration.

Minimal shared changes: reject zero embedding vectors because cosine distance is undefined; make httpx a runtime dependency for managed reranking; extract a common safe service-error base while preserving the existing ingestion error envelope; advance readiness to the new migration.

## Executed checks

The disposable database used this local-only test configuration, with no paid credentials:

```sh
export API_KEY=test-only-api-key-with-at-least-32-characters
export DATABASE_URL=postgresql+psycopg://MEHDI@localhost:55432/eke_test
```

Commands and final results:

```sh
make test
# 105 passed; 35 database tests intentionally excluded
make lint
# Ruff lint and formatting passed
RUN_DB_TESTS=1 .venv/bin/pytest tests/test_retrieval_database.py -x
# 26 passed
RUN_DB_TESTS=1 .venv/bin/pytest
# 140 passed; no skipped/failed tests
.venv/bin/alembic upgrade head
.venv/bin/alembic check
# No new upgrade operations detected
.venv/bin/alembic downgrade 0002_ingestion
.venv/bin/alembic upgrade head
.venv/bin/alembic check
# Rollback/upgrade passed; no model drift
.venv/bin/python scripts/demo_search.py
# Four uploaded documents; twelve successful searches; temporary demo tenant removed
```

Final test totals: **105 unit tests + 35 integration tests = 140 passed, 0 failed**. Existing ingestion/database tests continue to pass. There is one existing Starlette TestClient/httpx deprecation warning; it was not suppressed.

The first background database baseline run overlapped the readiness-revision edit and produced one transient mocked-readiness mismatch (66 passed, 1 failed). Rerunning after the edits and applying the migration resolved it; the final complete suite above has no failures. The isolated pre-change unit baseline was unaffected.

Database checks cover real cosine distances and ordering, English stemming, phrases, identifier discrimination, generated-column updates, installed index definitions, RRF evidence, empty tenants, hostile query text, failed-document exclusion, provider/model compatibility and zero-vector exclusion. Tenant isolation is exercised across vector/keyword/hybrid, exact/HNSW strategy, and with/without a fake scored reranker; the fake reranker never receives another tenant's content.

Unit checks cover ranking ties, RRF arithmetic and duplicate suppression, source-score semantics, bounded/parameterized SQL, strict input bounds, caller tenant rejection, embedding failures, no-op reranking, real adapter request contract, managed timeout sanitization, invalid reranker indices/scores, fallback, and candidate cost caps. No automated test makes a paid request.

## Migration and schema

`0003_retrieval`:

- Requires pgvector >=0.8.0 for the optional iterative HNSW path.
- Adds stored generated `search_english` and `search_simple` tsvectors on chunk content.
- Adds GIN indexes `ix_chunks_fts_english` and `ix_chunks_fts_simple`.
- Adds `ix_chunks_embedding_hnsw` with `vector_cosine_ops` over `VECTOR(1536)`.
- Retains existing tenant indexes/foreign keys and all document/chunk data on downgrade to Phase 2.

Live SQL confirmed all three search indexes, matching vector dimensions, and generated vectors for the two pre-existing handbook chunks after rollback/upgrade. `alembic check` confirmed model/migration agreement. The migration builds indexes transactionally and can lock writes; large-data rollout behavior was not benchmarked.

## Demonstrations

The default comparison script runs FastAPI requests in-process against real PostgreSQL. It uploads the four small documents in `examples/search` using a fresh temporary tenant, substitutes explicitly labeled controlled synthetic embeddings, compares vector/keyword/hybrid for four scenarios, then deletes its tenant. This exercises actual ingestion, persistence, full-text matching, database distance ranking, fusion and API serialization. It is a **mechanics demonstration, not a semantic-quality benchmark**.

Observed examples:

| Query | Vector first | Keyword first | Hybrid first |
| --- | --- | --- | --- |
| refund policy | refunds.md | qx9000.md | qx9000.md |
| QX-9000 | refunds.md | qx9000.md | qx9000.md |
| money back | refunds.md | refunds.md | refunds.md |
| subscription cancellation | billing.md | billing.md | billing.md |

For `refund policy`, qx9000.md had vector rank 2 and keyword rank 1; RRF was `1/62 + 1/61 = 0.03252247488101534`. For the exact identifier, full-text retrieval distinguished QX-9000 from QX-9001. These intentionally controlled vectors illustrate the source-combination behavior, not actual OpenAI similarity.

Also started a real Uvicorn HTTP server on loopback port 58000 with the existing handbook tenant and fake SHAKE embeddings, then executed:

```sh
curl --fail-with-body -sS http://127.0.0.1:58000/api/v1/search \
  -H 'X-API-Key: test-only-api-key-with-at-least-32-characters' \
  -H 'Content-Type: application/json' \
  -d '{"query":"tenant","mode":"hybrid","top_k":2,"rerank":false}'
```

It returned HTTP 200 with two handbook chunks, `score_type=rrf`, `vector_strategy=exact` and no warnings. The first chunk had vector/keyword rank 1 and score `0.03278688524590164`; the second had vector rank 2 only and score `0.016129032258064516`. No relevance claim is made for fake SHAKE vectors. The temporary API and database were stopped after verification.

## File inventory

New:

- `src/enterprise_knowledge_engine/core/errors.py`
- `src/enterprise_knowledge_engine/api/v1/search.py`
- `src/enterprise_knowledge_engine/retrieval/__init__.py`
- `src/enterprise_knowledge_engine/retrieval/errors.py`
- `src/enterprise_knowledge_engine/retrieval/schemas.py`
- `src/enterprise_knowledge_engine/retrieval/ranking.py`
- `src/enterprise_knowledge_engine/retrieval/repository.py`
- `src/enterprise_knowledge_engine/retrieval/reranking.py`
- `src/enterprise_knowledge_engine/retrieval/service.py`
- `migrations/versions/0003_retrieval.py`
- `tests/test_retrieval_units.py`
- `tests/test_retrieval_database.py`
- `tests/test_search_api.py`
- `tests/test_reranking.py`
- `scripts/demo_search.py`
- `examples/search/refunds.md`
- `examples/search/qx9000.md`
- `examples/search/qx9001.md`
- `examples/search/billing.md`
- `examples/search/scenarios.json`
- `docs/verification-phase3.md`

Changed:

- `pyproject.toml`: move httpx into runtime dependencies.
- `src/enterprise_knowledge_engine/core/config.py`: candidate limits, RRF, ANN and reranker settings.
- `src/enterprise_knowledge_engine/db/models.py`: generated full-text vectors and search indexes.
- `src/enterprise_knowledge_engine/ingestion/embeddings.py`: reject zero vectors.
- `src/enterprise_knowledge_engine/ingestion/errors.py`: retain ingestion errors over shared service base.
- `src/enterprise_knowledge_engine/main.py`: common safe error handler and accurate API description.
- `src/enterprise_knowledge_engine/api/v1/router.py`: mount search endpoint.
- `src/enterprise_knowledge_engine/api/health.py`, `tests/test_api.py`: current readiness revision.
- `Makefile`: demo-search target.
- `.env.example`: retrieval/reranker options, no real secrets.
- `README.md`, `docs/ARCHITECTURE.md`: API, configuration, scoring, comparisons, performance and limits.

Existing authentication semantics, Docker/Compose and CI structure were preserved. CI already opts into all database tests and checks migrations, so new tests are included automatically.

## Limitations and unverified behavior

- No live paid OpenAI or Cohere requests were made. Managed adapter serialization and failure behavior use mocks; real provider availability, credentials and relevance quality remain unverified.
- Synthetic/fake vectors prove mechanics and isolation, not semantic accuracy. No labeled evaluation corpus, calibrated threshold or quality/latency benchmark is claimed.
- No large-data query-plan benchmarking was performed. Index existence, SQL structure and functionality were verified; PostgreSQL may choose sequential scans on tiny datasets. Exact mode scans eligible tenant vectors in SQL. ANN has recall/boundary-tie limits, even when a full pool is returned; exact underfill fallback does not repair all recall loss.
- HNSW shares a graph across tenants/models, so recall/performance can depend on other data even though all access filters remain in SQL. Tenant partitioning is not implemented.
- English/simple tokenization is not arbitrary substring matching or guaranteed punctuation-exact identifier lookup. Multi-language stemming, query expansion, typo correction and full exact-ID fields are absent.
- The API exposes top-k retrieval without deep pagination. Candidate caps can omit relevant items beyond the pools. Overlapping chunks are not deduplicated by meaning/document.
- Docker build, Compose execution, hosted GitHub Actions, Python 3.12 and Linux-specific behavior were not executed in this macOS/Python 3.13 session.
- No LLM answering, MCP, frontend, GitHub push or production-readiness claim was added.
