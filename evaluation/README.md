# Evaluation artifacts

- `datasets/v1/`: publishable synthetic source documents, graded judgments and 34 questions.
- `reports/local-keyword/`: reviewed, actually executed local PostgreSQL keyword results and HTTP measurements. See `docs/verification-phase6.md` for scope and dates.
- `results/`: ignored local outputs. Do not commit private corpora, provider prompts or answers without review.

Use `make evaluate-validate`, then follow [the evaluation guide](../docs/EVALUATION.md). Semantic/hybrid/reranked and real-answer/judge results remain pending unless those providers have actually been configured and run. No fake-provider quality scores are published.
