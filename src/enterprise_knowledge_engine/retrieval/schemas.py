import re
import unicodedata
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

SearchMode = Literal["vector", "keyword", "hybrid"]
ScoreType = Literal["normalized_cosine", "keyword_rank", "rrf", "reranker_relevance"]


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=1000)
    mode: SearchMode = "hybrid"
    top_k: int = Field(default=5, ge=1, le=50, strict=True)
    rerank: StrictBool = False

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if any(unicodedata.category(c) == "Cc" and c not in "\n\r\t" for c in value):
            raise ValueError("Control characters are not allowed")
        value = unicodedata.normalize("NFC", re.sub(r"\s+", " ", value).strip())
        if not value:
            raise ValueError("Query must not be blank")
        return value


class SearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    filename: str | None
    content: str
    page: int | None
    chunk_position: int
    start_offset: int | None
    end_offset: int | None
    rank: int
    score: float = Field(
        description="Final ordering score; interpret using score_type, not as probability"
    )
    score_type: ScoreType
    retrieval_score: float
    sources: list[Literal["vector", "keyword"]]
    vector_rank: int | None
    keyword_rank: int | None
    vector_distance: float | None
    cosine_similarity: float | None
    normalized_similarity: float | None = Field(
        description="(1 + cosine_similarity)/2, not probability"
    )
    keyword_score: float | None
    rrf_score: float | None = Field(description="Sum of 1/(k + rank), never a probability")
    rerank_score: float | None


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    results: list[SearchResult]
    score_type: ScoreType
    rrf_k: int | None
    candidate_limit_per_source: int
    vector_strategy: Literal["exact", "hnsw", "exact_fallback"] | None
    reranking_status: Literal["not_requested", "noop", "applied", "fallback", "empty"]
    reranker_model: str | None
    warnings: list[str]
