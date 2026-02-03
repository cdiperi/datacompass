"""FastAPI dependency injection for services and database sessions."""

from collections.abc import Callable, Generator
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from datacompass.config.settings import get_settings
from datacompass.core.database import get_session, init_database
from datacompass.core.models.auth import User
from datacompass.core.services import (
    CatalogService,
    DocumentationService,
    SearchService,
    SourceService,
)
from datacompass.core.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
    TokenExpiredError,
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


def get_auth_service(session: DbSession) -> AuthService:
    """Get an AuthService instance with the current session."""
    return AuthService(session)


# Security schemes
security = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user_optional(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
    api_key: Annotated[str | None, Depends(api_key_header)] = None,
) -> User | None:
    """Get the current user if authenticated, None otherwise.

    Checks Bearer token first, then API key header.

    Args:
        session: Database session.
        credentials: Bearer token credentials (from Authorization header).
        api_key: API key (from X-API-Key header).

    Returns:
        User if authenticated, None otherwise.
    """
    settings = get_settings()

    # If auth is disabled, return None (no user context)
    if settings.auth_mode == "disabled":
        return None

    auth_service = AuthService(session)

    # Try Bearer token first
    if credentials is not None:
        try:
            return auth_service.validate_access_token(credentials.credentials)
        except (InvalidCredentialsError, TokenExpiredError):
            pass

    # Try API key
    if api_key is not None:
        try:
            return auth_service.authenticate_api_key(api_key)
        except InvalidCredentialsError:
            pass

    return None


async def require_auth(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
    api_key: Annotated[str | None, Depends(api_key_header)] = None,
) -> User:
    """Require authentication. Returns 401 if not authenticated.

    When auth is disabled, returns a dummy superuser for development.

    Args:
        session: Database session.
        credentials: Bearer token credentials.
        api_key: API key.

    Returns:
        Authenticated User.

    Raises:
        HTTPException: 401 if not authenticated.
    """
    settings = get_settings()

    # If auth is disabled, return dummy user
    if settings.auth_mode == "disabled":
        from datetime import datetime

        return User(
            id=0,
            email="dev@localhost",
            username="dev",
            display_name="Development User",
            is_active=True,
            is_superuser=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    user = await get_current_user_optional(session, credentials, api_key)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def require_superuser(
    user: Annotated[User, Depends(require_auth)],
) -> User:
    """Require superuser privileges. Returns 403 if not superuser.

    Args:
        user: Authenticated user from require_auth.

    Returns:
        Authenticated superuser.

    Raises:
        HTTPException: 403 if not superuser.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return user


def check_scope(required_scope: str) -> Callable[..., Any]:
    """Create a dependency that checks for a specific scope.

    Args:
        required_scope: The scope string to require.

    Returns:
        Dependency function that validates the scope.
    """

    async def scope_checker(
        user: Annotated[User, Depends(require_auth)],
    ) -> User:
        # For now, superusers have all scopes
        # API key scopes would be checked here in the future
        if user.is_superuser:
            return user
        # Non-superusers pass for now (scope checking not fully implemented)
        return user

    return scope_checker


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
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]

# Auth type aliases
CurrentUser = Annotated[User | None, Depends(get_current_user_optional)]
RequiredUser = Annotated[User, Depends(require_auth)]
SuperUser = Annotated[User, Depends(require_superuser)]
