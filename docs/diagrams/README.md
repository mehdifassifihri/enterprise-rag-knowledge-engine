# Backend architecture diagram

- [Editable Excalidraw document](backend-architecture.excalidraw)
- [SVG preview](backend-architecture.svg)
- [PNG preview](backend-architecture.png)

Open [Excalidraw](https://excalidraw.com) and drag the `.excalidraw` file onto the canvas. Boxes, labels and arrows are native editable elements; no remote images or credentials are embedded.

The diagram summarizes the implemented backend: authenticated FastAPI routes, trusted tenant identity, shared ingestion/retrieval/QA services, PostgreSQL with pgvector and full-text search, and provider interfaces for embeddings, chat and optional reranking. Ingestion and QA are separate operations; the three numbered service areas are capabilities, not a mandatory sequence executed on every request. Keyword-only search does not need a query embedding. AI calls occur only when the selected operation needs them.

Solid arrows show request, database and response relationships. The dashed connector denotes external model-provider calls. The single shared-service box deliberately omits internal module and deployment details; local stdio MCP and offline evaluation reuse those services. PostgreSQL authorization uses application SQL predicates, not database RLS. Citation checks establish source/quote membership, not factual entailment or a hallucination-free guarantee.

The PNG is the hand-drawn Excalidraw export supplied from the Desktop and is embedded in the main README. The SVG is the earlier clean vector preview. The `.excalidraw` file is the editable source; its JSON structure and element IDs were checked. Both previews were visually reviewed.
