# Developer portfolio brief

## Summary (under 100 words)

I built Enterprise Knowledge Engine to make tenant-specific documents searchable and usable as cited answer context. It combines validated ingestion, PostgreSQL vector and full-text retrieval, rank fusion, structured answer validation and a read-only MCP adapter. A synthetic evaluation corpus makes retrieval weaknesses visible rather than hiding them behind successful demos. Current evidence establishes local orchestration and isolation behavior; real-model quality and deployment readiness remain work to verify.

## Problem, architecture and stack

The problem is turning scattered business files into inspectable evidence while respecting tenant ownership. Python/FastAPI exposes ingestion, retrieval and Q&A; PostgreSQL 16/pgvector owns metadata, chunks, vectors and full-text indexes. SQLAlchemy/Alembic, Pydantic, pypdf, OpenAI SDK, official MCP SDK, pytest/Ruff and Docker configuration complete the backend.

## Challenges and decisions

I kept tenant filters in SQL and added composite ownership constraints. Transactional ingestion prevents a partially embedded document appearing ready. Independent lexical/semantic candidates merge with RRF rather than incompatible raw scores. Exact vector search favors predictable recall; optional ANN needs workload measurements. Typed provider interfaces keep tests free and make external failures explicit. Citation checks validate authorized source IDs and verbatim evidence without claiming semantic proof.

## Evaluation and security

The versioned 34-question corpus reports document-level Recall, MRR and graded nDCG. The measured keyword Recall@5 is 0.1667; semantic comparisons remain pending. This revealed the limitations of conjunctive keyword queries for natural-language questions and motivates measuring real embeddings before tuning. Synthetic vectors/scripted answers test plumbing only. Environment-bound keys, tenant predicates, bounded parsing/context and content-free logs reduce specific risks; no RLS, global rate limiting or certification is claimed.

## Lessons and limits

A plausible cited answer is not proof of factual support, and a passing fixture demo is not a relevance benchmark. Explicit abstention/errors, reproducible datasets and exposed score provenance make review more useful. Real-model evaluation, deployment/container execution, durable jobs, operational identity/quotas and backup verification remain pending. No knowledge graph, cloud deployment or prior company experience is implied by this portfolio.
