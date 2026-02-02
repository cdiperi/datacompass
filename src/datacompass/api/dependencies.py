"""FastAPI dependency injection for services and database sessions."""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from datacompass.core.database import get_session, init_database
from datacompass.core.services import (
    CatalogService,
    DocumentationService,
    SearchService,
    SourceService,
)
from datacompass.core.services.deprecation_service import DeprecationService
from datacompass.core.services.dq_service import DQService
from datacompass.core.services.lineage_service import LineageService
from datacompass.core.services.notification_service import NotificationService
from datacompass.core.services.scheduling_service import SchedulingService

# Flag to track if database has been initialized
_db_initialized = False


def get_db() -> Generator[Session, None, None]:
    """Yield database session with auto-commit/rollback.

    Initializes the database on first call and provides a session
    that commits on success or rolls back on exception.
    """
    global _db_initialized
    if not _db_initialized:
        init_database()
        _db_initialized = True

    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_db_initialized() -> None:
    """Reset the database initialized flag.

    Used for testing to ensure clean state.
    """
    global _db_initialized
    _db_initialized = False


# Type alias for database session dependency
DbSession = Annotated[Session, Depends(get_db)]


def get_source_service(session: DbSession) -> SourceService:
    """Get a SourceService instance with the current session."""
    return SourceService(session)


def get_catalog_service(session: DbSession) -> CatalogService:
    """Get a CatalogService instance with the current session."""
    return CatalogService(session)


def get_search_service(session: DbSession) -> SearchService:
    """Get a SearchService instance with the current session."""
    return SearchService(session)


def get_documentation_service(session: DbSession) -> DocumentationService:
    """Get a DocumentationService instance with the current session."""
    return DocumentationService(session)


def get_lineage_service(session: DbSession) -> LineageService:
    """Get a LineageService instance with the current session."""
    return LineageService(session)


def get_dq_service(session: DbSession) -> DQService:
    """Get a DQService instance with the current session."""
    return DQService(session)


def get_deprecation_service(session: DbSession) -> DeprecationService:
    """Get a DeprecationService instance with the current session."""
    return DeprecationService(session)


def get_scheduling_service(session: DbSession) -> SchedulingService:
    """Get a SchedulingService instance with the current session."""
    return SchedulingService(session)


def get_notification_service(session: DbSession) -> NotificationService:
    """Get a NotificationService instance with the current session."""
    return NotificationService(session)


# Type aliases for service dependencies
SourceServiceDep = Annotated[SourceService, Depends(get_source_service)]
CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
DocumentationServiceDep = Annotated[DocumentationService, Depends(get_documentation_service)]
LineageServiceDep = Annotated[LineageService, Depends(get_lineage_service)]
DQServiceDep = Annotated[DQService, Depends(get_dq_service)]
DeprecationServiceDep = Annotated[DeprecationService, Depends(get_deprecation_service)]
SchedulingServiceDep = Annotated[SchedulingService, Depends(get_scheduling_service)]
NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]
