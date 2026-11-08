# 90-second Loom script

Record only after executing `bash demo/demo_requests.sh` successfully on a disposable migrated database. The unified API/MCP demo completed successfully during publication verification. Do not display an unexecuted script as a successful run. Keep keys, `.env` and private data off-screen.

**0–15 seconds — README/architecture:** “Company knowledge is useful when we can find the right passages and show where an answer came from. I built this backend around PostgreSQL, with tenant-owned documents, vector search and full-text search feeding the same answer service.”

**15–35 seconds — run demo:** “These are synthetic documents. This free walkthrough uses controlled embeddings and scripted answer fixtures, so it demonstrates API, database and citation plumbing rather than real-model relevance. Upload responses show ready documents and persisted chunk counts; a duplicate is rejected.”

**35–55 seconds — search/Q&A output:** “Here are keyword, vector and hybrid requests. Hybrid merges independent ranks using RRF. This supported question returns source IDs and excerpts; the multi-document example cites both sources. An unsupported question abstains. The server checks source identity and exact quotes, although that alone does not prove a claim is supported.”

**55–70 seconds — isolation/MCP:** “The second credential cannot access the first tenant's documents. The official MCP client connects to a local subprocess and invokes the same read-only knowledge services.”

**70–90 seconds — benchmark/report:** “The measured keyword baseline has Recall@5 of 0.1667 over 26 positive questions, showing room for improvement. Real semantic and reranking comparisons are pending. I would use these measurements and failure cases to guide the next retrieval experiment, alongside deployment and security verification for a business workload.”
