"""Tests for sources endpoints."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from datacompass.core.adapters import AdapterRegistry
from datacompass.core.adapters.schemas import DatabricksConfig


class TestListSources:
    """Tests for GET /api/v1/sources."""

    def test_list_sources_empty(self, client: TestClient):
        """Returns empty list when no sources configured."""
        response = client.get("/api/v1/sources")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_sources_with_sources(self, client_with_source: TestClient):
        """Returns list of configured sources."""
        response = client_with_source.get("/api/v1/sources")

        assert response.status_code == 200
        sources = response.json()
        assert len(sources) == 1
        assert sources[0]["name"] == "test-source"
        assert sources[0]["source_type"] == "databricks"
        assert sources[0]["display_name"] == "Test Source"


class TestCreateSource:
    """Tests for POST /api/v1/sources."""

    def test_create_source_success(self, client: TestClient):
        """Successfully creates a new source."""
        with patch.object(AdapterRegistry, "is_registered", return_value=True):
            with patch.object(AdapterRegistry, "get_config_schema", return_value=DatabricksConfig):
                response = client.post(
                    "/api/v1/sources",
                    json={
                        "name": "prod",
                        "source_type": "databricks",
                        "connection_info": {
                            "host": "prod.azuredatabricks.net",
                            "http_path": "/sql/1.0/warehouses/prod",
                            "catalog": "main",
                            "auth_method": "personal_token",
                            "access_token": "prod-token",
                        },
                    },
                )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "prod"
        assert data["source_type"] == "databricks"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_source_with_display_name(self, client: TestClient):
        """Creates source with optional display name."""
        with patch.object(AdapterRegistry, "is_registered", return_value=True):
            with patch.object(AdapterRegistry, "get_config_schema", return_value=DatabricksConfig):
                response = client.post(
                    "/api/v1/sources",
                    json={
                        "name": "prod",
                        "source_type": "databricks",
                        "display_name": "Production Databricks",
                        "connection_info": {
                            "host": "prod.azuredatabricks.net",
                            "http_path": "/sql/1.0/warehouses/prod",
                            "catalog": "main",
                            "auth_method": "personal_token",
                            "access_token": "prod-token",
                        },
                    },
                )

        assert response.status_code == 201
        assert response.json()["display_name"] == "Production Databricks"

    def test_create_source_duplicate_name(self, client_with_source: TestClient):
        """Returns 409 when source name already exists."""
        with patch.object(AdapterRegistry, "is_registered", return_value=True):
            with patch.object(AdapterRegistry, "get_config_schema", return_value=DatabricksConfig):
                response = client_with_source.post(
                    "/api/v1/sources",
                    json={
                        "name": "test-source",  # Already exists
                        "source_type": "databricks",
                        "connection_info": {
                            "host": "other.azuredatabricks.net",
                            "http_path": "/sql/1.0/warehouses/other",
                            "catalog": "main",
                            "auth_method": "personal_token",
                            "access_token": "other-token",
                        },
                    },
                )

        assert response.status_code == 409
        data = response.json()
        assert data["error"] == "source_exists"
        assert "test-source" in data["message"]

    def test_create_source_invalid_adapter_type(self, client: TestClient):
        """Returns 400 when source type is not registered."""
        with patch.object(AdapterRegistry, "is_registered", return_value=False):
            response = client.post(
                "/api/v1/sources",
                json={
                    "name": "invalid",
                    "source_type": "unknown_type",
                    "connection_info": {"host": "localhost"},
                },
            )

        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "invalid_source_type"

    def test_create_source_missing_name(self, client: TestClient):
        """Returns 422 when name is missing."""
        response = client.post(
            "/api/v1/sources",
            json={
                "source_type": "databricks",
                "connection_info": {"host": "localhost"},
            },
        )

        assert response.status_code == 422


class TestGetSource:
    """Tests for GET /api/v1/sources/{name}."""

    def test_get_source_success(self, client_with_source: TestClient):
        """Returns source details by name."""
        response = client_with_source.get("/api/v1/sources/test-source")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-source"
        assert data["source_type"] == "databricks"
        assert data["display_name"] == "Test Source"

    def test_get_source_not_found(self, client: TestClient):
        """Returns 404 when source does not exist."""
        response = client.get("/api/v1/sources/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "source_not_found"
        assert "nonexistent" in data["message"]


class TestDeleteSource:
    """Tests for DELETE /api/v1/sources/{name}."""

    def test_delete_source_success(self, client_with_source: TestClient):
        """Successfully deletes a source."""
        response = client_with_source.delete("/api/v1/sources/test-source")

        assert response.status_code == 204
        assert response.content == b""

        # Verify source is gone
        get_response = client_with_source.get("/api/v1/sources/test-source")
        assert get_response.status_code == 404

    def test_delete_source_not_found(self, client: TestClient):
        """Returns 404 when source does not exist."""
        response = client.delete("/api/v1/sources/nonexistent")

        assert response.status_code == 404


class TestScanSource:
    """Tests for POST /api/v1/sources/{name}/scan."""

    def test_scan_source_success(self, client_with_source: TestClient, mock_adapter):
        """Successfully triggers a scan.

        Note: Due to asyncio.run() not being callable from within an event loop
        (FastAPI TestClient runs in an event loop), we mock the entire scan_source
        method to return a success result.
        """
        from datetime import datetime

        from datacompass.core.models import ScanResult, ScanStats
        from datacompass.core.services import CatalogService

        mock_result = ScanResult(
            source_name="test-source",
            source_type="databricks",
            status="success",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            duration_seconds=0.5,
            stats=ScanStats(
                objects_created=2,
                total_objects=2,
                columns_created=3,
                total_columns=3,
            ),
        )

        with patch.object(CatalogService, "scan_source", return_value=mock_result):
            response = client_with_source.post("/api/v1/sources/test-source/scan")

        assert response.status_code == 200
        data = response.json()
        assert data["source_name"] == "test-source"
        assert data["status"] == "success"
        assert "stats" in data
        assert data["stats"]["total_objects"] == 2

    def test_scan_source_full(self, client_with_source: TestClient, mock_adapter):
        """Triggers full scan when requested."""
        from datetime import datetime

        from datacompass.core.models import ScanResult, ScanStats
        from datacompass.core.services import CatalogService

        mock_result = ScanResult(
            source_name="test-source",
            source_type="databricks",
            status="success",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            duration_seconds=0.5,
            stats=ScanStats(total_objects=2),
        )

        with patch.object(CatalogService, "scan_source", return_value=mock_result):
            response = client_with_source.post(
                "/api/v1/sources/test-source/scan?full=true"
            )

        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_scan_source_not_found(self, client: TestClient):
        """Returns 404 when source does not exist."""
        response = client.post("/api/v1/sources/nonexistent/scan")

        assert response.status_code == 404
