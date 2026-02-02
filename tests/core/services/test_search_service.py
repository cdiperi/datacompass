"""Tests for SearchService."""

import pytest
from sqlalchemy.orm import Session

from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.repositories import DataSourceRepository, SearchRepository
from datacompass.core.services import SearchService


class TestSearchService:
    """Test cases for SearchService."""

    @pytest.fixture
    def source(self, test_db: Session) -> DataSource:
        """Create a test data source."""
        repo = DataSourceRepository(test_db)
        source = repo.create(
            name="test-source",
            source_type="databricks",
            connection_info={"host": "test.example.com"},
        )
        test_db.commit()
        return source

    @pytest.fixture
    def indexed_objects(self, test_db: Session, source: DataSource) -> list[CatalogObject]:
        """Create and index test catalog objects."""
        objects = [
            CatalogObject(
                source_id=source.id,
                schema_name="analytics",
                object_name="customers",
                object_type="TABLE",
                source_metadata={"description": "Customer master data"},
                user_metadata={"tags": ["pii", "core"]},
            ),
            CatalogObject(
                source_id=source.id,
                schema_name="analytics",
                object_name="orders",
                object_type="TABLE",
                source_metadata={"description": "Order transactions"},
            ),
        ]
        test_db.add_all(objects)
        test_db.commit()

        # Index objects
        search_repo = SearchRepository(test_db)
        search_repo.reindex_all()
        test_db.commit()

        return objects

    def test_search_returns_response_objects(
        self, test_db: Session, source: DataSource, indexed_objects: list[CatalogObject]
    ):
        """Test that search returns SearchResultResponse objects."""
        service = SearchService(test_db)

        results = service.search("customers")

        assert len(results) == 1
        result = results[0]
        assert result.source_name == "test-source"
        assert result.schema_name == "analytics"
        assert result.object_name == "customers"
        assert result.object_type == "TABLE"
        assert result.rank is not None

    def test_search_with_filters(
        self, test_db: Session, source: DataSource, indexed_objects: list[CatalogObject]
    ):
        """Test search with source and type filters."""
        service = SearchService(test_db)

        # Filter by source
        results = service.search("analytics", source="test-source")
        assert len(results) == 2

        # Filter by nonexistent source
        results = service.search("analytics", source="nonexistent")
        assert len(results) == 0

    def test_search_includes_tags(
        self, test_db: Session, source: DataSource, indexed_objects: list[CatalogObject]
    ):
        """Test that search results include tags."""
        service = SearchService(test_db)

        results = service.search("pii")

        assert len(results) == 1
        assert "pii" in results[0].tags
        assert "core" in results[0].tags

    def test_reindex(
        self, test_db: Session, source: DataSource
    ):
        """Test reindex method."""
        # Add an object without indexing
        obj = CatalogObject(
            source_id=source.id,
            schema_name="raw",
            object_name="events",
            object_type="TABLE",
        )
        test_db.add(obj)
        test_db.commit()

        service = SearchService(test_db)

        # Before reindex, no results
        results = service.search("events")
        assert len(results) == 0

        # Reindex
        count = service.reindex()
        test_db.commit()
        assert count == 1

        # After reindex, found
        results = service.search("events")
        assert len(results) == 1

    def test_reindex_specific_source(
        self, test_db: Session, source: DataSource, indexed_objects: list[CatalogObject]
    ):
        """Test reindex for specific source."""
        service = SearchService(test_db)

        # Reindex only test-source
        count = service.reindex(source="test-source")
        test_db.commit()

        assert count == 2

    def test_search_empty_results(self, test_db: Session, source: DataSource):
        """Test search with no matching results."""
        service = SearchService(test_db)

        results = service.search("nonexistent")

        assert len(results) == 0
