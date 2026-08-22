"""create books table with hnsw and gin indexes

Revision ID: b994c754f6d5
Revises: a677930b7b55
Create Date: 2026-08-20 16:59:04.386708

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b994c754f6d5"
down_revision: str | None = "a677930b7b55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1536
SEARCH_VECTOR_EXPRESSION = (
    "to_tsvector('simple', coalesce(description, '') || ' ' || coalesce(category, ''))"
)


def upgrade() -> None:
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("book_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.Text(), nullable=False, server_default=""),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column(
            "search_vector",
            TSVECTOR(),
            sa.Computed(SEARCH_VECTOR_EXPRESSION, persisted=True),
            nullable=False,
        ),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("book_id", name="uq_books_book_id"),
    )
    op.create_index("ix_books_book_id", "books", ["book_id"])
    op.execute(
        "CREATE INDEX ix_books_embedding_hnsw ON books "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.execute("CREATE INDEX ix_books_search_vector_gin ON books USING gin (search_vector)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_books_search_vector_gin")
    op.execute("DROP INDEX IF EXISTS ix_books_embedding_hnsw")
    op.drop_index("ix_books_book_id", table_name="books")
    op.drop_table("books")
