"""Service for Deprecation Campaign operations."""

from datetime import date

from sqlalchemy.orm import Session

from datacompass.core.models.deprecation import (
    CampaignDetailResponse,
    CampaignImpactSummary,
    CampaignListItem,
    Deprecation,
    DeprecationCampaign,
    DeprecationHubSummary,
    DeprecationImpact,
    DeprecationResponse,
    ImpactedObject,
)
from datacompass.core.repositories import CatalogObjectRepository, DataSourceRepository
from datacompass.core.repositories.deprecation import DeprecationRepository
from datacompass.core.services.catalog_service import CatalogService, ObjectNotFoundError
from datacompass.core.services.lineage_service import LineageService
from datacompass.core.services.source_service import SourceNotFoundError


class DeprecationServiceError(Exception):
    """Base exception for deprecation service errors."""

    pass


class CampaignNotFoundError(DeprecationServiceError):
    """Raised when a campaign is not found."""

    def __init__(self, identifier: str | int) -> None:
        self.identifier = identifier
        super().__init__(f"Campaign not found: {identifier}")


class CampaignExistsError(DeprecationServiceError):
    """Raised when a campaign already exists with the same name."""

    def __init__(self, source_id: int, name: str) -> None:
        self.source_id = source_id
        self.name = name
        super().__init__(f"Campaign '{name}' already exists for source {source_id}")


class DeprecationNotFoundError(DeprecationServiceError):
    """Raised when a deprecation is not found."""

    def __init__(self, identifier: int) -> None:
        self.identifier = identifier
        super().__init__(f"Deprecation not found: {identifier}")


class ObjectAlreadyDeprecatedError(DeprecationServiceError):
    """Raised when trying to add an already deprecated object."""

    def __init__(self, campaign_id: int, object_id: int) -> None:
        self.campaign_id = campaign_id
        self.object_id = object_id
        super().__init__(f"Object {object_id} is already in campaign {campaign_id}")


class DeprecationService:
    """Service for deprecation campaign operations.

    Handles:
    - Campaign lifecycle management (draft -> active -> completed)
    - Object-to-campaign assignment
    - Impact analysis using lineage data
    - Hub summary aggregation
    """

    def __init__(self, session: Session) -> None:
        """Initialize deprecation service.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self.deprecation_repo = DeprecationRepository(session)
        self.object_repo = CatalogObjectRepository(session)
        self.source_repo = DataSourceRepository(session)
        self.catalog_service = CatalogService(session)
        self.lineage_service = LineageService(session)

    # =========================================================================
    # Campaign Management
    # =========================================================================

    def create_campaign(
        self,
        source_id: int,
        name: str,
        target_date: date,
        description: str | None = None,
    ) -> CampaignDetailResponse:
        """Create a new deprecation campaign.

        Args:
            source_id: ID of the data source.
            name: Campaign name.
            target_date: Target retirement date.
            description: Optional description.

        Returns:
            Created CampaignDetailResponse.

        Raises:
            SourceNotFoundError: If source not found.
            CampaignExistsError: If campaign name already exists.
        """
        # Verify source exists
        source = self.source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(str(source_id))

        # Check for existing campaign with same name
        existing = self.deprecation_repo.get_campaign_by_name(source_id, name)
        if existing:
            raise CampaignExistsError(source_id, name)

        campaign = self.deprecation_repo.create_campaign(
            source_id=source_id,
            name=name,
            target_date=target_date,
            description=description,
        )

        # Reload with relationships
        campaign = self.deprecation_repo.get_campaign(campaign.id)
        return self._campaign_to_detail_response(campaign)

    def get_campaign(self, campaign_id: int) -> CampaignDetailResponse:
        """Get campaign by ID.

        Args:
            campaign_id: ID of the campaign.

        Returns:
            CampaignDetailResponse with full details.

        Raises:
            CampaignNotFoundError: If campaign not found.
        """
        campaign = self.deprecation_repo.get_campaign(campaign_id)
        if campaign is None:
            raise CampaignNotFoundError(campaign_id)

        return self._campaign_to_detail_response(campaign)

    def list_campaigns(
        self,
        source_id: int | None = None,
        status: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[CampaignListItem]:
        """List campaigns.

        Args:
            source_id: Filter by source.
            status: Filter by status.
            limit: Maximum results.
            offset: Number of results to skip.

        Returns:
            List of CampaignListItem.
        """
        campaigns = self.deprecation_repo.list_campaigns(
            source_id=source_id,
            status=status,
            limit=limit,
            offset=offset,
        )

        return [
            CampaignListItem(
                id=c.id,
                source_id=c.source_id,
                source_name=c.source.name,
                name=c.name,
                status=c.status,
                target_date=c.target_date,
                object_count=len(c.deprecations),
            )
            for c in campaigns
        ]

    def update_campaign(
        self,
        campaign_id: int,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        target_date: date | None = None,
    ) -> CampaignDetailResponse:
        """Update a campaign.

        Args:
            campaign_id: ID of the campaign.
            name: New name.
            description: New description.
            status: New status.
            target_date: New target date.

        Returns:
            Updated CampaignDetailResponse.

        Raises:
            CampaignNotFoundError: If campaign not found.
        """
        campaign = self.deprecation_repo.update_campaign(
            campaign_id=campaign_id,
            name=name,
            description=description,
            status=status,
            target_date=target_date,
        )

        if campaign is None:
            raise CampaignNotFoundError(campaign_id)

        # Reload with relationships
        campaign = self.deprecation_repo.get_campaign(campaign_id)
        return self._campaign_to_detail_response(campaign)

    def delete_campaign(self, campaign_id: int) -> bool:
        """Delete a campaign.

        Args:
            campaign_id: ID of the campaign.

        Returns:
            True if deleted.

        Raises:
            CampaignNotFoundError: If campaign not found.
        """
        deleted = self.deprecation_repo.delete_campaign(campaign_id)
        if not deleted:
            raise CampaignNotFoundError(campaign_id)
        return True

    # =========================================================================
    # Deprecation Management
    # =========================================================================

    def add_object_to_campaign(
        self,
        campaign_id: int,
        object_identifier: str | int,
        replacement_identifier: str | int | None = None,
        migration_notes: str | None = None,
    ) -> DeprecationResponse:
        """Add an object to a campaign.

        Args:
            campaign_id: ID of the campaign.
            object_identifier: Object ID or source.schema.name.
            replacement_identifier: Optional replacement object.
            migration_notes: Optional migration notes.

        Returns:
            Created DeprecationResponse.

        Raises:
            CampaignNotFoundError: If campaign not found.
            ObjectNotFoundError: If object not found.
            ObjectAlreadyDeprecatedError: If object already in campaign.
        """
        # Verify campaign exists
        campaign = self.deprecation_repo.get_by_id(campaign_id)
        if campaign is None:
            raise CampaignNotFoundError(campaign_id)

        # Resolve object identifier (convert int to string for catalog service)
        obj = self.catalog_service.get_object(str(object_identifier))

        # Check if already deprecated
        existing = self.deprecation_repo.get_deprecation_by_object(
            campaign_id, obj.id
        )
        if existing:
            raise ObjectAlreadyDeprecatedError(campaign_id, obj.id)

        # Resolve replacement if provided
        replacement_id = None
        if replacement_identifier is not None:
            replacement_obj = self.catalog_service.get_object(str(replacement_identifier))
            replacement_id = replacement_obj.id

        deprecation = self.deprecation_repo.add_object_to_campaign(
            campaign_id=campaign_id,
            object_id=obj.id,
            replacement_id=replacement_id,
            migration_notes=migration_notes,
        )

        # Reload with relationships
        deprecation = self.deprecation_repo.get_deprecation(deprecation.id)
        return self._deprecation_to_response(deprecation)

    def remove_object_from_campaign(self, deprecation_id: int) -> bool:
        """Remove an object from a campaign.

        Args:
            deprecation_id: ID of the deprecation.

        Returns:
            True if removed.

        Raises:
            DeprecationNotFoundError: If deprecation not found.
        """
        removed = self.deprecation_repo.remove_object_from_campaign(deprecation_id)
        if not removed:
            raise DeprecationNotFoundError(deprecation_id)
        return True

    def get_deprecation(self, deprecation_id: int) -> DeprecationResponse:
        """Get deprecation by ID.

        Args:
            deprecation_id: ID of the deprecation.

        Returns:
            DeprecationResponse.

        Raises:
            DeprecationNotFoundError: If not found.
        """
        deprecation = self.deprecation_repo.get_deprecation(deprecation_id)
        if deprecation is None:
            raise DeprecationNotFoundError(deprecation_id)

        return self._deprecation_to_response(deprecation)

    def list_deprecations(
        self,
        campaign_id: int | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[DeprecationResponse]:
        """List deprecations.

        Args:
            campaign_id: Filter by campaign.
            limit: Maximum results.
            offset: Number of results to skip.

        Returns:
            List of DeprecationResponse.
        """
        deprecations = self.deprecation_repo.list_deprecations(
            campaign_id=campaign_id,
            limit=limit,
            offset=offset,
        )

        return [self._deprecation_to_response(d) for d in deprecations]

    # =========================================================================
    # Impact Analysis
    # =========================================================================

    def check_impact(
        self,
        campaign_id: int,
        depth: int = 3,
    ) -> CampaignImpactSummary:
        """Analyze downstream impact of deprecations in a campaign.

        Uses the LineageService to find all downstream dependents
        of each deprecated object.

        Args:
            campaign_id: ID of the campaign.
            depth: Maximum traversal depth (1-10).

        Returns:
            CampaignImpactSummary with all impacts.

        Raises:
            CampaignNotFoundError: If campaign not found.
        """
        campaign = self.deprecation_repo.get_campaign(campaign_id)
        if campaign is None:
            raise CampaignNotFoundError(campaign_id)

        impacts: list[DeprecationImpact] = []
        total_impacted_ids: set[int] = set()

        for deprecation in campaign.deprecations:
            obj = deprecation.object
            deprecated_name = f"{obj.source.name}.{obj.schema_name}.{obj.object_name}"

            # Get downstream lineage
            try:
                graph = self.lineage_service.get_lineage(
                    object_id=obj.id,
                    direction="downstream",
                    depth=depth,
                )

                impacted_objects = [
                    ImpactedObject(
                        id=node.id,
                        source_name=node.source_name,
                        schema_name=node.schema_name,
                        object_name=node.object_name,
                        object_type=node.object_type,
                        distance=node.distance,
                    )
                    for node in graph.nodes
                ]

                # Track unique impacted IDs
                for node in graph.nodes:
                    total_impacted_ids.add(node.id)

                impacts.append(
                    DeprecationImpact(
                        deprecated_object_id=obj.id,
                        deprecated_object_name=deprecated_name,
                        downstream_count=len(impacted_objects),
                        impacted_objects=impacted_objects,
                    )
                )
            except ObjectNotFoundError:
                # Object might have been deleted; skip
                impacts.append(
                    DeprecationImpact(
                        deprecated_object_id=obj.id,
                        deprecated_object_name=deprecated_name,
                        downstream_count=0,
                        impacted_objects=[],
                    )
                )

        return CampaignImpactSummary(
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            total_deprecated=len(campaign.deprecations),
            total_impacted=len(total_impacted_ids),
            impacts=impacts,
        )

    # =========================================================================
    # Hub Summary
    # =========================================================================

    def get_hub_summary(self) -> DeprecationHubSummary:
        """Get deprecation hub dashboard summary.

        Returns:
            DeprecationHubSummary with aggregated stats.
        """
        status_counts = self.deprecation_repo.count_campaigns_by_status()
        total_deprecated = self.deprecation_repo.count_total_deprecated_objects()
        upcoming = self.deprecation_repo.get_upcoming_campaigns(days=30, limit=5)

        upcoming_items = [
            CampaignListItem(
                id=c.id,
                source_id=c.source_id,
                source_name=c.source.name,
                name=c.name,
                status=c.status,
                target_date=c.target_date,
                object_count=len(c.deprecations),
            )
            for c in upcoming
        ]

        return DeprecationHubSummary(
            total_campaigns=sum(status_counts.values()),
            active_campaigns=status_counts.get("active", 0),
            draft_campaigns=status_counts.get("draft", 0),
            completed_campaigns=status_counts.get("completed", 0),
            total_deprecated_objects=total_deprecated,
            upcoming_deadlines=upcoming_items,
        )

    # =========================================================================
    # Helpers
    # =========================================================================

    def _campaign_to_detail_response(
        self,
        campaign: DeprecationCampaign,
    ) -> CampaignDetailResponse:
        """Convert campaign to detail response."""
        return CampaignDetailResponse(
            id=campaign.id,
            source_id=campaign.source_id,
            source_name=campaign.source.name,
            name=campaign.name,
            description=campaign.description,
            status=campaign.status,
            target_date=campaign.target_date,
            deprecations=[
                self._deprecation_to_response(d) for d in campaign.deprecations
            ],
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
        )

    def _deprecation_to_response(self, deprecation: Deprecation) -> DeprecationResponse:
        """Convert deprecation to response."""
        return DeprecationResponse(
            id=deprecation.id,
            campaign_id=deprecation.campaign_id,
            object_id=deprecation.object_id,
            object_name=deprecation.object.object_name,
            schema_name=deprecation.object.schema_name,
            object_type=deprecation.object.object_type,
            replacement_id=deprecation.replacement_id,
            replacement_name=(
                f"{deprecation.replacement.schema_name}.{deprecation.replacement.object_name}"
                if deprecation.replacement
                else None
            ),
            migration_notes=deprecation.migration_notes,
            created_at=deprecation.created_at,
            updated_at=deprecation.updated_at,
        )
