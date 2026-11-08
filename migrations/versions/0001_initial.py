"""Create tenant-scoped knowledge tables and enable pgvector."""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "tenants",
        *identity_columns(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_tenants_name_not_blank"),
    )
    op.create_table(
        "documents",
        *identity_columns(),
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_uri", sa.Text()),
        sa.Column("media_type", sa.String(255)),
        sa.UniqueConstraint("tenant_id", "id", name="uq_documents_tenant_id_id"),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_documents_title_not_blank"),
    )
    op.create_index("ix_documents_tenant_created", "documents", ["tenant_id", "created_at"])
    op.create_table(
        "document_chunks",
        *identity_columns(),
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["documents.tenant_id", "documents.id"],
            ondelete="CASCADE",
            name="fk_chunks_tenant_document",
        ),
        sa.UniqueConstraint("tenant_id", "document_id", "position", name="uq_chunks_position"),
        sa.CheckConstraint("position >= 0", name="ck_document_chunks_position_nonnegative"),
        sa.CheckConstraint(
            "length(trim(content)) > 0", name="ck_document_chunks_content_not_blank"
        ),
    )


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_index("ix_documents_tenant_created", table_name="documents")
    op.drop_table("documents")
    op.drop_table("tenants")
    # The extension may be shared by other schemas; deliberately retain it.
