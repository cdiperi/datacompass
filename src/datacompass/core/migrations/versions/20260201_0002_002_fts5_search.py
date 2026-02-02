"""Add FTS5 virtual table for full-text search.

Revision ID: 002
Revises: 001
Create Date: 2026-02-01
"""

from collections.abc import Sequence

from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create FTS5 virtual table for full-text search
    # We store a copy of the content in FTS5 for retrieval
    # object_id is UNINDEXED since we only use it for joining back
    op.execute(
        """
        CREATE VIRTUAL TABLE catalog_fts USING fts5(
            object_id UNINDEXED,
            source_name,
            schema_name,
            object_name,
            object_type,
            description,
            tags,
            column_names,
            tokenize='porter unicode61'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS catalog_fts")
