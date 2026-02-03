"""Pytest configuration and shared fixtures."""

import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

# Import models to ensure all tables are registered with Base before create_all
from datacompass.core import models  # noqa: F401
from datacompass.core.models import Base


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI runner for testing Typer commands."""
    return CliRunner()


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Create an in-memory SQLite database for testing.

    Creates all tables and provides a session that auto-commits.
    """
    from sqlalchemy import text

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    # Create FTS5 virtual table for search (not handled by SQLAlchemy metadata)
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS catalog_fts USING fts5(
                    object_id UNINDEXED,
                    source_name,
                    schema_name,
                    object_name,
                    object_type,
                    description,
                    tags,
                    column_names,
                    tokenize='porter unicode61'
                )
                """
            )
        )
        conn.commit()

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary data directory for testing.

    Sets DATACOMPASS_DATA_DIR environment variable and cleans up after.
    Also resets the global database engine to ensure isolation.
    """
    from datacompass.config.settings import get_settings
    from datacompass.core.database import reset_engine

    # Reset any cached settings
    get_settings.cache_clear()

    data_dir = tmp_path / "datacompass"
    data_dir.mkdir()

    old_value = os.environ.get("DATACOMPASS_DATA_DIR")
    os.environ["DATACOMPASS_DATA_DIR"] = str(data_dir)

    # Reset engine to pick up new data dir
    reset_engine()

    try:
        yield data_dir
    finally:
        # Reset engine before restoring env
        reset_engine()

        if old_value is not None:
            os.environ["DATACOMPASS_DATA_DIR"] = old_value
        else:
            os.environ.pop("DATACOMPASS_DATA_DIR", None)

        # Clear cached settings
        get_settings.cache_clear()


@pytest.fixture
def mock_databricks_adapter():
    """Create a mock Databricks adapter for testing.

    Returns mock adapter that returns sample objects and columns.
    """
    adapter = MagicMock()

    # Make it work as async context manager
    adapter.__aenter__ = AsyncMock(return_value=adapter)
    adapter.__aexit__ = AsyncMock(return_value=None)

    # Mock methods
    adapter.test_connection = AsyncMock(return_value=True)
    adapter.get_objects = AsyncMock(
        return_value=[
            {
                "schema_name": "analytics",
                "object_name": "customers",
                "object_type": "TABLE",
                "source_metadata": {
                    "description": "Customer master data",
                    "created_at": "2024-01-01T00:00:00",
                },
            },
            {
                "schema_name": "analytics",
                "object_name": "orders",
                "object_type": "TABLE",
                "source_metadata": {
                    "description": "Order transactions",
                    "created_at": "2024-01-02T00:00:00",
                },
            },
            {
                "schema_name": "analytics",
                "object_name": "customer_summary",
                "object_type": "VIEW",
                "source_metadata": {
                    "description": "Customer aggregates",
                },
            },
        ]
    )

    adapter.get_columns = AsyncMock(
        return_value=[
            {
                "schema_name": "analytics",
                "object_name": "customers",
                "column_name": "customer_id",
                "position": 1,
                "source_metadata": {"data_type": "INTEGER", "nullable": False},
            },
            {
                "schema_name": "analytics",
                "object_name": "customers",
                "column_name": "name",
                "position": 2,
                "source_metadata": {"data_type": "STRING", "nullable": False},
            },
            {
                "schema_name": "analytics",
                "object_name": "customers",
                "column_name": "email",
                "position": 3,
                "source_metadata": {"data_type": "STRING", "nullable": True},
            },
            {
                "schema_name": "analytics",
                "object_name": "orders",
                "column_name": "order_id",
                "position": 1,
                "source_metadata": {"data_type": "INTEGER", "nullable": False},
            },
            {
                "schema_name": "analytics",
                "object_name": "orders",
                "column_name": "customer_id",
                "position": 2,
                "source_metadata": {"data_type": "INTEGER", "nullable": False},
            },
            {
                "schema_name": "analytics",
                "object_name": "orders",
                "column_name": "amount",
                "position": 3,
                "source_metadata": {"data_type": "DECIMAL(10,2)", "nullable": False},
            },
            {
                "schema_name": "analytics",
                "object_name": "customer_summary",
                "column_name": "customer_id",
                "position": 1,
                "source_metadata": {"data_type": "INTEGER", "nullable": False},
            },
            {
                "schema_name": "analytics",
                "object_name": "customer_summary",
                "column_name": "total_orders",
                "position": 2,
                "source_metadata": {"data_type": "INTEGER", "nullable": False},
            },
        ]
    )

    return adapter


@pytest.fixture
def sample_config_file(tmp_path: Path) -> Path:
    """Create a sample Databricks config file for testing."""
    config_file = tmp_path / "databricks.yaml"
    config_file.write_text(
        """
host: test-workspace.azuredatabricks.net
http_path: /sql/1.0/warehouses/abc123
catalog: main
auth_method: personal_token
access_token: test-token-12345
"""
    )
    return config_file


# =============================================================================
# Auth fixtures
# =============================================================================


@pytest.fixture
def admin_user(test_db: Session):
    """Create a test admin user with superuser privileges."""
    from datacompass.core.models.auth import UserCreate
    from datacompass.core.services.auth_service import AuthService

    # Enable auth temporarily
    old_mode = os.environ.get("DATACOMPASS_AUTH_MODE")
    os.environ["DATACOMPASS_AUTH_MODE"] = "local"

    from datacompass.config.settings import get_settings
    get_settings.cache_clear()

    try:
        service = AuthService(test_db)
        user = service.create_local_user(UserCreate(
            email="admin@test.example.com",
            password="adminpassword",
            display_name="Admin User",
            is_superuser=True,
        ))
        test_db.commit()
        yield user
    finally:
        if old_mode is not None:
            os.environ["DATACOMPASS_AUTH_MODE"] = old_mode
        else:
            os.environ.pop("DATACOMPASS_AUTH_MODE", None)
        get_settings.cache_clear()


@pytest.fixture
def regular_user(test_db: Session):
    """Create a test regular user without superuser privileges."""
    from datacompass.core.models.auth import UserCreate
    from datacompass.core.services.auth_service import AuthService

    # Enable auth temporarily
    old_mode = os.environ.get("DATACOMPASS_AUTH_MODE")
    os.environ["DATACOMPASS_AUTH_MODE"] = "local"

    from datacompass.config.settings import get_settings
    get_settings.cache_clear()

    try:
        service = AuthService(test_db)
        user = service.create_local_user(UserCreate(
            email="user@test.example.com",
            password="userpassword",
            display_name="Regular User",
            is_superuser=False,
        ))
        test_db.commit()
        yield user
    finally:
        if old_mode is not None:
            os.environ["DATACOMPASS_AUTH_MODE"] = old_mode
        else:
            os.environ.pop("DATACOMPASS_AUTH_MODE", None)
        get_settings.cache_clear()


@pytest.fixture
def api_key(test_db: Session, regular_user):
    """Create a test API key and return (APIKey, raw_key) tuple."""
    from datacompass.core.services.auth_service import AuthService

    # Enable auth temporarily
    old_mode = os.environ.get("DATACOMPASS_AUTH_MODE")
    os.environ["DATACOMPASS_AUTH_MODE"] = "local"

    from datacompass.config.settings import get_settings
    get_settings.cache_clear()

    try:
        service = AuthService(test_db)
        api_key_created = service.create_api_key(
            user=regular_user,
            name="Test API Key",
            scopes=["read", "write"],
        )
        test_db.commit()

        # Get the actual APIKey model from the database
        from datacompass.core.repositories.auth import APIKeyRepository
        repo = APIKeyRepository(test_db)
        api_key_model = repo.get_by_id(api_key_created.id)

        yield (api_key_model, api_key_created.key)
    finally:
        if old_mode is not None:
            os.environ["DATACOMPASS_AUTH_MODE"] = old_mode
        else:
            os.environ.pop("DATACOMPASS_AUTH_MODE", None)
        get_settings.cache_clear()
