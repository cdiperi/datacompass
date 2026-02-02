"""API-specific request/response schemas."""

from typing import Any

from pydantic import BaseModel, Field


class SourceCreateRequest(BaseModel):
    """Request schema for creating a data source via API."""

    name: str = Field(..., min_length=1, max_length=100, description="Unique source name")
    source_type: str = Field(..., description="Adapter type (e.g., 'databricks')")
    connection_info: dict[str, Any] = Field(..., description="Connection configuration")
    display_name: str | None = Field(None, description="Human-readable display name")


class ObjectUpdateRequest(BaseModel):
    """Request schema for updating a catalog object."""

    description: str | None = Field(None, description="New description for the object")
    tags_to_add: list[str] | None = Field(None, description="Tags to add to the object")
    tags_to_remove: list[str] | None = Field(None, description="Tags to remove from the object")


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    detail: dict[str, Any] | None = Field(None, description="Additional error details")


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Application version")
