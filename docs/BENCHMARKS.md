# Benchmark evidence

Retained actual run: 2026-11-08, Python 3.13.9, PostgreSQL 16.11, pgvector 0.8.1. Source: `evaluation/reports/local-keyword/metrics.json`, `comparison.md`, `per_question.jsonl` and `performance.json`. Dataset v1 fingerprint: `42bdb2da2b3e46868b61fad519f8cb66c8e9ce53ea0b363a341be14deb736ba1`. This Phase 7 environment did not rerun database benchmarks.

## Quality

12 synthetic documents, two tenants, 34 questions: 26 positive and eight zero-relevance. Candidate pool 50, chunk size 1500/overlap 200. Document ranking uses first chunk appearance; repeated chunks do not count repeatedly. Positive grades are relevant; graded nDCG uses 2^grade−1. Macro means exclude zero-relevance questions and disclose the denominator; positive-query failures score zero. Precision denominator is K even for short results. Negative outcomes are separate.

| Strategy | State | Recall@5 | MRR@5 | nDCG@5 |
|---|---|---:|---:|---:|
| Keyword | Measured, 26 eligible questions | 0.1667 | 0.1923 | 0.1719 |
| Vector | Pending real embeddings | — | — | — |
| Hybrid RRF | Pending real embeddings | — | — | — |
| Hybrid + real reranker | Pending real provider | — | — | — |

Keyword had zero errors across 34 requests; all eight negatives returned no hits. Precision@5 was 0.0462. The weak baseline exposes conjunctive natural-language query mismatch: it does not establish hybrid improvements. No fake vectors were indexed for this benchmark. Answer/judge quality has no measured denominator and no invented score.

## Latency and cost

The serial keyword service run averaged 1.162 ms, p95 1.291 ms, excluding indexing. Separate real loopback HTTP fixture measurements used 40 requests per scenario at concurrency four: list p95 15.297 ms; keyword p95 11.405 ms; zero failures. Snapshot: 2026-11-08T00:32:23 UTC. These tiny, local, short runs are not production benchmarks, ANN plans, sustained throughput or external-model latency measurements. No warm-up samples were removed.

Keyword used NULL vectors and zero paid model calls. Real embedding indexing, query embeddings, reranking and chat/judge add provider-dependent charges and latency. Logical answer/judge limits and bounded output constrain calls, not total dollar spend; retries can duplicate billed work. No estimated dollar cost is presented as measured cost.

## Reproduce

Use a disposable migrated UTF-8 PostgreSQL 16 + pgvector database and configured ignored `.env`.

```sh
make evaluate-validate
.venv/bin/python -m enterprise_knowledge_engine.evaluation.runner \
  --strategies keyword --output evaluation/results/keyword
.venv/bin/python scripts/demo_performance.py
# Explicit paid execution only after setting real OpenAI/Cohere credentials/providers:
.venv/bin/python -m enterprise_knowledge_engine.evaluation.runner --allow-paid \
  --strategies vector,keyword,hybrid,hybrid_rerank --output evaluation/results/real
```

Set `RERANKER_PROVIDER=cohere` for the last strategy; no-op/failure cannot count as successful real reranking. Add `--answers --max-answer-calls 10` and optionally `--judge-provider openai --max-judge-calls 5` only when explicitly authorizing those paid calls. Keep generated local outputs ignored; publish only reviewed synthetic artifacts. See [full methodology](EVALUATION.md).
