from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from enterprise_knowledge_engine.api.v1.ask import router as ask_router
from enterprise_knowledge_engine.api.v1.documents import router as documents_router
from enterprise_knowledge_engine.api.v1.search import router as search_router
from enterprise_knowledge_engine.core.security import TenantIdentity, require_api_key

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])


class ServiceInfo(BaseModel):
    name: str
    version: str


@router.get("/info", response_model=ServiceInfo, tags=["service"])
def service_info() -> ServiceInfo:
    return ServiceInfo(name="Enterprise Knowledge Engine", version="0.1.0")


router.include_router(documents_router)

router.include_router(search_router)

router.include_router(ask_router)


class WorkspaceCapabilities(BaseModel):
    embedding_provider: str
    embedding_model: str
    embeddings_configured: bool
    llm_provider: str
    llm_model: str
    llm_configured: bool
    reranking_available: bool
    max_upload_bytes: int
    embedding_dimensions: int
    mcp_transport: str = "stdio"


@router.get("/capabilities", response_model=WorkspaceCapabilities, tags=["service"])
def capabilities(request: Request, tenant_id: TenantIdentity) -> WorkspaceCapabilities:
    config = request.app.state.settings
    return WorkspaceCapabilities(
        embedding_provider=config.embedding_provider,
        embedding_model=config.embedding_model,
        embeddings_configured=config.embedding_provider == "fake" or bool(config.openai_api_key),
        llm_provider=config.llm_provider,
        llm_model=config.llm_model,
        llm_configured=config.llm_provider == "fake" or bool(config.openai_api_key),
        reranking_available=config.reranker_provider == "cohere" and bool(config.cohere_api_key),
        max_upload_bytes=config.max_upload_bytes,
        embedding_dimensions=config.embedding_dimensions,
    )
