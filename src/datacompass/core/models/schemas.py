"""Pydantic schemas for request/response models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Data Source Schemas
# =============================================================================


class DataSourceBase(BaseModel):
    """Base fields for data sources."""

    name: str = Field(..., description="Unique identifier for the source")
    display_name: str | None = Field(None, description="Human-readable display name")
    source_type: str = Field(..., description="Type of data source (e.g., databricks)")
    is_active: bool = Field(True, description="Whether the source is active")


class DataSourceCreate(DataSourceBase):
    """Schema for creating a data source."""

    connection_info: dict[str, Any] = Field(..., description="Connection configuration")
    sync_config: dict[str, Any] | None = Field(None, description="Sync/scan configuration")


class DataSourceResponse(DataSourceBase):
    """Schema for data source responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    last_scan_at: datetime | None = None
    last_scan_status: str | None = None
    created_at: datetime
    updated_at: datetime


class DataSourceDetail(DataSourceResponse):
    """Detailed data source response including object counts."""

    object_count: int = 0
    table_count: int = 0
    view_count: int = 0


# =============================================================================
# Column Schemas
# =============================================================================


class ForeignKeyConstraint(BaseModel):
    """Foreign key constraint information."""

    constraint_name: str
    references_schema: str
    references_table: str
    references_column: str


class ColumnResponse(BaseModel):
    """Schema for column responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    column_name: str
    position: int
    source_metadata: dict[str, Any] | None = None
    user_metadata: dict[str, Any] | None = None

    # Convenience properties extracted from source_metadata
    @property
    def data_type(self) -> str | None:
        if self.source_metadata:
            return self.source_metadata.get("data_type")
        return None

    @property
    def is_nullable(self) -> bool | None:
        if self.source_metadata:
            return self.source_metadata.get("nullable")
        return None


class ColumnSummary(BaseModel):
    """Summary view of a column."""

    column_name: str
    data_type: str | None = None
    nullable: bool | None = None
    description: str | None = None
    foreign_key: ForeignKeyConstraint | None = None


# =============================================================================
# Catalog Object Schemas
# =============================================================================


class CatalogObjectBase(BaseModel):
    """Base fields for catalog objects."""

    schema_name: str = Field(..., description="Schema/database name")
    object_name: str = Field(..., description="Object name (table, view, etc.)")
    object_type: str = Field(..., description="Type of object (TABLE, VIEW, etc.)")


class CatalogObjectResponse(CatalogObjectBase):
    """Schema for catalog object responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    source_metadata: dict[str, Any] | None = None
    user_metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class CatalogObjectSummary(BaseModel):
    """Summary view of a catalog object for list operations."""

    id: int
    source_name: str
    schema_name: str
    object_name: str
    object_type: str
    description: str | None = None
    column_count: int = 0


class CatalogObjectDetail(CatalogObjectResponse):
    """Detailed catalog object with columns and source info."""

    source_name: str
    columns: list[ColumnSummary] = []


# =============================================================================
# Scan Result Schemas
# =============================================================================


class ScanStats(BaseModel):
    """Statistics from a scan operation."""

    objects_created: int = 0
    objects_updated: int = 0
    objects_deleted: int = 0
    columns_created: int = 0
    columns_updated: int = 0
    columns_deleted: int = 0
    total_objects: int = 0
    total_columns: int = 0


class ScanResult(BaseModel):
    """Result of a source scan operation."""

    source_name: str
    source_type: str
    status: str = Field(..., description="success, partial, or failed")
    message: str | None = None
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    stats: ScanStats


# =============================================================================
# Connection Test Schemas
# =============================================================================


class ConnectionTestResult(BaseModel):
    """Result of testing a source connection."""

    source_name: str
    connected: bool
    message: str | None = None
    latency_ms: float | None = None


# =============================================================================
# Search Schemas (Phase 2)
# =============================================================================


class SearchResultResponse(BaseModel):
    """Schema for search results."""

    id: int = Field(..., description="Object ID")
    source_name: str = Field(..., description="Data source name")
    schema_name: str = Field(..., description="Schema name")
    object_name: str = Field(..., description="Object name")
    object_type: str = Field(..., description="Object type (TABLE, VIEW, etc.)")
    description: str | None = Field(None, description="Object description")
    tags: list[str] = Field(default_factory=list, description="Object tags")
    rank: float = Field(..., description="Search relevance rank (lower is better)")
    highlights: dict[str, str] = Field(
        default_factory=dict,
        description="Highlighted matches by field name",
    )


class SetDescriptionRequest(BaseModel):
    """Request to set an object's description."""

    description: str = Field(..., description="New description for the object")


class TagRequest(BaseModel):
    """Request to add or remove tags."""

    tags: list[str] = Field(..., description="Tags to add or remove")
