"""Tests for DependencyRepository."""

import pytest
from sqlalchemy.orm import Session

from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.repositories import (
    CatalogObjectRepository,
    DataSourceRepository,
    DependencyRepository,
)


class TestDependencyRepository:
    """Test cases for DependencyRepository."""

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

    @pytest.fixture
    def objects(self, test_db: Session, source: DataSource) -> list[CatalogObject]:
        """Create test catalog objects."""
        repo = CatalogObjectRepository(test_db)

        # Create table -> view dependency chain
        # raw_data -> processed_data -> summary_view
        obj1, _ = repo.upsert(source.id, "core", "raw_data", "TABLE")
        obj2, _ = repo.upsert(source.id, "core", "processed_data", "TABLE")
        obj3, _ = repo.upsert(source.id, "analytics", "summary_view", "VIEW")
        obj4, _ = repo.upsert(source.id, "core", "users", "TABLE")
        test_db.commit()
        return [obj1, obj2, obj3, obj4]

    def test_upsert_creates_new(self, test_db: Session, source: DataSource, objects: list):
        """Test that upsert creates new dependencies."""
        repo = DependencyRepository(test_db)
        raw_data, processed_data, _, _ = objects

        dep, action = repo.upsert(
            source_id=source.id,
            object_id=processed_data.id,
            target_id=raw_data.id,
            dependency_type="DIRECT",
            parsing_source="source_metadata",
        )
        test_db.commit()

        assert action == "created"
        assert dep.id is not None
        assert dep.object_id == processed_data.id
        assert dep.target_id == raw_data.id
        assert dep.dependency_type == "DIRECT"
        assert dep.confidence == "HIGH"

    def test_upsert_updates_existing(self, test_db: Session, source: DataSource, objects: list):
        """Test that upsert updates existing dependencies."""
        repo = DependencyRepository(test_db)
        raw_data, processed_data, _, _ = objects

        # Create initial
        dep1, action1 = repo.upsert(
            source_id=source.id,
            object_id=processed_data.id,
            target_id=raw_data.id,
            dependency_type="DIRECT",
            parsing_source="source_metadata",
            confidence="LOW",
        )
        test_db.commit()
        original_id = dep1.id

        # Update
        dep2, action2 = repo.upsert(
            source_id=source.id,
            object_id=processed_data.id,
            target_id=raw_data.id,
            dependency_type="DIRECT",
            parsing_source="source_metadata",
            confidence="HIGH",
        )
        test_db.commit()

        assert action2 == "updated"
        assert dep2.id == original_id
        assert dep2.confidence == "HIGH"

    def test_upsert_batch(self, test_db: Session, source: DataSource, objects: list):
        """Test batch upsert of dependencies."""
        repo = DependencyRepository(test_db)
        raw_data, processed_data, summary_view, users = objects

        dependencies = [
            {
                "object_id": processed_data.id,
                "target_id": raw_data.id,
                "dependency_type": "DIRECT",
            },
            {
                "object_id": summary_view.id,
                "target_id": processed_data.id,
                "dependency_type": "DIRECT",
            },
            {
                "object_id": summary_view.id,
                "target_id": users.id,
                "dependency_type": "DIRECT",
            },
        ]

        created, updated = repo.upsert_batch(
            source_id=source.id,
            dependencies=dependencies,
            parsing_source="source_metadata",
        )
        test_db.commit()

        assert created == 3
        assert updated == 0

    def test_get_upstream(self, test_db: Session, source: DataSource, objects: list):
        """Test getting upstream dependencies."""
        repo = DependencyRepository(test_db)
        raw_data, processed_data, summary_view, users = objects

        # summary_view depends on processed_data and users
        repo.upsert(source.id, summary_view.id, processed_data.id, "DIRECT", "source_metadata")
        repo.upsert(source.id, summary_view.id, users.id, "DIRECT", "source_metadata")
        test_db.commit()

        upstream = repo.get_upstream(summary_view.id)
        assert len(upstream) == 2
        target_ids = {d.target_id for d in upstream}
        assert target_ids == {processed_data.id, users.id}

    def test_get_downstream(self, test_db: Session, source: DataSource, objects: list):
        """Test getting downstream dependents."""
        repo = DependencyRepository(test_db)
        raw_data, processed_data, summary_view, _ = objects

        # processed_data depends on raw_data
        # summary_view depends on processed_data
        repo.upsert(source.id, processed_data.id, raw_data.id, "DIRECT", "source_metadata")
        repo.upsert(source.id, summary_view.id, processed_data.id, "DIRECT", "source_metadata")
        test_db.commit()

        # raw_data has one downstream dependent (processed_data)
        downstream = repo.get_downstream(raw_data.id)
        assert len(downstream) == 1
        assert downstream[0].object_id == processed_data.id

        # processed_data has one downstream dependent (summary_view)
        downstream = repo.get_downstream(processed_data.id)
        assert len(downstream) == 1
        assert downstream[0].object_id == summary_view.id

    def test_external_dependency(self, test_db: Session, source: DataSource, objects: list):
        """Test handling external dependencies (target not in catalog)."""
        repo = DependencyRepository(test_db)
        _, processed_data, _, _ = objects

        dep, _ = repo.upsert(
            source_id=source.id,
            object_id=processed_data.id,
            target_id=None,
            dependency_type="DIRECT",
            parsing_source="source_metadata",
            target_external={
                "schema": "external",
                "name": "third_party_data",
                "type": "TABLE",
            },
        )
        test_db.commit()

        assert dep.target_id is None
        assert dep.target_external["name"] == "third_party_data"

        upstream = repo.get_upstream(processed_data.id)
        assert len(upstream) == 1
        assert upstream[0].target_external is not None

    def test_delete_by_source(self, test_db: Session, source: DataSource, objects: list):
        """Test deleting all dependencies for a source."""
        repo = DependencyRepository(test_db)
        raw_data, processed_data, summary_view, _ = objects

        repo.upsert(source.id, processed_data.id, raw_data.id, "DIRECT", "source_metadata")
        repo.upsert(source.id, summary_view.id, processed_data.id, "DIRECT", "source_metadata")
        test_db.commit()

        assert len(repo.get_by_source(source.id)) == 2

        deleted = repo.delete_by_source(source.id)
        test_db.commit()

        assert deleted == 2
        assert len(repo.get_by_source(source.id)) == 0

    def test_delete_by_parsing_source(self, test_db: Session, source: DataSource, objects: list):
        """Test deleting dependencies from specific parsing source."""
        repo = DependencyRepository(test_db)
        raw_data, processed_data, summary_view, _ = objects

        # Add dependencies from different sources
        repo.upsert(source.id, processed_data.id, raw_data.id, "DIRECT", "source_metadata")
        repo.upsert(source.id, summary_view.id, processed_data.id, "DIRECT", "manual")
        test_db.commit()

        assert len(repo.get_by_source(source.id)) == 2

        # Only delete source_metadata dependencies
        deleted = repo.delete_by_parsing_source(source.id, "source_metadata")
        test_db.commit()

        assert deleted == 1
        deps = repo.get_by_source(source.id)
        assert len(deps) == 1
        assert deps[0].parsing_source == "manual"

    def test_count_by_object(self, test_db: Session, source: DataSource, objects: list):
        """Test counting dependencies for an object."""
        repo = DependencyRepository(test_db)
        raw_data, processed_data, summary_view, users = objects

        # processed_data depends on raw_data
        # summary_view depends on processed_data
        repo.upsert(source.id, processed_data.id, raw_data.id, "DIRECT", "source_metadata")
        repo.upsert(source.id, summary_view.id, processed_data.id, "DIRECT", "source_metadata")
        test_db.commit()

        # raw_data: 0 upstream, 1 downstream
        counts = repo.count_by_object(raw_data.id)
        assert counts["upstream"] == 0
        assert counts["downstream"] == 1

        # processed_data: 1 upstream, 1 downstream
        counts = repo.count_by_object(processed_data.id)
        assert counts["upstream"] == 1
        assert counts["downstream"] == 1

        # summary_view: 1 upstream, 0 downstream
        counts = repo.count_by_object(summary_view.id)
        assert counts["upstream"] == 1
        assert counts["downstream"] == 0
