# Reproducible synthetic demonstration

Prerequisites: Python environment (`make setup`), PostgreSQL 16 UTF-8 + pgvector >=0.8, migrated database, valid ignored `.env` (see root README). Use a disposable database: scripts administratively create and remove temporary tenants. No paid key is needed for this demo.

```sh
make migrate
bash demo/demo_requests.sh
```

The first script sends actual multipart/JSON requests through FastAPI TestClient and real PostgreSQL. The second launches a real MCP stdio subprocess and connects with the official SDK. This is an in-process HTTP application test, not a network/deployment benchmark. Every assertion failure exits nonzero. Normal/error cleanup deletes only freshly generated demo tenants; abrupt termination can leave fixtures.

Embedding vectors are deliberately identical and the answer provider selects synthetic `FACT:` lines. This verifies persistence, SQL execution, source plumbing, authorization and protocol behavior; **it does not demonstrate semantic relevance, real model reasoning or prompt-injection resistance**. All business facts are fictional. The MCP script uses the same original fixture documents in `examples/qa`; `sample_documents` copies are checked for consistency by the API script.

For real provider behavior, configure `OPENAI_API_KEY`, `EMBEDDING_PROVIDER=openai`, `LLM_PROVIDER=openai` in ignored `.env`, then explicitly run:

```sh
.venv/bin/python scripts/demo_qa.py --paid-openai
```

This incurs embedding/chat charges and prints synthetic answers for manual review; it makes no deterministic answer assertions. Real reranking and evaluation require separate explicit configuration; see `docs/EVALUATION.md`. Never capture keys or terminal environment dumps. The publication verification executed both scripts successfully. Selected actual synthetic API requests/responses are retained in `verified_output.jsonl`; controlled-provider caveats still apply.
