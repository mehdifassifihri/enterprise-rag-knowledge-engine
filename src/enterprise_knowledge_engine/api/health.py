import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from enterprise_knowledge_engine.db.session import DatabaseSession

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse, responses={503: {"description": "Not ready"}})
def ready(session: DatabaseSession) -> HealthResponse:
    try:
        session.execute(text("SELECT 1"))
        extension = session.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        revision = session.scalar(text("SELECT version_num FROM alembic_version"))
        if extension != 1 or revision != "0003_retrieval":
            raise HTTPException(status_code=503, detail="Service not ready")
    except SQLAlchemyError:
        logger.warning("database_readiness_failed")
        raise HTTPException(status_code=503, detail="Service not ready") from None
    return HealthResponse(status="ready")
