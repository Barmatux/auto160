"""Add pgvector listing_embeddings for semantic search.

Revision ID: 0027_listing_embeddings
Revises: 0026_listing_avby_timestamps
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0027_listing_embeddings"
down_revision: Union[str, None] = "0026_listing_avby_timestamps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE listing_embeddings (
            listing_id INTEGER NOT NULL PRIMARY KEY
                REFERENCES car_listings(id) ON DELETE CASCADE,
            embedding vector(1536) NOT NULL,
            content_hash VARCHAR(64) NOT NULL,
            model VARCHAR(80) NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        )
        """
    )
    op.create_index("ix_listing_embeddings_content_hash", "listing_embeddings", ["content_hash"])
    op.create_index("ix_listing_embeddings_model", "listing_embeddings", ["model"])
    op.execute(
        "CREATE INDEX ix_listing_embeddings_embedding_hnsw "
        "ON listing_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_listing_embeddings_embedding_hnsw")
    op.drop_index("ix_listing_embeddings_model", table_name="listing_embeddings")
    op.drop_index("ix_listing_embeddings_content_hash", table_name="listing_embeddings")
    op.drop_table("listing_embeddings")
