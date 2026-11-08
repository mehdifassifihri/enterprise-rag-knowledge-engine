import hashlib
import logging
import math
from collections.abc import Iterator, Sequence
from typing import Protocol

from fastapi import Request
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.core.telemetry import trace_context
from enterprise_knowledge_engine.ingestion.errors import IngestionError


class EmbeddingProvider(Protocol):
    model: str
    dimensions: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class FakeEmbeddingProvider:
    model = "fake-sha256-v1"

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            raw = hashlib.shake_256(text.encode()).digest(self.dimensions * 2)
            vector = [
                int.from_bytes(raw[i : i + 2], "big") / 32767.5 - 1 for i in range(0, len(raw), 2)
            ]
            norm = math.sqrt(sum(x * x for x in vector))
            vectors.append([x / norm for x in vector])
        return vectors


def embedding_batches(texts: Sequence[str], batch_size: int) -> Iterator[list[str]]:
    # UTF-8 byte counts conservatively bound BPE tokens, without an extra tokenizer dependency.
    batch: list[str] = []
    byte_count = 0
    for text in texts:
        size = len(text.encode("utf-8"))
        if not text.strip() or size > 8000:
            raise IngestionError("embedding_input_invalid", "Embedding input is empty or too large")
        if batch and (len(batch) >= batch_size or byte_count + size > 250_000):
            yield batch
            batch, byte_count = [], 0
        batch.append(text)
        byte_count += size
    if batch:
        yield batch


class OpenAIEmbeddingProvider:
    def __init__(self, config: Settings) -> None:
        self.model = config.embedding_model
        self.dimensions = config.embedding_dimensions
        self.max_retries = config.embedding_max_retries
        self.batch_size = config.embedding_batch_size
        self.config = config

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        if self.config.openai_api_key is None or not self.config.openai_api_key.get_secret_value():
            raise IngestionError(
                "embedding_not_configured", "Embedding provider is not configured", 503
            )
        client = OpenAI(
            api_key=self.config.openai_api_key.get_secret_value(),
            timeout=self.config.embedding_timeout_seconds,
            max_retries=self.max_retries,
        )
        try:
            for batch in embedding_batches(texts, self.batch_size):
                result = client.embeddings.create(
                    input=list(batch),
                    model=self.model,
                    dimensions=self.dimensions,
                    encoding_format="float",
                )
                usage = getattr(result, "usage", None)
                if usage is not None and type(getattr(usage, "total_tokens", None)) is int:
                    logging.getLogger(__name__).info(
                        "embedding_usage",
                        extra={
                            **(trace_context.get() or {}),
                            "total_tokens": usage.total_tokens,
                            "input_tokens": getattr(usage, "prompt_tokens", None),
                        },
                    )
                items = sorted(result.data, key=lambda item: item.index)
                if [item.index for item in items] != list(range(len(batch))):
                    raise IngestionError(
                        "embedding_invalid_response", "Invalid embedding response", 502
                    )
                vectors.extend(item.embedding for item in items)
        except APITimeoutError:
            raise IngestionError("embedding_timeout", "Embedding provider timed out", 504) from None
        except RateLimitError:
            raise IngestionError(
                "embedding_rate_limited", "Embedding provider is rate limited", 503
            ) from None
        except APIConnectionError:
            raise IngestionError(
                "embedding_unavailable", "Embedding provider is unavailable", 503
            ) from None
        except (AuthenticationError, PermissionDeniedError):
            raise IngestionError(
                "embedding_not_authorized", "Embedding provider authorization failed", 503
            ) from None
        except BadRequestError:
            raise IngestionError(
                "embedding_request_rejected", "Embedding provider rejected the request", 502
            ) from None
        except OpenAIError:
            raise IngestionError(
                "embedding_unavailable", "Embedding provider request failed", 502
            ) from None
        finally:
            client.close()
        return vectors


def validate_vectors(vectors: list[list[float]], count: int, dimensions: int) -> None:
    if len(vectors) != count or any(
        len(v) != dimensions
        or not any(x != 0 for x in v)
        or any(not math.isfinite(x) or abs(x) > 3.4e38 for x in v)
        for v in vectors
    ):
        raise IngestionError("embedding_invalid_response", "Invalid embedding response", 502)


def get_embedding_provider(request: Request) -> EmbeddingProvider:
    return build_embedding_provider(request.app.state.settings)


def build_embedding_provider(config: Settings) -> EmbeddingProvider:
    if config.embedding_provider == "fake":
        return FakeEmbeddingProvider(config.embedding_dimensions)
    return OpenAIEmbeddingProvider(config)
