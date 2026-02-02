"""Initial schema with data_sources, catalog_objects, and columns tables.

Revision ID: 001
Revises:
Create Date: 2026-02-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create data_sources table
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("connection_info", sa.JSON(), nullable=False),
        sa.Column("sync_config", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("last_scan_at", sa.DateTime(), nullable=True),
        sa.Column("last_scan_status", sa.String(length=50), nullable=True),
        sa.Column("last_scan_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_sources_name", "data_sources", ["name"], unique=True)

    # Create catalog_objects table
    op.create_table(
        "catalog_objects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("schema_name", sa.String(length=255), nullable=False),
        sa.Column("object_name", sa.String(length=255), nullable=False),
        sa.Column("object_type", sa.String(length=50), nullable=False),
        sa.Column("source_metadata", sa.JSON(), nullable=True),
        sa.Column("user_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["data_sources.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "schema_name",
            "object_name",
            "object_type",
            name="uq_catalog_object_natural_key",
        ),
    )
    op.create_index(
        "ix_catalog_objects_source_schema",
        "catalog_objects",
        ["source_id", "schema_name"],
    )
    op.create_index(
        "ix_catalog_objects_object_type",
        "catalog_objects",
        ["object_type"],
    )

    # Create columns table
    op.create_table(
        "columns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("object_id", sa.Integer(), nullable=False),
        sa.Column("column_name", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source_metadata", sa.JSON(), nullable=True),
        sa.Column("user_metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["object_id"],
            ["catalog_objects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_id", "column_name", name="uq_column_object_name"),
    )


def downgrade() -> None:
    op.drop_table("columns")
    op.drop_table("catalog_objects")
    op.drop_table("data_sources")
