"""Tests for Deprecation API endpoints."""

from collections.abc import Generator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from datacompass.api.app import create_app
from datacompass.api.dependencies import get_db
from datacompass.core.repositories import CatalogObjectRepository, DataSourceRepository


class TestDeprecationAPI:
    """Test cases for Deprecation API endpoints."""

    @pytest.fixture
    def client_with_source(self, test_session_factory) -> Generator[TestClient, None, None]:
        """Create a client with a pre-populated source."""
        app = create_app()

        # Create session and populate data
        session = test_session_factory()

        # Create source directly
        source_repo = DataSourceRepository(session)
        source_repo.create(
            name="demo",
            source_type="databricks",
            connection_info={},
        )
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

    @pytest.fixture
    def client_with_objects(self, test_session_factory) -> Generator[TestClient, None, None]:
        """Create a client with source and catalog objects."""
        app = create_app()

        # Create session and populate data
        session = test_session_factory()

        # Create source directly
        source_repo = DataSourceRepository(session)
        source = source_repo.create(
            name="demo",
            source_type="databricks",
            connection_info={},
        )
        session.flush()

        # Create catalog objects
        obj_repo = CatalogObjectRepository(session)
        obj_repo.upsert(source.id, "analytics", "old_table", "TABLE")
        obj_repo.upsert(source.id, "analytics", "new_table", "TABLE")
        obj_repo.upsert(source.id, "analytics", "other_table", "TABLE")
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

    def _get_source_id(self, client: TestClient) -> int:
        """Helper to get the demo source ID."""
        response = client.get("/api/v1/sources")
        sources = response.json()
        return sources[0]["id"]

    def _get_object_ids(self, client: TestClient) -> list[int]:
        """Helper to get catalog object IDs."""
        response = client.get("/api/v1/objects")
        objects = response.json()
        return [obj["id"] for obj in objects]

    # =========================================================================
    # Campaign Endpoints
    # =========================================================================

    def test_create_campaign(self, client_with_source: TestClient):
        """Test POST /api/v1/deprecations/campaigns."""
        source_id = self._get_source_id(client_with_source)

        response = client_with_source.post(
            "/api/v1/deprecations/campaigns",
            json={
                "source_id": source_id,
                "name": "Q2 Cleanup",
                "description": "Retiring old tables",
                "target_date": "2025-06-01",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Q2 Cleanup"
        assert data["source_name"] == "demo"
        assert data["status"] == "draft"
        assert data["target_date"] == "2025-06-01"

    def test_create_campaign_duplicate_name(self, client_with_source: TestClient):
        """Test creating campaign with duplicate name."""
        source_id = self._get_source_id(client_with_source)

        client_with_source.post(
            "/api/v1/deprecations/campaigns",
            json={
                "source_id": source_id,
                "name": "Test",
                "target_date": "2025-06-01",
            },
        )

        response = client_with_source.post(
            "/api/v1/deprecations/campaigns",
            json={
                "source_id": source_id,
                "name": "Test",
                "target_date": "2025-07-01",
            },
        )

        assert response.status_code == 409

    def test_list_campaigns(self, client_with_source: TestClient):
        """Test GET /api/v1/deprecations/campaigns."""
        source_id = self._get_source_id(client_with_source)

        # Create campaigns
        client_with_source.post(
            "/api/v1/deprecations/campaigns",
            json={
                "source_id": source_id,
                "name": "Campaign 1",
                "target_date": "2025-06-01",
            },
        )
        client_with_source.post(
            "/api/v1/deprecations/campaigns",
            json={
                "source_id": source_id,
                "name": "Campaign 2",
                "target_date": "2025-07-01",
            },
        )

        response = client_with_source.get("/api/v1/deprecations/campaigns")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_campaigns_filter_by_status(self, client_with_source: TestClient):
        """Test filtering campaigns by status."""
        source_id = self._get_source_id(client_with_source)

        # Create draft campaign
        client_with_source.post(
            "/api/v1/deprecations/campaigns",
            json={
                "source_id": source_id,
                "name": "Draft",
                "target_date": "2025-06-01",
            },
        )

        # Create and activate another
        create_resp2 = client_with_source.post(
            "/api/v1/deprecations/campaigns",
            json={
                "source_id": source_id,
                "name": "Active",
                "target_date": "2025-07-01",
            },
        )
        campaign_id = create_resp2.json()["id"]
        client_with_source.patch(
            f"/api/v1/deprecations/campaigns/{campaign_id}",
            json={"status": "active"},
        )

        # Filter by draft
        response = client_with_source.get("/api/v1/deprecations/campaigns?status=draft")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Draft"

    def test_get_campaign(self, client_with_source: TestClient):
        """Test GET /api/v1/deprecations/campaigns/{id}."""
        source_id = self._get_source_id(client_with_source)

        create_resp = client_with_source.post(
            "/api/v1/deprecations/campaigns",
            json={
                "source_id": source_id,
                "name": "Test",
                "target_date": "2025-06-01",
            },
        )
        campaign_id = create_resp.json()["id"]

        response = client_with_source.get(f"/api/v1/deprecations/campaigns/{campaign_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == campaign_id
        assert data["name"] == "Test"
        assert "deprecations" in data

    def test_get_campaign_not_found(self, client: TestClient):
        """Test getting non-existent campaign."""
        response = client.get("/api/v1/deprecations/campaigns/99999")
        assert response.status_code == 404

    def test_update_campaign(self, client_with_source: TestClient):
        """Test PATCH /api/v1/deprecations/campaigns/{id}."""
        source_id = self._get_source_id(client_with_source)

        create_resp = client_with_source.post(
            "/api/v1/deprecations/campaigns",
            json={
                "source_id": source_id,
                "name": "Original",
                "target_date": "2025-06-01",
            },
        )
        campaign_id = create_resp.json()["id"]

        response = client_with_source.patch(
            f"/api/v1/deprecations/campaigns/{campaign_id}",
            json={"name": "Updated", "status": "active"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated"
        assert data["status"] == "active"

    def test_delete_campaign(self, client_with_source: TestClient):
        """Test DELETE /api/v1/deprecations/campaigns/{id}."""
        source_id = self._get_source_id(client_with_source)

        create_resp = client_with_source.post(
            "/api/v1/deprecations/campaigns",
            json={
                "source_id": source_id,
                "name": "To Delete",
                "target_date": "2025-06-01",
            },
        )
        campaign_id = create_resp.json()["id"]

        response = client_with_source.delete(f"/api/v1/deprecations/campaigns/{campaign_id}")
        assert response.status_code == 204

        # Verify deleted
        get_resp = client_with_source.get(f"/api/v1/deprecations/campaigns/{campaign_id}")
        assert get_resp.status_code == 404

    # =========================================================================
    # Deprecation Endpoints
    # =========================================================================

    def test_add_object_to_campaign(self, client_with_objects: TestClient):
        """Test POST /api/v1/deprecations/campaigns/{id}/objects."""
        source_id = self._get_source_id(client_with_objects)
        object_ids = self._get_object_ids(client_with_objects)

        create_resp = client_with_objects.post(
            "/api/v1/deprecations/campaigns",
            json={
                "source_id": source_id,
                "name": "Test",
                "target_date": "2025-06-01",
            },
        )
        campaign_id = create_resp.json()["id"]

        response = client_with_objects.post(
            f"/api/v1/deprecations/campaigns/{campaign_id}/objects",
            json={
                "object_id": object_ids[0],
                "replacement_id": object_ids[1],
                "migration_notes": "Use new_table",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["object_id"] == object_ids[0]
        assert data["replacement_id"] == object_ids[1]

    def test_remove_object_from_campaign(self, client_with_objects: TestClient):
        """Test DELETE /api/v1/deprecations/objects/{id}."""
        source_id = self._get_source_id(client_with_objects)
        object_ids = self._get_object_ids(client_with_objects)

        create_resp = client_with_objects.post(
            "/api/v1/deprecations/campaigns",
            json={
                "source_id": source_id,
                "name": "Test",
                "target_date": "2025-06-01",
            },
        )
        campaign_id = create_resp.json()["id"]

        add_resp = client_with_objects.post(
            f"/api/v1/deprecations/campaigns/{campaign_id}/objects",
            json={"object_id": object_ids[0]},
        )
        deprecation_id = add_resp.json()["id"]

        response = client_with_objects.delete(f"/api/v1/deprecations/objects/{deprecation_id}")
        assert response.status_code == 204

    def test_list_deprecations(self, client_with_objects: TestClient):
        """Test GET /api/v1/deprecations/objects."""
        source_id = self._get_source_id(client_with_objects)
        object_ids = self._get_object_ids(client_with_objects)

        create_resp = client_with_objects.post(
            "/api/v1/deprecations/campaigns",
            json={
                "source_id": source_id,
                "name": "Test",
                "target_date": "2025-06-01",
            },
        )
        campaign_id = create_resp.json()["id"]

        client_with_objects.post(
            f"/api/v1/deprecations/campaigns/{campaign_id}/objects",
            json={"object_id": object_ids[0]},
        )
        client_with_objects.post(
            f"/api/v1/deprecations/campaigns/{campaign_id}/objects",
            json={"object_id": object_ids[1]},
        )

        response = client_with_objects.get(
            f"/api/v1/deprecations/objects?campaign_id={campaign_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    # =========================================================================
    # Impact Analysis Endpoint
    # =========================================================================

    def test_get_campaign_impact(self, client_with_objects: TestClient):
        """Test GET /api/v1/deprecations/campaigns/{id}/impact."""
        source_id = self._get_source_id(client_with_objects)
        object_ids = self._get_object_ids(client_with_objects)

        create_resp = client_with_objects.post(
            "/api/v1/deprecations/campaigns",
            json={
                "source_id": source_id,
                "name": "Test",
                "target_date": "2025-06-01",
            },
        )
        campaign_id = create_resp.json()["id"]

        client_with_objects.post(
            f"/api/v1/deprecations/campaigns/{campaign_id}/objects",
            json={"object_id": object_ids[0]},
        )

        response = client_with_objects.get(
            f"/api/v1/deprecations/campaigns/{campaign_id}/impact"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["campaign_id"] == campaign_id
        assert data["total_deprecated"] == 1
        assert "impacts" in data

    # =========================================================================
    # Hub Summary Endpoint
    # =========================================================================

    def test_get_hub_summary(self, client_with_source: TestClient):
        """Test GET /api/v1/deprecations/hub/summary."""
        source_id = self._get_source_id(client_with_source)

        # Create campaigns
        client_with_source.post(
            "/api/v1/deprecations/campaigns",
            json={
                "source_id": source_id,
                "name": "Draft",
                "target_date": str(date.today() + timedelta(days=10)),
            },
        )

        response = client_with_source.get("/api/v1/deprecations/hub/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total_campaigns"] == 1
        assert data["draft_campaigns"] == 1
        assert "upcoming_deadlines" in data
