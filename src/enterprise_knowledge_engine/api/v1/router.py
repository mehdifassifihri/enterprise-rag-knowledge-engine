from fastapi import APIRouter, Depends
from pydantic import BaseModel

from enterprise_knowledge_engine.api.v1.ask import router as ask_router
from enterprise_knowledge_engine.api.v1.documents import router as documents_router
from enterprise_knowledge_engine.api.v1.search import router as search_router
from enterprise_knowledge_engine.core.security import require_api_key

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
