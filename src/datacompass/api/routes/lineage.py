"""Lineage endpoints."""

from typing import Literal

from fastapi import APIRouter, Query

from datacompass.api.dependencies import CatalogServiceDep, LineageServiceDep
from datacompass.core.models.dependency import LineageGraph, LineageSummary

router = APIRouter(prefix="/objects", tags=["lineage"])


@router.get("/{object_id}/lineage", response_model=LineageGraph)
async def get_lineage(
    object_id: str,
    catalog_service: CatalogServiceDep,
    lineage_service: LineageServiceDep,
    direction: Literal["upstream", "downstream"] = Query(
        "upstream",
        description="Traversal direction: upstream (dependencies) or downstream (dependents)",
    ),
    depth: int = Query(
        3,
        ge=1,
        le=10,
        description="Maximum traversal depth (1-10)",
    ),
) -> LineageGraph:
    """Get lineage graph for a catalog object.

    Returns a graph of dependencies (upstream) or dependents (downstream)
    for the specified object, up to the given depth.

    Args:
        object_id: Object identifier (numeric ID or source.schema.name).
        direction: "upstream" for dependencies, "downstream" for dependents.
        depth: Maximum traversal depth (1-10).

    Returns:
        LineageGraph with root node, related nodes, and edges.

    Raises:
        404: If object not found.
    """
    # Resolve object identifier to numeric ID
    obj = catalog_service.get_object(object_id)

    return lineage_service.get_lineage(
        object_id=obj.id,
        direction=direction,
        depth=depth,
    )


@router.get("/{object_id}/lineage/summary", response_model=LineageSummary)
async def get_lineage_summary(
    object_id: str,
    catalog_service: CatalogServiceDep,
    lineage_service: LineageServiceDep,
) -> LineageSummary:
    """Get lineage summary counts for a catalog object.

    Returns counts of upstream dependencies, downstream dependents,
    and external references.

    Args:
        object_id: Object identifier (numeric ID or source.schema.name).

    Returns:
        LineageSummary with counts.

    Raises:
        404: If object not found.
    """
    # Resolve object identifier to numeric ID
    obj = catalog_service.get_object(object_id)

    return lineage_service.get_lineage_summary(obj.id)
