import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError

from enterprise_knowledge_engine.api.health import router as health_router
from enterprise_knowledge_engine.api.v1.router import router as v1_router
from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.core.errors import ServiceError
from enterprise_knowledge_engine.core.logging import configure_logging
from enterprise_knowledge_engine.core.telemetry import trace_context
from enterprise_knowledge_engine.core.upload_limit import UploadLimitMiddleware
from enterprise_knowledge_engine.db.session import build_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    configure_logging(config.log_level)
    logger = logging.getLogger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = build_engine(config)
        try:
            yield
        finally:
            app.state.engine.dispose()

    app = FastAPI(
        title="Enterprise Knowledge Engine",
        version="0.1.0",
        lifespan=lifespan,
        description="Tenant-scoped ingestion, hybrid retrieval and cited question answering.",
        docs_url="/docs" if config.docs_enabled else None,
        redoc_url="/redoc" if config.docs_enabled else None,
        openapi_url="/openapi.json" if config.docs_enabled else None,
    )
    app.state.settings = config
    app.add_middleware(UploadLimitMiddleware, max_bytes=config.max_upload_bytes)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        # FastAPI's default errors echo rejected inputs, including private questions and headers.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "loc": list(item["loc"][:1]),
                        "type": item["type"],
                        "msg": "Invalid request value",
                    }
                    for item in error.errors()
                ]
            },
        )

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, error: ServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "detail": {
                    "code": error.code,
                    "message": error.message,
                    "document_id": str(error.document_id) if error.document_id else None,
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        logger.warning("database_request_failed")
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "code": "database_unavailable",
                    "message": "Database operation failed",
                    "document_id": None,
                }
            },
        )

    @app.middleware("http")
    async def request_logging(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id
        trace_token = trace_context.set({"request_id": request_id})
        try:
            started = perf_counter()
            try:
                response = await call_next(request)
            except Exception:
                # Do not log exception text: driver errors may contain credentials or SQL data.
                logger.error("unhandled_request_error", extra={"request_id": request_id})
                response = JSONResponse(
                    status_code=500, content={"detail": "Internal server error"}
                )
            route = request.scope.get("route")
            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "tenant_id": str(getattr(request.state, "tenant_id", "unbound")),
                    "method": request.method,
                    "route": getattr(route, "path", "unmatched"),
                    "status_code": response.status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            trace_context.reset(trace_token)

    app.include_router(health_router)
    app.include_router(v1_router)
    return app
