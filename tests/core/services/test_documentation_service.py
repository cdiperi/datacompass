"""Tests for DocumentationService."""

import pytest
from sqlalchemy.orm import Session

from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.repositories import DataSourceRepository, SearchRepository
from datacompass.core.services import DocumentationService, ObjectNotFoundError


class TestDocumentationService:
    """Test cases for DocumentationService."""

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
    def obj(self, test_db: Session, source: DataSource) -> CatalogObject:
        """Create a test catalog object."""
        obj = CatalogObject(
            source_id=source.id,
            schema_name="analytics",
            object_name="customers",
            object_type="TABLE",
            source_metadata={"description": "Source description"},
        )
        test_db.add(obj)
        test_db.commit()
        return obj

    def test_set_description(self, test_db: Session, source: DataSource, obj: CatalogObject):
        """Test setting a description."""
        service = DocumentationService(test_db)

        result = service.set_description(
            "test-source.analytics.customers",
            "User-defined description",
        )
        test_db.commit()

        assert result.user_metadata["description"] == "User-defined description"

    def test_set_description_by_id(self, test_db: Session, source: DataSource, obj: CatalogObject):
        """Test setting description using object ID."""
        service = DocumentationService(test_db)

        result = service.set_description(str(obj.id), "Description by ID")
        test_db.commit()

        assert result.user_metadata["description"] == "Description by ID"

    def test_set_description_not_found(self, test_db: Session, source: DataSource):
        """Test setting description on nonexistent object."""
        service = DocumentationService(test_db)

        with pytest.raises(ObjectNotFoundError):
            service.set_description("nonexistent.schema.table", "Description")

    def test_get_description_user_metadata(self, test_db: Session, source: DataSource, obj: CatalogObject):
        """Test getting description from user_metadata."""
        service = DocumentationService(test_db)

        # Set user description
        service.set_description("test-source.analytics.customers", "User description")
        test_db.commit()

        # Should return user description
        desc = service.get_description("test-source.analytics.customers")
        assert desc == "User description"

    def test_get_description_falls_back_to_source(self, test_db: Session, source: DataSource, obj: CatalogObject):
        """Test getting description falls back to source_metadata."""
        service = DocumentationService(test_db)

        # No user description set, should return source description
        desc = service.get_description("test-source.analytics.customers")
        assert desc == "Source description"

    def test_get_description_none(self, test_db: Session, source: DataSource):
        """Test getting description when none exists."""
        # Create object without any description
        obj = CatalogObject(
            source_id=source.id,
            schema_name="raw",
            object_name="events",
            object_type="TABLE",
        )
        test_db.add(obj)
        test_db.commit()

        service = DocumentationService(test_db)
        desc = service.get_description("test-source.raw.events")
        assert desc is None

    def test_add_tag(self, test_db: Session, source: DataSource, obj: CatalogObject):
        """Test adding a tag."""
        service = DocumentationService(test_db)

        result = service.add_tag("test-source.analytics.customers", "pii")
        test_db.commit()

        assert "pii" in result.user_metadata["tags"]

    def test_add_tag_idempotent(self, test_db: Session, source: DataSource, obj: CatalogObject):
        """Test that adding same tag twice is idempotent."""
        service = DocumentationService(test_db)

        service.add_tag("test-source.analytics.customers", "pii")
        result = service.add_tag("test-source.analytics.customers", "pii")
        test_db.commit()

        assert result.user_metadata["tags"].count("pii") == 1

    def test_remove_tag(self, test_db: Session, source: DataSource, obj: CatalogObject):
        """Test removing a tag."""
        service = DocumentationService(test_db)

        # Add then remove
        service.add_tag("test-source.analytics.customers", "pii")
        result = service.remove_tag("test-source.analytics.customers", "pii")
        test_db.commit()

        assert "pii" not in result.user_metadata.get("tags", [])

    def test_remove_nonexistent_tag(self, test_db: Session, source: DataSource, obj: CatalogObject):
        """Test removing a tag that doesn't exist."""
        service = DocumentationService(test_db)

        # Should not raise
        result = service.remove_tag("test-source.analytics.customers", "nonexistent")
        test_db.commit()

        assert result is not None

    def test_get_tags(self, test_db: Session, source: DataSource, obj: CatalogObject):
        """Test getting all tags."""
        service = DocumentationService(test_db)

        service.add_tag("test-source.analytics.customers", "pii")
        service.add_tag("test-source.analytics.customers", "core")
        test_db.commit()

        tags = service.get_tags("test-source.analytics.customers")
        assert "pii" in tags
        assert "core" in tags

    def test_get_tags_empty(self, test_db: Session, source: DataSource, obj: CatalogObject):
        """Test getting tags when none exist."""
        service = DocumentationService(test_db)

        tags = service.get_tags("test-source.analytics.customers")
        assert tags == []

    def test_add_tags_multiple(self, test_db: Session, source: DataSource, obj: CatalogObject):
        """Test adding multiple tags at once."""
        service = DocumentationService(test_db)

        result = service.add_tags("test-source.analytics.customers", ["pii", "core", "finance"])
        test_db.commit()

        assert "pii" in result.user_metadata["tags"]
        assert "core" in result.user_metadata["tags"]
        assert "finance" in result.user_metadata["tags"]

    def test_remove_tags_multiple(self, test_db: Session, source: DataSource, obj: CatalogObject):
        """Test removing multiple tags at once."""
        service = DocumentationService(test_db)

        # Add tags
        service.add_tags("test-source.analytics.customers", ["pii", "core", "finance"])
        test_db.commit()

        # Remove some
        result = service.remove_tags("test-source.analytics.customers", ["pii", "finance"])
        test_db.commit()

        assert "pii" not in result.user_metadata["tags"]
        assert "finance" not in result.user_metadata["tags"]
        assert "core" in result.user_metadata["tags"]

    def test_documentation_updates_search_index(
        self, test_db: Session, source: DataSource, obj: CatalogObject
    ):
        """Test that setting description updates the search index."""
        doc_service = DocumentationService(test_db)
        search_repo = SearchRepository(test_db)

        # Initially not indexed
        results = search_repo.search("unique_term")
        assert len(results) == 0

        # Set description with unique term
        doc_service.set_description("test-source.analytics.customers", "Contains unique_term here")
        test_db.commit()

        # Now should be searchable
        results = search_repo.search("unique_term")
        assert len(results) == 1
        assert results[0].object_name == "customers"

    def test_tags_update_search_index(
        self, test_db: Session, source: DataSource, obj: CatalogObject
    ):
        """Test that adding tags updates the search index."""
        doc_service = DocumentationService(test_db)
        search_repo = SearchRepository(test_db)

        # Initially not indexed
        results = search_repo.search("special_tag")
        assert len(results) == 0

        # Add tag
        doc_service.add_tag("test-source.analytics.customers", "special_tag")
        test_db.commit()

        # Now should be searchable
        results = search_repo.search("special_tag")
        assert len(results) == 1
        assert results[0].object_name == "customers"
