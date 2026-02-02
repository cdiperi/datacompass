"""Tests for DataSourceRepository."""

from sqlalchemy.orm import Session

from datacompass.core.repositories import DataSourceRepository


class TestDataSourceRepository:
    """Test cases for DataSourceRepository."""

    def test_create_source(self, test_db: Session):
        """Test creating a new data source."""
        repo = DataSourceRepository(test_db)

        source = repo.create(
            name="test-source",
            source_type="databricks",
            connection_info={"host": "test.databricks.net"},
            display_name="Test Source",
        )
        test_db.commit()

        assert source.id is not None
        assert source.name == "test-source"
        assert source.source_type == "databricks"
        assert source.connection_info == {"host": "test.databricks.net"}
        assert source.display_name == "Test Source"
        assert source.is_active is True

    def test_get_by_name(self, test_db: Session):
        """Test retrieving a source by name."""
        repo = DataSourceRepository(test_db)

        # Create source
        repo.create(name="my-source", source_type="databricks", connection_info={})
        test_db.commit()

        # Retrieve by name
        source = repo.get_by_name("my-source")
        assert source is not None
        assert source.name == "my-source"

        # Non-existent name returns None
        assert repo.get_by_name("nonexistent") is None

    def test_exists(self, test_db: Session):
        """Test checking if a source exists."""
        repo = DataSourceRepository(test_db)

        assert repo.exists("test") is False

        repo.create(name="test", source_type="databricks", connection_info={})
        test_db.commit()

        assert repo.exists("test") is True

    def test_get_active(self, test_db: Session):
        """Test getting only active sources."""
        repo = DataSourceRepository(test_db)

        # Create active and inactive sources
        repo.create(name="active", source_type="databricks", connection_info={})
        inactive = repo.create(name="inactive", source_type="databricks", connection_info={})
        test_db.commit()

        inactive.is_active = False
        test_db.commit()

        # Get active sources
        sources = repo.get_active()
        assert len(sources) == 1
        assert sources[0].name == "active"

    def test_update_scan_status(self, test_db: Session):
        """Test updating scan status."""
        repo = DataSourceRepository(test_db)

        source = repo.create(name="test", source_type="databricks", connection_info={})
        test_db.commit()

        # Update status
        repo.update_scan_status(source, "success", "Scanned 10 objects")
        test_db.commit()

        assert source.last_scan_at is not None
        assert source.last_scan_status == "success"
        assert source.last_scan_message == "Scanned 10 objects"

    def test_deactivate_and_activate(self, test_db: Session):
        """Test deactivating and reactivating a source."""
        repo = DataSourceRepository(test_db)

        source = repo.create(name="test", source_type="databricks", connection_info={})
        test_db.commit()
        assert source.is_active is True

        repo.deactivate(source)
        test_db.commit()
        assert source.is_active is False

        repo.activate(source)
        test_db.commit()
        assert source.is_active is True

    def test_get_by_type(self, test_db: Session):
        """Test filtering sources by type."""
        repo = DataSourceRepository(test_db)

        repo.create(name="db1", source_type="databricks", connection_info={})
        repo.create(name="db2", source_type="databricks", connection_info={})
        repo.create(name="pg1", source_type="postgresql", connection_info={})
        test_db.commit()

        databricks_sources = repo.get_by_type("databricks")
        assert len(databricks_sources) == 2

        pg_sources = repo.get_by_type("postgresql")
        assert len(pg_sources) == 1
