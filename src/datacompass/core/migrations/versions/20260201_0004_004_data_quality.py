"""Add data quality tables.

Revision ID: 004
Revises: 003
Create Date: 2026-02-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create dq_configs table
    op.create_table(
        "dq_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "object_id",
            sa.Integer(),
            sa.ForeignKey("catalog_objects.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("date_column", sa.String(100), nullable=True),
        sa.Column("grain", sa.String(50), nullable=False, server_default="daily"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
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

    op.create_index(
        "ix_dq_configs_object_id",
        "dq_configs",
        ["object_id"],
    )

    # Create dq_expectations table
    op.create_table(
        "dq_expectations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "config_id",
            sa.Integer(),
            sa.ForeignKey("dq_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expectation_type", sa.String(50), nullable=False),
        sa.Column("column_name", sa.String(100), nullable=True),
        sa.Column("threshold_config", sa.JSON(), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
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

    op.create_index(
        "ix_dq_expectations_config_id",
        "dq_expectations",
        ["config_id"],
    )

    # Create dq_results table
    op.create_table(
        "dq_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "expectation_id",
            sa.Integer(),
            sa.ForeignKey("dq_expectations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("computed_threshold_low", sa.Float(), nullable=True),
        sa.Column("computed_threshold_high", sa.Float(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_unique_constraint(
        "uq_dq_results_expectation_date",
        "dq_results",
        ["expectation_id", "snapshot_date"],
    )

    op.create_index(
        "ix_dq_results_expectation_id",
        "dq_results",
        ["expectation_id"],
    )

    op.create_index(
        "ix_dq_results_snapshot_date",
        "dq_results",
        ["snapshot_date"],
    )

    # Create dq_breaches table
    op.create_table(
        "dq_breaches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "expectation_id",
            sa.Integer(),
            sa.ForeignKey("dq_expectations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "result_id",
            sa.Integer(),
            sa.ForeignKey("dq_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("breach_direction", sa.String(10), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.Column("deviation_value", sa.Float(), nullable=False),
        sa.Column("deviation_percent", sa.Float(), nullable=False),
        sa.Column("threshold_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("lifecycle_events", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "detected_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
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

    op.create_unique_constraint(
        "uq_dq_breaches_expectation_date",
        "dq_breaches",
        ["expectation_id", "snapshot_date"],
    )

    op.create_index(
        "ix_dq_breaches_expectation_id",
        "dq_breaches",
        ["expectation_id"],
    )

    op.create_index(
        "ix_dq_breaches_status",
        "dq_breaches",
        ["status"],
    )

    op.create_index(
        "ix_dq_breaches_snapshot_date",
        "dq_breaches",
        ["snapshot_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_dq_breaches_snapshot_date")
    op.drop_index("ix_dq_breaches_status")
    op.drop_index("ix_dq_breaches_expectation_id")
    op.drop_constraint("uq_dq_breaches_expectation_date", "dq_breaches")
    op.drop_table("dq_breaches")

    op.drop_index("ix_dq_results_snapshot_date")
    op.drop_index("ix_dq_results_expectation_id")
    op.drop_constraint("uq_dq_results_expectation_date", "dq_results")
    op.drop_table("dq_results")

    op.drop_index("ix_dq_expectations_config_id")
    op.drop_table("dq_expectations")

    op.drop_index("ix_dq_configs_object_id")
    op.drop_table("dq_configs")
