"""Add deprecation campaign tables.

Revision ID: 005
Revises: 004
Create Date: 2026-02-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create deprecation_campaigns table
    op.create_table(
        "deprecation_campaigns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("data_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("target_date", sa.Date(), nullable=False),
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

    # Unique constraint on (source_id, name)
    op.create_unique_constraint(
        "uq_deprecation_campaigns_source_name",
        "deprecation_campaigns",
        ["source_id", "name"],
    )

    op.create_index(
        "ix_deprecation_campaigns_source_id",
        "deprecation_campaigns",
        ["source_id"],
    )

    op.create_index(
        "ix_deprecation_campaigns_status",
        "deprecation_campaigns",
        ["status"],
    )

    # Create deprecations table
    op.create_table(
        "deprecations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "campaign_id",
            sa.Integer(),
            sa.ForeignKey("deprecation_campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "object_id",
            sa.Integer(),
            sa.ForeignKey("catalog_objects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "replacement_id",
            sa.Integer(),
            sa.ForeignKey("catalog_objects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("migration_notes", sa.Text(), nullable=True),
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

    # Unique constraint on (campaign_id, object_id)
    op.create_unique_constraint(
        "uq_deprecations_campaign_object",
        "deprecations",
        ["campaign_id", "object_id"],
    )

    op.create_index(
        "ix_deprecations_campaign_id",
        "deprecations",
        ["campaign_id"],
    )

    op.create_index(
        "ix_deprecations_object_id",
        "deprecations",
        ["object_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_deprecations_object_id")
    op.drop_index("ix_deprecations_campaign_id")
    op.drop_constraint("uq_deprecations_campaign_object", "deprecations")
    op.drop_table("deprecations")

    op.drop_index("ix_deprecation_campaigns_status")
    op.drop_index("ix_deprecation_campaigns_source_id")
    op.drop_constraint("uq_deprecation_campaigns_source_name", "deprecation_campaigns")
    op.drop_table("deprecation_campaigns")
