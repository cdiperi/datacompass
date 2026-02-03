"""Repository for authentication operations."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from datacompass.core.models.auth import APIKey, RefreshToken, Session, User
from datacompass.core.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User CRUD operations."""

    model = User

    def get_by_email(self, email: str) -> User | None:
        """Get user by email address.

        Args:
            email: Email address to search for.

        Returns:
            User instance or None if not found.
        """
        stmt = select(User).where(User.email == email)
        return self.session.scalar(stmt)

    def get_by_external_id(self, provider: str, external_id: str) -> User | None:
        """Get user by external provider and ID.

        Args:
            provider: External provider name (e.g., 'oidc', 'ldap').
            external_id: User's ID in the external system.

        Returns:
            User instance or None if not found.
        """
        stmt = select(User).where(
            User.external_provider == provider,
            User.external_id == external_id,
        )
        return self.session.scalar(stmt)

    def create(
        self,
        email: str,
        password_hash: str | None = None,
        username: str | None = None,
        display_name: str | None = None,
        external_provider: str | None = None,
        external_id: str | None = None,
        is_superuser: bool = False,
    ) -> User:
        """Create a new user.

        Args:
            email: User's email address (unique).
            password_hash: Hashed password for local auth.
            username: Optional username.
            display_name: Optional display name.
            external_provider: External auth provider name.
            external_id: User's ID in external system.
            is_superuser: Whether user has superuser privileges.

        Returns:
            Created User instance.
        """
        user = User(
            email=email,
            password_hash=password_hash,
            username=username,
            display_name=display_name,
            external_provider=external_provider,
            external_id=external_id,
            is_superuser=is_superuser,
        )
        self.add(user)
        self.flush()
        return user

    def list_all(self, include_inactive: bool = False) -> list[User]:
        """List all users.

        Args:
            include_inactive: Include inactive users in results.

        Returns:
            List of User instances.
        """
        stmt = select(User).order_by(User.email)

        if not include_inactive:
            stmt = stmt.where(User.is_active == True)  # noqa: E712

        return list(self.session.scalars(stmt))

    def update_last_login(self, user_id: int) -> User | None:
        """Update user's last login timestamp.

        Args:
            user_id: ID of the user.

        Returns:
            Updated User or None if not found.
        """
        user = self.get_by_id(user_id)
        if user is None:
            return None

        user.last_login_at = datetime.utcnow()
        return user

    def set_active(self, user_id: int, is_active: bool) -> User | None:
        """Enable or disable a user.

        Args:
            user_id: ID of the user.
            is_active: New active status.

        Returns:
            Updated User or None if not found.
        """
        user = self.get_by_id(user_id)
        if user is None:
            return None

        user.is_active = is_active
        user.updated_at = datetime.utcnow()
        return user

    def set_superuser(self, user_id: int, is_superuser: bool) -> User | None:
        """Set user's superuser status.

        Args:
            user_id: ID of the user.
            is_superuser: New superuser status.

        Returns:
            Updated User or None if not found.
        """
        user = self.get_by_id(user_id)
        if user is None:
            return None

        user.is_superuser = is_superuser
        user.updated_at = datetime.utcnow()
        return user

    def update_password(self, user_id: int, password_hash: str) -> User | None:
        """Update user's password hash.

        Args:
            user_id: ID of the user.
            password_hash: New password hash.

        Returns:
            Updated User or None if not found.
        """
        user = self.get_by_id(user_id)
        if user is None:
            return None

        user.password_hash = password_hash
        user.updated_at = datetime.utcnow()
        return user


class APIKeyRepository(BaseRepository[APIKey]):
    """Repository for API key CRUD operations."""

    model = APIKey

    def get_by_prefix(self, prefix: str) -> APIKey | None:
        """Get API key by prefix.

        Args:
            prefix: Key prefix to search for.

        Returns:
            APIKey instance or None if not found.
        """
        stmt = (
            select(APIKey)
            .options(joinedload(APIKey.user))
            .where(APIKey.key_prefix == prefix)
        )
        return self.session.scalar(stmt)

    def list_by_user(self, user_id: int, include_inactive: bool = False) -> list[APIKey]:
        """List API keys for a user.

        Args:
            user_id: ID of the user.
            include_inactive: Include inactive keys in results.

        Returns:
            List of APIKey instances.
        """
        stmt = (
            select(APIKey)
            .where(APIKey.user_id == user_id)
            .order_by(APIKey.created_at.desc())
        )

        if not include_inactive:
            stmt = stmt.where(APIKey.is_active == True)  # noqa: E712

        return list(self.session.scalars(stmt))

    def create(
        self,
        user_id: int,
        name: str,
        key_prefix: str,
        key_hash: str,
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> APIKey:
        """Create a new API key.

        Args:
            user_id: ID of the owning user.
            name: Descriptive name for the key.
            key_prefix: First characters of key for identification.
            key_hash: Hash of the full key.
            scopes: Optional list of permission scopes.
            expires_at: Optional expiration timestamp.

        Returns:
            Created APIKey instance.
        """
        api_key = APIKey(
            user_id=user_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes,
            expires_at=expires_at,
        )
        self.add(api_key)
        self.flush()
        return api_key

    def update_last_used(self, key_id: int) -> APIKey | None:
        """Update key's last used timestamp.

        Args:
            key_id: ID of the API key.

        Returns:
            Updated APIKey or None if not found.
        """
        api_key = self.get_by_id(key_id)
        if api_key is None:
            return None

        api_key.last_used_at = datetime.utcnow()
        return api_key

    def revoke(self, key_id: int) -> APIKey | None:
        """Revoke an API key.

        Args:
            key_id: ID of the API key.

        Returns:
            Updated APIKey or None if not found.
        """
        api_key = self.get_by_id(key_id)
        if api_key is None:
            return None

        api_key.is_active = False
        return api_key


class SessionRepository(BaseRepository[Session]):
    """Repository for Session CRUD operations."""

    model = Session

    def get_active(self, session_id: str) -> Session | None:
        """Get an active (non-expired) session.

        Args:
            session_id: Session ID to search for.

        Returns:
            Session instance or None if not found or expired.
        """
        stmt = (
            select(Session)
            .options(joinedload(Session.user))
            .where(
                Session.id == session_id,
                Session.expires_at > datetime.utcnow(),
            )
        )
        return self.session.scalar(stmt)

    def list_by_user(self, user_id: int) -> list[Session]:
        """List active sessions for a user.

        Args:
            user_id: ID of the user.

        Returns:
            List of active Session instances.
        """
        stmt = (
            select(Session)
            .where(
                Session.user_id == user_id,
                Session.expires_at > datetime.utcnow(),
            )
            .order_by(Session.created_at.desc())
        )
        return list(self.session.scalars(stmt))

    def create(
        self,
        session_id: str,
        user_id: int,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> Session:
        """Create a new session.

        Args:
            session_id: Unique session identifier.
            user_id: ID of the user.
            expires_at: Session expiration timestamp.
            user_agent: Optional user agent string.
            ip_address: Optional IP address.

        Returns:
            Created Session instance.
        """
        session = Session(
            id=session_id,
            user_id=user_id,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.add(session)
        self.flush()
        return session

    def delete_expired(self) -> int:
        """Delete all expired sessions.

        Returns:
            Number of sessions deleted.
        """
        stmt = select(Session).where(Session.expires_at <= datetime.utcnow())
        expired = list(self.session.scalars(stmt))
        for session in expired:
            self.delete(session)
        return len(expired)

    def delete_for_user(self, user_id: int) -> int:
        """Delete all sessions for a user.

        Args:
            user_id: ID of the user.

        Returns:
            Number of sessions deleted.
        """
        stmt = select(Session).where(Session.user_id == user_id)
        sessions = list(self.session.scalars(stmt))
        for session in sessions:
            self.delete(session)
        return len(sessions)


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """Repository for RefreshToken CRUD operations."""

    model = RefreshToken

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Get refresh token by hash.

        Args:
            token_hash: Hash of the token to search for.

        Returns:
            RefreshToken instance or None if not found.
        """
        stmt = (
            select(RefreshToken)
            .options(joinedload(RefreshToken.user))
            .where(RefreshToken.token_hash == token_hash)
        )
        return self.session.scalar(stmt)

    def get_valid(self, token_hash: str) -> RefreshToken | None:
        """Get a valid (non-expired, non-replaced) refresh token.

        Args:
            token_hash: Hash of the token to search for.

        Returns:
            RefreshToken instance or None if invalid.
        """
        stmt = (
            select(RefreshToken)
            .options(joinedload(RefreshToken.user))
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.expires_at > datetime.utcnow(),
                RefreshToken.replaced_by == None,  # noqa: E711
            )
        )
        return self.session.scalar(stmt)

    def create(
        self,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        """Create a new refresh token.

        Args:
            user_id: ID of the user.
            token_hash: Hash of the token.
            expires_at: Token expiration timestamp.

        Returns:
            Created RefreshToken instance.
        """
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.add(token)
        self.flush()
        return token

    def rotate(self, old_token_id: int, new_token: RefreshToken) -> RefreshToken | None:
        """Rotate a refresh token (replace with a new one).

        Args:
            old_token_id: ID of the old token to replace.
            new_token: New token to use.

        Returns:
            Old token with replaced_by set, or None if not found.
        """
        old_token = self.get_by_id(old_token_id)
        if old_token is None:
            return None

        self.add(new_token)
        self.flush()
        old_token.replaced_by = new_token.id
        return old_token

    def delete_expired(self) -> int:
        """Delete all expired refresh tokens.

        Returns:
            Number of tokens deleted.
        """
        stmt = select(RefreshToken).where(RefreshToken.expires_at <= datetime.utcnow())
        expired = list(self.session.scalars(stmt))
        for token in expired:
            self.delete(token)
        return len(expired)

    def delete_for_user(self, user_id: int) -> int:
        """Delete all refresh tokens for a user.

        Args:
            user_id: ID of the user.

        Returns:
            Number of tokens deleted.
        """
        stmt = select(RefreshToken).where(RefreshToken.user_id == user_id)
        tokens = list(self.session.scalars(stmt))
        for token in tokens:
            self.delete(token)
        return len(tokens)
