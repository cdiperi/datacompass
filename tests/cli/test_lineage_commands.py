"""Tests for lineage CLI commands."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from datacompass.cli.main import app
from datacompass.core.models.dependency import LineageGraph, LineageNode


class TestLineageCommand:
    """Test cases for the lineage command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_lineage_graph(self) -> LineageGraph:
        """Create a mock lineage graph for testing."""
        return LineageGraph(
            root=LineageNode(
                id=3,
                source_name="demo",
                schema_name="analytics",
                object_name="order_summary",
                object_type="VIEW",
                distance=0,
            ),
            nodes=[
                LineageNode(
                    id=1,
                    source_name="demo",
                    schema_name="core",
                    object_name="orders",
                    object_type="TABLE",
                    distance=1,
                ),
                LineageNode(
                    id=2,
                    source_name="demo",
                    schema_name="core",
                    object_name="users",
                    object_type="TABLE",
                    distance=1,
                ),
            ],
            external_nodes=[],
            edges=[
                {"from_id": 3, "to_id": 1, "dependency_type": "DIRECT", "confidence": "HIGH"},
                {"from_id": 3, "to_id": 2, "dependency_type": "DIRECT", "confidence": "HIGH"},
            ],
            direction="upstream",
            depth=3,
            truncated=False,
        )

    def test_lineage_json_output(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
        mock_lineage_graph: LineageGraph,
    ):
        """Test lineage command with JSON output."""
        # Mock the services
        with patch("datacompass.cli.main.CatalogService") as MockCatalog, patch(
            "datacompass.cli.main.LineageService"
        ) as MockLineage:
            # Setup mock catalog service
            mock_catalog = MockCatalog.return_value
            mock_obj = type("Object", (), {"id": 3})()
            mock_catalog.get_object.return_value = mock_obj

            # Setup mock lineage service
            mock_lineage = MockLineage.return_value
            mock_lineage.get_lineage.return_value = mock_lineage_graph

            result = runner.invoke(
                app, ["lineage", "demo.analytics.order_summary", "--format", "json"]
            )

            assert result.exit_code == 0
            data = json.loads(result.stdout)

            assert data["root"]["object_name"] == "order_summary"
            assert len(data["nodes"]) == 2
            assert data["direction"] == "upstream"

    def test_lineage_table_output(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
        mock_lineage_graph: LineageGraph,
    ):
        """Test lineage command with table output."""
        with patch("datacompass.cli.main.CatalogService") as MockCatalog, patch(
            "datacompass.cli.main.LineageService"
        ) as MockLineage:
            mock_catalog = MockCatalog.return_value
            mock_obj = type("Object", (), {"id": 3})()
            mock_catalog.get_object.return_value = mock_obj

            mock_lineage = MockLineage.return_value
            mock_lineage.get_lineage.return_value = mock_lineage_graph

            result = runner.invoke(
                app, ["lineage", "demo.analytics.order_summary", "--format", "table"]
            )

            assert result.exit_code == 0
            assert "UPSTREAM DEPENDENCIES" in result.stdout
            assert "orders" in result.stdout
            assert "users" in result.stdout

    def test_lineage_tree_output(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
        mock_lineage_graph: LineageGraph,
    ):
        """Test lineage command with tree output."""
        with patch("datacompass.cli.main.CatalogService") as MockCatalog, patch(
            "datacompass.cli.main.LineageService"
        ) as MockLineage:
            mock_catalog = MockCatalog.return_value
            mock_obj = type("Object", (), {"id": 3})()
            mock_catalog.get_object.return_value = mock_obj

            mock_lineage = MockLineage.return_value
            mock_lineage.get_lineage.return_value = mock_lineage_graph

            result = runner.invoke(
                app, ["lineage", "demo.analytics.order_summary", "--format", "tree"]
            )

            assert result.exit_code == 0
            # Tree format should show the root and children
            assert "order_summary" in result.stdout

    def test_lineage_direction_downstream(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
    ):
        """Test lineage command with downstream direction."""
        downstream_graph = LineageGraph(
            root=LineageNode(
                id=1,
                source_name="demo",
                schema_name="core",
                object_name="orders",
                object_type="TABLE",
                distance=0,
            ),
            nodes=[
                LineageNode(
                    id=3,
                    source_name="demo",
                    schema_name="analytics",
                    object_name="order_summary",
                    object_type="VIEW",
                    distance=1,
                ),
            ],
            external_nodes=[],
            edges=[],
            direction="downstream",
            depth=3,
            truncated=False,
        )

        with patch("datacompass.cli.main.CatalogService") as MockCatalog, patch(
            "datacompass.cli.main.LineageService"
        ) as MockLineage:
            mock_catalog = MockCatalog.return_value
            mock_obj = type("Object", (), {"id": 1})()
            mock_catalog.get_object.return_value = mock_obj

            mock_lineage = MockLineage.return_value
            mock_lineage.get_lineage.return_value = downstream_graph

            result = runner.invoke(
                app,
                [
                    "lineage",
                    "demo.core.orders",
                    "--direction",
                    "downstream",
                    "--format",
                    "json",
                ],
            )

            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["direction"] == "downstream"

            # Verify service was called with correct args
            mock_lineage.get_lineage.assert_called_once_with(
                object_id=1,
                direction="downstream",
                depth=3,
            )

    def test_lineage_depth_option(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
        mock_lineage_graph: LineageGraph,
    ):
        """Test lineage command with custom depth."""
        with patch("datacompass.cli.main.CatalogService") as MockCatalog, patch(
            "datacompass.cli.main.LineageService"
        ) as MockLineage:
            mock_catalog = MockCatalog.return_value
            mock_obj = type("Object", (), {"id": 3})()
            mock_catalog.get_object.return_value = mock_obj

            mock_lineage = MockLineage.return_value
            mock_lineage.get_lineage.return_value = mock_lineage_graph

            result = runner.invoke(
                app,
                [
                    "lineage",
                    "demo.analytics.order_summary",
                    "--depth",
                    "5",
                    "--format",
                    "json",
                ],
            )

            assert result.exit_code == 0
            mock_lineage.get_lineage.assert_called_once_with(
                object_id=3,
                direction="upstream",
                depth=5,
            )

    def test_lineage_object_not_found(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
    ):
        """Test lineage command when object doesn't exist."""
        from datacompass.core.services import ObjectNotFoundError

        with patch("datacompass.cli.main.CatalogService") as MockCatalog:
            mock_catalog = MockCatalog.return_value
            mock_catalog.get_object.side_effect = ObjectNotFoundError("nonexistent")

            result = runner.invoke(app, ["lineage", "nonexistent"])

            assert result.exit_code == 1
            # Error goes to stderr, so check output which includes both
            assert "Object not found" in result.output

    def test_lineage_help(self, runner: CliRunner):
        """Test lineage command help."""
        result = runner.invoke(app, ["lineage", "--help"])

        assert result.exit_code == 0
        assert "--direction" in result.stdout
        assert "--depth" in result.stdout
        assert "--format" in result.stdout
