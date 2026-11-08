from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.core.errors import ServiceError
from enterprise_knowledge_engine.core.security import authenticate_api_key
from enterprise_knowledge_engine.db.models import DocumentChunk, Tenant
from enterprise_knowledge_engine.db.session import build_engine
from enterprise_knowledge_engine.documents.schemas import DocumentResponse
from enterprise_knowledge_engine.documents.service import read_documents
from enterprise_knowledge_engine.ingestion.embeddings import build_embedding_provider
from enterprise_knowledge_engine.ingestion.service import find_document
from enterprise_knowledge_engine.qa.providers import build_llm_provider
from enterprise_knowledge_engine.qa.schemas import AskRequest
from enterprise_knowledge_engine.qa.service import answer_question
from enterprise_knowledge_engine.retrieval.reranking import build_reranker
from enterprise_knowledge_engine.retrieval.schemas import SearchRequest
from enterprise_knowledge_engine.retrieval.service import search


class KnowledgeRuntime:
    def __init__(self, config: Settings, engine: Engine, tenant_id: UUID) -> None:
        self.config, self.engine, self.tenant_id = config, engine, tenant_id
        self.embeddings = build_embedding_provider(config)
        self.reranker = build_reranker(config)
        self.llm = build_llm_provider(config)

    def invoke(self, name: str, args: dict[str, Any], request_id: str) -> dict[str, Any]:
        key = self.config.mcp_api_key
        principal = authenticate_api_key(self.config, key.get_secret_value() if key else None)
        if principal is None or principal.tenant_id != self.tenant_id:
            raise ServiceError(
                "credential_unavailable", "MCP credential is no longer authorized", 403
            )
        with Session(self.engine) as session:
            if session.get(Tenant, self.tenant_id) is None:
                raise ServiceError("tenant_unavailable", "Tenant is unavailable", 403)
            session.rollback()  # Retrieval owns its transaction and snapshot.
            if name == "search_knowledge":
                return search(
                    session,
                    self.tenant_id,
                    SearchRequest(**args),
                    self.config,
                    self.embeddings,
                    self.reranker,
                ).model_dump(mode="json")
            if name == "ask_knowledge":
                outcome = answer_question(
                    session,
                    self.tenant_id,
                    AskRequest(**args),
                    self.config,
                    self.embeddings,
                    self.reranker,
                    self.llm,
                    request_id,
                )
                if outcome.response.status == "error":
                    error = outcome.response.error
                    raise ServiceError(error.code, error.message, outcome.http_status)
                return outcome.response.model_dump(mode="json")
            if name == "list_documents":
                return read_documents(session, self.tenant_id, **args).model_dump(mode="json")
            doc = find_document(session, self.tenant_id, args["document_id"])
            if name == "get_document":
                return DocumentResponse.model_validate(doc).model_dump(mode="json")
            if name != "get_document_chunks":
                raise ServiceError("unknown_tool", "Unknown tool")
            rows = session.execute(
                select(
                    DocumentChunk.id,
                    DocumentChunk.position,
                    DocumentChunk.page_number,
                    DocumentChunk.start_offset,
                    DocumentChunk.end_offset,
                    func.substr(DocumentChunk.content, 1, 2000).label("content"),
                    (func.length(DocumentChunk.content) > 2000).label("truncated"),
                )
                .where(
                    DocumentChunk.tenant_id == self.tenant_id, DocumentChunk.document_id == doc.id
                )
                .order_by(DocumentChunk.position, DocumentChunk.id)
                .limit(args["limit"])
                .offset(args["offset"])
            ).all()
            return {
                "document_id": str(doc.id),
                "filename": doc.filename,
                "limit": args["limit"],
                "offset": args["offset"],
                "items": [{**dict(row._mapping), "id": str(row.id)} for row in rows],
            }


@contextmanager
def open_runtime(config: Settings) -> Iterator[KnowledgeRuntime]:
    key = config.mcp_api_key
    principal = authenticate_api_key(config, key.get_secret_value() if key else None)
    if principal is None or principal.tenant_id is None:
        raise ValueError("MCP requires a valid tenant-bound MCP_API_KEY")
    engine = build_engine(config)
    engine.update_execution_options(postgresql_readonly=True)
    try:
        with Session(engine) as session:
            if session.get(Tenant, principal.tenant_id) is None:
                raise ValueError("MCP tenant must be provisioned")
        yield KnowledgeRuntime(config, engine, principal.tenant_id)
    finally:
        engine.dispose()
