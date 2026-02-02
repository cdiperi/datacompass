"""Deprecation Campaign API endpoints."""

from datetime import date

from fastapi import APIRouter, Query

from datacompass.api.dependencies import DeprecationServiceDep
from datacompass.core.models.deprecation import (
    CampaignCreate,
    CampaignDetailResponse,
    CampaignImpactSummary,
    CampaignListItem,
    CampaignUpdate,
    DeprecationCreate,
    DeprecationHubSummary,
    DeprecationResponse,
)

router = APIRouter(prefix="/deprecations", tags=["deprecations"])


# =============================================================================
# Campaigns
# =============================================================================


@router.get("/campaigns", response_model=list[CampaignListItem])
async def list_campaigns(
    deprecation_service: DeprecationServiceDep,
    source_id: int | None = Query(None, description="Filter by source ID"),
    status: str | None = Query(None, description="Filter by status (draft, active, completed)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> list[CampaignListItem]:
    """List deprecation campaigns.

    Returns a list of campaigns with summary information including
    object counts and days remaining.
    """
    return deprecation_service.list_campaigns(
        source_id=source_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.post("/campaigns", response_model=CampaignDetailResponse, status_code=201)
async def create_campaign(
    data: CampaignCreate,
    deprecation_service: DeprecationServiceDep,
) -> CampaignDetailResponse:
    """Create a new deprecation campaign.

    Creates a campaign scoped to a data source with a target retirement date.

    Raises:
        404: If source not found.
        409: If campaign name already exists for source.
    """
    return deprecation_service.create_campaign(
        source_id=data.source_id,
        name=data.name,
        target_date=data.target_date,
        description=data.description,
    )


@router.get("/campaigns/{campaign_id}", response_model=CampaignDetailResponse)
async def get_campaign(
    campaign_id: int,
    deprecation_service: DeprecationServiceDep,
) -> CampaignDetailResponse:
    """Get campaign details.

    Returns the full campaign with all deprecated objects.

    Raises:
        404: If campaign not found.
    """
    return deprecation_service.get_campaign(campaign_id)


@router.patch("/campaigns/{campaign_id}", response_model=CampaignDetailResponse)
async def update_campaign(
    campaign_id: int,
    data: CampaignUpdate,
    deprecation_service: DeprecationServiceDep,
) -> CampaignDetailResponse:
    """Update a campaign.

    Partially updates a campaign. Only provided fields are updated.

    Raises:
        404: If campaign not found.
    """
    return deprecation_service.update_campaign(
        campaign_id=campaign_id,
        name=data.name,
        description=data.description,
        status=data.status,
        target_date=data.target_date,
    )


@router.delete("/campaigns/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: int,
    deprecation_service: DeprecationServiceDep,
) -> None:
    """Delete a campaign.

    Deletes the campaign and all associated deprecations.

    Raises:
        404: If campaign not found.
    """
    deprecation_service.delete_campaign(campaign_id)


# =============================================================================
# Deprecations (Objects in Campaigns)
# =============================================================================


@router.post(
    "/campaigns/{campaign_id}/objects",
    response_model=DeprecationResponse,
    status_code=201,
)
async def add_object_to_campaign(
    campaign_id: int,
    data: DeprecationCreate,
    deprecation_service: DeprecationServiceDep,
) -> DeprecationResponse:
    """Add an object to a campaign.

    Adds a catalog object to the deprecation campaign with optional
    replacement and migration notes.

    Raises:
        404: If campaign or object not found.
        409: If object already in campaign.
    """
    return deprecation_service.add_object_to_campaign(
        campaign_id=campaign_id,
        object_identifier=data.object_id,
        replacement_identifier=data.replacement_id,
        migration_notes=data.migration_notes,
    )


@router.delete("/objects/{deprecation_id}", status_code=204)
async def remove_object_from_campaign(
    deprecation_id: int,
    deprecation_service: DeprecationServiceDep,
) -> None:
    """Remove an object from a campaign.

    Raises:
        404: If deprecation not found.
    """
    deprecation_service.remove_object_from_campaign(deprecation_id)


@router.get("/objects", response_model=list[DeprecationResponse])
async def list_deprecations(
    deprecation_service: DeprecationServiceDep,
    campaign_id: int | None = Query(None, description="Filter by campaign ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> list[DeprecationResponse]:
    """List deprecated objects.

    Returns deprecations with object details and replacement info.
    """
    return deprecation_service.list_deprecations(
        campaign_id=campaign_id,
        limit=limit,
        offset=offset,
    )


# =============================================================================
# Impact Analysis
# =============================================================================


@router.get("/campaigns/{campaign_id}/impact", response_model=CampaignImpactSummary)
async def get_campaign_impact(
    campaign_id: int,
    deprecation_service: DeprecationServiceDep,
    depth: int = Query(3, ge=1, le=10, description="Maximum traversal depth"),
) -> CampaignImpactSummary:
    """Get impact analysis for a campaign.

    Analyzes downstream dependencies of all deprecated objects in
    the campaign using lineage data.

    Raises:
        404: If campaign not found.
    """
    return deprecation_service.check_impact(campaign_id, depth=depth)


# =============================================================================
# Hub
# =============================================================================


@router.get("/hub/summary", response_model=DeprecationHubSummary)
async def get_hub_summary(
    deprecation_service: DeprecationServiceDep,
) -> DeprecationHubSummary:
    """Get deprecation hub dashboard summary.

    Returns aggregated statistics including campaign counts by status,
    total deprecated objects, and upcoming deadlines.
    """
    return deprecation_service.get_hub_summary()
