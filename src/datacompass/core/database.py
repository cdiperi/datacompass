"""Database engine and session management."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from datacompass.config import get_settings


def get_database_url() -> str:
    """Get the database URL, creating data directory if needed."""
    settings = get_settings()
    settings.ensure_data_dir()
    return settings.resolved_database_url


def create_database_engine(database_url: str | None = None, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine.

    Args:
        database_url: Database connection string. Defaults to settings.
        echo: Whether to echo SQL statements for debugging.

    Returns:
        SQLAlchemy Engine instance.
    """
    url = database_url or get_database_url()

    # SQLite-specific configuration
    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            echo=echo,
            connect_args={"check_same_thread": False},
        )
        # Enable foreign keys for SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    else:
        # PostgreSQL or other databases
        engine = create_engine(url, echo=echo, pool_pre_ping=True)

    return engine


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Create a session factory.

    Args:
        engine: SQLAlchemy engine. Creates default if not provided.

    Returns:
        Configured sessionmaker.
    """
    if engine is None:
        engine = create_database_engine()
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


# Default engine and session factory (lazily initialized)
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Get or create the default database engine."""
    global _engine
    if _engine is None:
        _engine = create_database_engine()
    return _engine


def get_session() -> Session:
    """Get a new database session."""
    global _session_factory
    if _session_factory is None:
        _session_factory = get_session_factory(get_engine())
    return _session_factory()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around operations.

    Usage:
        with session_scope() as session:
            session.add(obj)
            # Commits on success, rolls back on exception
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database(engine: Engine | None = None) -> None:
    """Initialize database tables.

    For production, use Alembic migrations instead.
    This is primarily for testing.
    """
    from sqlalchemy import text

    from datacompass.core.models.base import Base

    if engine is None:
        engine = get_engine()
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


def reset_engine() -> None:
    """Reset the global engine and session factory.

    Useful for testing to ensure a fresh state.
    """
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
