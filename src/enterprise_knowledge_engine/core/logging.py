import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for name in (
            "tool_name",
            "method",
            "route",
            "status_code",
            "duration_ms",
            "request_id",
            "tenant_id",
            "retrieval_duration_ms",
            "model_duration_ms",
            "sources_count",
            "error_category",
            "answer_status",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "llm_model",
        ):
            if hasattr(record, name):
                payload[name] = getattr(record, name)
        return json.dumps(payload)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Request URLs can contain credentials or user input; use our sanitized access events.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    logging.getLogger("httpcore2").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.CRITICAL)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.CRITICAL)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
