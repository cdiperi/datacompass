"""Tests for search endpoint."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from datacompass.core.adapters import AdapterRegistry
from datacompass.core.adapters.schemas import DatabricksConfig


def setup_source_with_real_objects(client: TestClient, test_session_factory) -> None:
    """Helper to create a source and directly insert objects for testing.

    This bypasses the scan process to avoid asyncio issues while still providing
    real test data for search tests.
    """
    from datacompass.core.models import CatalogObject, Column
    from datacompass.core.repositories import SearchRepository

    with patch.object(AdapterRegistry, "is_registered", return_value=True):
        with patch.object(AdapterRegistry, "get_config_schema", return_value=DatabricksConfig):
            resp = client.post(
                "/api/v1/sources",
                json={
                    "name": "test-source",
                    "source_type": "databricks",
                    "connection_info": {
                        "host": "test.azuredatabricks.net",
                        "http_path": "/sql/1.0/warehouses/test",
                        "catalog": "main",
                        "auth_method": "personal_token",
                        "access_token": "test-token",
                    },
                },
            )
            source_id = resp.json()["id"]

    # Directly insert test objects
    session = test_session_factory()
    try:
        # Create objects
        obj1 = CatalogObject(
            source_id=source_id,
            schema_name="analytics",
            object_name="customers",
            object_type="TABLE",
            source_metadata={"description": "Customer data"},
        )
        obj2 = CatalogObject(
            source_id=source_id,
            schema_name="analytics",
            object_name="orders",
            object_type="TABLE",
            source_metadata={"description": "Order data"},
        )
        session.add_all([obj1, obj2])
        session.flush()

        # Create columns
        col1 = Column(object_id=obj1.id, column_name="id", position=1, source_metadata={"data_type": "INTEGER"})
        col2 = Column(object_id=obj1.id, column_name="name", position=2, source_metadata={"data_type": "STRING"})
        col3 = Column(object_id=obj2.id, column_name="order_id", position=1, source_metadata={"data_type": "INTEGER"})
        session.add_all([col1, col2, col3])
        session.flush()

        # Reindex FTS
        search_repo = SearchRepository(session)
        search_repo.reindex_all(source_id=source_id)

        session.commit()
    finally:
        session.close()


class TestSearch:
    """Tests for GET /api/v1/search."""

    def test_search_no_results(self, client: TestClient):
        """Returns empty list when no matches found."""
        response = client.get("/api/v1/search?q=nonexistent")

        assert response.status_code == 200
        assert response.json() == []

    def test_search_by_object_name(self, client: TestClient, test_session_factory):
        """Finds objects by name."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.get("/api/v1/search?q=customers")

        assert response.status_code == 200
        results = response.json()
        assert len(results) >= 1
        assert any(r["object_name"] == "customers" for r in results)

    def test_search_includes_rank(self, client: TestClient, test_session_factory):
        """Search results include relevance rank."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.get("/api/v1/search?q=customers")

        assert response.status_code == 200
        results = response.json()
        assert len(results) >= 1
        assert "rank" in results[0]

    def test_search_filter_by_source(self, client: TestClient, test_session_factory):
        """Filters search results by source."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.get("/api/v1/search?q=customers&source=test-source")

        assert response.status_code == 200
        results = response.json()
        assert all(r["source_name"] == "test-source" for r in results)

    def test_search_filter_by_type(self, client: TestClient, test_session_factory):
        """Filters search results by object type."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.get("/api/v1/search?q=analytics&object_type=TABLE")

        assert response.status_code == 200
        results = response.json()
        assert all(r["object_type"] == "TABLE" for r in results)

    def test_search_with_limit(self, client: TestClient, test_session_factory):
        """Respects limit parameter."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.get("/api/v1/search?q=analytics&limit=1")

        assert response.status_code == 200
        results = response.json()
        assert len(results) <= 1

    def test_search_requires_query(self, client: TestClient):
        """Returns 422 when query is missing."""
        response = client.get("/api/v1/search")

        assert response.status_code == 422

    def test_search_empty_query(self, client: TestClient):
        """Returns 422 for empty query string."""
        response = client.get("/api/v1/search?q=")

        assert response.status_code == 422

    def test_search_limit_bounds(self, client: TestClient, test_session_factory):
        """Limit is bounded between 1 and 200."""
        setup_source_with_real_objects(client, test_session_factory)

        # Zero should fail
        response = client.get("/api/v1/search?q=customers&limit=0")
        assert response.status_code == 422

        # Over 200 should fail
        response = client.get("/api/v1/search?q=customers&limit=201")
        assert response.status_code == 422

        # Valid limits work
        response = client.get("/api/v1/search?q=customers&limit=1")
        assert response.status_code == 200

        response = client.get("/api/v1/search?q=customers&limit=200")
        assert response.status_code == 200

    def test_search_highlights(self, client: TestClient, test_session_factory):
        """Search results include highlights dict."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.get("/api/v1/search?q=customers")

        assert response.status_code == 200
        results = response.json()
        if results:
            assert "highlights" in results[0]
            assert isinstance(results[0]["highlights"], dict)
