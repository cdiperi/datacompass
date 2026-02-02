"""Tests for DQ API endpoints."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from datacompass.api.app import create_app
from datacompass.api.dependencies import get_db
from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.repositories import CatalogObjectRepository, DataSourceRepository


class TestDQAPI:
    """Test cases for DQ API endpoints."""

    @pytest.fixture
    def client_with_object(self, test_session_factory) -> Generator[TestClient, None, None]:
        """Create a client with a pre-populated source and objects."""
        from datacompass.core.adapters import AdapterRegistry
        from datacompass.core.adapters.schemas import DatabricksConfig

        app = create_app()

        # Create session and populate data
        session = test_session_factory()

        # Create source directly
        source_repo = DataSourceRepository(session)
        source = source_repo.create(
            name="test-source",
            source_type="databricks",
            connection_info={
                "host": "test.azuredatabricks.net",
                "http_path": "/sql/1.0/warehouses/test",
                "catalog": "main",
                "auth_method": "personal_token",
                "access_token": "test-token",
            },
            display_name="Test Source",
        )
        session.flush()

        # Create objects directly
        obj_repo = CatalogObjectRepository(session)
        obj_repo.upsert(source.id, "analytics", "customers", "TABLE")
        obj_repo.upsert(source.id, "analytics", "orders", "TABLE")
        session.commit()

        def override_get_db() -> Generator[Session, None, None]:
            db_session = test_session_factory()
            try:
                yield db_session
                db_session.commit()
            except Exception:
                db_session.rollback()
                raise
            finally:
                db_session.close()

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as test_client:
            yield test_client

        session.close()

    # =========================================================================
    # Config Tests
    # =========================================================================

    def test_list_configs_empty(self, client: TestClient):
        """Test listing configs when none exist."""
        response = client.get("/api/v1/dq/configs")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_config(self, client_with_object: TestClient):
        """Test creating a DQ config."""
        # Get object ID
        objects_response = client_with_object.get("/api/v1/objects")
        objects = objects_response.json()
        assert len(objects) > 0
        object_id = objects[0]["id"]

        response = client_with_object.post(
            "/api/v1/dq/configs",
            json={
                "object_id": object_id,
                "date_column": "created_at",
                "grain": "daily",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["object_id"] == object_id
        assert data["date_column"] == "created_at"
        assert data["grain"] == "daily"

    def test_create_config_object_not_found(self, client: TestClient):
        """Test creating config for non-existent object."""
        response = client.post(
            "/api/v1/dq/configs",
            json={"object_id": 99999},
        )

        assert response.status_code == 404
        assert "object_not_found" in response.json()["error"]

    def test_create_config_duplicate(self, client_with_object: TestClient):
        """Test creating duplicate config fails."""
        objects_response = client_with_object.get("/api/v1/objects")
        object_id = objects_response.json()[0]["id"]

        # Create first config
        client_with_object.post(
            "/api/v1/dq/configs",
            json={"object_id": object_id},
        )

        # Try to create duplicate
        response = client_with_object.post(
            "/api/v1/dq/configs",
            json={"object_id": object_id},
        )

        assert response.status_code == 409
        assert "dq_config_exists" in response.json()["error"]

    def test_get_config(self, client_with_object: TestClient):
        """Test getting a config by ID."""
        objects_response = client_with_object.get("/api/v1/objects")
        object_id = objects_response.json()[0]["id"]

        # Create config
        create_response = client_with_object.post(
            "/api/v1/dq/configs",
            json={"object_id": object_id},
        )
        config_id = create_response.json()["id"]

        # Get config
        response = client_with_object.get(f"/api/v1/dq/configs/{config_id}")

        assert response.status_code == 200
        assert response.json()["id"] == config_id

    def test_get_config_not_found(self, client: TestClient):
        """Test getting non-existent config."""
        response = client.get("/api/v1/dq/configs/99999")
        assert response.status_code == 404

    def test_delete_config(self, client_with_object: TestClient):
        """Test deleting a config."""
        objects_response = client_with_object.get("/api/v1/objects")
        object_id = objects_response.json()[0]["id"]

        # Create config
        create_response = client_with_object.post(
            "/api/v1/dq/configs",
            json={"object_id": object_id},
        )
        config_id = create_response.json()["id"]

        # Delete config
        response = client_with_object.delete(f"/api/v1/dq/configs/{config_id}")
        assert response.status_code == 204

        # Verify deleted
        get_response = client_with_object.get(f"/api/v1/dq/configs/{config_id}")
        assert get_response.status_code == 404

    # =========================================================================
    # Expectation Tests
    # =========================================================================

    def test_create_expectation(self, client_with_object: TestClient):
        """Test creating an expectation."""
        objects_response = client_with_object.get("/api/v1/objects")
        object_id = objects_response.json()[0]["id"]

        # Create config
        config_response = client_with_object.post(
            "/api/v1/dq/configs",
            json={"object_id": object_id},
        )
        config_id = config_response.json()["id"]

        # Create expectation
        response = client_with_object.post(
            "/api/v1/dq/expectations",
            json={
                "config_id": config_id,
                "expectation_type": "row_count",
                "threshold_config": {
                    "type": "absolute",
                    "min": 100,
                    "max": 10000,
                },
                "priority": "high",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["expectation_type"] == "row_count"
        assert data["priority"] == "high"

    def test_update_expectation(self, client_with_object: TestClient):
        """Test updating an expectation."""
        objects_response = client_with_object.get("/api/v1/objects")
        object_id = objects_response.json()[0]["id"]

        config_response = client_with_object.post(
            "/api/v1/dq/configs",
            json={"object_id": object_id},
        )
        config_id = config_response.json()["id"]

        exp_response = client_with_object.post(
            "/api/v1/dq/expectations",
            json={
                "config_id": config_id,
                "expectation_type": "row_count",
                "threshold_config": {"type": "absolute"},
                "priority": "medium",
            },
        )
        exp_id = exp_response.json()["id"]

        # Update
        response = client_with_object.patch(
            f"/api/v1/dq/expectations/{exp_id}",
            json={"priority": "critical", "is_enabled": False},
        )

        assert response.status_code == 200
        assert response.json()["priority"] == "critical"
        assert response.json()["is_enabled"] is False

    def test_delete_expectation(self, client_with_object: TestClient):
        """Test deleting an expectation."""
        objects_response = client_with_object.get("/api/v1/objects")
        object_id = objects_response.json()[0]["id"]

        config_response = client_with_object.post(
            "/api/v1/dq/configs",
            json={"object_id": object_id},
        )
        config_id = config_response.json()["id"]

        exp_response = client_with_object.post(
            "/api/v1/dq/expectations",
            json={
                "config_id": config_id,
                "expectation_type": "row_count",
                "threshold_config": {"type": "absolute"},
            },
        )
        exp_id = exp_response.json()["id"]

        response = client_with_object.delete(f"/api/v1/dq/expectations/{exp_id}")
        assert response.status_code == 204

    # =========================================================================
    # Execution Tests
    # =========================================================================

    def test_run_config(self, client_with_object: TestClient):
        """Test running DQ checks."""
        objects_response = client_with_object.get("/api/v1/objects")
        object_id = objects_response.json()[0]["id"]

        config_response = client_with_object.post(
            "/api/v1/dq/configs",
            json={"object_id": object_id},
        )
        config_id = config_response.json()["id"]

        client_with_object.post(
            "/api/v1/dq/expectations",
            json={
                "config_id": config_id,
                "expectation_type": "row_count",
                "threshold_config": {"type": "absolute", "min": 0, "max": 100000},
            },
        )

        # Run checks
        response = client_with_object.post(f"/api/v1/dq/configs/{config_id}/run")

        assert response.status_code == 200
        data = response.json()
        assert data["config_id"] == config_id
        assert data["total_checks"] == 1
        assert "results" in data

    # =========================================================================
    # Breach Tests
    # =========================================================================

    def test_list_breaches_empty(self, client: TestClient):
        """Test listing breaches when none exist."""
        response = client.get("/api/v1/dq/breaches")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_breaches_with_filter(self, client_with_object: TestClient):
        """Test listing breaches with status filter."""
        objects_response = client_with_object.get("/api/v1/objects")
        object_id = objects_response.json()[0]["id"]

        config_response = client_with_object.post(
            "/api/v1/dq/configs",
            json={"object_id": object_id},
        )
        config_id = config_response.json()["id"]

        # Create expectation that will always breach
        client_with_object.post(
            "/api/v1/dq/expectations",
            json={
                "config_id": config_id,
                "expectation_type": "row_count",
                "threshold_config": {"type": "absolute", "max": 0},
            },
        )

        # Run to create breach
        client_with_object.post(f"/api/v1/dq/configs/{config_id}/run")

        # List open breaches
        response = client_with_object.get("/api/v1/dq/breaches?status=open")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert all(b["status"] == "open" for b in data)

    def test_update_breach_status(self, client_with_object: TestClient):
        """Test updating breach status."""
        objects_response = client_with_object.get("/api/v1/objects")
        object_id = objects_response.json()[0]["id"]

        config_response = client_with_object.post(
            "/api/v1/dq/configs",
            json={"object_id": object_id},
        )
        config_id = config_response.json()["id"]

        client_with_object.post(
            "/api/v1/dq/expectations",
            json={
                "config_id": config_id,
                "expectation_type": "row_count",
                "threshold_config": {"type": "absolute", "max": 0},
            },
        )

        # Run to create breach
        client_with_object.post(f"/api/v1/dq/configs/{config_id}/run")

        # Get breach ID
        breaches = client_with_object.get("/api/v1/dq/breaches?status=open").json()
        breach_id = breaches[0]["id"]

        # Update status
        response = client_with_object.patch(
            f"/api/v1/dq/breaches/{breach_id}/status",
            json={"status": "acknowledged", "notes": "Looking into it"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "acknowledged"
        assert len(data["lifecycle_events"]) >= 1

    # =========================================================================
    # Hub Tests
    # =========================================================================

    def test_get_hub_summary(self, client: TestClient):
        """Test getting hub summary."""
        response = client.get("/api/v1/dq/hub/summary")

        assert response.status_code == 200
        data = response.json()
        assert "total_configs" in data
        assert "open_breaches" in data
        assert "breaches_by_priority" in data

    def test_get_hub_summary_with_data(self, client_with_object: TestClient):
        """Test hub summary with actual data."""
        objects_response = client_with_object.get("/api/v1/objects")
        object_id = objects_response.json()[0]["id"]

        # Create config
        client_with_object.post(
            "/api/v1/dq/configs",
            json={"object_id": object_id},
        )

        response = client_with_object.get("/api/v1/dq/hub/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total_configs"] == 1
