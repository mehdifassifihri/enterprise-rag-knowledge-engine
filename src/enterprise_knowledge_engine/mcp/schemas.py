from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from enterprise_knowledge_engine.retrieval.schemas import SearchMode, SearchRequest


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class SearchArguments(SearchRequest):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    query: str = Field(min_length=1, max_length=1000, description="Nonblank knowledge search query")
    mode: SearchMode = Field(
        default="hybrid", description="Vector, keyword, or RRF hybrid retrieval"
    )
    top_k: Annotated[
        int, Field(strict=True, ge=1, le=20, description="Maximum returned passages")
    ] = 5
    rerank: StrictBool = Field(default=False, description="Use configured optional reranker")


class AskArguments(Arguments):
    question: str = Field(
        min_length=1, max_length=1000, description="Question grounded in tenant sources"
    )
    top_k: Annotated[
        int, Field(strict=True, ge=1, le=20, description="Maximum retrieved passages")
    ] = 5
    search_mode: SearchMode = Field(
        default="hybrid", description="Retrieval mode used for evidence"
    )
    rerank: StrictBool = Field(default=False, description="Use configured optional reranker")

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        return SearchRequest.validate_query(value)


class PageArguments(Arguments):
    limit: Annotated[int, Field(strict=True, ge=1, le=20, description="Maximum items per page")] = (
        10
    )
    offset: Annotated[int, Field(strict=True, ge=0, le=100000, description="Items to skip")] = 0


class DocumentArguments(Arguments):
    document_id: UUID = Field(description="UUID of a document authorized for the bound tenant")


class ChunkArguments(PageArguments, DocumentArguments):
    pass
