"""Tests for SearchRepository."""

import pytest
from sqlalchemy.orm import Session

from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.repositories import DataSourceRepository, SearchRepository


class TestSearchRepository:
    """Test cases for SearchRepository."""

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
    def objects(self, test_db: Session, source: DataSource) -> list[CatalogObject]:
        """Create test catalog objects."""
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
                user_metadata={"tags": ["core"]},
            ),
            CatalogObject(
                source_id=source.id,
                schema_name="reporting",
                object_name="customer_summary",
                object_type="VIEW",
                user_metadata={"description": "Aggregated customer metrics"},
            ),
        ]
        test_db.add_all(objects)
        test_db.commit()
        return objects

    def test_reindex_all(self, test_db: Session, source: DataSource, objects: list[CatalogObject]):
        """Test reindexing all objects."""
        repo = SearchRepository(test_db)

        count = repo.reindex_all()
        test_db.commit()

        assert count == 3

    def test_search_by_name(self, test_db: Session, source: DataSource, objects: list[CatalogObject]):
        """Test searching by object name."""
        repo = SearchRepository(test_db)
        repo.reindex_all()
        test_db.commit()

        results = repo.search("customers")

        assert len(results) >= 1
        names = [r.object_name for r in results]
        assert "customers" in names or "customer_summary" in names

    def test_search_by_description(self, test_db: Session, source: DataSource, objects: list[CatalogObject]):
        """Test searching by description."""
        repo = SearchRepository(test_db)
        repo.reindex_all()
        test_db.commit()

        results = repo.search("transactions")

        assert len(results) == 1
        assert results[0].object_name == "orders"

    def test_search_by_tag(self, test_db: Session, source: DataSource, objects: list[CatalogObject]):
        """Test searching by tag."""
        repo = SearchRepository(test_db)
        repo.reindex_all()
        test_db.commit()

        results = repo.search("pii")

        assert len(results) == 1
        assert results[0].object_name == "customers"

    def test_search_filter_by_source(self, test_db: Session, source: DataSource, objects: list[CatalogObject]):
        """Test search with source filter."""
        repo = SearchRepository(test_db)
        repo.reindex_all()
        test_db.commit()

        results = repo.search("customer", source="test-source")
        assert len(results) >= 1

        results = repo.search("customer", source="nonexistent")
        assert len(results) == 0

    def test_search_filter_by_type(self, test_db: Session, source: DataSource, objects: list[CatalogObject]):
        """Test search with object type filter."""
        repo = SearchRepository(test_db)
        repo.reindex_all()
        test_db.commit()

        results = repo.search("customer", object_type="VIEW")
        assert len(results) == 1
        assert results[0].object_name == "customer_summary"

        results = repo.search("customer", object_type="TABLE")
        assert len(results) == 1
        assert results[0].object_name == "customers"

    def test_search_limit(self, test_db: Session, source: DataSource, objects: list[CatalogObject]):
        """Test search with limit."""
        repo = SearchRepository(test_db)
        repo.reindex_all()
        test_db.commit()

        results = repo.search("customer", limit=1)
        assert len(results) == 1

    def test_search_no_results(self, test_db: Session, source: DataSource, objects: list[CatalogObject]):
        """Test search returning no results."""
        repo = SearchRepository(test_db)
        repo.reindex_all()
        test_db.commit()

        results = repo.search("nonexistent_term")
        assert len(results) == 0

    def test_reindex_object(self, test_db: Session, source: DataSource, objects: list[CatalogObject]):
        """Test reindexing a single object."""
        repo = SearchRepository(test_db)

        # Index all first
        repo.reindex_all()
        test_db.commit()

        # Update object metadata
        obj = objects[0]
        obj.user_metadata = {"description": "Updated description", "tags": ["new_tag"]}
        test_db.commit()

        # Reindex single object
        repo.reindex_object(obj.id)
        test_db.commit()

        # Search should find updated content
        results = repo.search("new_tag")
        assert len(results) == 1
        assert results[0].object_name == "customers"

    def test_reindex_all_for_source(self, test_db: Session, source: DataSource, objects: list[CatalogObject]):
        """Test reindexing only objects for a specific source."""
        repo = SearchRepository(test_db)

        count = repo.reindex_all(source_id=source.id)
        test_db.commit()

        assert count == 3

    def test_delete_object_from_index(self, test_db: Session, source: DataSource, objects: list[CatalogObject]):
        """Test removing an object from the search index."""
        repo = SearchRepository(test_db)
        repo.reindex_all()
        test_db.commit()

        # Verify object is searchable
        results = repo.search("orders")
        assert len(results) == 1

        # Delete from index
        repo.delete_object(objects[1].id)
        test_db.commit()

        # Should no longer be found
        results = repo.search("orders")
        assert len(results) == 0
