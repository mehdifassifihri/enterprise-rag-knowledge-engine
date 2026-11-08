# Local Model Context Protocol server

Phase 5 adds a read-only adapter over the existing PostgreSQL retrieval and grounded-answer services. It does not add a second search engine, document ingestion interface, agent framework, HTTP route, or persistent conversation memory. No migrations are needed. REST interfaces remain available.

## SDK and transport decision

The dependency is the **official `mcp[cli]==1.30.0` Python SDK**, which provides `mcp.server.fastmcp.FastMCP`. The official SDK 2.3.0 installed during investigation renamed this interface to `MCPServer`; the 1.x maintenance line is pinned deliberately to satisfy this project's FastMCP requirement. Review maintenance/security releases and plan a tested migration before remote deployment.

SDK 1.30 supports stdio, Streamable HTTP and legacy SSE. **This application supports stdio only.** Its entry point uses stdio explicitly; other `run()` transports and HTTP ASGI builders raise errors. There is no FastAPI MCP mount. Stdio stdout contains protocol messages only; structured logs go to stderr.

References: [official SDK](https://github.com/modelcontextprotocol/python-sdk), [v1 SDK documentation](https://py.sdk.modelcontextprotocol.io/v1/), [migration guide](https://py.sdk.modelcontextprotocol.io/migration/), [MCP transport specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports).

## Configure a trusted local client

Follow the root README to install dependencies, start PostgreSQL, migrate, provision a tenant, and ingest documents. From the repository directory:

```sh
make setup
cp .env.example .env  # only for a new installation; preserve an existing .env
chmod 600 .env
```

Generate a strong API key using `.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(40))'` and put it in the ignored `.env` as `API_KEY`. Set `API_KEY_TENANT_ID=11111111-1111-1111-1111-111111111111`. Set `MCP_API_KEY` to that same key. Alternatively choose a key already mapped to a tenant in `TENANT_API_KEYS`. The server uses the **same credential resolver as REST**; it does not accept a separate unverified tenant setting. Missing, invalid, unbound, or unprovisioned credentials prevent startup. Tenant existence is checked again on every call. Restart the process to apply credential changes.

After setting all required database credentials and keys in `.env`:

```sh
make db-up
make migrate
.venv/bin/python -m enterprise_knowledge_engine.provision \
  --id 11111111-1111-1111-1111-111111111111 --name 'Local demo' --slug local-demo
```

`MCP_API_KEY` is not an additional token exchanged with tool callers: it binds the local server process to one principal. Every client controlling that process's stdin can read that tenant's knowledge. Only launch it for trusted local clients under a trusted OS account. A user who can edit the environment/configuration or execute arbitrary local code is outside this isolation boundary. Do not share the process across tenants. Authentication is not authorization to publish an HTTP server.

Run directly for client-managed stdio, or have the client launch it:

```sh
.venv/bin/python -m enterprise_knowledge_engine.mcp --env-file /absolute/path/advanced-rag/.env
# Equivalent from the repository: make mcp
```

Direct invocation waits for JSON-RPC on stdin; it is not an interactive chat shell. Install the project into the exact virtualenv referenced by the client. A generic Claude Desktop configuration is in `examples/mcp/claude_desktop_config.json`. Replace both absolute paths, merge its `mcpServers` entry into your client configuration, and restart the client. It contains no secrets: credentials stay in the protected `.env` or are supplied by a trusted process launcher. Review inherited environment variables too: Pydantic environment variables override `.env` values.

For a paid model, use the existing OpenAI configuration. Fake embeddings only match documents ingested with that fake model, and the default fake LLM always abstains. Never interpret fixture providers as real semantic search or reasoning.

## Tools and contracts

All tools have described JSON input schemas with `additionalProperties: false`. No tool accepts tenant IDs, tenant headers, paths, URLs, SQL, or provider credentials. Unknown fields, invalid UUIDs, blank/control-character queries, out-of-range pagination, coercible string booleans and non-integer limits are rejected. UUIDs are identifiers, not capabilities: another tenant's valid document UUID returns the same `document_not_found` error as an absent UUID.

| Tool | Inputs / defaults | Output |
|---|---|---|
| `search_knowledge` | `query` (1–1000 chars), `mode=hybrid`, `top_k=5` (1–20), `rerank=false` | Existing SearchResponse: ranked results, document/chunk UUIDs, filename, content, page/offsets, score types, component ranks/scores, reranker warnings |
| `ask_knowledge` | `question` (1–1000 chars), `top_k=5` (1–20), `search_mode=hybrid`, `rerank=false` | Existing AskResponse: `answered` or `insufficient_evidence`, answer, verified citation IDs/metadata/excerpts, retrieval summary, optional usage/timings |
| `list_documents` | `limit=10` (1–20), `offset=0` (0–100000) | `{items,limit,offset}` using existing document metadata schema |
| `get_document` | `document_id` UUID | Existing document metadata, status, chunk count and extraction metadata; no embedding vectors |
| `get_document_chunks` | `document_id`, same pagination bounds | `{document_id,filename,limit,offset,items}`; items contain `id`, `position`, `page_number`, offsets, `content`, `truncated` |

Search modes are `vector`, `keyword`, `hybrid`. Vector ordering is cosine distance; normalized similarity is `(1+cosine)/2`, not confidence. Keyword rank is PostgreSQL text-search rank. Hybrid RRF is a sum of reciprocal ranks, never a probability. Optional reranking retains the existing score/provenance contract and fallback warnings. Default no-op reranking does not invent scores.

Chunk pages are ordered by position and UUID; metadata pages by creation time and UUID descending. Offset pagination can shift during concurrent ingestion/deletion. Chunk text is bounded **in SQL** to 2000 characters per item and `truncated` explicitly signals clipping. It does not load whole documents or vectors. Search/QA retain their existing bounded candidate/context budgets. A final `MCP_MAX_OUTPUT_BYTES` budget (default 262144, range 4096–1048576) counts UTF-8 serialized CallToolResult, including duplicated text and structured content, before sending it. JSON-RPC framing is additional. Oversized results fail with `output_too_large`; reduce `top_k` or page size rather than receive silently clipped search evidence.

Success is returned as both MCP `structuredContent` and JSON text content. Operational and argument failures use `isError=true` and a safe `{status:"error",error:{code,message},request_id}` payload. QA provider failures are tool errors, not successful fabricated answers. Empty searches return `results:[]`; insufficient evidence is a successful abstention with no invented citations. Errors never include raw exceptions or connection strings. These shapes are tool payloads, not HTTP envelopes.

## Actual protocol demo

```sh
make demo-mcp
# Or: .venv/bin/python scripts/demo_mcp.py
```

Requires a migrated writable local test/demo database and normal Settings credentials. It creates a temporary tenant, ingests the existing `examples/qa/*.md` through REST ingestion, launches a separate stdio subprocess, initializes an official SDK ClientSession, discovers all five tools, searches hybrid passages, and calls `ask_knowledge` for all four QA scenarios. Finally it closes the client/process and deletes the temporary tenant and documents. It uses explicit scripted providers only and makes no paid calls. Run against a disposable database; interruption/kill can prevent fixture cleanup.

Observed discovery:

```text
search_knowledge, ask_knowledge, list_documents, get_document, get_document_chunks
```

Example MCP tool arguments:

```json
{"name":"search_knowledge","arguments":{"query":"retail returns","mode":"hybrid","top_k":5,"rerank":false}}
```

Observed `ask_knowledge` excerpt from the scripted demo (IDs from one run; omitted fields still exist in the full response):

```json
{
  "question": "What is the retail returns policy?",
  "answer": "Retail returns can be requested within 21 calendar days of delivery. [S1]",
  "status": "answered",
  "citations": [{
    "source_id": "S1",
    "document_id": "a8af779e-0a47-4fa4-9bf1-228d6b29cd52",
    "chunk_id": "f14e87e3-a5eb-417c-8168-062f36b34940",
    "filename": "returns.md",
    "page": null,
    "excerpt": "Retail returns can be requested within 21 calendar days of delivery."
  }]
}
```

The multi-document case cites portal submission instructions and the returns policy. The unsupported question abstains. The malicious fixture's canary does not appear in the scripted answer. This verifies protocol/service plumbing and server-side citation/quote checks, **not** a real model's resistance to prompt injection or factual entailment. Source IDs are scoped to each answer, not global document identifiers.

Optional MCP Inspector (Node/npm and network access needed):

```sh
npx @modelcontextprotocol/inspector \
  /absolute/path/advanced-rag/.venv/bin/python \
  -m enterprise_knowledge_engine.mcp --env-file /absolute/path/advanced-rag/.env
```

Select stdio; use tools/list and tools/call. Inspector UI was not exercised here. Do not publish its proxy or expose local credentials in screenshots. No desktop client installation or user client configuration is modified by this project.

## Lifecycle, reliability and security limits

Each process has a tenant-bound runtime and engine, disposed on shutdown and startup failure. Each tool uses a fresh session. MCP engine connections are transaction-read-only, verified by attempting SQL writes in tests; use a SELECT-only PostgreSQL role as defense in depth. Database role isolation/RLS is not implemented; application SQL predicates remain essential. Retrieval applies both tenant and document predicates in SQL. Other tenants' IDs never become citations.

`MCP_MAX_CONCURRENT_CALLS` defaults to 1 (range 1–4), bounding active synchronous domain work in AnyIO worker threads. Queued protocol requests are not a distributed rate limit. Database connections/statements and embedding, reranker and LLM requests reuse existing timeout/retry budgets. There is no hard end-to-end deadline. Cancellation waits for worker completion and session cleanup rather than abandoning live database work. A large number of local queued calls or multiple processes can still consume resources/provider cost. Configured external providers can receive queries and selected private passages: review consent, retention and billing settings.

Logs contain server-generated request IDs, tenant UUIDs, known tool names, durations and error categories; QA adds existing retrieval/model timing and available token usage. They exclude tool arguments and raw source text. SDK/HTTP verbose payload logging is suppressed even with application DEBUG. These events are operational tracing, not durable or tamper-evident audit logs.

Tool annotations are client hints, not enforcement. Returned passages and filenames are untrusted data: clients must not execute embedded instructions or use them to authorize unrelated tool calls. The existing QA instruction boundary, supplied-source validation and exact-quote checks reduce some failure modes but do not eliminate hallucinations, false entailment, data exfiltration by a compromised client, or malicious document influence.

Before remote deployment: migrate/review the SDK version; build supported Streamable HTTP authentication with per-request principal binding (MCP OAuth/resource-server validation or suitable verified bearer tokens); validate issuer, audience, expiry, scopes and token ownership; validate Origin/Host and DNS rebinding protections; use TLS; reject arbitrary tenant headers; design revocation and permission checks. Define process/worker scaling, bounded admission and rate limits, tenant quotas, tracing propagation, persistent audit policies, access review, secrets management and injection evaluation. None of this is claimed implemented or production-verified by the local stdio demonstration.
