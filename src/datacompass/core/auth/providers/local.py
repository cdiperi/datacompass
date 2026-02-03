"""Local password authentication provider."""

from datetime import datetime, timedelta
from typing import Any

import bcrypt
import jwt
from sqlalchemy.orm import Session

from datacompass.config.settings import get_settings
from datacompass.core.auth.providers.base import AuthProvider, AuthResult
from datacompass.core.models.auth import User
from datacompass.core.repositories.auth import UserRepository


class LocalAuthProvider(AuthProvider):
    """Authentication provider for local username/password auth.

    Uses bcrypt for password hashing and JWT for tokens.
    """

    def __init__(self, session: Session) -> None:
        """Initialize provider with database session.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self.user_repo = UserRepository(session)
        self._settings = get_settings()

    @property
    def provider_name(self) -> str:
        return "local"

    def authenticate(self, credentials: dict[str, Any]) -> AuthResult:
        """Authenticate user with email and password.

        Args:
            credentials: Dict with "email" and "password" keys.

        Returns:
            AuthResult with success status and user or error.
        """
        email = credentials.get("email")
        password = credentials.get("password")

        if not email or not password:
            return AuthResult(
                success=False,
                error="Email and password are required",
            )

        # Find user by email
        user = self.user_repo.get_by_email(email)
        if user is None:
            return AuthResult(
                success=False,
                error="Invalid email or password",
            )

        # Check if user has a password hash (local auth)
        if not user.password_hash:
            return AuthResult(
                success=False,
                error="User does not have password authentication enabled",
            )

        # Check if user is active
        if not user.is_active:
            return AuthResult(
                success=False,
                error="User account is disabled",
            )

        # Verify password
        if not self.verify_password(password, user.password_hash):
            return AuthResult(
                success=False,
                error="Invalid email or password",
            )

        # Update last login
        self.user_repo.update_last_login(user.id)

        return AuthResult(
            success=True,
            user=user,
        )

    def validate_token(self, token: str) -> AuthResult:
        """Validate a JWT access token.

        Args:
            token: JWT access token to validate.

        Returns:
            AuthResult with success status and user or error.
        """
        try:
            payload = jwt.decode(
                token,
                self._settings.auth_secret_key,
                algorithms=["HS256"],
            )

            # Check token type
            if payload.get("type") != "access":
                return AuthResult(
                    success=False,
                    error="Invalid token type",
                )

            # Check expiration (jwt.decode handles this, but be explicit)
            exp = payload.get("exp")
            if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
                return AuthResult(
                    success=False,
                    error="Token has expired",
                )

            # Get user
            user_id = payload.get("sub")
            if not user_id:
                return AuthResult(
                    success=False,
                    error="Invalid token: missing subject",
                )

            user = self.user_repo.get_by_id(int(user_id))
            if user is None:
                return AuthResult(
                    success=False,
                    error="User not found",
                )

            if not user.is_active:
                return AuthResult(
                    success=False,
                    error="User account is disabled",
                )

            return AuthResult(
                success=True,
                user=user,
            )

        except jwt.ExpiredSignatureError:
            return AuthResult(
                success=False,
                error="Token has expired",
            )
        except jwt.InvalidTokenError as e:
            return AuthResult(
                success=False,
                error=f"Invalid token: {e}",
            )

    def supports_password_auth(self) -> bool:
        return True

    # Password hashing utilities

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt.

        Args:
            password: Plain text password.

        Returns:
            Bcrypt hash string.
        """
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its hash.

        Args:
            password: Plain text password.
            password_hash: Bcrypt hash to compare against.

        Returns:
            True if password matches.
        """
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )

    # Token generation utilities

    def create_access_token(
        self,
        user: User,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a JWT access token for a user.

        Args:
            user: User to create token for.
            expires_delta: Optional custom expiration time.

        Returns:
            JWT access token string.
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=self._settings.auth_access_token_expire_minutes)

        expire = datetime.utcnow() + expires_delta
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow(),
        }

        return jwt.encode(
            payload,
            self._settings.auth_secret_key,
            algorithm="HS256",
        )

    def create_refresh_token(self, user: User) -> tuple[str, datetime]:
        """Create a refresh token for a user.

        Args:
            user: User to create token for.

        Returns:
            Tuple of (token string, expiration datetime).
        """
        expires_delta = timedelta(days=self._settings.auth_refresh_token_expire_days)
        expire = datetime.utcnow() + expires_delta

        payload = {
            "sub": str(user.id),
            "type": "refresh",
            "exp": expire,
            "iat": datetime.utcnow(),
        }

        token = jwt.encode(
            payload,
            self._settings.auth_secret_key,
            algorithm="HS256",
        )

        return token, expire

    def decode_refresh_token(self, token: str) -> dict[str, Any] | None:
        """Decode and validate a refresh token.

        Args:
            token: Refresh token to decode.

        Returns:
            Token payload or None if invalid.
        """
        try:
            payload = jwt.decode(
                token,
                self._settings.auth_secret_key,
                algorithms=["HS256"],
            )

            if payload.get("type") != "refresh":
                return None

            return payload
        except jwt.InvalidTokenError:
            return None
