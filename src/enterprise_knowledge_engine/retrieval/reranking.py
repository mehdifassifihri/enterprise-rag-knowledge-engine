import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import httpx
from fastapi import Request

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.retrieval.errors import RetrievalError


@dataclass(frozen=True)
class RerankItem:
    index: int
    score: float | None


class Reranker(Protocol):
    model: str | None

    def rerank(self, query: str, documents: Sequence[str]) -> list[RerankItem]: ...


class NoopReranker:
    model = None

    def rerank(self, query: str, documents: Sequence[str]) -> list[RerankItem]:
        return [RerankItem(i, None) for i in range(len(documents))]


class CohereReranker:
    def __init__(self, config: Settings) -> None:
        self.config = config
        self.model = config.reranker_model

    def rerank(self, query: str, documents: Sequence[str]) -> list[RerankItem]:
        if not documents:
            return []
        if len(documents) > self.config.reranker_max_candidates:
            raise RetrievalError("reranker_limit", "Reranking candidate limit exceeded", 502)
        key = self.config.cohere_api_key
        if key is None or not key.get_secret_value():
            raise RetrievalError(
                "reranker_not_configured", "Reranker credential is not configured", 503
            )
        try:
            # One bounded request; only same-tenant candidates leave the service.
            with httpx.Client(timeout=self.config.reranker_timeout_seconds) as client:
                response = client.post(
                    "https://api.cohere.com/v2/rerank",
                    headers={"Authorization": f"Bearer {key.get_secret_value()}"},
                    json={
                        "model": self.model,
                        "query": query,
                        "documents": [doc[:2000] for doc in documents],
                        "top_n": len(documents),
                        "max_tokens_per_doc": 2048,
                    },
                )
                response.raise_for_status()
                payload = response.json()
            result = [
                RerankItem(item["index"], item["relevance_score"]) for item in payload["results"]
            ]
            validate_reranking(result, len(documents))
            return result
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise RetrievalError("reranker_unavailable", "Reranker request failed", 502) from None


def validate_reranking(items: list[RerankItem], count: int) -> None:
    if len(items) != count or any(type(item.index) is not int for item in items):
        raise ValueError("Invalid reranking indices")
    if sorted(item.index for item in items) != list(range(count)):
        raise ValueError("Reranker must return each candidate exactly once")
    if any(
        item.score is None
        or isinstance(item.score, bool)
        or not math.isfinite(item.score)
        or not 0 <= item.score <= 1
        for item in items
    ):
        raise ValueError("Invalid reranking scores")


def get_reranker(request: Request) -> Reranker:
    return build_reranker(request.app.state.settings)


def build_reranker(config: Settings) -> Reranker:
    if config.reranker_provider == "cohere":
        return CohereReranker(config)
    return NoopReranker()
