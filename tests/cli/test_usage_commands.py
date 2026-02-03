"""Tests for usage CLI commands."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from datacompass.cli.main import app
from datacompass.core.models.usage import (
    HotTableItem,
    UsageCollectResult,
    UsageMetricDetailResponse,
    UsageMetricResponse,
)


class TestUsageCommands:
    """Test cases for usage CLI commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_collect_result(self) -> UsageCollectResult:
        """Create a mock collect result."""
        return UsageCollectResult(
            source_name="demo",
            collected_count=10,
            skipped_count=2,
            error_count=0,
            collected_at=datetime(2025, 1, 15, 10, 30, 0),
        )

    @pytest.fixture
    def mock_usage_metric(self) -> UsageMetricDetailResponse:
        """Create a mock usage metric response."""
        return UsageMetricDetailResponse(
            id=1,
            object_id=123,
            collected_at=datetime(2025, 1, 15, 10, 30, 0),
            row_count=10000,
            size_bytes=5 * 1024 * 1024,  # 5 MB
            read_count=500,
            write_count=50,
            last_read_at=None,
            last_written_at=None,
            distinct_users=None,
            query_count=None,
            source_metrics={"seq_scan": 200, "idx_scan": 300},
            object_name="customers",
            schema_name="analytics",
            source_name="demo",
        )

    @pytest.fixture
    def mock_hot_tables(self) -> list[HotTableItem]:
        """Create mock hot tables."""
        return [
            HotTableItem(
                object_id=1,
                object_name="orders",
                schema_name="analytics",
                source_name="demo",
                row_count=50000,
                size_bytes=20 * 1024 * 1024,
                read_count=1000,
                write_count=100,
            ),
            HotTableItem(
                object_id=2,
                object_name="customers",
                schema_name="analytics",
                source_name="demo",
                row_count=10000,
                size_bytes=5 * 1024 * 1024,
                read_count=500,
                write_count=50,
            ),
        ]

    # =========================================================================
    # Usage Collect Tests
    # =========================================================================

    def test_usage_collect_json(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
        mock_collect_result: UsageCollectResult,
    ):
        """Test usage collect with JSON output."""
        with patch("datacompass.cli.main.UsageService") as MockService:
            mock_service = MagicMock()
            mock_service.collect_metrics.return_value = mock_collect_result
            MockService.return_value = mock_service

            result = runner.invoke(app, ["usage", "collect", "demo"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["source_name"] == "demo"
        assert data["collected_count"] == 10
        assert data["skipped_count"] == 2

    def test_usage_collect_table(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
        mock_collect_result: UsageCollectResult,
    ):
        """Test usage collect with table output."""
        with patch("datacompass.cli.main.UsageService") as MockService:
            mock_service = MagicMock()
            mock_service.collect_metrics.return_value = mock_collect_result
            MockService.return_value = mock_service

            result = runner.invoke(app, ["usage", "collect", "demo", "--format", "table"])

        assert result.exit_code == 0
        assert "Usage Collection Complete" in result.output
        assert "demo" in result.output
        assert "10" in result.output  # collected count

    # =========================================================================
    # Usage Show Tests
    # =========================================================================

    def test_usage_show_json(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
        mock_usage_metric: UsageMetricDetailResponse,
    ):
        """Test usage show with JSON output."""
        with patch("datacompass.cli.main.UsageService") as MockService:
            mock_service = MagicMock()
            mock_service.get_object_usage.return_value = mock_usage_metric
            MockService.return_value = mock_service

            result = runner.invoke(app, ["usage", "show", "demo.analytics.customers"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["object_name"] == "customers"
        assert data["row_count"] == 10000
        assert data["read_count"] == 500

    def test_usage_show_table(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
        mock_usage_metric: UsageMetricDetailResponse,
    ):
        """Test usage show with table output."""
        with patch("datacompass.cli.main.UsageService") as MockService:
            mock_service = MagicMock()
            mock_service.get_object_usage.return_value = mock_usage_metric
            MockService.return_value = mock_service

            result = runner.invoke(
                app, ["usage", "show", "demo.analytics.customers", "--format", "table"]
            )

        assert result.exit_code == 0
        assert "Usage Metrics" in result.output
        assert "customers" in result.output
        assert "10000" in result.output  # row count

    def test_usage_show_no_metrics(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
    ):
        """Test usage show when no metrics exist."""
        with patch("datacompass.cli.main.UsageService") as MockService:
            mock_service = MagicMock()
            mock_service.get_object_usage.return_value = None
            MockService.return_value = mock_service

            result = runner.invoke(app, ["usage", "show", "demo.analytics.customers"])

        assert result.exit_code == 0
        assert "No usage metrics found" in result.output

    def test_usage_show_history(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
    ):
        """Test usage show with history flag."""
        mock_history = [
            UsageMetricResponse(
                id=i,
                object_id=123,
                collected_at=datetime(2025, 1, 15 - i, 10, 0, 0),
                row_count=1000 * (i + 1),
                size_bytes=1024 * 1024 * (i + 1),
                read_count=100 * (i + 1),
                write_count=10 * (i + 1),
            )
            for i in range(5)
        ]

        with patch("datacompass.cli.main.UsageService") as MockService:
            mock_service = MagicMock()
            mock_service.get_usage_history.return_value = mock_history
            MockService.return_value = mock_service

            result = runner.invoke(
                app, ["usage", "show", "demo.analytics.customers", "--history", "30"]
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 5

    def test_usage_show_object_not_found(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
    ):
        """Test usage show with non-existent object."""
        from datacompass.core.services.usage_service import ObjectNotFoundError

        with patch("datacompass.cli.main.UsageService") as MockService:
            mock_service = MagicMock()
            mock_service.get_object_usage.side_effect = ObjectNotFoundError("nonexistent")
            MockService.return_value = mock_service

            result = runner.invoke(app, ["usage", "show", "nonexistent"])

        assert result.exit_code == 1
        assert "Object not found" in result.output

    # =========================================================================
    # Usage Hot Tests
    # =========================================================================

    def test_usage_hot_json(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
        mock_hot_tables: list[HotTableItem],
    ):
        """Test usage hot with JSON output."""
        with patch("datacompass.cli.main.UsageService") as MockService:
            mock_service = MagicMock()
            mock_service.get_hot_tables.return_value = mock_hot_tables
            MockService.return_value = mock_service

            result = runner.invoke(app, ["usage", "hot"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["object_name"] == "orders"
        assert data[0]["read_count"] == 1000

    def test_usage_hot_table(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
        mock_hot_tables: list[HotTableItem],
    ):
        """Test usage hot with table output."""
        with patch("datacompass.cli.main.UsageService") as MockService:
            mock_service = MagicMock()
            mock_service.get_hot_tables.return_value = mock_hot_tables
            MockService.return_value = mock_service

            result = runner.invoke(app, ["usage", "hot", "--format", "table"])

        assert result.exit_code == 0
        assert "Hot Tables" in result.output
        assert "orders" in result.output
        assert "1000" in result.output  # read count

    def test_usage_hot_with_source_filter(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
        mock_hot_tables: list[HotTableItem],
    ):
        """Test usage hot with source filter."""
        with patch("datacompass.cli.main.UsageService") as MockService:
            mock_service = MagicMock()
            mock_service.get_hot_tables.return_value = mock_hot_tables
            MockService.return_value = mock_service

            result = runner.invoke(app, ["usage", "hot", "--source", "demo"])

        assert result.exit_code == 0
        mock_service.get_hot_tables.assert_called_once_with(
            source_name="demo",
            days=7,
            limit=20,
            order_by="read_count",
        )

    def test_usage_hot_with_options(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
        mock_hot_tables: list[HotTableItem],
    ):
        """Test usage hot with custom options."""
        with patch("datacompass.cli.main.UsageService") as MockService:
            mock_service = MagicMock()
            mock_service.get_hot_tables.return_value = mock_hot_tables
            MockService.return_value = mock_service

            result = runner.invoke(
                app,
                [
                    "usage",
                    "hot",
                    "--days",
                    "30",
                    "--limit",
                    "10",
                    "--order-by",
                    "size_bytes",
                ],
            )

        assert result.exit_code == 0
        mock_service.get_hot_tables.assert_called_once_with(
            source_name=None,
            days=30,
            limit=10,
            order_by="size_bytes",
        )

    def test_usage_hot_empty(
        self,
        runner: CliRunner,
        temp_data_dir: Path,
    ):
        """Test usage hot with no metrics."""
        with patch("datacompass.cli.main.UsageService") as MockService:
            mock_service = MagicMock()
            mock_service.get_hot_tables.return_value = []
            MockService.return_value = mock_service

            result = runner.invoke(app, ["usage", "hot"])

        assert result.exit_code == 0
        assert "No usage metrics found" in result.output
