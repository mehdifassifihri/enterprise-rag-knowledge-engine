"""Add ingestion metadata, tenant deduplication and fixed-dimension pgvector embeddings."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_ingestion"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in [
        sa.Column("filename", sa.String(255)),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(50)),
        sa.Column("page_count", sa.Integer()),
        sa.Column("extraction_metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("embedding_model", sa.String(100)),
        sa.Column("embedding_dimensions", sa.Integer()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    ]:
        op.add_column("documents", column)
    op.create_unique_constraint(
        "uq_documents_tenant_hash", "documents", ["tenant_id", "content_hash"]
    )
    for name, condition in [
        ("status_valid", "status IN ('pending', 'processing', 'ready', 'failed')"),
        ("chunk_count_nonnegative", "chunk_count >= 0"),
        ("size_nonnegative", "size_bytes >= 0"),
        ("ready_has_chunks", "status != 'ready' OR chunk_count > 0"),
    ]:
        op.create_check_constraint(op.f(f"ck_documents_{name}"), "documents", condition)
    for column in [
        sa.Column("embedding", VECTOR(1536)),
        sa.Column("page_number", sa.Integer()),
        sa.Column("start_offset", sa.Integer()),
        sa.Column("end_offset", sa.Integer()),
    ]:
        op.add_column("document_chunks", column)


def downgrade() -> None:
    for name in ["end_offset", "start_offset", "page_number", "embedding"]:
        op.drop_column("document_chunks", name)
    for name in ["ready_has_chunks", "size_nonnegative", "chunk_count_nonnegative", "status_valid"]:
        op.drop_constraint(op.f(f"ck_documents_{name}"), "documents", type_="check")
    op.drop_constraint("uq_documents_tenant_hash", "documents", type_="unique")
    for name in [
        "processed_at",
        "embedding_dimensions",
        "embedding_model",
        "extraction_metadata",
        "page_count",
        "error_code",
        "chunk_count",
        "status",
        "content_hash",
        "size_bytes",
        "filename",
    ]:
        op.drop_column("documents", name)
