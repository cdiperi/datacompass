"""Catalog object endpoints."""

from fastapi import APIRouter

from datacompass.api.dependencies import (
    CatalogServiceDep,
    DocumentationServiceDep,
)
from datacompass.api.schemas import ObjectUpdateRequest
from datacompass.core.models import CatalogObjectDetail, CatalogObjectSummary

router = APIRouter(prefix="/objects", tags=["objects"])


@router.get("", response_model=list[CatalogObjectSummary])
async def list_objects(
    catalog_service: CatalogServiceDep,
    source: str | None = None,
    object_type: str | None = None,
    schema: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[CatalogObjectSummary]:
    """List catalog objects with optional filters.

    Args:
        source: Filter by source name.
        object_type: Filter by object type (TABLE, VIEW, etc.).
        schema: Filter by schema name.
        limit: Maximum results to return.
        offset: Number of results to skip.

    Returns:
        List of catalog object summaries.
    """
    return catalog_service.list_objects(
        source=source,
        object_type=object_type,
        schema=schema,
        limit=limit,
        offset=offset,
    )


@router.get("/{object_id}", response_model=CatalogObjectDetail)
async def get_object(
    object_id: str,
    catalog_service: CatalogServiceDep,
) -> CatalogObjectDetail:
    """Get detailed information about a catalog object.

    Args:
        object_id: Object identifier (numeric ID or source.schema.name).

    Returns:
        Full object details including columns.

    Raises:
        404: If object not found.
    """
    return catalog_service.get_object(object_id)


@router.patch("/{object_id}", response_model=CatalogObjectDetail)
async def update_object(
    object_id: str,
    request: ObjectUpdateRequest,
    catalog_service: CatalogServiceDep,
    documentation_service: DocumentationServiceDep,
) -> CatalogObjectDetail:
    """Update a catalog object's documentation.

    Allows updating description and tags for an object.

    Args:
        object_id: Object identifier (numeric ID or source.schema.name).
        request: Update request with optional description and tag changes.

    Returns:
        Updated object details.

    Raises:
        404: If object not found.
    """
    # Apply description update if provided
    if request.description is not None:
        documentation_service.set_description(object_id, request.description)

    # Apply tag additions if provided
    if request.tags_to_add:
        documentation_service.add_tags(object_id, request.tags_to_add)

    # Apply tag removals if provided
    if request.tags_to_remove:
        documentation_service.remove_tags(object_id, request.tags_to_remove)

    # Return updated object
    return catalog_service.get_object(object_id)
