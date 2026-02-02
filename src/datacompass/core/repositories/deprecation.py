"""Repository for Deprecation Campaign operations."""

from datetime import date, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import joinedload

from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.models.deprecation import Deprecation, DeprecationCampaign
from datacompass.core.repositories.base import BaseRepository


class DeprecationRepository(BaseRepository[DeprecationCampaign]):
    """Repository for deprecation CRUD operations."""

    model = DeprecationCampaign

    # =========================================================================
    # Campaign Operations
    # =========================================================================

    def get_campaign(self, campaign_id: int) -> DeprecationCampaign | None:
        """Get campaign by ID with relationships loaded.

        Args:
            campaign_id: ID of the campaign.

        Returns:
            DeprecationCampaign instance or None.
        """
        stmt = (
            select(DeprecationCampaign)
            .options(
                joinedload(DeprecationCampaign.source),
                joinedload(DeprecationCampaign.deprecations)
                .joinedload(Deprecation.object),
                joinedload(DeprecationCampaign.deprecations)
                .joinedload(Deprecation.replacement),
            )
            .where(DeprecationCampaign.id == campaign_id)
        )
        return self.session.scalar(stmt)

    def get_campaign_by_name(
        self,
        source_id: int,
        name: str,
    ) -> DeprecationCampaign | None:
        """Get campaign by source and name.

        Args:
            source_id: ID of the data source.
            name: Campaign name.

        Returns:
            DeprecationCampaign instance or None.
        """
        stmt = (
            select(DeprecationCampaign)
            .options(
                joinedload(DeprecationCampaign.source),
                joinedload(DeprecationCampaign.deprecations),
            )
            .where(
                and_(
                    DeprecationCampaign.source_id == source_id,
                    DeprecationCampaign.name == name,
                )
            )
        )
        return self.session.scalar(stmt)

    def list_campaigns(
        self,
        source_id: int | None = None,
        status: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[DeprecationCampaign]:
        """List campaigns with optional filters.

        Args:
            source_id: Filter by source ID.
            status: Filter by status (draft, active, completed).
            limit: Maximum results.
            offset: Number of results to skip.

        Returns:
            List of DeprecationCampaign instances.
        """
        stmt = (
            select(DeprecationCampaign)
            .options(
                joinedload(DeprecationCampaign.source),
                joinedload(DeprecationCampaign.deprecations),
            )
        )

        if source_id is not None:
            stmt = stmt.where(DeprecationCampaign.source_id == source_id)

        if status is not None:
            stmt = stmt.where(DeprecationCampaign.status == status)

        stmt = stmt.order_by(DeprecationCampaign.target_date.asc())
        stmt = stmt.offset(offset)

        if limit is not None:
            stmt = stmt.limit(limit)

        return list(self.session.scalars(stmt).unique())

    def create_campaign(
        self,
        source_id: int,
        name: str,
        target_date: date,
        description: str | None = None,
    ) -> DeprecationCampaign:
        """Create a new campaign.

        Args:
            source_id: ID of the data source.
            name: Campaign name.
            target_date: Target retirement date.
            description: Optional description.

        Returns:
            Created DeprecationCampaign instance.
        """
        campaign = DeprecationCampaign(
            source_id=source_id,
            name=name,
            description=description,
            target_date=target_date,
        )
        self.add(campaign)
        self.flush()
        return campaign

    def update_campaign(
        self,
        campaign_id: int,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        target_date: date | None = None,
    ) -> DeprecationCampaign | None:
        """Update a campaign.

        Args:
            campaign_id: ID of the campaign.
            name: New name.
            description: New description.
            status: New status.
            target_date: New target date.

        Returns:
            Updated DeprecationCampaign or None if not found.
        """
        campaign = self.get_by_id(campaign_id)
        if campaign is None:
            return None

        if name is not None:
            campaign.name = name
        if description is not None:
            campaign.description = description
        if status is not None:
            campaign.status = status
        if target_date is not None:
            campaign.target_date = target_date

        campaign.updated_at = datetime.utcnow()
        return campaign

    def delete_campaign(self, campaign_id: int) -> bool:
        """Delete a campaign and all its deprecations.

        Args:
            campaign_id: ID of the campaign.

        Returns:
            True if deleted, False if not found.
        """
        campaign = self.get_by_id(campaign_id)
        if campaign is None:
            return False
        self.delete(campaign)
        return True

    # =========================================================================
    # Deprecation Operations
    # =========================================================================

    def get_deprecation(self, deprecation_id: int) -> Deprecation | None:
        """Get deprecation by ID.

        Args:
            deprecation_id: ID of the deprecation.

        Returns:
            Deprecation instance or None.
        """
        stmt = (
            select(Deprecation)
            .options(
                joinedload(Deprecation.campaign).joinedload(DeprecationCampaign.source),
                joinedload(Deprecation.object),
                joinedload(Deprecation.replacement),
            )
            .where(Deprecation.id == deprecation_id)
        )
        return self.session.scalar(stmt)

    def get_deprecation_by_object(
        self,
        campaign_id: int,
        object_id: int,
    ) -> Deprecation | None:
        """Get deprecation by campaign and object.

        Args:
            campaign_id: ID of the campaign.
            object_id: ID of the object.

        Returns:
            Deprecation instance or None.
        """
        stmt = select(Deprecation).where(
            and_(
                Deprecation.campaign_id == campaign_id,
                Deprecation.object_id == object_id,
            )
        )
        return self.session.scalar(stmt)

    def list_deprecations(
        self,
        campaign_id: int | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Deprecation]:
        """List deprecations with optional campaign filter.

        Args:
            campaign_id: Filter by campaign ID.
            limit: Maximum results.
            offset: Number of results to skip.

        Returns:
            List of Deprecation instances.
        """
        stmt = (
            select(Deprecation)
            .options(
                joinedload(Deprecation.campaign).joinedload(DeprecationCampaign.source),
                joinedload(Deprecation.object),
                joinedload(Deprecation.replacement),
            )
        )

        if campaign_id is not None:
            stmt = stmt.where(Deprecation.campaign_id == campaign_id)

        stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        return list(self.session.scalars(stmt).unique())

    def add_object_to_campaign(
        self,
        campaign_id: int,
        object_id: int,
        replacement_id: int | None = None,
        migration_notes: str | None = None,
    ) -> Deprecation:
        """Add an object to a campaign.

        Args:
            campaign_id: ID of the campaign.
            object_id: ID of the object to deprecate.
            replacement_id: Optional replacement object ID.
            migration_notes: Optional migration notes.

        Returns:
            Created Deprecation instance.
        """
        deprecation = Deprecation(
            campaign_id=campaign_id,
            object_id=object_id,
            replacement_id=replacement_id,
            migration_notes=migration_notes,
        )
        self.session.add(deprecation)
        self.flush()
        return deprecation

    def update_deprecation(
        self,
        deprecation_id: int,
        replacement_id: int | None = None,
        migration_notes: str | None = None,
    ) -> Deprecation | None:
        """Update a deprecation.

        Args:
            deprecation_id: ID of the deprecation.
            replacement_id: New replacement object ID.
            migration_notes: New migration notes.

        Returns:
            Updated Deprecation or None if not found.
        """
        deprecation = self.session.get(Deprecation, deprecation_id)
        if deprecation is None:
            return None

        if replacement_id is not None:
            deprecation.replacement_id = replacement_id
        if migration_notes is not None:
            deprecation.migration_notes = migration_notes

        deprecation.updated_at = datetime.utcnow()
        return deprecation

    def remove_object_from_campaign(self, deprecation_id: int) -> bool:
        """Remove an object from a campaign.

        Args:
            deprecation_id: ID of the deprecation.

        Returns:
            True if removed, False if not found.
        """
        deprecation = self.session.get(Deprecation, deprecation_id)
        if deprecation is None:
            return False
        self.session.delete(deprecation)
        return True

    # =========================================================================
    # Aggregate Queries
    # =========================================================================

    def count_campaigns_by_status(self) -> dict[str, int]:
        """Count campaigns grouped by status.

        Returns:
            Dict mapping status to count.
        """
        stmt = (
            select(DeprecationCampaign.status, func.count(DeprecationCampaign.id))
            .group_by(DeprecationCampaign.status)
        )
        results = self.session.execute(stmt).all()
        return dict(results)

    def count_total_deprecated_objects(self) -> int:
        """Count total deprecated objects across all campaigns.

        Returns:
            Total count of deprecations.
        """
        stmt = select(func.count(Deprecation.id))
        return self.session.scalar(stmt) or 0

    def get_object_count_for_campaign(self, campaign_id: int) -> int:
        """Get count of deprecated objects in a campaign.

        Args:
            campaign_id: ID of the campaign.

        Returns:
            Number of deprecated objects.
        """
        stmt = (
            select(func.count(Deprecation.id))
            .where(Deprecation.campaign_id == campaign_id)
        )
        return self.session.scalar(stmt) or 0

    def get_upcoming_campaigns(
        self,
        days: int = 30,
        limit: int = 10,
    ) -> list[DeprecationCampaign]:
        """Get campaigns with upcoming target dates.

        Args:
            days: Number of days to look ahead.
            limit: Maximum results.

        Returns:
            List of upcoming campaigns ordered by target date.
        """
        from datetime import timedelta

        today = date.today()
        end_date = today + timedelta(days=days)

        stmt = (
            select(DeprecationCampaign)
            .options(
                joinedload(DeprecationCampaign.source),
                joinedload(DeprecationCampaign.deprecations),
            )
            .where(
                and_(
                    DeprecationCampaign.status.in_(["draft", "active"]),
                    DeprecationCampaign.target_date >= today,
                    DeprecationCampaign.target_date <= end_date,
                )
            )
            .order_by(DeprecationCampaign.target_date.asc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).unique())

    def get_deprecated_object_ids_for_campaign(
        self,
        campaign_id: int,
    ) -> list[int]:
        """Get all object IDs being deprecated in a campaign.

        Args:
            campaign_id: ID of the campaign.

        Returns:
            List of object IDs.
        """
        stmt = (
            select(Deprecation.object_id)
            .where(Deprecation.campaign_id == campaign_id)
        )
        return list(self.session.scalars(stmt))
