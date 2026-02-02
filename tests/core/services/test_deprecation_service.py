"""Tests for DeprecationService."""

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.repositories import CatalogObjectRepository, DataSourceRepository
from datacompass.core.repositories.dependency import DependencyRepository
from datacompass.core.services.deprecation_service import (
    CampaignExistsError,
    CampaignNotFoundError,
    DeprecationNotFoundError,
    DeprecationService,
    ObjectAlreadyDeprecatedError,
)
from datacompass.core.services import ObjectNotFoundError


class TestDeprecationService:
    """Test cases for DeprecationService."""

    @pytest.fixture
    def source(self, test_db: Session) -> DataSource:
        """Create a test data source."""
        repo = DataSourceRepository(test_db)
        source = repo.create(
            name="demo",
            source_type="databricks",
            connection_info={},
        )
        test_db.commit()
        return source

    @pytest.fixture
    def catalog_objects(self, test_db: Session, source: DataSource) -> list[CatalogObject]:
        """Create multiple test catalog objects."""
        repo = CatalogObjectRepository(test_db)
        objects = []
        for name in ["old_table", "new_table", "downstream_view"]:
            obj, _ = repo.upsert(source.id, "analytics", name, "TABLE")
            objects.append(obj)
        test_db.commit()
        return objects

    @pytest.fixture
    def service(self, test_db: Session) -> DeprecationService:
        """Create a deprecation service."""
        return DeprecationService(test_db)

    # =========================================================================
    # Campaign Tests
    # =========================================================================

    def test_create_campaign(
        self, test_db: Session, source: DataSource, service: DeprecationService
    ):
        """Test creating a campaign."""
        campaign = service.create_campaign(
            source_id=source.id,
            name="Q2 Cleanup",
            target_date=date(2025, 6, 1),
            description="Retiring old tables",
        )
        test_db.commit()

        assert campaign.id is not None
        assert campaign.name == "Q2 Cleanup"
        assert campaign.source_name == "demo"
        assert campaign.status == "draft"
        assert campaign.target_date == date(2025, 6, 1)
        assert campaign.description == "Retiring old tables"

    def test_create_campaign_duplicate_name(
        self, test_db: Session, source: DataSource, service: DeprecationService
    ):
        """Test creating campaign with duplicate name raises error."""
        service.create_campaign(
            source_id=source.id,
            name="Test Campaign",
            target_date=date(2025, 6, 1),
        )
        test_db.commit()

        with pytest.raises(CampaignExistsError):
            service.create_campaign(
                source_id=source.id,
                name="Test Campaign",
                target_date=date(2025, 7, 1),
            )

    def test_get_campaign(
        self, test_db: Session, source: DataSource, service: DeprecationService
    ):
        """Test getting campaign by ID."""
        created = service.create_campaign(
            source_id=source.id,
            name="Test",
            target_date=date(2025, 6, 1),
        )
        test_db.commit()

        campaign = service.get_campaign(created.id)
        assert campaign.id == created.id
        assert campaign.name == "Test"

    def test_get_campaign_not_found(self, service: DeprecationService):
        """Test getting non-existent campaign raises error."""
        with pytest.raises(CampaignNotFoundError):
            service.get_campaign(99999)

    def test_list_campaigns(
        self, test_db: Session, source: DataSource, service: DeprecationService
    ):
        """Test listing campaigns."""
        service.create_campaign(
            source_id=source.id,
            name="Campaign 1",
            target_date=date(2025, 6, 1),
        )
        service.create_campaign(
            source_id=source.id,
            name="Campaign 2",
            target_date=date(2025, 7, 1),
        )
        test_db.commit()

        campaigns = service.list_campaigns()
        assert len(campaigns) == 2
        assert campaigns[0].days_remaining is not None

    def test_update_campaign(
        self, test_db: Session, source: DataSource, service: DeprecationService
    ):
        """Test updating a campaign."""
        created = service.create_campaign(
            source_id=source.id,
            name="Original",
            target_date=date(2025, 6, 1),
        )
        test_db.commit()

        updated = service.update_campaign(
            campaign_id=created.id,
            name="Updated",
            status="active",
        )
        test_db.commit()

        assert updated.name == "Updated"
        assert updated.status == "active"

    def test_delete_campaign(
        self, test_db: Session, source: DataSource, service: DeprecationService
    ):
        """Test deleting a campaign."""
        created = service.create_campaign(
            source_id=source.id,
            name="To Delete",
            target_date=date(2025, 6, 1),
        )
        test_db.commit()

        result = service.delete_campaign(created.id)
        test_db.commit()

        assert result is True
        with pytest.raises(CampaignNotFoundError):
            service.get_campaign(created.id)

    # =========================================================================
    # Deprecation Tests
    # =========================================================================

    def test_add_object_to_campaign(
        self,
        test_db: Session,
        source: DataSource,
        catalog_objects: list[CatalogObject],
        service: DeprecationService,
    ):
        """Test adding an object to a campaign."""
        campaign = service.create_campaign(
            source_id=source.id,
            name="Test",
            target_date=date(2025, 6, 1),
        )
        test_db.commit()

        deprecation = service.add_object_to_campaign(
            campaign_id=campaign.id,
            object_identifier=catalog_objects[0].id,
            replacement_identifier=catalog_objects[1].id,
            migration_notes="Use new_table",
        )
        test_db.commit()

        assert deprecation.id is not None
        assert deprecation.object_id == catalog_objects[0].id
        assert deprecation.replacement_id == catalog_objects[1].id

    def test_add_object_to_campaign_by_name(
        self,
        test_db: Session,
        source: DataSource,
        catalog_objects: list[CatalogObject],
        service: DeprecationService,
    ):
        """Test adding an object using its qualified name."""
        campaign = service.create_campaign(
            source_id=source.id,
            name="Test",
            target_date=date(2025, 6, 1),
        )
        test_db.commit()

        deprecation = service.add_object_to_campaign(
            campaign_id=campaign.id,
            object_identifier="demo.analytics.old_table",
        )
        test_db.commit()

        assert deprecation.object_name == "old_table"

    def test_add_object_already_deprecated(
        self,
        test_db: Session,
        source: DataSource,
        catalog_objects: list[CatalogObject],
        service: DeprecationService,
    ):
        """Test adding already deprecated object raises error."""
        campaign = service.create_campaign(
            source_id=source.id,
            name="Test",
            target_date=date(2025, 6, 1),
        )
        service.add_object_to_campaign(
            campaign_id=campaign.id,
            object_identifier=catalog_objects[0].id,
        )
        test_db.commit()

        with pytest.raises(ObjectAlreadyDeprecatedError):
            service.add_object_to_campaign(
                campaign_id=campaign.id,
                object_identifier=catalog_objects[0].id,
            )

    def test_remove_object_from_campaign(
        self,
        test_db: Session,
        source: DataSource,
        catalog_objects: list[CatalogObject],
        service: DeprecationService,
    ):
        """Test removing an object from a campaign."""
        campaign = service.create_campaign(
            source_id=source.id,
            name="Test",
            target_date=date(2025, 6, 1),
        )
        deprecation = service.add_object_to_campaign(
            campaign_id=campaign.id,
            object_identifier=catalog_objects[0].id,
        )
        test_db.commit()

        result = service.remove_object_from_campaign(deprecation.id)
        test_db.commit()

        assert result is True
        with pytest.raises(DeprecationNotFoundError):
            service.get_deprecation(deprecation.id)

    def test_list_deprecations(
        self,
        test_db: Session,
        source: DataSource,
        catalog_objects: list[CatalogObject],
        service: DeprecationService,
    ):
        """Test listing deprecations."""
        campaign = service.create_campaign(
            source_id=source.id,
            name="Test",
            target_date=date(2025, 6, 1),
        )
        service.add_object_to_campaign(campaign.id, catalog_objects[0].id)
        service.add_object_to_campaign(campaign.id, catalog_objects[1].id)
        test_db.commit()

        deprecations = service.list_deprecations(campaign_id=campaign.id)
        assert len(deprecations) == 2

    # =========================================================================
    # Impact Analysis Tests
    # =========================================================================

    def test_check_impact_no_dependencies(
        self,
        test_db: Session,
        source: DataSource,
        catalog_objects: list[CatalogObject],
        service: DeprecationService,
    ):
        """Test impact analysis with no dependencies."""
        campaign = service.create_campaign(
            source_id=source.id,
            name="Test",
            target_date=date(2025, 6, 1),
        )
        service.add_object_to_campaign(campaign.id, catalog_objects[0].id)
        test_db.commit()

        impact = service.check_impact(campaign.id)

        assert impact.campaign_id == campaign.id
        assert impact.total_deprecated == 1
        assert impact.total_impacted == 0
        assert len(impact.impacts) == 1
        assert impact.impacts[0].downstream_count == 0

    def test_check_impact_with_dependencies(
        self,
        test_db: Session,
        source: DataSource,
        catalog_objects: list[CatalogObject],
        service: DeprecationService,
    ):
        """Test impact analysis with dependencies."""
        # Create dependency: downstream_view depends on old_table
        dep_repo = DependencyRepository(test_db)
        dep_repo.upsert(
            source_id=source.id,
            object_id=catalog_objects[2].id,  # downstream_view
            target_id=catalog_objects[0].id,  # old_table
            dependency_type="DIRECT",
            parsing_source="test",
            confidence="HIGH",
        )
        test_db.commit()

        campaign = service.create_campaign(
            source_id=source.id,
            name="Test",
            target_date=date(2025, 6, 1),
        )
        service.add_object_to_campaign(campaign.id, catalog_objects[0].id)
        test_db.commit()

        impact = service.check_impact(campaign.id)

        assert impact.total_deprecated == 1
        assert impact.total_impacted == 1
        assert len(impact.impacts) == 1
        assert impact.impacts[0].downstream_count == 1
        assert len(impact.impacts[0].impacted_objects) == 1
        assert impact.impacts[0].impacted_objects[0].object_name == "downstream_view"

    # =========================================================================
    # Hub Summary Tests
    # =========================================================================

    def test_get_hub_summary(
        self,
        test_db: Session,
        source: DataSource,
        catalog_objects: list[CatalogObject],
        service: DeprecationService,
    ):
        """Test hub summary."""
        # Create campaigns
        campaign1 = service.create_campaign(
            source_id=source.id,
            name="Draft",
            target_date=date.today() + timedelta(days=10),
        )
        campaign2 = service.create_campaign(
            source_id=source.id,
            name="Active",
            target_date=date.today() + timedelta(days=5),
        )
        service.update_campaign(campaign2.id, status="active")

        # Add deprecations
        service.add_object_to_campaign(campaign1.id, catalog_objects[0].id)
        service.add_object_to_campaign(campaign2.id, catalog_objects[1].id)
        test_db.commit()

        summary = service.get_hub_summary()

        assert summary.total_campaigns == 2
        assert summary.draft_campaigns == 1
        assert summary.active_campaigns == 1
        assert summary.total_deprecated_objects == 2
        assert len(summary.upcoming_deadlines) >= 1
