"""Tests for DeprecationRepository."""

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.repositories import CatalogObjectRepository, DataSourceRepository
from datacompass.core.repositories.deprecation import DeprecationRepository


class TestDeprecationRepository:
    """Test cases for DeprecationRepository."""

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
        for name in ["old_table", "new_table", "other_table"]:
            obj, _ = repo.upsert(source.id, "analytics", name, "TABLE")
            objects.append(obj)
        test_db.commit()
        return objects

    # =========================================================================
    # Campaign Tests
    # =========================================================================

    def test_create_campaign(self, test_db: Session, source: DataSource):
        """Test creating a deprecation campaign."""
        repo = DeprecationRepository(test_db)

        campaign = repo.create_campaign(
            source_id=source.id,
            name="Q2 Cleanup",
            target_date=date(2025, 6, 1),
            description="Retiring old tables",
        )
        test_db.commit()

        assert campaign.id is not None
        assert campaign.source_id == source.id
        assert campaign.name == "Q2 Cleanup"
        assert campaign.status == "draft"
        assert campaign.target_date == date(2025, 6, 1)
        assert campaign.description == "Retiring old tables"

    def test_get_campaign(self, test_db: Session, source: DataSource):
        """Test getting campaign by ID."""
        repo = DeprecationRepository(test_db)

        campaign = repo.create_campaign(
            source_id=source.id,
            name="Test Campaign",
            target_date=date(2025, 6, 1),
        )
        test_db.commit()

        retrieved = repo.get_campaign(campaign.id)
        assert retrieved is not None
        assert retrieved.id == campaign.id
        assert retrieved.source is not None

    def test_get_campaign_not_found(self, test_db: Session):
        """Test getting non-existent campaign returns None."""
        repo = DeprecationRepository(test_db)

        result = repo.get_campaign(99999)
        assert result is None

    def test_get_campaign_by_name(self, test_db: Session, source: DataSource):
        """Test getting campaign by source and name."""
        repo = DeprecationRepository(test_db)

        repo.create_campaign(
            source_id=source.id,
            name="Test Campaign",
            target_date=date(2025, 6, 1),
        )
        test_db.commit()

        retrieved = repo.get_campaign_by_name(source.id, "Test Campaign")
        assert retrieved is not None
        assert retrieved.name == "Test Campaign"

        # Non-existent name
        result = repo.get_campaign_by_name(source.id, "Non-existent")
        assert result is None

    def test_list_campaigns(self, test_db: Session, source: DataSource):
        """Test listing campaigns."""
        repo = DeprecationRepository(test_db)

        repo.create_campaign(
            source_id=source.id,
            name="Campaign 1",
            target_date=date(2025, 6, 1),
        )
        repo.create_campaign(
            source_id=source.id,
            name="Campaign 2",
            target_date=date(2025, 7, 1),
        )
        test_db.commit()

        campaigns = repo.list_campaigns()
        assert len(campaigns) == 2

    def test_list_campaigns_by_status(self, test_db: Session, source: DataSource):
        """Test filtering campaigns by status."""
        repo = DeprecationRepository(test_db)

        campaign1 = repo.create_campaign(
            source_id=source.id,
            name="Draft",
            target_date=date(2025, 6, 1),
        )
        campaign2 = repo.create_campaign(
            source_id=source.id,
            name="Active",
            target_date=date(2025, 7, 1),
        )
        repo.update_campaign(campaign2.id, status="active")
        test_db.commit()

        draft_campaigns = repo.list_campaigns(status="draft")
        assert len(draft_campaigns) == 1
        assert draft_campaigns[0].name == "Draft"

        active_campaigns = repo.list_campaigns(status="active")
        assert len(active_campaigns) == 1
        assert active_campaigns[0].name == "Active"

    def test_update_campaign(self, test_db: Session, source: DataSource):
        """Test updating a campaign."""
        repo = DeprecationRepository(test_db)

        campaign = repo.create_campaign(
            source_id=source.id,
            name="Original",
            target_date=date(2025, 6, 1),
        )
        test_db.commit()

        updated = repo.update_campaign(
            campaign.id,
            name="Updated",
            status="active",
            target_date=date(2025, 7, 1),
        )
        test_db.commit()

        assert updated.name == "Updated"
        assert updated.status == "active"
        assert updated.target_date == date(2025, 7, 1)

    def test_delete_campaign(self, test_db: Session, source: DataSource):
        """Test deleting a campaign."""
        repo = DeprecationRepository(test_db)

        campaign = repo.create_campaign(
            source_id=source.id,
            name="To Delete",
            target_date=date(2025, 6, 1),
        )
        test_db.commit()

        deleted = repo.delete_campaign(campaign.id)
        test_db.commit()

        assert deleted is True
        assert repo.get_campaign(campaign.id) is None

    def test_delete_campaign_not_found(self, test_db: Session):
        """Test deleting non-existent campaign returns False."""
        repo = DeprecationRepository(test_db)

        result = repo.delete_campaign(99999)
        assert result is False

    # =========================================================================
    # Deprecation Tests
    # =========================================================================

    def test_add_object_to_campaign(
        self, test_db: Session, source: DataSource, catalog_objects: list[CatalogObject]
    ):
        """Test adding an object to a campaign."""
        repo = DeprecationRepository(test_db)

        campaign = repo.create_campaign(
            source_id=source.id,
            name="Test",
            target_date=date(2025, 6, 1),
        )
        test_db.commit()

        deprecation = repo.add_object_to_campaign(
            campaign_id=campaign.id,
            object_id=catalog_objects[0].id,
            replacement_id=catalog_objects[1].id,
            migration_notes="Use new_table instead",
        )
        test_db.commit()

        assert deprecation.id is not None
        assert deprecation.campaign_id == campaign.id
        assert deprecation.object_id == catalog_objects[0].id
        assert deprecation.replacement_id == catalog_objects[1].id
        assert deprecation.migration_notes == "Use new_table instead"

    def test_get_deprecation(
        self, test_db: Session, source: DataSource, catalog_objects: list[CatalogObject]
    ):
        """Test getting deprecation by ID."""
        repo = DeprecationRepository(test_db)

        campaign = repo.create_campaign(
            source_id=source.id,
            name="Test",
            target_date=date(2025, 6, 1),
        )
        deprecation = repo.add_object_to_campaign(
            campaign_id=campaign.id,
            object_id=catalog_objects[0].id,
        )
        test_db.commit()

        retrieved = repo.get_deprecation(deprecation.id)
        assert retrieved is not None
        assert retrieved.object is not None
        assert retrieved.campaign is not None

    def test_get_deprecation_by_object(
        self, test_db: Session, source: DataSource, catalog_objects: list[CatalogObject]
    ):
        """Test getting deprecation by campaign and object."""
        repo = DeprecationRepository(test_db)

        campaign = repo.create_campaign(
            source_id=source.id,
            name="Test",
            target_date=date(2025, 6, 1),
        )
        repo.add_object_to_campaign(
            campaign_id=campaign.id,
            object_id=catalog_objects[0].id,
        )
        test_db.commit()

        retrieved = repo.get_deprecation_by_object(campaign.id, catalog_objects[0].id)
        assert retrieved is not None

        # Non-existent combination
        result = repo.get_deprecation_by_object(campaign.id, catalog_objects[1].id)
        assert result is None

    def test_list_deprecations(
        self, test_db: Session, source: DataSource, catalog_objects: list[CatalogObject]
    ):
        """Test listing deprecations."""
        repo = DeprecationRepository(test_db)

        campaign = repo.create_campaign(
            source_id=source.id,
            name="Test",
            target_date=date(2025, 6, 1),
        )
        repo.add_object_to_campaign(campaign.id, catalog_objects[0].id)
        repo.add_object_to_campaign(campaign.id, catalog_objects[1].id)
        test_db.commit()

        deprecations = repo.list_deprecations(campaign_id=campaign.id)
        assert len(deprecations) == 2

    def test_remove_object_from_campaign(
        self, test_db: Session, source: DataSource, catalog_objects: list[CatalogObject]
    ):
        """Test removing an object from a campaign."""
        repo = DeprecationRepository(test_db)

        campaign = repo.create_campaign(
            source_id=source.id,
            name="Test",
            target_date=date(2025, 6, 1),
        )
        deprecation = repo.add_object_to_campaign(
            campaign_id=campaign.id,
            object_id=catalog_objects[0].id,
        )
        test_db.commit()

        removed = repo.remove_object_from_campaign(deprecation.id)
        test_db.commit()

        assert removed is True
        assert repo.get_deprecation(deprecation.id) is None

    # =========================================================================
    # Aggregate Tests
    # =========================================================================

    def test_count_campaigns_by_status(self, test_db: Session, source: DataSource):
        """Test counting campaigns by status."""
        repo = DeprecationRepository(test_db)

        campaign1 = repo.create_campaign(
            source_id=source.id,
            name="Draft 1",
            target_date=date(2025, 6, 1),
        )
        campaign2 = repo.create_campaign(
            source_id=source.id,
            name="Draft 2",
            target_date=date(2025, 7, 1),
        )
        campaign3 = repo.create_campaign(
            source_id=source.id,
            name="Active",
            target_date=date(2025, 8, 1),
        )
        repo.update_campaign(campaign3.id, status="active")
        test_db.commit()

        counts = repo.count_campaigns_by_status()
        assert counts.get("draft", 0) == 2
        assert counts.get("active", 0) == 1

    def test_count_total_deprecated_objects(
        self, test_db: Session, source: DataSource, catalog_objects: list[CatalogObject]
    ):
        """Test counting total deprecated objects."""
        repo = DeprecationRepository(test_db)

        campaign = repo.create_campaign(
            source_id=source.id,
            name="Test",
            target_date=date(2025, 6, 1),
        )
        repo.add_object_to_campaign(campaign.id, catalog_objects[0].id)
        repo.add_object_to_campaign(campaign.id, catalog_objects[1].id)
        test_db.commit()

        count = repo.count_total_deprecated_objects()
        assert count == 2

    def test_get_upcoming_campaigns(self, test_db: Session, source: DataSource):
        """Test getting campaigns with upcoming deadlines."""
        repo = DeprecationRepository(test_db)

        today = date.today()

        # Create campaigns with different target dates
        repo.create_campaign(
            source_id=source.id,
            name="Soon",
            target_date=today + timedelta(days=7),
        )
        repo.create_campaign(
            source_id=source.id,
            name="Later",
            target_date=today + timedelta(days=60),  # Beyond 30 days
        )
        completed = repo.create_campaign(
            source_id=source.id,
            name="Completed",
            target_date=today + timedelta(days=5),
        )
        repo.update_campaign(completed.id, status="completed")
        test_db.commit()

        upcoming = repo.get_upcoming_campaigns(days=30)
        assert len(upcoming) == 1
        assert upcoming[0].name == "Soon"
