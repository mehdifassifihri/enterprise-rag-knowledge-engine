# Synthetic retrieval comparison

Dataset SHA-256: `42bdb2da2b3e46868b61fad519f8cb66c8e9ce53ea0b363a341be14deb736ba1`

No fake embeddings. Pending strategies have no scores. Errors count as empty retrieval.

| Strategy | State | K | Recall | Precision | MRR@K | nDCG | Hit rate |
|---|---|---|---|---|---|---|---|
| vector | pending: real embeddings or explicit paid authorization unavailable | — | — | — | — | — | — |
| keyword | completed | 1 | 0.1474 | 0.1923 | 0.1923 | 0.1923 | 0.1923 |
| keyword | completed | 3 | 0.1667 | 0.0769 | 0.1923 | 0.1719 | 0.1923 |
| keyword | completed | 5 | 0.1667 | 0.0462 | 0.1923 | 0.1719 | 0.1923 |
| keyword | completed | 10 | 0.1667 | 0.0231 | 0.1923 | 0.1719 | 0.1923 |
| hybrid | pending: real embeddings or explicit paid authorization unavailable | — | — | — | — | — | — |
| hybrid_rerank | pending: real embeddings or explicit paid authorization unavailable | — | — | — | — | — | — |

Latency is per serial service call including query embedding/reranking where applicable;
Indexing excluded. This tiny corpus does not establish production performance.
Documents deduplicated by first appearance within the first 50 retrieved chunks.
