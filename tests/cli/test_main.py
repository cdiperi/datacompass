"""Tests for the main CLI entry point."""

import json
from pathlib import Path

from typer.testing import CliRunner

from datacompass import __version__
from datacompass.cli.main import app


class TestVersion:
    """Tests for version display."""

    def test_version_flag(self, cli_runner: CliRunner):
        """Test --version flag shows version."""
        result = cli_runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout

    def test_version_short_flag(self, cli_runner: CliRunner):
        """Test -v flag shows version."""
        result = cli_runner.invoke(app, ["-v"])
        assert result.exit_code == 0
        assert __version__ in result.stdout


class TestHelp:
    """Tests for help display."""

    def test_help_flag(self, cli_runner: CliRunner):
        """Test --help flag shows help text."""
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "datacompass" in result.stdout.lower()
        assert "metadata catalog" in result.stdout.lower()

    def test_no_args_shows_help(self, cli_runner: CliRunner):
        """Test that running without arguments shows help."""
        result = cli_runner.invoke(app, [])
        # Typer returns exit code 2 when showing help due to no_args_is_help
        assert result.exit_code == 2
        assert "Usage" in result.stdout


class TestSourceCommands:
    """Tests for source command group."""

    def test_source_help(self, cli_runner: CliRunner):
        """Test source --help shows subcommands."""
        result = cli_runner.invoke(app, ["source", "--help"])
        assert result.exit_code == 0
        assert "add" in result.stdout
        assert "list" in result.stdout
        assert "test" in result.stdout

    def test_source_add_success(
        self, cli_runner: CliRunner, temp_data_dir: Path, sample_config_file: Path
    ):
        """Test source add creates a new source."""
        result = cli_runner.invoke(
            app,
            [
                "source",
                "add",
                "prod",
                "--type",
                "databricks",
                "--config",
                str(sample_config_file),
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["name"] == "prod"
        assert output["type"] == "databricks"

    def test_source_add_invalid_type(
        self, cli_runner: CliRunner, temp_data_dir: Path, sample_config_file: Path
    ):
        """Test source add with invalid type shows error."""
        result = cli_runner.invoke(
            app,
            [
                "source",
                "add",
                "test",
                "--type",
                "nonexistent",
                "--config",
                str(sample_config_file),
            ],
        )
        assert result.exit_code == 1
        assert "unknown source type" in result.output.lower()

    def test_source_list_empty(self, cli_runner: CliRunner, temp_data_dir: Path):
        """Test source list with no sources returns empty list."""
        result = cli_runner.invoke(app, ["source", "list"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output == []

    def test_source_list_with_sources(
        self, cli_runner: CliRunner, temp_data_dir: Path, sample_config_file: Path
    ):
        """Test source list shows added sources."""
        # Add a source first
        cli_runner.invoke(
            app,
            ["source", "add", "test", "--type", "databricks", "--config", str(sample_config_file)],
        )

        result = cli_runner.invoke(app, ["source", "list"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert len(output) == 1
        assert output[0]["name"] == "test"


class TestObjectsCommands:
    """Tests for objects command group."""

    def test_objects_help(self, cli_runner: CliRunner):
        """Test objects --help shows subcommands."""
        result = cli_runner.invoke(app, ["objects", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout
        assert "show" in result.stdout

    def test_objects_list_empty(self, cli_runner: CliRunner, temp_data_dir: Path):
        """Test objects list with no objects returns empty list."""
        result = cli_runner.invoke(app, ["objects", "list"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output == []

    def test_objects_show_not_found(self, cli_runner: CliRunner, temp_data_dir: Path):
        """Test objects show with invalid ID returns error."""
        result = cli_runner.invoke(app, ["objects", "show", "nonexistent.schema.table"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestSearchCommands:
    """Tests for search command."""

    def test_search_help(self, cli_runner: CliRunner):
        """Test search --help shows usage."""
        result = cli_runner.invoke(app, ["search", "--help"])
        assert result.exit_code == 0
        assert "search" in result.stdout.lower()

    def test_search_no_results(self, cli_runner: CliRunner, temp_data_dir):
        """Test search with no results shows appropriate message."""
        result = cli_runner.invoke(app, ["search", "nonexistent"])
        assert result.exit_code == 0
        assert "no results" in result.output.lower()


class TestDqCommands:
    """Tests for data quality command group."""

    def test_dq_help(self, cli_runner: CliRunner):
        """Test dq --help shows subcommands."""
        result = cli_runner.invoke(app, ["dq", "--help"])
        assert result.exit_code == 0
        assert "run" in result.stdout
        assert "status" in result.stdout

    def test_dq_run_no_configs(self, cli_runner: CliRunner):
        """Test dq run with --all when no configs exist."""
        result = cli_runner.invoke(app, ["dq", "run", "--all"])
        assert result.exit_code == 0
        # Should return empty array when no configs
        assert "[]" in result.output or "No enabled" in result.output


class TestScanCommand:
    """Tests for scan command."""

    def test_scan_help(self, cli_runner: CliRunner):
        """Test scan --help shows options."""
        result = cli_runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--full" in result.stdout
        assert "--format" in result.stdout

    def test_scan_source_not_found(self, cli_runner: CliRunner, temp_data_dir: Path):
        """Test scan with non-existent source shows error."""
        result = cli_runner.invoke(app, ["scan", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestAdaptersCommands:
    """Tests for adapters command group."""

    def test_adapters_list(self, cli_runner: CliRunner):
        """Test adapters list shows registered adapters."""
        result = cli_runner.invoke(app, ["adapters", "list"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert len(output) >= 1

        # Find databricks
        types = [a["type"] for a in output]
        assert "databricks" in types

    def test_adapters_list_table_format(self, cli_runner: CliRunner):
        """Test adapters list with table format."""
        result = cli_runner.invoke(app, ["adapters", "list", "--format", "table"])
        assert result.exit_code == 0
        assert "databricks" in result.stdout.lower()
