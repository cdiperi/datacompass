"""Tests for Schedules API endpoints."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from datacompass.api.app import create_app
from datacompass.api.dependencies import get_db
from datacompass.core.repositories import DataSourceRepository


class TestSchedulesAPI:
    """Test cases for Schedules API endpoints."""

    @pytest.fixture
    def client_with_source(self, test_session_factory) -> Generator[TestClient, None, None]:
        """Create a test client with a pre-populated source."""
        from datacompass.core.adapters import AdapterRegistry
        from datacompass.core.adapters.schemas import DatabricksConfig

        app = create_app()

        def override_get_db() -> Generator[Session, None, None]:
            session = test_session_factory()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as test_client:
            # Mock adapter registration check and create source
            with patch.object(AdapterRegistry, "is_registered", return_value=True):
                with patch.object(
                    AdapterRegistry, "get_config_schema", return_value=DatabricksConfig
                ):
                    response = test_client.post(
                        "/api/v1/sources",
                        json={
                            "name": "demo",
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
                    assert (
                        response.status_code == 201
                    ), f"Failed to create source: {response.json()}"

            yield test_client

    # =========================================================================
    # Schedule CRUD Tests
    # =========================================================================

    def test_list_schedules_empty(self, client: TestClient):
        """Test listing schedules when none exist."""
        response = client.get("/api/v1/schedules")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_schedule(self, client_with_source: TestClient):
        """Test creating a schedule."""
        # Get source ID first
        sources = client_with_source.get("/api/v1/sources").json()
        source_id = sources[0]["id"]

        response = client_with_source.post(
            "/api/v1/schedules",
            json={
                "name": "daily-scan",
                "job_type": "scan",
                "cron_expression": "0 6 * * *",
                "target_id": source_id,
                "description": "Daily catalog scan",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "daily-scan"
        assert data["job_type"] == "scan"
        assert data["cron_expression"] == "0 6 * * *"
        assert data["target_id"] == source_id
        assert data["is_enabled"] is True

    def test_create_schedule_duplicate_name(self, client: TestClient):
        """Test creating schedule with duplicate name returns 409."""
        client.post(
            "/api/v1/schedules",
            json={
                "name": "test-schedule",
                "job_type": "scan",
                "cron_expression": "0 6 * * *",
            },
        )

        response = client.post(
            "/api/v1/schedules",
            json={
                "name": "test-schedule",
                "job_type": "dq_run",
                "cron_expression": "0 7 * * *",
            },
        )
        assert response.status_code == 409

    def test_get_schedule(self, client: TestClient):
        """Test getting a schedule by ID."""
        create_response = client.post(
            "/api/v1/schedules",
            json={
                "name": "test",
                "job_type": "scan",
                "cron_expression": "0 6 * * *",
            },
        )
        schedule_id = create_response.json()["id"]

        response = client.get(f"/api/v1/schedules/{schedule_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "test"

    def test_get_schedule_not_found(self, client: TestClient):
        """Test getting non-existent schedule returns 404."""
        response = client.get("/api/v1/schedules/9999")
        assert response.status_code == 404

    def test_update_schedule(self, client: TestClient):
        """Test updating a schedule."""
        create_response = client.post(
            "/api/v1/schedules",
            json={
                "name": "test",
                "job_type": "scan",
                "cron_expression": "0 6 * * *",
            },
        )
        schedule_id = create_response.json()["id"]

        response = client.patch(
            f"/api/v1/schedules/{schedule_id}",
            json={
                "name": "updated-name",
                "cron_expression": "0 8 * * *",
                "is_enabled": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-name"
        assert data["cron_expression"] == "0 8 * * *"
        assert data["is_enabled"] is False

    def test_delete_schedule(self, client: TestClient):
        """Test deleting a schedule."""
        create_response = client.post(
            "/api/v1/schedules",
            json={
                "name": "test",
                "job_type": "scan",
                "cron_expression": "0 6 * * *",
            },
        )
        schedule_id = create_response.json()["id"]

        response = client.delete(f"/api/v1/schedules/{schedule_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/api/v1/schedules/{schedule_id}")
        assert get_response.status_code == 404

    # =========================================================================
    # Hub Summary Tests
    # =========================================================================

    def test_get_hub_summary_empty(self, client: TestClient):
        """Test hub summary with no schedules."""
        response = client.get("/api/v1/schedules/hub/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_schedules"] == 0
        assert data["enabled_schedules"] == 0

    def test_get_hub_summary_with_schedules(self, client: TestClient):
        """Test hub summary with schedules."""
        client.post(
            "/api/v1/schedules",
            json={
                "name": "scan-1",
                "job_type": "scan",
                "cron_expression": "0 6 * * *",
            },
        )
        client.post(
            "/api/v1/schedules",
            json={
                "name": "dq-1",
                "job_type": "dq_run",
                "cron_expression": "0 7 * * *",
            },
        )

        response = client.get("/api/v1/schedules/hub/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_schedules"] == 2
        assert data["enabled_schedules"] == 2
        assert "scan" in data["schedules_by_type"]
        assert "dq_run" in data["schedules_by_type"]
