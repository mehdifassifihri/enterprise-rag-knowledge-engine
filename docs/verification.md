# Phase 2 verification — 2026-11-07

## Phase 1 baseline review

Reviewed the application factory, environment configuration, structured logging, bootstrap authentication, tenant/document/chunk models, initial migration, readiness probe, Docker/Compose configuration, CI and existing tests. Before implementation, `make test` passed 15 tests and `make lint` passed. The Phase 1 API key had no tenant binding; document APIs were blocked until this was extended with server-configured tenant principals.

## Verified locally

Environment: macOS arm64, Python 3.13.9, PostgreSQL 16.11 and pgvector 0.8.1. PostgreSQL and pgvector were built into an isolated `/tmp` prefix because Docker was unavailable; the existing PostgreSQL 14 installation was not changed. The temporary server used a disposable database on loopback port 55432.

- `make test`: **58 passed**, 9 integration tests excluded by design.
- `make lint`: Ruff lint and formatting checks passed.
- Full `RUN_DB_TESTS=1 .venv/bin/pytest`: **67 passed**, no skipped or failed tests.
- `alembic upgrade head`: passed against real PostgreSQL with pgvector.
- `alembic check`: no model/migration drift.
- `alembic downgrade base` followed by `alembic upgrade head`: passed on the disposable database.
- Phase 1 cross-tenant foreign-key and cascade tests passed against the actual database.
- Phase 2 persistence, independent tenant duplicates, cross-tenant GET/DELETE hiding, list scoping, failed replacement cleanup, retry with stable ID, invalid-vector rejection, PDF page provenance and concurrent duplicate tests passed.
- Unit tests verify size limits, chunked request limits, invalid content, UTF-8 decoding, extraction/page/time limits, encrypted and textless PDFs, chunk coverage and offsets, deterministic fake vectors, SDK batching/reordering, safe provider failure messages and configuration constraints.

A single dependency deprecation warning remains: the installed Starlette version deprecates its httpx TestClient transport in favor of httpx2. Tests pass with the declared httpx dependency. No warning was suppressed.

## Live HTTP ingestion demonstration

Ran Uvicorn on `127.0.0.1:58000` with `EMBEDDING_PROVIDER=fake`, provisioned the sample tenant, and ran:

```sh
.venv/bin/python scripts/demo_ingestion.py --base-url http://127.0.0.1:58000
```

The script makes a real multipart `POST /api/v1/documents/upload` with the server-configured API key and `examples/handbook.md`. It verifies GET/list behavior and queries PostgreSQL directly. Observed response fields:

```json
{
  "id": "7650f22b-7486-483e-a9f7-87e6abf16106",
  "filename": "handbook.md",
  "size_bytes": 1893,
  "content_hash": "2a57a5bfa7195bfe8751daf1c8a80b2a671f9c2b7a652b21015aa0bd0d73bcda",
  "status": "ready",
  "chunk_count": 2,
  "embedding_model": "fake-sha256-v1",
  "embedding_dimensions": 1536,
  "error_code": null
}
```

The upload returned **201**, the duplicate upload returned **409 duplicate_document**, and the direct PostgreSQL query verified **2 persisted VECTOR(1536) chunks**. This confirms the HTTP/extraction/chunking/vector-persistence path with a deterministic provider; it is not evidence of OpenAI connectivity or semantic quality. Temporary verification services were stopped after use.

## File inventory

New files:

- `src/enterprise_knowledge_engine/ingestion/__init__.py`
- `src/enterprise_knowledge_engine/ingestion/errors.py`
- `src/enterprise_knowledge_engine/ingestion/extraction.py`
- `src/enterprise_knowledge_engine/ingestion/pdf_worker.py`
- `src/enterprise_knowledge_engine/ingestion/chunking.py`
- `src/enterprise_knowledge_engine/ingestion/embeddings.py`
- `src/enterprise_knowledge_engine/ingestion/service.py`
- `src/enterprise_knowledge_engine/api/v1/documents.py`
- `src/enterprise_knowledge_engine/core/upload_limit.py`
- `src/enterprise_knowledge_engine/provision.py`
- `migrations/versions/0002_ingestion.py`
- `tests/test_ingestion_units.py`
- `tests/test_upload_validation.py`
- `tests/test_ingestion_database.py`
- `examples/handbook.md`
- `scripts/demo_ingestion.py`
- `docs/verification.md`

Modified files:

- `pyproject.toml`: ingestion dependencies.
- `.env.example`: tenant bindings, provider and ingestion limits; placeholders only.
- `Makefile`: reproducible demo target.
- `README.md`, `docs/ARCHITECTURE.md`: Phase 2 setup, API, architecture and limitations.
- `src/enterprise_knowledge_engine/main.py`: request limit and safe ingestion/database error responses.
- `src/enterprise_knowledge_engine/core/config.py`: validated tenant/ingestion/provider settings.
- `src/enterprise_knowledge_engine/core/security.py`: tenant-bound principals.
- `src/enterprise_knowledge_engine/core/logging.py`: suppress SDK/driver debug data.
- `src/enterprise_knowledge_engine/db/models.py`: ingestion state, metadata and vectors.
- `src/enterprise_knowledge_engine/api/v1/router.py`: document routes.
- `src/enterprise_knowledge_engine/api/health.py`: current migration revision.
- `tests/test_api.py`: updated readiness revision.
- `tests/test_database.py`: scope cascade assertion to its own tenant.

The existing Dockerfile, Compose and CI already install the package dependencies, run migrations and execute opted-in database tests; they did not need structural changes for this phase.

## Unverified and remaining limits

- Docker image build, Compose startup and the GitHub-hosted CI workflow were not executed locally because Docker is unavailable. YAML syntax was checked; equivalent real PostgreSQL checks passed locally.
- Paid OpenAI requests were not made. The SDK adapter was exercised with mocks; service tests use deterministic fake vectors.
- Python 3.12 and Linux-specific PDF resource-limit behavior remain CI/container checks; local execution used Python 3.13 on macOS.
- OCR is absent; image-only PDFs are rejected. PDF tables/layout may extract imperfectly. Source reprocessing requires re-upload.
- Vector dimension changes require a reviewed schema migration, matching configuration and full re-embedding. Ingestion is synchronous and needs concurrency/rate controls before high-volume deployment.
- No RAG answering, retrieval, MCP or frontend was added. No production-readiness claim or GitHub push was made.
