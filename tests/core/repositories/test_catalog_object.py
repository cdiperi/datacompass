"""Tests for CatalogObjectRepository."""

import pytest
from sqlalchemy.orm import Session

from datacompass.core.models import DataSource
from datacompass.core.repositories import CatalogObjectRepository, DataSourceRepository


class TestCatalogObjectRepository:
    """Test cases for CatalogObjectRepository."""

    @pytest.fixture
    def source(self, test_db: Session) -> DataSource:
        """Create a test data source."""
        repo = DataSourceRepository(test_db)
        source = repo.create(
            name="test-source",
            source_type="databricks",
            connection_info={},
        )
        test_db.commit()
        return source

    def test_upsert_creates_new(self, test_db: Session, source: DataSource):
        """Test that upsert creates new objects."""
        repo = CatalogObjectRepository(test_db)

        obj, action = repo.upsert(
            source_id=source.id,
            schema_name="analytics",
            object_name="customers",
            object_type="TABLE",
            source_metadata={"description": "Customer data"},
        )
        test_db.commit()

        assert action == "created"
        assert obj.id is not None
        assert obj.schema_name == "analytics"
        assert obj.object_name == "customers"
        assert obj.object_type == "TABLE"
        assert obj.source_metadata == {"description": "Customer data"}

    def test_upsert_updates_existing(self, test_db: Session, source: DataSource):
        """Test that upsert updates existing objects."""
        repo = CatalogObjectRepository(test_db)

        # Create initial
        obj1, action1 = repo.upsert(
            source_id=source.id,
            schema_name="analytics",
            object_name="customers",
            object_type="TABLE",
            source_metadata={"version": 1},
        )
        test_db.commit()
        original_id = obj1.id

        # Update
        obj2, action2 = repo.upsert(
            source_id=source.id,
            schema_name="analytics",
            object_name="customers",
            object_type="TABLE",
            source_metadata={"version": 2},
        )
        test_db.commit()

        assert action2 == "updated"
        assert obj2.id == original_id
        assert obj2.source_metadata == {"version": 2}

    def test_upsert_preserves_user_metadata(self, test_db: Session, source: DataSource):
        """Test that upsert preserves user metadata."""
        repo = CatalogObjectRepository(test_db)

        obj, _ = repo.upsert(
            source_id=source.id,
            schema_name="analytics",
            object_name="customers",
            object_type="TABLE",
        )
        test_db.commit()

        # Set user metadata
        obj.user_metadata = {"owner": "data-team", "tags": ["pii"]}
        test_db.commit()

        # Upsert again
        obj2, _ = repo.upsert(
            source_id=source.id,
            schema_name="analytics",
            object_name="customers",
            object_type="TABLE",
            source_metadata={"updated": True},
        )
        test_db.commit()

        # User metadata should be preserved
        assert obj2.user_metadata == {"owner": "data-team", "tags": ["pii"]}

    def test_upsert_undeletes(self, test_db: Session, source: DataSource):
        """Test that upsert un-deletes soft-deleted objects."""
        repo = CatalogObjectRepository(test_db)

        obj, _ = repo.upsert(
            source_id=source.id,
            schema_name="analytics",
            object_name="customers",
            object_type="TABLE",
        )
        test_db.commit()

        # Soft delete
        obj.soft_delete()
        test_db.commit()
        assert obj.deleted_at is not None

        # Upsert should un-delete
        obj2, action = repo.upsert(
            source_id=source.id,
            schema_name="analytics",
            object_name="customers",
            object_type="TABLE",
        )
        test_db.commit()

        assert action == "updated"
        assert obj2.deleted_at is None

    def test_get_by_source(self, test_db: Session, source: DataSource):
        """Test getting all objects for a source."""
        repo = CatalogObjectRepository(test_db)

        repo.upsert(source.id, "schema1", "table1", "TABLE")
        repo.upsert(source.id, "schema1", "table2", "TABLE")
        repo.upsert(source.id, "schema2", "view1", "VIEW")
        test_db.commit()

        objects = repo.get_by_source(source.id)
        assert len(objects) == 3

    def test_get_by_source_excludes_deleted(self, test_db: Session, source: DataSource):
        """Test that get_by_source excludes soft-deleted by default."""
        repo = CatalogObjectRepository(test_db)

        obj1, _ = repo.upsert(source.id, "schema1", "table1", "TABLE")
        obj2, _ = repo.upsert(source.id, "schema1", "table2", "TABLE")
        test_db.commit()

        obj1.soft_delete()
        test_db.commit()

        # Default excludes deleted
        objects = repo.get_by_source(source.id)
        assert len(objects) == 1

        # Can include deleted
        objects = repo.get_by_source(source.id, include_deleted=True)
        assert len(objects) == 2

    def test_soft_delete_missing(self, test_db: Session, source: DataSource):
        """Test soft-deleting objects not in current scan."""
        repo = CatalogObjectRepository(test_db)

        obj1, _ = repo.upsert(source.id, "schema1", "table1", "TABLE")
        obj2, _ = repo.upsert(source.id, "schema1", "table2", "TABLE")
        obj3, _ = repo.upsert(source.id, "schema1", "table3", "TABLE")
        test_db.commit()

        # Simulate scan that only found table1 and table2
        current_ids = {obj1.id, obj2.id}
        deleted_count = repo.soft_delete_missing(source.id, current_ids)
        test_db.commit()  # Commit changes from soft_delete

        assert deleted_count == 1
        test_db.refresh(obj3)
        assert obj3.deleted_at is not None

    def test_list_objects_with_filters(self, test_db: Session, source: DataSource):
        """Test listing objects with various filters."""
        repo = CatalogObjectRepository(test_db)

        repo.upsert(source.id, "schema1", "table1", "TABLE")
        repo.upsert(source.id, "schema1", "view1", "VIEW")
        repo.upsert(source.id, "schema2", "table2", "TABLE")
        test_db.commit()

        # Filter by type
        tables = repo.list_objects(source_id=source.id, object_type="TABLE")
        assert len(tables) == 2

        # Filter by schema
        schema1_objects = repo.list_objects(source_id=source.id, schema_name="schema1")
        assert len(schema1_objects) == 2

        # Combined filters
        schema2_tables = repo.list_objects(
            source_id=source.id,
            object_type="TABLE",
            schema_name="schema2",
        )
        assert len(schema2_tables) == 1
