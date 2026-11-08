# Evaluation and reproducibility

Phase 6 adds a lightweight evaluator over the existing extraction, chunking, ingestion, PostgreSQL search and grounded QA services. No RAGAS/DeepEval dependency is required: the metrics are small enough to verify by hand, and provider-based judgments stay separate from deterministic checks.

## Dataset

[`evaluation/datasets/v1`](../evaluation/datasets/v1) contains 12 synthetic Markdown documents, two tenants and 34 questions with stable IDs, reference answers or expected abstention, categories and graded document relevance. See its README for annotation policy and limitations. There is no real business data. The benchmark fingerprints source bytes and judgments, records configuration/provider versions, and maps generated document UUIDs to labels. Benchmark chunk UUIDs are deterministically derived for stable tie-breaking. This special indexer is an administrative test fixture, not a public ingestion API.

Documents are the evaluation unit: chunks are collapsed by document label at first appearance within the first 50 retrieved chunks. This avoids rewarding a strategy for returning many chunks from the same document. It is not a chunk-level benchmark; larger corpora may require more candidate depth and separate chunk judgments. All strategies use the same corpus/index and normal service candidate limits. The real indexer uses actual embeddings through existing ingestion when semantic evaluation is authorized. Free keyword-only evaluation uses existing extraction/chunking and NULL vectors, never fake semantic embeddings.

Only one benchmark instance per dataset/database should run at once because deterministic chunk IDs are shared across fixture runs. Temporary tenant UUIDs are unique; normal completion/failure deletes only those tenants and disposes the engine. Process kills can leave synthetic fixtures and IDs; use a disposable database or inspect/remove orphaned `Synthetic evaluation` tenants administratively. Do not run administrative fixtures against an unreviewed production database.

## Install and validate

Follow the root setup instructions to configure a strong API key, PostgreSQL 16 + pgvector >=0.8, UTF-8 database and migrations. Docker is optional if a suitable database is installed locally.

```sh
make setup                          # installs pinned requirements-dev.lock, then editable project
make migrate
make evaluate-validate              # 34 questions, fingerprint; no database or paid API needed
make test
RUN_DB_TESTS=1 make test-integration # disposable migrated database only
make lint
make audit                         # common-format secret guard + public dependency advisories
```

`requirements.lock` pins runtime packages; `requirements-dev.lock` pins runtime, test and audit tools across supported platforms/Python versions. CI installs the latter and the project with `--no-deps`, checks dependency compatibility, Ruff, dataset validity, unit and PostgreSQL tests, migrations and Docker build. No paid provider calls are required. Locks pin versions but do not contain artifact hashes; supply-chain verification and build/image signing remain future work. Build backend/base image dependencies are not fully frozen.

To refresh deliberately (requires uv and package-index network access), review changes, audit and rerun all checks:

```sh
uv pip compile pyproject.toml --universal --no-header -o requirements.lock
uv pip compile pyproject.toml --extra dev --extra security --universal --no-header -o requirements-dev.lock
```

## Run retrieval comparisons

Free run, no AI credentials or synthetic embedding substitutes:

```sh
.venv/bin/python -m enterprise_knowledge_engine.evaluation.runner \
  --dataset evaluation/datasets/v1 --output evaluation/results/keyword \
  --ks 1,3,5,10
```

Keyword results are measured against real PostgreSQL full-text search. Vector, hybrid and hybrid-plus-reranker entries remain **pending**, with explicit reasons and no scores. No-op reranking is never presented as a real reranker. The runner does not use fake providers for quality benchmarks, even if local test configuration selects fake embeddings.

To run actual vector/keyword/hybrid comparisons, set `EMBEDDING_PROVIDER=openai` and `OPENAI_API_KEY` in your ignored `.env`, then explicitly authorize costs:

```sh
.venv/bin/python -m enterprise_knowledge_engine.evaluation.runner \
  --allow-paid --ks 1,3,5,10 --output evaluation/results/real-retrieval
```

For the fourth strategy, additionally configure `RERANKER_PROVIDER=cohere`, `COHERE_API_KEY` and the existing reranker model. The runner requires actual reranking to apply; provider fallback/no-op is an evaluation error, not reranked quality. By default it compares every available strategy. `--strategies vector,keyword,hybrid` can narrow the run. Search errors count as empty retrieval and cause nonzero CLI exit; reports retain error categories. Do not compare errored runs as if all strategies completed successfully.

Each run writes:

- `metrics.json`: configuration, versions, fingerprints, status/pending reasons, macro/category metrics, latency and deterministic answer aggregates.
- `metrics.csv`: each available strategy/category/K with metric denominators and errors; `mrr` here is MRR@K.
- `per_question.jsonl`: stable question ID, tenant label, ordered result labels and actual chunk/document metadata/scores, latency, errors, optional answers and judge evidence.
- `comparison.md`: measured retrieval table and unavailable strategy states.

Indexing latency is excluded; query latency includes query embedding/reranking if used. No warm-up is silently removed. Serial strategy order and cache effects can bias timing comparisons; these are not controlled production performance experiments. Real semantic quality, real reranking and live LLM/judge results have **not** been run in this environment. Reviewed free results are under `evaluation/reports/local-keyword`; new outputs default to ignored `evaluation/results` because they can contain prompts/passages/answers.

## Metric definitions and denominator policy

Let R be the set of positively judged authorized document labels, L the ranked list after document deduplication, and g(d) the relevance grade (0 for unjudged). At each K in 1, 3, 5, 10:

| Metric | Definition |
|---|---|
| Recall@K | Number of labels in `L[:K] ∩ R` divided by `|R|` |
| Precision@K | Number of hits divided by **K**, including when fewer than K results exist |
| Reciprocal rank@K | `1/rank` of the first positively judged label within K, or 0 |
| MRR | Macro mean reciprocal rank over the entire returned candidate pool; also report MRR@K at each cutoff |
| nDCG@K | `DCG/IDCG`, using gains `2^g−1` and discounts `log2(rank+1)`; ideal grades sorted descending |
| Hit rate@K | 1 if any relevant label occurs within K, otherwise 0; macro averaged |

Queries with **zero positive relevance** return null for all five cutoff metrics and are excluded from their denominators. They do not receive a perfect score for returning nothing. Overall and category aggregates expose eligible denominators, total queries, zero-relevance counts and errors. Negative queries also report successful-query denominators and how many returned any passages. Returned lexical matches are not automatically enough evidence to answer. An operationally failed negative query is not counted as a successful empty result.

Failed positive-relevance searches count as zeros, preserving the planned denominator rather than hiding outages. Unavailable strategies have no metric aggregates. Closed-world missing judgments count as nonrelevant, so incomplete annotation can underestimate quality. Tenant B has only one document; Precision@10 can never exceed 0.1 for its answerable question. That is a deliberate consequence of the fixed-K definition, not a hidden denominator change. Metrics are deterministic given the same ordered results; changing provider/index/configuration can change those results.

## Answer and judge evaluation

The `Judge` protocol is extensible; the optional real adapter is OpenAI. Existing QA orchestration performs retrieval again, and a recording provider captures the **actual passages supplied on that answer call** for verification. It does not trust a separate search's source IDs. No conversation/history is sent to the judge. Calls without LLM invocation (for example empty retrieval) have no supplied sources.

Deterministic checks report:

- Exact normalized reference-string equality, explicitly not semantic correctness.
- Expected answered/abstention status; provider errors are missing scores, not correct abstentions.
- Citation IDs **and** document/chunk IDs against supplied sources, plus answer markers.
- Supporting quote substring membership, not factual entailment.
- Dataset-defined forbidden canary output for injection questions.

Semantic correctness, faithfulness and citation support quality stay null until assessed by a human or configured judge. The optional judge estimates each on a 0–2 rubric, supplies rationales and verbatim input evidence, and includes available usage. Returned evidence is checked for membership in the minimal input. This still does not establish semantic entailment or impartiality.

```sh
# Set LLM_PROVIDER=openai and OPENAI_API_KEY first. Explicit paid authorization is required.
.venv/bin/python -m enterprise_knowledge_engine.evaluation.runner \
  --allow-paid --answers --max-answer-calls 10 \
  --judge-provider openai --judge-model gpt-4.1-mini --max-judge-calls 5 \
  --output evaluation/results/answer-evaluation
```

The example preserves the existing project's model family; compatibility and quality must be verified against your account. Structured output follows [official OpenAI documentation](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat). Model/JSON validation failures, missing evidence, timeouts and rate limits return explicit missing-score/error states. There is no invented fallback score. Judge input is capped at 16000 characters and includes only question, reference, expected status, generated answer and necessary source IDs/content (cited passages, or available evidence for abstention). Judge metadata omits tenant/document/chunk UUIDs and filenames. Source and answer content remain untrusted data.

The judge has one retry, 20-second request timeout and 1200 output-token limit per logical call. CLI budgets default to ten answer attempts and five judge attempts, with hard maximums 136 and 20. Budgets count logical calls, not SDK retry attempts; provider retries and cached/billed token behavior can add cost. This is not a dollar-denominated budget or a hard end-to-end deadline. Evaluation runs serially; answers go to the first eligible questions in strategy order, so budget-limited answer coverage is not balanced. Use `--strategies` and explicit budgets to control cost and coverage. Embedding index/query calls and reranker calls are also paid when enabled.

`RUBRIC` in `evaluation/answers.py` contains positive, incorrect and abstention calibration examples. Unit tests validate score/evidence/error handling without live calls. These examples are not a completed judge calibration study; human calibration and agreement analysis remain pending. Judge scores can be biased or prompt-injected and must be treated as estimates. Do not use them as automatic proof of security, factual support or customer suitability.

## Lightweight HTTP performance checks

Against a local running API with the configured tenant's key:

```sh
.venv/bin/python -m enterprise_knowledge_engine.evaluation.performance \
  --base-url http://127.0.0.1:8000 --scenarios list,keyword \
  --requests 40 --concurrency 4 --output evaluation/results/performance.json

# Real configured vector/hybrid corpus only; providers can incur costs:
.venv/bin/python -m enterprise_knowledge_engine.evaluation.performance \
  --scenarios vector,hybrid --requests 10 --concurrency 2 --allow-paid
# Answer load is capped at ten requests per run:
.venv/bin/python -m enterprise_knowledge_engine.evaluation.performance \
  --scenarios ask --requests 5 --concurrency 1 --allow-paid

# Self-contained free demo: create corpus, start real loopback Uvicorn, measure and clean up.
make performance-demo
# To capture a deliberately reviewed snapshot instead of ignored local output:
.venv/bin/python scripts/demo_performance.py --output evaluation/reports/local-keyword/performance.json
```

The harness permits loopback HTTP only, 1–500 requests per scenario and concurrency 1–16. It refuses provider scenarios without explicit authorization and disables proxy inheritance/redirect following. Paid authorization does not prove that an existing remote corpus uses real embeddings: prepare and verify that corpus first. The self-contained demo uses NULL vectors and only listing/keyword scenarios; it makes no AI calls.

Reports include request count, concurrency, average latency, P50/P95 (linear interpolation at `(n−1)*p`), failure count/categories, elapsed wall time and total-attempt throughput. Latency includes failed calls, and throughput counts all attempts; HTTP status checks measure transport/API availability, not answer quality. Client queue wait before worker execution is excluded; HTTP/DB pool wait after execution begins is included. Scenarios run sequentially without warm-up removal. The tiny synthetic local dataset and a single process are not representative of production load, concurrency fairness, tenant scale or provider rate limits.
