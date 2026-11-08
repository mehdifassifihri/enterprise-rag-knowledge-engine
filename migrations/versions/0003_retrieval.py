"""Add generated full-text vectors, GIN indexes and cosine HNSW index."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = "0003_retrieval"
down_revision = "0002_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # HNSW iterative scan support used by the optional ANN path requires pgvector >= 0.8.
    op.execute("""
        DO $$
        DECLARE parts int[];
        BEGIN
            SELECT string_to_array(extversion, '.')::int[] INTO parts
            FROM pg_extension WHERE extname = 'vector';
            IF parts IS NULL OR parts < ARRAY[0,8,0] THEN
                RAISE EXCEPTION 'Phase 3 requires pgvector >= 0.8.0; upgrade extension first';
            END IF;
        END $$
    """)
    for language in ("english", "simple"):
        op.add_column(
            "document_chunks",
            sa.Column(
                f"search_{language}",
                TSVECTOR,
                sa.Computed(f"to_tsvector('{language}'::regconfig, content)", persisted=True),
                nullable=False,
            ),
        )
        op.create_index(
            f"ix_chunks_fts_{language}",
            "document_chunks",
            [f"search_{language}"],
            postgresql_using="gin",
        )
    op.create_index(
        "ix_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_chunks_embedding_hnsw", table_name="document_chunks")
    for language in ("simple", "english"):
        op.drop_index(f"ix_chunks_fts_{language}", table_name="document_chunks")
        op.drop_column("document_chunks", f"search_{language}")
