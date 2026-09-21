"""Add rag_chunks (guides/FAQ embeddings) and chat_logs.

Revision ID: 0028_rag_chunks_chat
Revises: 0027_listing_embeddings
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0028_rag_chunks_chat"
down_revision: Union[str, None] = "0027_listing_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE rag_chunks (
            id SERIAL PRIMARY KEY,
            source_key VARCHAR(120) NOT NULL UNIQUE,
            title VARCHAR(200) NOT NULL,
            content TEXT NOT NULL,
            url VARCHAR(500),
            embedding vector(1536) NOT NULL,
            content_hash VARCHAR(64) NOT NULL,
            model VARCHAR(80) NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        )
        """
    )
    op.create_index("ix_rag_chunks_content_hash", "rag_chunks", ["content_hash"])
    op.create_index("ix_rag_chunks_model", "rag_chunks", ["model"])
    op.execute(
        "CREATE INDEX ix_rag_chunks_embedding_hnsw "
        "ON rag_chunks USING hnsw (embedding vector_cosine_ops)"
    )

    op.execute(
        """
        CREATE TABLE chat_logs (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            client_ip VARCHAR(64),
            session_id VARCHAR(64),
            question TEXT NOT NULL,
            answer TEXT,
            tool_calls JSONB,
            error TEXT
        )
        """
    )
    op.create_index("ix_chat_logs_created_at", "chat_logs", ["created_at"])
    op.create_index("ix_chat_logs_client_ip", "chat_logs", ["client_ip"])


def downgrade() -> None:
    op.drop_index("ix_chat_logs_client_ip", table_name="chat_logs")
    op.drop_index("ix_chat_logs_created_at", table_name="chat_logs")
    op.drop_table("chat_logs")
    op.execute("DROP INDEX IF EXISTS ix_rag_chunks_embedding_hnsw")
    op.drop_index("ix_rag_chunks_model", table_name="rag_chunks")
    op.drop_index("ix_rag_chunks_content_hash", table_name="rag_chunks")
    op.drop_table("rag_chunks")
