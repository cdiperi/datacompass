"""Tests for objects endpoints."""

from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from datacompass.core.adapters import AdapterRegistry
from datacompass.core.adapters.schemas import DatabricksConfig
from datacompass.core.models import ScanResult, ScanStats
from datacompass.core.services import CatalogService


def setup_source_with_objects(client: TestClient) -> None:
    """Helper to create a source and scan it to populate objects.

    Uses mocked scan_source to avoid asyncio.run() issues in test event loop.
    """
    with patch.object(AdapterRegistry, "is_registered", return_value=True):
        with patch.object(AdapterRegistry, "get_config_schema", return_value=DatabricksConfig):
            client.post(
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

    # Use real scan but with mocked adapter to avoid async issues
    # We need to directly insert test data instead
    mock_result = ScanResult(
        source_name="test-source",
        source_type="databricks",
        status="success",
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        duration_seconds=0.5,
        stats=ScanStats(objects_created=2, total_objects=2),
    )

    with patch.object(CatalogService, "scan_source", return_value=mock_result):
        client.post("/api/v1/sources/test-source/scan")


def setup_source_with_real_objects(client: TestClient, test_session_factory) -> None:
    """Helper to create a source and directly insert objects for testing.

    This bypasses the scan process to avoid asyncio issues while still providing
    real test data for object/search tests.
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


class TestListObjects:
    """Tests for GET /api/v1/objects."""

    def test_list_objects_empty(self, client: TestClient):
        """Returns empty list when no objects exist."""
        response = client.get("/api/v1/objects")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_objects_with_objects(self, client: TestClient, test_session_factory):
        """Returns list of catalog objects."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.get("/api/v1/objects")

        assert response.status_code == 200
        objects = response.json()
        assert len(objects) == 2
        assert any(obj["object_name"] == "customers" for obj in objects)
        assert any(obj["object_name"] == "orders" for obj in objects)

    def test_list_objects_filter_by_source(self, client: TestClient, test_session_factory):
        """Filters objects by source name."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.get("/api/v1/objects?source=test-source")

        assert response.status_code == 200
        objects = response.json()
        assert len(objects) == 2
        assert all(obj["source_name"] == "test-source" for obj in objects)

    def test_list_objects_filter_by_type(self, client: TestClient, test_session_factory):
        """Filters objects by type."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.get("/api/v1/objects?object_type=TABLE")

        assert response.status_code == 200
        objects = response.json()
        assert len(objects) == 2
        assert all(obj["object_type"] == "TABLE" for obj in objects)

    def test_list_objects_filter_by_schema(self, client: TestClient, test_session_factory):
        """Filters objects by schema name."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.get("/api/v1/objects?schema=analytics")

        assert response.status_code == 200
        objects = response.json()
        assert len(objects) == 2
        assert all(obj["schema_name"] == "analytics" for obj in objects)

    def test_list_objects_pagination(self, client: TestClient, test_session_factory):
        """Supports limit and offset for pagination."""
        setup_source_with_real_objects(client, test_session_factory)

        # Get first object
        response = client.get("/api/v1/objects?limit=1")
        assert response.status_code == 200
        assert len(response.json()) == 1

        # Get second object
        response = client.get("/api/v1/objects?limit=1&offset=1")
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestGetObject:
    """Tests for GET /api/v1/objects/{id}."""

    def test_get_object_by_id(self, client: TestClient, test_session_factory):
        """Returns object details by numeric ID."""
        setup_source_with_real_objects(client, test_session_factory)

        # Get list to find an ID
        list_response = client.get("/api/v1/objects")
        object_id = list_response.json()[0]["id"]

        response = client.get(f"/api/v1/objects/{object_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == object_id
        assert "columns" in data
        assert len(data["columns"]) > 0

    def test_get_object_by_qualified_name(self, client: TestClient, test_session_factory):
        """Returns object details by qualified name."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.get("/api/v1/objects/test-source.analytics.customers")

        assert response.status_code == 200
        data = response.json()
        assert data["source_name"] == "test-source"
        assert data["schema_name"] == "analytics"
        assert data["object_name"] == "customers"
        assert "columns" in data

    def test_get_object_not_found(self, client: TestClient):
        """Returns 404 when object not found."""
        response = client.get("/api/v1/objects/999")

        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "object_not_found"

    def test_get_object_includes_columns(self, client: TestClient, test_session_factory):
        """Object details include column information."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.get("/api/v1/objects/test-source.analytics.customers")

        assert response.status_code == 200
        data = response.json()
        assert "columns" in data
        columns = data["columns"]
        assert len(columns) == 2
        assert any(col["column_name"] == "id" for col in columns)
        assert any(col["column_name"] == "name" for col in columns)


class TestUpdateObject:
    """Tests for PATCH /api/v1/objects/{id}."""

    def test_update_description(self, client: TestClient, test_session_factory):
        """Updates object description."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.patch(
            "/api/v1/objects/test-source.analytics.customers",
            json={"description": "Main customer table"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_metadata"]["description"] == "Main customer table"

    def test_add_tags(self, client: TestClient, test_session_factory):
        """Adds tags to an object."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.patch(
            "/api/v1/objects/test-source.analytics.customers",
            json={"tags_to_add": ["pii", "important"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "pii" in data["user_metadata"]["tags"]
        assert "important" in data["user_metadata"]["tags"]

    def test_remove_tags(self, client: TestClient, test_session_factory):
        """Removes tags from an object."""
        setup_source_with_real_objects(client, test_session_factory)

        # First add tags
        client.patch(
            "/api/v1/objects/test-source.analytics.customers",
            json={"tags_to_add": ["pii", "important", "sensitive"]},
        )

        # Then remove some
        response = client.patch(
            "/api/v1/objects/test-source.analytics.customers",
            json={"tags_to_remove": ["pii", "sensitive"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "pii" not in data["user_metadata"]["tags"]
        assert "sensitive" not in data["user_metadata"]["tags"]
        assert "important" in data["user_metadata"]["tags"]

    def test_update_multiple_fields(self, client: TestClient, test_session_factory):
        """Updates description and tags in single request."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.patch(
            "/api/v1/objects/test-source.analytics.customers",
            json={
                "description": "Customer master data",
                "tags_to_add": ["master-data"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_metadata"]["description"] == "Customer master data"
        assert "master-data" in data["user_metadata"]["tags"]

    def test_update_object_not_found(self, client: TestClient):
        """Returns 404 when object not found."""
        response = client.patch(
            "/api/v1/objects/999",
            json={"description": "Test"},
        )

        assert response.status_code == 404

    def test_update_empty_request(self, client: TestClient, test_session_factory):
        """Empty request returns object unchanged."""
        setup_source_with_real_objects(client, test_session_factory)

        response = client.patch(
            "/api/v1/objects/test-source.analytics.customers",
            json={},
        )

        assert response.status_code == 200
