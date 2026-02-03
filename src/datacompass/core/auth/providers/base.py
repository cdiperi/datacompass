"""Base authentication provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from datacompass.core.models.auth import User


@dataclass
class AuthResult:
    """Result of an authentication attempt.

    Attributes:
        success: Whether authentication was successful.
        user: The authenticated user (if successful).
        error: Error message (if unsuccessful).
        needs_registration: Whether the user needs to be registered (for OIDC/LDAP).
        external_user_info: External user info for registration (for OIDC/LDAP).
    """

    success: bool
    user: User | None = None
    error: str | None = None
    needs_registration: bool = False
    external_user_info: dict[str, Any] | None = None


class AuthProvider(ABC):
    """Abstract base class for authentication providers.

    Each auth provider implements a specific authentication mechanism
    (local password, OIDC, LDAP, etc.).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name (e.g., 'local', 'oidc', 'ldap')."""
        ...

    @abstractmethod
    def authenticate(
        self,
        credentials: dict[str, Any],
    ) -> AuthResult:
        """Authenticate a user with the given credentials.

        Args:
            credentials: Provider-specific credentials dict.
                For local: {"email": str, "password": str}
                For OIDC: {"token": str}
                For LDAP: {"username": str, "password": str}

        Returns:
            AuthResult with success status and user or error.
        """
        ...

    @abstractmethod
    def validate_token(self, token: str) -> AuthResult:
        """Validate an access token and return the associated user.

        Args:
            token: JWT access token to validate.

        Returns:
            AuthResult with success status and user or error.
        """
        ...

    def supports_password_auth(self) -> bool:
        """Check if provider supports password authentication.

        Returns:
            True if password auth is supported.
        """
        return False

    def supports_token_refresh(self) -> bool:
        """Check if provider supports token refresh.

        Returns:
            True if token refresh is supported.
        """
        return True
