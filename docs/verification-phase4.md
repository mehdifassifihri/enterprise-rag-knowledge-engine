# Phase 4 verification — 2026-11-07

## Actual repository baseline

Inspected the existing FastAPI factory/router/dependencies, tenant authentication, JSON logging, configuration, document/chunk schema, migrations, ingestion and retrieval providers/services, tests and demonstration patterns. The implemented Phase 3 search service was present and is reused directly. No QA endpoint or LLM answer provider existed before this phase.

Before editing QA code: **105 unit tests passed**, Ruff passed, and the unchanged full PostgreSQL-backed suite passed **140 tests**. `alembic check` reported no drift. The isolated PostgreSQL 16.11/pgvector 0.8.1 environment from earlier phases was restarted under `/tmp`; the installed system database was not modified.

## Files created

- `src/enterprise_knowledge_engine/api/v1/ask.py`
- `src/enterprise_knowledge_engine/qa/__init__.py`
- `src/enterprise_knowledge_engine/qa/errors.py`
- `src/enterprise_knowledge_engine/qa/schemas.py`
- `src/enterprise_knowledge_engine/qa/context.py`
- `src/enterprise_knowledge_engine/qa/prompts.py`
- `src/enterprise_knowledge_engine/qa/citations.py`
- `src/enterprise_knowledge_engine/qa/providers.py`
- `src/enterprise_knowledge_engine/qa/service.py`
- `tests/qa_support.py`
- `tests/test_qa_units.py`
- `tests/test_qa_providers.py`
- `tests/test_qa_database.py`
- `tests/test_ask_api.py`
- `scripts/demo_qa.py`
- `examples/qa/returns.md`
- `examples/qa/portal.md`
- `examples/qa/device-service.md`
- `examples/qa/scenarios.json`
- `docs/verification-phase4.md`

## Files modified

- `src/enterprise_knowledge_engine/api/v1/router.py`: register `/ask` under the existing authenticated v1 router.
- `src/enterprise_knowledge_engine/core/config.py`: validated LLM/retrieval/context settings.
- `src/enterprise_knowledge_engine/core/logging.py`: allowlisted QA metrics and safe identifiers in JSON events.
- `src/enterprise_knowledge_engine/main.py`: expose generated request ID in request state; update API description.
- `.env.example`: provider, budget and evidence-gate settings; no real credentials.
- `Makefile`: `demo-qa` target.
- `README.md`: curl, flow, citation contract, history, abstention, costs, demo and limits.
- `docs/ARCHITECTURE.md`: Phase 4 module boundaries and reliability/security tradeoffs.

No additional dependency or migration was needed. Schema head remains `0003_retrieval`; existing ingestion/search interfaces and authentication were preserved. Docker/Compose and CI already install these dependencies and include all test files.

## Executed commands and results

Local-only disposable database configuration:

```sh
export API_KEY=test-only-api-key-with-at-least-32-characters
export DATABASE_URL=postgresql+psycopg://MEHDI@localhost:55432/eke_test
```

Checks:

```sh
make test
# 167 unit tests passed; integration tests excluded by design
make lint
# Ruff lint and formatting passed
RUN_DB_TESTS=1 .venv/bin/pytest tests/test_qa_database.py -x
# 13 QA integration tests passed
RUN_DB_TESTS=1 .venv/bin/pytest
# 215 passed, no skipped/failed tests
.venv/bin/alembic check
# No new upgrade operations detected
.venv/bin/python scripts/demo_qa.py
# All four fixture scenarios passed; temporary tenant removed
```

Final totals: **167 unit tests + 48 integration tests = 215 passed, 0 failed**. The original 140 tests remain passing. A pre-existing Starlette TestClient/httpx deprecation warning remains and was not suppressed.

During development, the malformed-empty-output case caught a fake-provider bug that treated an empty scripted string like omitted configuration. It was fixed to distinguish empty output from `None`; the empty output is now validated and rejected as an explicit model-output error.

## Verified behavior

- Each generated factual claim requires at least one evidence object; every source ID must belong to the current supplied context.
- Each supporting quote is checked as a verbatim substring of the actual supplied, possibly clipped passage. Quotes outside that prefix are rejected.
- The server assembles answer markers and document/chunk/filename/page metadata. Model-inserted citation markers, unknown IDs, invented quotes, malformed/oversized structured output, missing claims, incomplete output and refusals fail closed with no partial factual answer/citations.
- Multiple claims/documents produce the correct distinct cited chunks and supporting quotes.
- Empty/weak retrieval bypasses the LLM. Model abstention produces no citations. Fixture-reported insufficient/conflicting evidence is preserved.
- All three retrieval modes, with/without reranking, use the authenticated tenant. Integration assertions compare citation IDs/quotes against PostgreSQL rows scoped to that tenant; foreign-tenant content never reaches the fake LLM. Fabricated quotations from another tenant are rejected.
- Questions/history/document text remain JSON user data, not system/tool messages. Prior assistant claims cannot serve as evidence quotes. Injection text is present in the fixture context but is not executed by the backend or used by the scripted demo as a command.
- SDK request-contract tests verify strict JSON schema, configured model, output-token cap, timeout/retry values, `store=false`, no tools and provider-reported token usage. Timeout, rate-limit, connection and generic provider failures have safe categories and no fake-provider substitution.
- Request IDs correlate response/header/log events. Tests verify safe tenant/count/timing events exclude question/source canaries. Missing usage and skipped model timings remain null.

These checks establish source identity, quote provenance, API behavior and isolation. They do **not** establish that a real model's claims are entailed by its quotes or that prompt injection/hallucination is eliminated.

## Four-case demo

The free demo uploads three fictional sample files via the ingestion API under a new temporary tenant, reuses actual Phase 3 retrieval against PostgreSQL, and injects explicitly scripted embeddings/chat fixtures. The fixture selects verbatim `FACT:` lines for known sample questions; the application service contains no policy answer. Token usage is null because the fixture reports none.

| Case | Question type | Observed status | Sources used |
| --- | --- | --- | --- |
| A | Retail returns policy | answered | 1 |
| B | Policy plus separate submission instructions | answered | 2 |
| C | Executive bonus outside the source facts | insufficient_evidence | 0 |
| D | Device servicing fact alongside malicious document instructions | answered | 1 |

Case C abstains despite retrieved vector neighbors. Case D answers from the appointment fact and does not include `INJECTION_CANARY_EXECUTED` or `[S99]`. The fixture is intentionally programmed this way; this is not a real-model injection-resistance evaluation. The optional `--paid-openai` path exists but was not executed.

## Real HTTP request and response

A temporary Uvicorn server on loopback port 58000 used the **same scripted demo providers**, injected through a temporary `/tmp` factory, and a separate temporary tenant. Three sample uploads returned 201. The following real request returned HTTP 200:

```sh
curl --fail-with-body -sS http://127.0.0.1:58000/api/v1/ask \
  -H 'X-API-Key: test-only-api-key-with-at-least-32-characters' \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is the retail returns policy?","top_k":5,"search_mode":"hybrid","rerank":false}'
```

Observed response:

```json
{
  "question": "What is the retail returns policy?",
  "answer": "Retail returns can be requested within 21 calendar days of delivery. [S1]",
  "status": "answered",
  "abstention_reason": null,
  "citations": [
    {
      "source_id": "S1",
      "document_id": "8d75d4e5-07b0-4b2a-b26a-08ae78817d8d",
      "chunk_id": "384a94bb-cd84-408a-8978-2e34a6f0ed84",
      "filename": "returns.md",
      "page": null,
      "chunk_position": 0,
      "start_offset": 0,
      "end_offset": 183,
      "excerpt": "Retail returns can be requested within 21 calendar days of delivery.",
      "supporting_quotes": [
        "Retail returns can be requested within 21 calendar days of delivery."
      ]
    }
  ],
  "retrieval": {
    "mode": "hybrid",
    "top_k": 5,
    "sources_retrieved": 3,
    "sources_supplied": 3,
    "sources_used": 1,
    "context_characters": 1509,
    "reranking_status": "not_requested",
    "warnings": []
  },
  "model": "controlled-qa-demo-v1",
  "usage": null,
  "timings": {"retrieval_ms": 7.29, "model_ms": 0.35},
  "request_id": "4f2199b3-5704-4a2c-ad63-a20115757f29",
  "error": null
}
```

The returned request ID matched `X-Request-ID`. Sample policy text comes from `examples/qa/returns.md`. The demonstration tenant/data and temporary services were cleaned up after verification. Timings describe fixture execution only and are not model-performance benchmarks.

## Remaining limitations / unverified features

- No paid OpenAI/Cohere call was made. Real model availability, strict-schema acceptance, semantic answer quality, refusal behavior and prompt-injection resistance remain unverified externally; SDK behavior was tested with mocks.
- Valid IDs/quotes do not establish entailment, completeness or general contradiction detection. A model can attach a real but irrelevant quote to a wrong claim. Prompt instructions are a mitigation, not a security proof.
- Retrieval quality gates are uncalibrated. Top-k, source caps, clipped prefixes and ANN recall can hide needed or contradictory evidence. There is no labeled grounding evaluation or calibrated confidence score.
- Conversation history is caller-supplied, bounded and untrusted. Retrieval uses only the current question; pronoun resolution/query rewriting and persistent memory are not implemented.
- Character budgets are not exact token budgets. SDK timeout/retry settings are per attempt; there is no end-to-end latency/cost benchmark. Usage excludes embedding/reranking and unreported failed retries.
- Citation metadata represents a retrieval snapshot, not immutable source versions; later reprocessing/deletion can change availability.
- Docker/Compose execution, hosted CI, Python 3.12 and Linux-specific behavior were not executed here; verification used macOS/Python 3.13 and actual PostgreSQL 16/pgvector.
- No MCP, frontend, production-readiness/enterprise-certification claim, or GitHub push was added.
