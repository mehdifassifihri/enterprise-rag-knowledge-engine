from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from enterprise_knowledge_engine.retrieval.schemas import SearchMode, SearchRequest

AbstentionReason = Literal["no_relevant_sources", "insufficient_support", "conflicting_evidence"]


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return SearchRequest.validate_query(value)


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=20, strict=True)
    search_mode: SearchMode | None = None
    rerank: StrictBool | None = None
    history: list[HistoryMessage] = Field(default_factory=list, max_length=6)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        return SearchRequest.validate_query(value)

    @model_validator(mode="after")
    def validate_history_budget(self) -> "AskRequest":
        if sum(len(message.content) for message in self.history) > 4000:
            raise ValueError("Conversation history exceeds 4000 characters")
        return self


class EvidenceQuote(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_id: str = Field(pattern=r"^S[1-9][0-9]?$", max_length=3)
    quote: str = Field(min_length=8, max_length=600)


class GroundedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1, max_length=1000)
    evidence: list[EvidenceQuote] = Field(min_length=1, max_length=4)


class GeneratedAnswer(BaseModel):
    """The provider emits claims, never document metadata or a free-form final answer."""

    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["answered", "insufficient_evidence"]
    claims: list[GroundedClaim] = Field(max_length=8)
    reason: AbstentionReason | None

    @model_validator(mode="after")
    def validate_status(self) -> "GeneratedAnswer":
        if self.status == "answered" and (not self.claims or self.reason is not None):
            raise ValueError("Answered output requires claims and no abstention reason")
        if self.status == "insufficient_evidence" and (self.claims or self.reason is None):
            raise ValueError("Abstention requires a reason and no claims")
        return self


class Citation(BaseModel):
    source_id: str
    document_id: UUID
    chunk_id: UUID
    filename: str | None
    page: int | None
    chunk_position: int
    start_offset: int | None
    end_offset: int | None
    excerpt: str = Field(description="First validated verbatim supporting quote")
    supporting_quotes: list[str]


class TokenUsage(BaseModel):
    input_tokens: int | None = Field(default=None, ge=0, strict=True)
    output_tokens: int | None = Field(default=None, ge=0, strict=True)
    total_tokens: int | None = Field(default=None, ge=0, strict=True)


class RetrievalSummary(BaseModel):
    mode: SearchMode
    top_k: int
    sources_retrieved: int
    sources_supplied: int
    sources_used: int
    context_characters: int
    reranking_status: str | None
    warnings: list[str]


class QATimings(BaseModel):
    retrieval_ms: float | None = None
    model_ms: float | None = None


class AnswerError(BaseModel):
    code: str
    message: str


class AskResponse(BaseModel):
    question: str
    answer: str
    status: Literal["answered", "insufficient_evidence", "error"]
    abstention_reason: AbstentionReason | None
    citations: list[Citation]
    retrieval: RetrievalSummary
    model: str | None
    usage: TokenUsage | None
    timings: QATimings
    request_id: str | None
    error: AnswerError | None
