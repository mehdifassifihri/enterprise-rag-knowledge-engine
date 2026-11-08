from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from enterprise_knowledge_engine.db.base import Base


class IdentityMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Tenant(IdentityMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)


class Document(IdentityMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_documents_tenant_id_id"),
        CheckConstraint("length(trim(title)) > 0", name="title_not_blank"),
        Index("ix_documents_tenant_created", "tenant_id", "created_at"),
        UniqueConstraint("tenant_id", "content_hash", name="uq_documents_tenant_hash"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed')", name="status_valid"
        ),
        CheckConstraint("chunk_count >= 0", name="chunk_count_nonnegative"),
        CheckConstraint("size_bytes >= 0", name="size_nonnegative"),
        CheckConstraint("status != 'ready' OR chunk_count > 0", name="ready_has_chunks"),
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(500))
    source_uri: Mapped[str | None] = mapped_column(Text)
    media_type: Mapped[str | None] = mapped_column(String(255))

    filename: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    content_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_code: Mapped[str | None] = mapped_column(String(50))
    page_count: Mapped[int | None] = mapped_column(Integer)
    extraction_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentChunk(IdentityMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["documents.tenant_id", "documents.id"],
            ondelete="CASCADE",
            name="fk_chunks_tenant_document",
        ),
        UniqueConstraint("tenant_id", "document_id", "position", name="uq_chunks_position"),
        Index("ix_chunks_fts_english", "search_english", postgresql_using="gin"),
        Index("ix_chunks_fts_simple", "search_simple", postgresql_using="gin"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        CheckConstraint("position >= 0", name="position_nonnegative"),
        CheckConstraint("length(trim(content)) > 0", name="content_not_blank"),
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    document_id: Mapped[UUID] = mapped_column()
    position: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)

    # Nullable for pre-ingestion Phase 1 rows; all new ingestions supply vectors.
    embedding: Mapped[list[float] | None] = mapped_column(VECTOR(1536))
    page_number: Mapped[int | None] = mapped_column(Integer)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)

    search_english: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english'::regconfig, content)", persisted=True)
    )
    search_simple: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple'::regconfig, content)", persisted=True)
    )
