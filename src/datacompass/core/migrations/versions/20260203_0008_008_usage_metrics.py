"""Add usage metrics table.

Revision ID: 008
Revises: 007
Create Date: 2026-02-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create usage_metrics table
    op.create_table(
        "usage_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "object_id",
            sa.Integer(),
            sa.ForeignKey("catalog_objects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "collected_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Tier 1: Core metrics
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("read_count", sa.Integer(), nullable=True),
        sa.Column("write_count", sa.Integer(), nullable=True),
        # Tier 2: Timestamp metrics
        sa.Column("last_read_at", sa.DateTime(), nullable=True),
        sa.Column("last_written_at", sa.DateTime(), nullable=True),
        # Tier 3: Advanced metrics
        sa.Column("distinct_users", sa.Integer(), nullable=True),
        sa.Column("query_count", sa.Integer(), nullable=True),
        # Platform-specific metrics
        sa.Column("source_metrics", sa.JSON(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Indexes for efficient querying
    op.create_index(
        "ix_usage_metrics_object_id",
        "usage_metrics",
        ["object_id"],
    )

    op.create_index(
        "ix_usage_metrics_collected_at",
        "usage_metrics",
        ["collected_at"],
    )

    op.create_index(
        "ix_usage_metrics_object_collected",
        "usage_metrics",
        ["object_id", "collected_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_usage_metrics_object_collected")
    op.drop_index("ix_usage_metrics_collected_at")
    op.drop_index("ix_usage_metrics_object_id")
    op.drop_table("usage_metrics")
