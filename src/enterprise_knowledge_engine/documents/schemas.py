from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    filename: str | None
    media_type: str | None
    size_bytes: int
    content_hash: str | None
    status: Literal["pending", "processing", "ready", "failed"]
    chunk_count: int
    page_count: int | None
    extraction_metadata: dict
    embedding_model: str | None
    embedding_dimensions: int | None
    error_code: str | None
    created_at: datetime
    processed_at: datetime | None


class DocumentList(BaseModel):
    items: list[DocumentResponse]
    limit: int
    offset: int


class DocumentStats(BaseModel):
    documents: int
    ready: int
    failed: int
    chunks: int


class ChunkPreview(BaseModel):
    id: UUID
    document_id: UUID
    position: int
    content: str
    page_number: int | None
    start_offset: int | None
    end_offset: int | None
    truncated: bool


class ChunkPage(BaseModel):
    items: list[ChunkPreview]
    limit: int
    offset: int
