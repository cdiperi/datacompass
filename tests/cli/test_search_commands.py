"""Tests for search and documentation CLI commands."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from datacompass.cli.main import app


class TestSearchCommands:
    """Tests for search command."""

    def test_search_help(self, cli_runner: CliRunner):
        """Test search --help shows usage."""
        result = cli_runner.invoke(app, ["search", "--help"])
        assert result.exit_code == 0
        assert "search" in result.stdout.lower()

    def test_search_empty_results(self, cli_runner: CliRunner, temp_data_dir: Path):
        """Test search with no results."""
        result = cli_runner.invoke(app, ["search", "nonexistent"])
        assert result.exit_code == 0
        assert "no results" in result.output.lower()

    def test_reindex_help(self, cli_runner: CliRunner):
        """Test reindex --help."""
        result = cli_runner.invoke(app, ["reindex", "--help"])
        assert result.exit_code == 0
        assert "--source" in result.stdout

    def test_reindex_empty(self, cli_runner: CliRunner, temp_data_dir: Path):
        """Test reindex with no objects."""
        result = cli_runner.invoke(app, ["reindex"])
        assert result.exit_code == 0
        assert "indexed 0 objects" in result.output.lower()


class TestObjectsDescribeCommand:
    """Tests for objects describe command."""

    def test_describe_help(self, cli_runner: CliRunner):
        """Test objects describe --help."""
        result = cli_runner.invoke(app, ["objects", "describe", "--help"])
        assert result.exit_code == 0
        assert "--set" in result.stdout

    def test_describe_not_found(self, cli_runner: CliRunner, temp_data_dir: Path):
        """Test describe nonexistent object."""
        result = cli_runner.invoke(app, ["objects", "describe", "source.schema.table"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestObjectsTagCommand:
    """Tests for objects tag command."""

    def test_tag_help(self, cli_runner: CliRunner):
        """Test objects tag --help."""
        result = cli_runner.invoke(app, ["objects", "tag", "--help"])
        assert result.exit_code == 0
        assert "--add" in result.stdout
        assert "--remove" in result.stdout

    def test_tag_not_found(self, cli_runner: CliRunner, temp_data_dir: Path):
        """Test tagging nonexistent object."""
        result = cli_runner.invoke(
            app, ["objects", "tag", "source.schema.table", "--add", "test"]
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestSearchWithData:
    """Tests for search commands with actual data."""

    @pytest.fixture
    def scanned_source(self, cli_runner: CliRunner, temp_data_dir: Path, sample_config_file: Path, mock_databricks_adapter):
        """Create a source and scan it to populate data."""
        # Add source
        result = cli_runner.invoke(
            app,
            [
                "source", "add", "test-source",
                "--type", "databricks",
                "--config", str(sample_config_file),
            ],
        )
        assert result.exit_code == 0

        # Scan with mocked adapter
        with patch(
            "datacompass.core.services.catalog_service.AdapterRegistry.get_adapter"
        ) as mock_get:
            mock_get.return_value = mock_databricks_adapter
            result = cli_runner.invoke(app, ["scan", "test-source"])
            assert result.exit_code == 0

        return "test-source"

    def test_search_finds_scanned_objects(
        self, cli_runner: CliRunner, scanned_source: str
    ):
        """Test that search finds scanned objects."""
        result = cli_runner.invoke(app, ["search", "customers"])
        assert result.exit_code == 0

        # Should find the customers table
        output = json.loads(result.output)
        assert len(output) >= 1
        names = [r["object_name"] for r in output]
        assert "customers" in names or "customer_summary" in names

    def test_search_with_source_filter(
        self, cli_runner: CliRunner, scanned_source: str
    ):
        """Test search with source filter."""
        result = cli_runner.invoke(
            app, ["search", "analytics", "--source", "test-source"]
        )
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert len(output) >= 1

    def test_search_with_type_filter(
        self, cli_runner: CliRunner, scanned_source: str
    ):
        """Test search with object type filter."""
        result = cli_runner.invoke(
            app, ["search", "customer", "--type", "VIEW"]
        )
        assert result.exit_code == 0
        output = json.loads(result.output)
        # Should only find the VIEW
        for r in output:
            assert r["object_type"] == "VIEW"

    def test_describe_set_description(
        self, cli_runner: CliRunner, scanned_source: str
    ):
        """Test setting a description."""
        result = cli_runner.invoke(
            app,
            [
                "objects", "describe", "test-source.analytics.customers",
                "--set", "Main customer table",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["description"] == "Main customer table"
        assert output["status"] == "updated"

    def test_describe_get_description(
        self, cli_runner: CliRunner, scanned_source: str
    ):
        """Test getting a description."""
        # First set
        cli_runner.invoke(
            app,
            [
                "objects", "describe", "test-source.analytics.customers",
                "--set", "Test description",
            ],
        )

        # Then get
        result = cli_runner.invoke(
            app, ["objects", "describe", "test-source.analytics.customers"]
        )
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["description"] == "Test description"

    def test_tag_add_and_list(self, cli_runner: CliRunner, scanned_source: str):
        """Test adding tags."""
        result = cli_runner.invoke(
            app,
            [
                "objects", "tag", "test-source.analytics.customers",
                "--add", "pii",
                "--add", "core",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "pii" in output["tags"]
        assert "core" in output["tags"]

    def test_tag_remove(self, cli_runner: CliRunner, scanned_source: str):
        """Test removing tags."""
        # Add tags first
        cli_runner.invoke(
            app,
            [
                "objects", "tag", "test-source.analytics.customers",
                "--add", "pii",
                "--add", "core",
            ],
        )

        # Remove one
        result = cli_runner.invoke(
            app,
            [
                "objects", "tag", "test-source.analytics.customers",
                "--remove", "pii",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "pii" not in output["tags"]
        assert "core" in output["tags"]

    def test_search_finds_tagged_objects(self, cli_runner: CliRunner, scanned_source: str):
        """Test that search finds objects by tag."""
        # Add a unique tag
        cli_runner.invoke(
            app,
            [
                "objects", "tag", "test-source.analytics.customers",
                "--add", "uniquetag123",
            ],
        )

        # Search by tag
        result = cli_runner.invoke(app, ["search", "uniquetag123"])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert len(output) == 1
        assert output[0]["object_name"] == "customers"
