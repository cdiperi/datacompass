"""Tests for LineageService."""

import pytest
from sqlalchemy.orm import Session

from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.repositories import (
    CatalogObjectRepository,
    DataSourceRepository,
    DependencyRepository,
)
from datacompass.core.services import ObjectNotFoundError
from datacompass.core.services.lineage_service import LineageService


class TestLineageService:
    """Test cases for LineageService."""

    @pytest.fixture
    def source(self, test_db: Session) -> DataSource:
        """Create a test data source."""
        repo = DataSourceRepository(test_db)
        source = repo.create(
            name="demo",
            source_type="databricks",
            connection_info={},
        )
        test_db.commit()
        return source

    @pytest.fixture
    def objects(self, test_db: Session, source: DataSource) -> dict[str, CatalogObject]:
        """Create test catalog objects with a dependency chain.

        Chain: raw_events -> orders -> order_summary -> daily_report
        Also: users -> order_summary
        """
        repo = CatalogObjectRepository(test_db)

        objs = {}
        for schema, name, obj_type in [
            ("staging", "raw_events", "TABLE"),
            ("core", "orders", "TABLE"),
            ("core", "users", "TABLE"),
            ("analytics", "order_summary", "VIEW"),
            ("reporting", "daily_report", "VIEW"),
        ]:
            obj, _ = repo.upsert(source.id, schema, name, obj_type)
            objs[name] = obj

        test_db.commit()
        return objs

    @pytest.fixture
    def dependencies(
        self, test_db: Session, source: DataSource, objects: dict[str, CatalogObject]
    ):
        """Set up dependencies between objects."""
        repo = DependencyRepository(test_db)

        # orders depends on raw_events
        repo.upsert(
            source.id,
            objects["orders"].id,
            objects["raw_events"].id,
            "DIRECT",
            "source_metadata",
        )
        # order_summary depends on orders and users
        repo.upsert(
            source.id,
            objects["order_summary"].id,
            objects["orders"].id,
            "DIRECT",
            "source_metadata",
        )
        repo.upsert(
            source.id,
            objects["order_summary"].id,
            objects["users"].id,
            "DIRECT",
            "source_metadata",
        )
        # daily_report depends on order_summary
        repo.upsert(
            source.id,
            objects["daily_report"].id,
            objects["order_summary"].id,
            "DIRECT",
            "source_metadata",
        )
        test_db.commit()

    def test_get_lineage_upstream(
        self,
        test_db: Session,
        source: DataSource,
        objects: dict[str, CatalogObject],
        dependencies,
    ):
        """Test getting upstream lineage."""
        service = LineageService(test_db)

        # Get upstream of order_summary with depth 1 (should find orders and users only)
        graph = service.get_lineage(
            objects["order_summary"].id, direction="upstream", depth=1
        )

        assert graph.root.id == objects["order_summary"].id
        assert graph.root.object_name == "order_summary"
        assert graph.direction == "upstream"
        assert len(graph.nodes) == 2

        node_ids = {n.id for n in graph.nodes}
        assert node_ids == {objects["orders"].id, objects["users"].id}

        # All nodes should be at distance 1
        for node in graph.nodes:
            assert node.distance == 1

    def test_get_lineage_upstream_depth(
        self,
        test_db: Session,
        source: DataSource,
        objects: dict[str, CatalogObject],
        dependencies,
    ):
        """Test upstream lineage with depth."""
        service = LineageService(test_db)

        # Get upstream of daily_report with depth 2
        graph = service.get_lineage(
            objects["daily_report"].id, direction="upstream", depth=2
        )

        # Depth 1: order_summary
        # Depth 2: orders, users
        assert len(graph.nodes) == 3

        # Check distances
        by_distance = {}
        for node in graph.nodes:
            by_distance.setdefault(node.distance, []).append(node.object_name)

        assert "order_summary" in by_distance[1]
        assert set(by_distance[2]) == {"orders", "users"}

    def test_get_lineage_downstream(
        self,
        test_db: Session,
        source: DataSource,
        objects: dict[str, CatalogObject],
        dependencies,
    ):
        """Test getting downstream lineage."""
        service = LineageService(test_db)

        # Get downstream of orders with depth 1 (should find order_summary only)
        graph = service.get_lineage(
            objects["orders"].id, direction="downstream", depth=1
        )

        assert graph.root.id == objects["orders"].id
        assert graph.direction == "downstream"
        assert len(graph.nodes) == 1
        assert graph.nodes[0].object_name == "order_summary"

    def test_get_lineage_downstream_depth(
        self,
        test_db: Session,
        source: DataSource,
        objects: dict[str, CatalogObject],
        dependencies,
    ):
        """Test downstream lineage with depth."""
        service = LineageService(test_db)

        # Get downstream of orders with depth 2
        graph = service.get_lineage(
            objects["orders"].id, direction="downstream", depth=2
        )

        # Depth 1: order_summary
        # Depth 2: daily_report
        assert len(graph.nodes) == 2

        by_distance = {}
        for node in graph.nodes:
            by_distance.setdefault(node.distance, []).append(node.object_name)

        assert "order_summary" in by_distance[1]
        assert "daily_report" in by_distance[2]

    def test_get_lineage_both(
        self,
        test_db: Session,
        source: DataSource,
        objects: dict[str, CatalogObject],
        dependencies,
    ):
        """Test getting both upstream and downstream lineage."""
        service = LineageService(test_db)

        # Get both directions from order_summary with depth 1
        # Upstream: orders, users
        # Downstream: daily_report
        graph = service.get_lineage(
            objects["order_summary"].id, direction="both", depth=1
        )

        assert graph.root.id == objects["order_summary"].id
        assert graph.direction == "both"
        assert len(graph.nodes) == 3

        node_names = {n.object_name for n in graph.nodes}
        assert node_names == {"orders", "users", "daily_report"}

        # All nodes should be at distance 1
        for node in graph.nodes:
            assert node.distance == 1

    def test_get_lineage_both_no_duplicates(
        self,
        test_db: Session,
        source: DataSource,
        objects: dict[str, CatalogObject],
        dependencies,
    ):
        """Test that 'both' direction doesn't create duplicate nodes or edges."""
        service = LineageService(test_db)

        # orders: upstream raw_events, downstream order_summary
        graph = service.get_lineage(objects["orders"].id, direction="both", depth=2)

        assert graph.root.id == objects["orders"].id

        # Should not have duplicate nodes
        node_ids = [n.id for n in graph.nodes]
        assert len(node_ids) == len(set(node_ids))

        # Should not have duplicate edges
        edge_keys = [(e.from_id, e.to_id) for e in graph.edges]
        assert len(edge_keys) == len(set(edge_keys))

    def test_get_lineage_truncated(
        self,
        test_db: Session,
        source: DataSource,
        objects: dict[str, CatalogObject],
        dependencies,
    ):
        """Test lineage truncation when depth is reached."""
        service = LineageService(test_db)

        # Get upstream of daily_report with depth 1
        graph = service.get_lineage(
            objects["daily_report"].id, direction="upstream", depth=1
        )

        # Should only get order_summary (depth 1)
        assert len(graph.nodes) == 1
        assert graph.nodes[0].object_name == "order_summary"
        assert graph.truncated is True

    def test_get_lineage_no_dependencies(
        self,
        test_db: Session,
        source: DataSource,
        objects: dict[str, CatalogObject],
        dependencies,
    ):
        """Test lineage for object with no dependencies."""
        service = LineageService(test_db)

        # raw_events has no upstream
        graph = service.get_lineage(objects["raw_events"].id, direction="upstream")

        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_get_lineage_object_not_found(self, test_db: Session):
        """Test that lineage raises error for non-existent object."""
        service = LineageService(test_db)

        with pytest.raises(ObjectNotFoundError):
            service.get_lineage(99999, direction="upstream")

    def test_get_lineage_summary(
        self,
        test_db: Session,
        source: DataSource,
        objects: dict[str, CatalogObject],
        dependencies,
    ):
        """Test getting lineage summary counts."""
        service = LineageService(test_db)

        # order_summary: 2 upstream (orders, users), 1 downstream (daily_report)
        summary = service.get_lineage_summary(objects["order_summary"].id)

        assert summary.upstream_count == 2
        assert summary.downstream_count == 1
        assert summary.external_count == 0

    def test_ingest_dependencies(self, test_db: Session, source: DataSource):
        """Test ingesting dependencies from adapter format."""
        obj_repo = CatalogObjectRepository(test_db)
        obj_repo.upsert(source.id, "schema1", "table_a", "TABLE")
        obj_repo.upsert(source.id, "schema1", "table_b", "TABLE")
        obj_repo.upsert(source.id, "schema1", "view_c", "VIEW")
        test_db.commit()

        service = LineageService(test_db)

        raw_deps = [
            {
                "object_schema": "schema1",
                "object_name": "view_c",
                "target_schema": "schema1",
                "target_name": "table_a",
            },
            {
                "object_schema": "schema1",
                "object_name": "view_c",
                "target_schema": "schema1",
                "target_name": "table_b",
            },
            # External dependency
            {
                "object_schema": "schema1",
                "object_name": "view_c",
                "target_schema": "external",
                "target_name": "other_table",
                "target_type": "TABLE",
            },
        ]

        created, updated = service.ingest_dependencies(
            source.id, raw_deps, "source_metadata"
        )
        test_db.commit()

        assert created == 3
        assert updated == 0

        # Verify dependencies were created
        dep_repo = DependencyRepository(test_db)
        deps = dep_repo.get_by_source(source.id)
        assert len(deps) == 3

        # One should be external
        external_deps = [d for d in deps if d.target_id is None]
        assert len(external_deps) == 1
        assert external_deps[0].target_external["name"] == "other_table"

    def test_add_manual_dependency(
        self, test_db: Session, source: DataSource, objects: dict[str, CatalogObject]
    ):
        """Test adding a manual dependency."""
        service = LineageService(test_db)

        # Add manual dependency: users -> orders (users depends on orders)
        dep_id, obj_id, target_id = service.add_manual_dependency(
            f"demo.core.users",
            f"demo.core.orders",
        )
        test_db.commit()

        assert dep_id is not None
        assert obj_id == objects["users"].id
        assert target_id == objects["orders"].id

        # Verify it was created
        dep_repo = DependencyRepository(test_db)
        dep = dep_repo.get_by_natural_key(objects["users"].id, objects["orders"].id, "manual")
        assert dep is not None
        assert dep.parsing_source == "manual"

    def test_remove_manual_dependency(
        self, test_db: Session, source: DataSource, objects: dict[str, CatalogObject]
    ):
        """Test removing a manual dependency."""
        service = LineageService(test_db)
        dep_repo = DependencyRepository(test_db)

        # Add manual dependency first
        dep_repo.upsert(
            source.id,
            objects["users"].id,
            objects["orders"].id,
            "DIRECT",
            "manual",
        )
        test_db.commit()

        # Remove it
        result = service.remove_manual_dependency(
            objects["users"].id, objects["orders"].id
        )
        test_db.commit()

        assert result is True

        # Verify it was removed
        dep = dep_repo.get_by_natural_key(
            objects["users"].id, objects["orders"].id, "manual"
        )
        assert dep is None
