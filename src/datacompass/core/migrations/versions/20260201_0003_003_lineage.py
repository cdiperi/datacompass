"""Add dependencies table for lineage tracking.

Revision ID: 003
Revises: 002
Create Date: 2026-02-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create dependencies table for tracking lineage between catalog objects
    op.create_table(
        "dependencies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("data_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "object_id",
            sa.Integer(),
            sa.ForeignKey("catalog_objects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            sa.Integer(),
            sa.ForeignKey("catalog_objects.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("target_external", sa.JSON(), nullable=True),
        sa.Column("dependency_type", sa.String(50), nullable=False),
        sa.Column("parsing_source", sa.String(50), nullable=False),
        sa.Column("confidence", sa.String(50), nullable=False, server_default="HIGH"),
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

    # Create unique constraint to prevent duplicate dependencies from same parsing source
    op.create_unique_constraint(
        "uq_dependency_natural_key",
        "dependencies",
        ["object_id", "target_id", "parsing_source"],
    )

    # Create indexes for efficient lookups
    op.create_index(
        "ix_dependencies_object_id",
        "dependencies",
        ["object_id"],
    )
    op.create_index(
        "ix_dependencies_target_id",
        "dependencies",
        ["target_id"],
    )
    op.create_index(
        "ix_dependencies_source_id",
        "dependencies",
        ["source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_dependencies_source_id")
    op.drop_index("ix_dependencies_target_id")
    op.drop_index("ix_dependencies_object_id")
    op.drop_constraint("uq_dependency_natural_key", "dependencies")
    op.drop_table("dependencies")
