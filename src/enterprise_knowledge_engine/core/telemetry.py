"""Content-free timing events shared by HTTP, domain services and MCP workers."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter
from typing import Any

trace_context: ContextVar[dict[str, Any] | None] = ContextVar("trace_context", default=None)
logger = logging.getLogger(__name__)


@contextmanager
def measured(event: str, **fields: Any) -> Iterator[None]:
    context = {**(trace_context.get() or {}), **fields}
    token = trace_context.set(context)
    started = perf_counter()
    error = None
    try:
        yield
    except Exception as exc:
        error = getattr(exc, "code", "unexpected_error")
        raise
    finally:
        logger.info(
            event,
            extra={
                **context,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
                "error_category": error,
            },
        )
        trace_context.reset(token)
