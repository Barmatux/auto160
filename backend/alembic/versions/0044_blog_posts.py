"""Blog posts for public /blog and admin editor.

Revision ID: 0044_blog_posts
Revises: 0043_avby_price_config_stats
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0044_blog_posts"
down_revision: Union[str, None] = "0043_avby_price_config_stats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "blog_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_blog_posts_slug", "blog_posts", ["slug"], unique=True)
    op.create_index("ix_blog_posts_is_published", "blog_posts", ["is_published"])
    op.create_index("ix_blog_posts_published_at", "blog_posts", ["published_at"])
    op.create_index("ix_blog_posts_author_id", "blog_posts", ["author_id"])
    op.create_index("ix_blog_posts_created_at", "blog_posts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_blog_posts_created_at", table_name="blog_posts")
    op.drop_index("ix_blog_posts_author_id", table_name="blog_posts")
    op.drop_index("ix_blog_posts_published_at", table_name="blog_posts")
    op.drop_index("ix_blog_posts_is_published", table_name="blog_posts")
    op.drop_index("ix_blog_posts_slug", table_name="blog_posts")
    op.drop_table("blog_posts")
