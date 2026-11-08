# Draft application — AI Engineer, Knowledge & Retrieval Systems

Hi,

I built Enterprise Knowledge Engine as a hands-on example of the ingestion, retrieval and reliability work your product needs. It uses FastAPI and PostgreSQL/pgvector for tenant-scoped document chunks, semantic and full-text candidate retrieval, RRF fusion, optional managed reranking and structured answers with server-validated citation IDs and quotes. I learned that successful citation plumbing and deterministic tests are different from retrieval quality: the measured keyword baseline exposes weak natural-language recall, and real embedding/reranking comparisons are explicitly pending.

Project link: https://github.com/mehdifassifihri/enterprise-rag-knowledge-engine — the implementation was pushed to `main` after explicit owner approval.

The project also exposes five read-only tools through the official MCP SDK and includes a versioned evaluation corpus, ranking metrics, failure handling and tenant-isolation tests. Those boundaries would give us a concrete starting point for discussing your knowledge model, evidence requirements and the experiments that should drive retrieval changes. It does not yet implement knowledge graphs or persistent memory.

I’m interested in working directly with an early-stage founder, owning a focused backend slice and communicating what is measured, what failed and what remains uncertain. I would start by reviewing your corpus and access model, then agree on a small set of retrieval and answer-quality checks before expanding the system.

Availability: [your start date, hours/week and timezone overlap]
Hourly rate: [your expected rate and currency]

Before sending: fill in availability and rate, verify repository visibility, and adjust the first-person wording to your own voice. No proposal has been submitted.
