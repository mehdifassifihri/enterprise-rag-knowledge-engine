from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from enterprise_knowledge_engine.core.security import TenantIdentity
from enterprise_knowledge_engine.db.session import DatabaseSession
from enterprise_knowledge_engine.ingestion.embeddings import (
    EmbeddingProvider,
    get_embedding_provider,
)
from enterprise_knowledge_engine.qa.providers import LLMProvider, get_llm_provider
from enterprise_knowledge_engine.qa.schemas import AskRequest, AskResponse
from enterprise_knowledge_engine.qa.service import answer_question
from enterprise_knowledge_engine.retrieval.reranking import Reranker, get_reranker

router = APIRouter(tags=["question answering"])


@router.post(
    "/ask",
    response_model=AskResponse,
    responses={
        502: {"model": AskResponse, "description": "Invalid or failed provider response"},
        503: {"model": AskResponse, "description": "Dependency unavailable"},
        504: {"model": AskResponse, "description": "Answer provider timeout"},
    },
)
def ask(
    payload: AskRequest,
    request: Request,
    tenant_id: TenantIdentity,
    session: DatabaseSession,
    embeddings: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    reranker: Annotated[Reranker, Depends(get_reranker)],
    llm: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> AskResponse | JSONResponse:
    outcome = answer_question(
        session,
        tenant_id,
        payload,
        request.app.state.settings,
        embeddings,
        reranker,
        llm,
        getattr(request.state, "request_id", None),
    )
    if outcome.http_status != 200:
        return JSONResponse(
            status_code=outcome.http_status, content=outcome.response.model_dump(mode="json")
        )
    return outcome.response
