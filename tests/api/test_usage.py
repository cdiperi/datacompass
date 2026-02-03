"""Tests for usage API endpoints."""

from collections.abc import Generator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from datacompass.api.app import create_app
from datacompass.api.dependencies import get_db
from datacompass.core.repositories import CatalogObjectRepository, DataSourceRepository
from datacompass.core.repositories.usage import UsageRepository


class TestUsageAPI:
    """Test cases for usage API endpoints."""

    @pytest.fixture
    def client_with_usage_data(self, test_session_factory) -> Generator[TestClient, None, None]:
        """Create a test client with pre-populated usage data."""
        app = create_app()

        # Create session and populate data
        session = test_session_factory()

        # Create source
        source_repo = DataSourceRepository(session)
        source = source_repo.create(
            name="demo",
            source_type="postgresql",
            connection_info={"host": "localhost"},
        )
        session.flush()

        # Create catalog objects
        obj_repo = CatalogObjectRepository(session)
        objects = []
        for name in ["customers", "orders", "products"]:
            obj, _ = obj_repo.upsert(source.id, "analytics", name, "TABLE")
            objects.append(obj)
        session.flush()

        # Create usage metrics
        usage_repo = UsageRepository(session)
        for i, obj in enumerate(objects):
            usage_repo.record_metrics(
                object_id=obj.id,
                row_count=1000 * (i + 1),
                size_bytes=1024 * 1024 * (i + 1),
                read_count=100 * (len(objects) - i),
                write_count=10 * (i + 1),
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

    # =========================================================================
    # Get Object Usage Tests
    # =========================================================================

    def test_get_object_usage(
        self,
        client_with_usage_data: TestClient,
    ):
        """Test getting latest usage for an object."""
        # Get objects first to find ID
        response = client_with_usage_data.get("/api/v1/objects")
        assert response.status_code == 200
        objects = response.json()

        # Find customers
        customers = next((o for o in objects if o["object_name"] == "customers"), None)
        assert customers is not None

        # Get usage
        response = client_with_usage_data.get(f"/api/v1/usage/objects/{customers['id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["object_id"] == customers["id"]
        assert data["row_count"] == 1000
        assert data["read_count"] == 300
        assert data["object_name"] == "customers"

    def test_get_object_usage_no_metrics(
        self,
        client: TestClient,
        test_session_factory,
    ):
        """Test getting usage when no metrics exist."""
        # Create an object without metrics
        session = test_session_factory()
        source_repo = DataSourceRepository(session)
        source = source_repo.create(
            name="empty",
            source_type="postgresql",
            connection_info={},
        )
        session.flush()

        obj_repo = CatalogObjectRepository(session)
        obj, _ = obj_repo.upsert(source.id, "test", "table1", "TABLE")
        session.commit()

        response = client.get(f"/api/v1/usage/objects/{obj.id}")

        assert response.status_code == 200
        assert response.json() is None

        session.close()

    # =========================================================================
    # Get Object Usage History Tests
    # =========================================================================

    def test_get_object_usage_history(
        self,
        client: TestClient,
        test_session_factory,
    ):
        """Test getting historical usage metrics."""
        # Create object with multiple metrics
        session = test_session_factory()
        source_repo = DataSourceRepository(session)
        source = source_repo.create(
            name="history_test",
            source_type="postgresql",
            connection_info={},
        )
        session.flush()

        obj_repo = CatalogObjectRepository(session)
        obj, _ = obj_repo.upsert(source.id, "test", "table1", "TABLE")
        session.flush()

        usage_repo = UsageRepository(session)
        for i in range(5):
            usage_repo.record_metrics(
                object_id=obj.id,
                row_count=100 * (i + 1),
            )
        session.commit()

        response = client.get(f"/api/v1/usage/objects/{obj.id}/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

        session.close()

    def test_get_object_usage_history_with_params(
        self,
        client: TestClient,
        test_session_factory,
    ):
        """Test history with days and limit parameters."""
        session = test_session_factory()
        source_repo = DataSourceRepository(session)
        source = source_repo.create(
            name="history_params",
            source_type="postgresql",
            connection_info={},
        )
        session.flush()

        obj_repo = CatalogObjectRepository(session)
        obj, _ = obj_repo.upsert(source.id, "test", "table1", "TABLE")
        session.flush()

        usage_repo = UsageRepository(session)
        for i in range(10):
            usage_repo.record_metrics(object_id=obj.id, row_count=100 * i)
        session.commit()

        response = client.get(
            f"/api/v1/usage/objects/{obj.id}/history",
            params={"days": 30, "limit": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

        session.close()

    # =========================================================================
    # Hot Tables Tests
    # =========================================================================

    def test_get_hot_tables(
        self,
        client_with_usage_data: TestClient,
    ):
        """Test getting hot tables."""
        response = client_with_usage_data.get("/api/v1/usage/hot")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # First should have highest read_count (customers = 300)
        assert data[0]["object_name"] == "customers"
        assert data[0]["read_count"] == 300

    def test_get_hot_tables_with_source_filter(
        self,
        client_with_usage_data: TestClient,
    ):
        """Test hot tables with source filter."""
        response = client_with_usage_data.get(
            "/api/v1/usage/hot",
            params={"source_name": "demo"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_get_hot_tables_with_params(
        self,
        client_with_usage_data: TestClient,
    ):
        """Test hot tables with custom parameters."""
        response = client_with_usage_data.get(
            "/api/v1/usage/hot",
            params={"days": 7, "limit": 2, "order_by": "size_bytes"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Should be ordered by size_bytes descending
        assert data[0]["size_bytes"] >= data[1]["size_bytes"]

    def test_get_hot_tables_empty(
        self,
        client: TestClient,
    ):
        """Test hot tables when no metrics exist."""
        response = client.get("/api/v1/usage/hot")

        assert response.status_code == 200
        assert response.json() == []

    # =========================================================================
    # Hub Summary Tests
    # =========================================================================

    def test_get_hub_summary(
        self,
        client_with_usage_data: TestClient,
    ):
        """Test getting hub summary."""
        response = client_with_usage_data.get("/api/v1/usage/hub/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total_objects_with_metrics"] == 3
        assert data["total_metrics_collected"] == 3
        assert len(data["hot_tables"]) > 0

    def test_get_hub_summary_empty(
        self,
        client: TestClient,
    ):
        """Test hub summary with no metrics."""
        response = client.get("/api/v1/usage/hub/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total_objects_with_metrics"] == 0
        assert data["total_metrics_collected"] == 0
        assert data["hot_tables"] == []

    def test_get_hub_summary_with_source_filter(
        self,
        client_with_usage_data: TestClient,
    ):
        """Test hub summary with source filter."""
        response = client_with_usage_data.get(
            "/api/v1/usage/hub/summary",
            params={"source_name": "demo"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_objects_with_metrics"] == 3

    # =========================================================================
    # Collection Tests
    # =========================================================================

    def test_collect_source_not_found(
        self,
        client: TestClient,
    ):
        """Test collection with non-existent source."""
        response = client.post("/api/v1/usage/sources/nonexistent/collect")

        # Should return 404
        assert response.status_code == 404
