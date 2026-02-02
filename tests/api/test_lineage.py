"""Tests for lineage API endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from datacompass.core.adapters import AdapterRegistry
from datacompass.core.adapters.schemas import DatabricksConfig


def setup_source_with_objects(client: TestClient, test_session_factory) -> dict[str, int]:
    """Helper to create a source and objects for lineage testing.

    Returns dict mapping object names to IDs.
    """
    from datacompass.core.models import CatalogObject

    # Create source
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
        obj1 = CatalogObject(
            source_id=source_id,
            schema_name="analytics",
            object_name="customers",
            object_type="TABLE",
        )
        obj2 = CatalogObject(
            source_id=source_id,
            schema_name="analytics",
            object_name="orders",
            object_type="TABLE",
        )
        session.add_all([obj1, obj2])
        session.commit()

        return {
            "customers": obj1.id,
            "orders": obj2.id,
            "source_id": source_id,
        }
    finally:
        session.close()


class TestLineageEndpoints:
    """Test cases for lineage API endpoints."""

    def test_get_lineage_upstream(self, client: TestClient, test_session_factory):
        """Test getting upstream lineage for an object."""
        ids = setup_source_with_objects(client, test_session_factory)
        object_id = ids["customers"]

        response = client.get(
            f"/api/v1/objects/{object_id}/lineage",
            params={"direction": "upstream"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["root"]["id"] == object_id
        assert data["direction"] == "upstream"
        assert "nodes" in data
        assert "edges" in data

    def test_get_lineage_downstream(self, client: TestClient, test_session_factory):
        """Test getting downstream lineage for an object."""
        ids = setup_source_with_objects(client, test_session_factory)
        object_id = ids["customers"]

        response = client.get(
            f"/api/v1/objects/{object_id}/lineage",
            params={"direction": "downstream"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["direction"] == "downstream"

    def test_get_lineage_with_depth(self, client: TestClient, test_session_factory):
        """Test getting lineage with custom depth."""
        ids = setup_source_with_objects(client, test_session_factory)
        object_id = ids["customers"]

        response = client.get(
            f"/api/v1/objects/{object_id}/lineage",
            params={"depth": 5},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["depth"] == 5

    def test_get_lineage_depth_validation(self, client: TestClient, test_session_factory):
        """Test lineage depth parameter validation."""
        ids = setup_source_with_objects(client, test_session_factory)
        object_id = ids["customers"]

        # Depth must be between 1 and 10
        response = client.get(
            f"/api/v1/objects/{object_id}/lineage",
            params={"depth": 0},
        )
        assert response.status_code == 422  # Validation error

        response = client.get(
            f"/api/v1/objects/{object_id}/lineage",
            params={"depth": 11},
        )
        assert response.status_code == 422

    def test_get_lineage_object_not_found(self, client: TestClient):
        """Test lineage for non-existent object."""
        response = client.get("/api/v1/objects/99999/lineage")
        assert response.status_code == 404

    def test_get_lineage_by_qualified_name(self, client: TestClient, test_session_factory):
        """Test getting lineage using qualified object name."""
        setup_source_with_objects(client, test_session_factory)

        response = client.get(
            "/api/v1/objects/test-source.analytics.customers/lineage"
        )
        assert response.status_code == 200
        data = response.json()

        assert data["root"]["object_name"] == "customers"

    def test_get_lineage_summary(self, client: TestClient, test_session_factory):
        """Test getting lineage summary counts."""
        ids = setup_source_with_objects(client, test_session_factory)
        object_id = ids["customers"]

        response = client.get(
            f"/api/v1/objects/{object_id}/lineage/summary"
        )
        assert response.status_code == 200
        data = response.json()

        assert "upstream_count" in data
        assert "downstream_count" in data
        assert "external_count" in data
        assert isinstance(data["upstream_count"], int)

    def test_get_lineage_summary_not_found(self, client: TestClient):
        """Test lineage summary for non-existent object."""
        response = client.get("/api/v1/objects/99999/lineage/summary")
        assert response.status_code == 404


class TestLineageWithDependencies:
    """Test lineage endpoints with actual dependency data."""

    @pytest.fixture
    def client_with_dependencies(self, test_session_factory):
        """Create client with objects that have dependencies."""
        from datacompass.api.app import create_app
        from datacompass.api.dependencies import get_db
        from datacompass.core.models import CatalogObject, DataSource, Dependency
        from sqlalchemy.orm import Session
        from collections.abc import Generator

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

        # Create test data
        session = test_session_factory()
        try:
            # Create source
            source = DataSource(
                name="demo",
                source_type="databricks",
                connection_info={},
            )
            session.add(source)
            session.flush()

            # Create objects
            raw = CatalogObject(
                source_id=source.id,
                schema_name="staging",
                object_name="raw_events",
                object_type="TABLE",
            )
            orders = CatalogObject(
                source_id=source.id,
                schema_name="core",
                object_name="orders",
                object_type="TABLE",
            )
            summary = CatalogObject(
                source_id=source.id,
                schema_name="analytics",
                object_name="order_summary",
                object_type="VIEW",
            )
            session.add_all([raw, orders, summary])
            session.flush()

            # Create dependencies: orders -> raw, summary -> orders
            session.add(
                Dependency(
                    source_id=source.id,
                    object_id=orders.id,
                    target_id=raw.id,
                    dependency_type="DIRECT",
                    parsing_source="source_metadata",
                )
            )
            session.add(
                Dependency(
                    source_id=source.id,
                    object_id=summary.id,
                    target_id=orders.id,
                    dependency_type="DIRECT",
                    parsing_source="source_metadata",
                )
            )
            session.commit()

            # Store object IDs for tests
            object_ids = {
                "raw": raw.id,
                "orders": orders.id,
                "summary": summary.id,
            }
        finally:
            session.close()

        with TestClient(app) as test_client:
            test_client.object_ids = object_ids
            yield test_client

    def test_upstream_lineage_with_deps(self, client_with_dependencies: TestClient):
        """Test upstream lineage returns correct dependencies."""
        object_ids = client_with_dependencies.object_ids

        response = client_with_dependencies.get(
            f"/api/v1/objects/{object_ids['summary']}/lineage",
            params={"direction": "upstream", "depth": 1},
        )
        assert response.status_code == 200
        data = response.json()

        # order_summary depends on orders
        assert data["root"]["object_name"] == "order_summary"
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["object_name"] == "orders"
        assert data["nodes"][0]["distance"] == 1

    def test_upstream_lineage_depth_2(self, client_with_dependencies: TestClient):
        """Test upstream lineage with depth 2 finds transitive deps."""
        object_ids = client_with_dependencies.object_ids

        response = client_with_dependencies.get(
            f"/api/v1/objects/{object_ids['summary']}/lineage",
            params={"direction": "upstream", "depth": 2},
        )
        assert response.status_code == 200
        data = response.json()

        # Should find orders (dist 1) and raw_events (dist 2)
        assert len(data["nodes"]) == 2
        names = {n["object_name"] for n in data["nodes"]}
        assert names == {"orders", "raw_events"}

    def test_downstream_lineage_with_deps(self, client_with_dependencies: TestClient):
        """Test downstream lineage returns correct dependents."""
        object_ids = client_with_dependencies.object_ids

        response = client_with_dependencies.get(
            f"/api/v1/objects/{object_ids['orders']}/lineage",
            params={"direction": "downstream"},
        )
        assert response.status_code == 200
        data = response.json()

        # orders is used by order_summary
        assert data["root"]["object_name"] == "orders"
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["object_name"] == "order_summary"

    def test_lineage_summary_counts(self, client_with_dependencies: TestClient):
        """Test lineage summary shows correct counts."""
        object_ids = client_with_dependencies.object_ids

        # orders: 1 upstream (raw_events), 1 downstream (order_summary)
        response = client_with_dependencies.get(
            f"/api/v1/objects/{object_ids['orders']}/lineage/summary"
        )
        assert response.status_code == 200
        data = response.json()

        assert data["upstream_count"] == 1
        assert data["downstream_count"] == 1
