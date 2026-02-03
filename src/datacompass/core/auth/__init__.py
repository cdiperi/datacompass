"""Authentication module for Data Compass."""

from sqlalchemy.orm import Session

from datacompass.config.settings import get_settings
from datacompass.core.auth.providers import (
    AuthProvider,
    AuthResult,
    DisabledAuthProvider,
    LocalAuthProvider,
)


def get_provider(session: Session) -> AuthProvider:
    """Get the appropriate auth provider based on settings.

    Args:
        session: SQLAlchemy database session.

    Returns:
        AuthProvider instance for the configured auth mode.

    Raises:
        ValueError: If auth mode is not supported.
    """
    settings = get_settings()

    if settings.auth_mode == "disabled":
        return DisabledAuthProvider()
    elif settings.auth_mode == "local":
        return LocalAuthProvider(session)
    elif settings.auth_mode == "oidc":
        raise ValueError("OIDC authentication is not yet implemented")
    elif settings.auth_mode == "ldap":
        raise ValueError("LDAP authentication is not yet implemented")
    else:
        raise ValueError(f"Unknown auth mode: {settings.auth_mode}")


__all__ = [
    "get_provider",
    "AuthProvider",
    "AuthResult",
    "DisabledAuthProvider",
    "LocalAuthProvider",
]
