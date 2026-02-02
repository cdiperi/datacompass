"""API test fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from datacompass.api.app import create_app
from datacompass.api.dependencies import get_db

# Import all models to ensure they're registered with Base before creating tables
from datacompass.core.models import (  # noqa: F401
    Base,
    CatalogObject,
    Column,
    DataSource,
    Dependency,
    Deprecation,
    DeprecationCampaign,
    DQBreach,
    DQConfig,
    DQExpectation,
    DQResult,
    NotificationChannel,
    NotificationLog,
    NotificationRule,
    Schedule,
    ScheduleRun,
)


@pytest.fixture
def test_engine():
    """Create an in-memory SQLite engine for testing.

    Uses StaticPool to ensure all connections share the same in-memory database.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables
    Base.metadata.create_all(engine)

    # Create FTS5 virtual table for search (not handled by SQLAlchemy)
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

    yield engine

    engine.dispose()


@pytest.fixture
def test_session_factory(test_engine):
    """Create a session factory bound to the test engine."""
    return sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture
def client(test_session_factory) -> Generator[TestClient, None, None]:
    """Create a test client with database dependency override.

    Yields:
        FastAPI TestClient configured with test database.
    """
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

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client_with_source(test_session_factory) -> Generator[TestClient, None, None]:
    """Create a test client with a pre-configured source.

    Mocks the adapter registry to allow source creation.
    """
    from datacompass.core.adapters import AdapterRegistry
    from datacompass.core.adapters.schemas import DatabricksConfig

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

    with TestClient(app) as test_client:
        # Mock adapter registration check
        with patch.object(AdapterRegistry, "is_registered", return_value=True):
            with patch.object(AdapterRegistry, "get_config_schema", return_value=DatabricksConfig):
                # Create a test source
                response = test_client.post(
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
                        "display_name": "Test Source",
                    },
                )
                assert response.status_code == 201, f"Failed to create source: {response.json()}"

        yield test_client


@pytest.fixture
def mock_adapter():
    """Create a mock adapter for testing scan operations."""
    adapter = MagicMock()
    adapter.__aenter__ = AsyncMock(return_value=adapter)
    adapter.__aexit__ = AsyncMock(return_value=None)
    adapter.test_connection = AsyncMock(return_value=True)
    adapter.get_objects = AsyncMock(
        return_value=[
            {
                "schema_name": "analytics",
                "object_name": "customers",
                "object_type": "TABLE",
                "source_metadata": {"description": "Customer data"},
            },
            {
                "schema_name": "analytics",
                "object_name": "orders",
                "object_type": "TABLE",
                "source_metadata": {"description": "Order data"},
            },
        ]
    )
    adapter.get_columns = AsyncMock(
        return_value=[
            {
                "schema_name": "analytics",
                "object_name": "customers",
                "column_name": "id",
                "position": 1,
                "source_metadata": {"data_type": "INTEGER"},
            },
            {
                "schema_name": "analytics",
                "object_name": "customers",
                "column_name": "name",
                "position": 2,
                "source_metadata": {"data_type": "STRING"},
            },
            {
                "schema_name": "analytics",
                "object_name": "orders",
                "column_name": "order_id",
                "position": 1,
                "source_metadata": {"data_type": "INTEGER"},
            },
        ]
    )
    return adapter
