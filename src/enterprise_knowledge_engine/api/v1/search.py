from typing import Annotated

from fastapi import APIRouter, Depends, Request

from enterprise_knowledge_engine.core.security import TenantIdentity
from enterprise_knowledge_engine.db.session import DatabaseSession
from enterprise_knowledge_engine.ingestion.embeddings import (
    EmbeddingProvider,
    get_embedding_provider,
)
from enterprise_knowledge_engine.retrieval.reranking import Reranker, get_reranker
from enterprise_knowledge_engine.retrieval.schemas import SearchRequest, SearchResponse
from enterprise_knowledge_engine.retrieval.service import search

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
def search_documents(
    payload: SearchRequest,
    request: Request,
    tenant_id: TenantIdentity,
    session: DatabaseSession,
    provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    reranker: Annotated[Reranker, Depends(get_reranker)],
) -> SearchResponse:
    return search(session, tenant_id, payload, request.app.state.settings, provider, reranker)
