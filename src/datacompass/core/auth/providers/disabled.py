"""Disabled authentication provider (no-op)."""

from typing import Any

from datacompass.core.auth.providers.base import AuthProvider, AuthResult


class DisabledAuthProvider(AuthProvider):
    """Authentication provider when auth is disabled.

    All operations succeed without actual authentication.
    Used when auth_mode is 'disabled'.
    """

    @property
    def provider_name(self) -> str:
        return "disabled"

    def authenticate(self, credentials: dict[str, Any]) -> AuthResult:
        """Always succeeds with no user.

        When auth is disabled, any credentials are accepted
        but no user session is created.
        """
        return AuthResult(
            success=True,
            user=None,
            error=None,
        )

    def validate_token(self, token: str) -> AuthResult:
        """Always succeeds with no user.

        When auth is disabled, all tokens are considered valid.
        """
        return AuthResult(
            success=True,
            user=None,
            error=None,
        )

    def supports_password_auth(self) -> bool:
        return False

    def supports_token_refresh(self) -> bool:
        return False
