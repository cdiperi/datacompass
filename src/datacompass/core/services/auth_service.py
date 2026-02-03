"""Service for authentication and user management."""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from datacompass.config.settings import get_settings
from datacompass.core.auth import get_provider
from datacompass.core.auth.providers.local import LocalAuthProvider
from datacompass.core.models.auth import (
    APIKey,
    APIKeyCreated,
    TokenResponse,
    User,
    UserCreate,
)
from datacompass.core.repositories.auth import (
    APIKeyRepository,
    RefreshTokenRepository,
    SessionRepository,
    UserRepository,
)

# =============================================================================
# Exceptions
# =============================================================================


class AuthServiceError(Exception):
    """Base exception for auth service errors."""

    pass


class InvalidCredentialsError(AuthServiceError):
    """Raised when credentials are invalid."""

    def __init__(self, message: str = "Invalid credentials") -> None:
        super().__init__(message)
        self.message = message


class UserNotFoundError(AuthServiceError):
    """Raised when a user is not found."""

    def __init__(self, identifier: str) -> None:
        super().__init__(f"User not found: {identifier!r}")
        self.identifier = identifier


class UserExistsError(AuthServiceError):
    """Raised when trying to create a user that already exists."""

    def __init__(self, email: str) -> None:
        super().__init__(f"User already exists: {email!r}")
        self.email = email


class APIKeyNotFoundError(AuthServiceError):
    """Raised when an API key is not found."""

    def __init__(self, identifier: str | int) -> None:
        super().__init__(f"API key not found: {identifier!r}")
        self.identifier = identifier


class TokenExpiredError(AuthServiceError):
    """Raised when a token has expired."""

    def __init__(self, message: str = "Token has expired") -> None:
        super().__init__(message)
        self.message = message


class AuthDisabledError(AuthServiceError):
    """Raised when auth operations are called with auth disabled."""

    def __init__(self, operation: str) -> None:
        super().__init__(f"Authentication is disabled: cannot {operation}")
        self.operation = operation


# =============================================================================
# Service
# =============================================================================


class AuthService:
    """Service for authentication and user management.

    Handles:
    - User authentication (via providers)
    - Token management (access/refresh tokens)
    - User CRUD operations
    - API key management
    """

    def __init__(self, session: Session) -> None:
        """Initialize auth service.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self.user_repo = UserRepository(session)
        self.api_key_repo = APIKeyRepository(session)
        self.session_repo = SessionRepository(session)
        self.refresh_token_repo = RefreshTokenRepository(session)
        self._settings = get_settings()

    # =========================================================================
    # Authentication
    # =========================================================================

    def authenticate(self, email: str, password: str) -> TokenResponse:
        """Authenticate a user with email and password.

        Args:
            email: User's email address.
            password: User's password.

        Returns:
            TokenResponse with access and refresh tokens.

        Raises:
            AuthDisabledError: If auth is disabled.
            InvalidCredentialsError: If credentials are invalid.
        """
        if self._settings.auth_mode == "disabled":
            raise AuthDisabledError("authenticate")

        provider = get_provider(self.session)
        result = provider.authenticate({"email": email, "password": password})

        if not result.success or result.user is None:
            raise InvalidCredentialsError(result.error or "Invalid credentials")

        return self.create_token_response(result.user)

    def authenticate_api_key(self, key: str) -> User:
        """Authenticate using an API key.

        Args:
            key: Full API key string.

        Returns:
            User associated with the key.

        Raises:
            AuthDisabledError: If auth is disabled.
            InvalidCredentialsError: If key is invalid or expired.
        """
        if self._settings.auth_mode == "disabled":
            raise AuthDisabledError("authenticate with API key")

        # Extract prefix (first 8 chars) and find key
        if len(key) < 8:
            raise InvalidCredentialsError("Invalid API key format")

        prefix = key[:8]
        api_key = self.api_key_repo.get_by_prefix(prefix)

        if api_key is None:
            raise InvalidCredentialsError("Invalid API key")

        # Verify key hash
        key_hash = self._hash_api_key(key)
        if api_key.key_hash != key_hash:
            raise InvalidCredentialsError("Invalid API key")

        # Check if key is active
        if not api_key.is_active:
            raise InvalidCredentialsError("API key has been revoked")

        # Check if key is expired
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            raise InvalidCredentialsError("API key has expired")

        # Check if user is active
        if not api_key.user.is_active:
            raise InvalidCredentialsError("User account is disabled")

        # Update last used
        self.api_key_repo.update_last_used(api_key.id)

        return api_key.user

    def validate_access_token(self, token: str) -> User:
        """Validate an access token and return the user.

        Args:
            token: JWT access token.

        Returns:
            User associated with the token.

        Raises:
            AuthDisabledError: If auth is disabled.
            InvalidCredentialsError: If token is invalid.
            TokenExpiredError: If token has expired.
        """
        if self._settings.auth_mode == "disabled":
            raise AuthDisabledError("validate token")

        provider = get_provider(self.session)
        result = provider.validate_token(token)

        if not result.success:
            if result.error and "expired" in result.error.lower():
                raise TokenExpiredError(result.error)
            raise InvalidCredentialsError(result.error or "Invalid token")

        if result.user is None:
            raise InvalidCredentialsError("Invalid token: no user")

        return result.user

    def validate_refresh_token(self, token: str) -> User:
        """Validate a refresh token and return the user.

        Args:
            token: Refresh token string.

        Returns:
            User associated with the token.

        Raises:
            AuthDisabledError: If auth is disabled.
            InvalidCredentialsError: If token is invalid.
            TokenExpiredError: If token has expired.
        """
        if self._settings.auth_mode == "disabled":
            raise AuthDisabledError("validate refresh token")

        if self._settings.auth_mode != "local":
            raise AuthServiceError("Refresh tokens only supported for local auth")

        provider = LocalAuthProvider(self.session)
        payload = provider.decode_refresh_token(token)

        if payload is None:
            raise InvalidCredentialsError("Invalid refresh token")

        # Hash the token and check against stored hash
        token_hash = self._hash_refresh_token(token)
        stored_token = self.refresh_token_repo.get_valid(token_hash)

        if stored_token is None:
            raise InvalidCredentialsError("Refresh token not found or already used")

        user = stored_token.user
        if not user.is_active:
            raise InvalidCredentialsError("User account is disabled")

        return user

    def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """Refresh access and refresh tokens.

        Args:
            refresh_token: Current refresh token.

        Returns:
            New TokenResponse with new access and refresh tokens.

        Raises:
            AuthDisabledError: If auth is disabled.
            InvalidCredentialsError: If token is invalid.
        """
        user = self.validate_refresh_token(refresh_token)

        # Invalidate old refresh token
        old_hash = self._hash_refresh_token(refresh_token)
        old_token = self.refresh_token_repo.get_by_hash(old_hash)

        # Create new tokens
        response = self.create_token_response(user)

        # Mark old token as replaced
        if old_token:
            new_hash = self._hash_refresh_token(response.refresh_token)
            new_token = self.refresh_token_repo.get_by_hash(new_hash)
            if new_token:
                old_token.replaced_by = new_token.id

        return response

    # =========================================================================
    # Token Management
    # =========================================================================

    def create_access_token(self, user: User) -> str:
        """Create an access token for a user.

        Args:
            user: User to create token for.

        Returns:
            JWT access token string.
        """
        provider = LocalAuthProvider(self.session)
        return provider.create_access_token(user)

    def create_refresh_token(self, user: User) -> str:
        """Create and store a refresh token for a user.

        Args:
            user: User to create token for.

        Returns:
            Refresh token string.
        """
        provider = LocalAuthProvider(self.session)
        token, expires_at = provider.create_refresh_token(user)

        # Store hashed token
        token_hash = self._hash_refresh_token(token)
        self.refresh_token_repo.create(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        return token

    def create_token_response(self, user: User) -> TokenResponse:
        """Create a full token response for a user.

        Args:
            user: User to create tokens for.

        Returns:
            TokenResponse with access and refresh tokens.
        """
        access_token = self.create_access_token(user)
        refresh_token = self.create_refresh_token(user)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=self._settings.auth_access_token_expire_minutes * 60,
        )

    # =========================================================================
    # User Management
    # =========================================================================

    def create_local_user(self, data: UserCreate) -> User:
        """Create a new local user with password.

        Args:
            data: User creation data.

        Returns:
            Created User instance.

        Raises:
            UserExistsError: If user with email already exists.
        """
        # Check if user exists
        existing = self.user_repo.get_by_email(data.email)
        if existing is not None:
            raise UserExistsError(data.email)

        # Hash password if provided
        password_hash = None
        if data.password:
            password_hash = LocalAuthProvider.hash_password(data.password)

        user = self.user_repo.create(
            email=data.email,
            password_hash=password_hash,
            username=data.username,
            display_name=data.display_name,
            is_superuser=data.is_superuser,
        )

        return user

    def get_user_by_id(self, user_id: int) -> User:
        """Get a user by ID.

        Args:
            user_id: User ID.

        Returns:
            User instance.

        Raises:
            UserNotFoundError: If user not found.
        """
        user = self.user_repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(str(user_id))
        return user

    def get_user_by_email(self, email: str) -> User:
        """Get a user by email.

        Args:
            email: User email address.

        Returns:
            User instance.

        Raises:
            UserNotFoundError: If user not found.
        """
        user = self.user_repo.get_by_email(email)
        if user is None:
            raise UserNotFoundError(email)
        return user

    def list_users(self, include_inactive: bool = False) -> list[User]:
        """List all users.

        Args:
            include_inactive: Include inactive users.

        Returns:
            List of User instances.
        """
        return self.user_repo.list_all(include_inactive=include_inactive)

    def disable_user(self, email: str) -> User:
        """Disable a user account.

        Args:
            email: User email address.

        Returns:
            Updated User instance.

        Raises:
            UserNotFoundError: If user not found.
        """
        user = self.get_user_by_email(email)
        updated = self.user_repo.set_active(user.id, False)
        if updated is None:
            raise UserNotFoundError(email)

        # Invalidate all sessions and refresh tokens
        self.session_repo.delete_for_user(user.id)
        self.refresh_token_repo.delete_for_user(user.id)

        return updated

    def enable_user(self, email: str) -> User:
        """Enable a user account.

        Args:
            email: User email address.

        Returns:
            Updated User instance.

        Raises:
            UserNotFoundError: If user not found.
        """
        user = self.get_user_by_email(email)
        updated = self.user_repo.set_active(user.id, True)
        if updated is None:
            raise UserNotFoundError(email)
        return updated

    def set_superuser(self, email: str, is_superuser: bool) -> User:
        """Set user's superuser status.

        Args:
            email: User email address.
            is_superuser: New superuser status.

        Returns:
            Updated User instance.

        Raises:
            UserNotFoundError: If user not found.
        """
        user = self.get_user_by_email(email)
        updated = self.user_repo.set_superuser(user.id, is_superuser)
        if updated is None:
            raise UserNotFoundError(email)
        return updated

    # =========================================================================
    # API Key Management
    # =========================================================================

    def create_api_key(
        self,
        user: User,
        name: str,
        scopes: list[str] | None = None,
        expires_days: int | None = None,
    ) -> APIKeyCreated:
        """Create a new API key for a user.

        Args:
            user: User to create key for.
            name: Descriptive name for the key.
            scopes: Optional permission scopes.
            expires_days: Optional expiration in days.

        Returns:
            APIKeyCreated with full key (shown only once).
        """
        # Generate key: prefix (8 chars) + secret (32 chars)
        prefix = secrets.token_urlsafe(6)[:8]
        secret = secrets.token_urlsafe(24)
        full_key = f"{prefix}{secret}"

        # Hash the full key for storage
        key_hash = self._hash_api_key(full_key)

        # Calculate expiration
        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)

        api_key = self.api_key_repo.create(
            user_id=user.id,
            name=name,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=scopes,
            expires_at=expires_at,
        )

        return APIKeyCreated(
            id=api_key.id,
            user_id=api_key.user_id,
            name=api_key.name,
            key=full_key,
            key_prefix=prefix,
            scopes=scopes,
            expires_at=expires_at,
            created_at=api_key.created_at,
        )

    def list_api_keys(self, user: User, include_inactive: bool = False) -> list[APIKey]:
        """List API keys for a user.

        Args:
            user: User to list keys for.
            include_inactive: Include revoked keys.

        Returns:
            List of APIKey instances.
        """
        return self.api_key_repo.list_by_user(user.id, include_inactive=include_inactive)

    def revoke_api_key(self, key_id: int, user: User) -> APIKey:
        """Revoke an API key.

        Args:
            key_id: ID of the key to revoke.
            user: User making the request (must own the key or be superuser).

        Returns:
            Revoked APIKey instance.

        Raises:
            APIKeyNotFoundError: If key not found or not owned by user.
        """
        api_key = self.api_key_repo.get_by_id(key_id)

        if api_key is None:
            raise APIKeyNotFoundError(key_id)

        # Check ownership (unless superuser)
        if api_key.user_id != user.id and not user.is_superuser:
            raise APIKeyNotFoundError(key_id)

        revoked = self.api_key_repo.revoke(key_id)
        if revoked is None:
            raise APIKeyNotFoundError(key_id)

        return revoked

    # =========================================================================
    # Utilities
    # =========================================================================

    def get_auth_status(self) -> dict[str, Any]:
        """Get current authentication status and configuration.

        Returns:
            Dict with auth mode and configuration.
        """
        return {
            "auth_mode": self._settings.auth_mode,
            "auth_enabled": self._settings.auth_mode != "disabled",
            "supports_local_auth": self._settings.auth_mode == "local",
            "access_token_expire_minutes": self._settings.auth_access_token_expire_minutes,
            "refresh_token_expire_days": self._settings.auth_refresh_token_expire_days,
        }

    @staticmethod
    def _hash_api_key(key: str) -> str:
        """Hash an API key for storage.

        Args:
            key: Full API key.

        Returns:
            SHA-256 hash of the key.
        """
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    @staticmethod
    def _hash_refresh_token(token: str) -> str:
        """Hash a refresh token for storage.

        Args:
            token: Refresh token.

        Returns:
            SHA-256 hash of the token.
        """
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
