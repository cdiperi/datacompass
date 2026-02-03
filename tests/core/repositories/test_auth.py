"""Tests for authentication repositories."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from datacompass.core.repositories.auth import (
    APIKeyRepository,
    RefreshTokenRepository,
    SessionRepository,
    UserRepository,
)


class TestUserRepository:
    """Test cases for UserRepository."""

    def test_create_user(self, test_db: Session):
        """Test creating a user."""
        repo = UserRepository(test_db)

        user = repo.create(
            email="test@example.com",
            password_hash="hashed_password",
            display_name="Test User",
        )
        test_db.commit()

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.password_hash == "hashed_password"
        assert user.display_name == "Test User"
        assert user.is_active is True
        assert user.is_superuser is False

    def test_create_superuser(self, test_db: Session):
        """Test creating a superuser."""
        repo = UserRepository(test_db)

        user = repo.create(
            email="admin@example.com",
            password_hash="hashed_password",
            is_superuser=True,
        )
        test_db.commit()

        assert user.is_superuser is True

    def test_get_by_email(self, test_db: Session):
        """Test getting user by email."""
        repo = UserRepository(test_db)

        repo.create(email="find@example.com")
        test_db.commit()

        user = repo.get_by_email("find@example.com")
        assert user is not None
        assert user.email == "find@example.com"

        not_found = repo.get_by_email("notfound@example.com")
        assert not_found is None

    def test_get_by_external_id(self, test_db: Session):
        """Test getting user by external provider and ID."""
        repo = UserRepository(test_db)

        repo.create(
            email="external@example.com",
            external_provider="oidc",
            external_id="ext-123",
        )
        test_db.commit()

        user = repo.get_by_external_id("oidc", "ext-123")
        assert user is not None
        assert user.email == "external@example.com"

        not_found = repo.get_by_external_id("oidc", "wrong-id")
        assert not_found is None

    def test_list_all(self, test_db: Session):
        """Test listing all users."""
        repo = UserRepository(test_db)

        repo.create(email="user1@example.com")
        repo.create(email="user2@example.com")
        user3 = repo.create(email="user3@example.com")
        test_db.commit()

        # Disable one user
        repo.set_active(user3.id, False)
        test_db.commit()

        # Default: only active users
        users = repo.list_all()
        assert len(users) == 2

        # Include inactive
        all_users = repo.list_all(include_inactive=True)
        assert len(all_users) == 3

    def test_update_last_login(self, test_db: Session):
        """Test updating last login timestamp."""
        repo = UserRepository(test_db)

        user = repo.create(email="login@example.com")
        test_db.commit()

        assert user.last_login_at is None

        updated = repo.update_last_login(user.id)
        test_db.commit()

        assert updated is not None
        assert updated.last_login_at is not None

    def test_set_active(self, test_db: Session):
        """Test enabling/disabling users."""
        repo = UserRepository(test_db)

        user = repo.create(email="toggle@example.com")
        test_db.commit()

        assert user.is_active is True

        repo.set_active(user.id, False)
        test_db.commit()

        assert user.is_active is False

        repo.set_active(user.id, True)
        test_db.commit()

        assert user.is_active is True

    def test_set_superuser(self, test_db: Session):
        """Test granting/revoking superuser privileges."""
        repo = UserRepository(test_db)

        user = repo.create(email="promote@example.com")
        test_db.commit()

        assert user.is_superuser is False

        repo.set_superuser(user.id, True)
        test_db.commit()

        assert user.is_superuser is True

        repo.set_superuser(user.id, False)
        test_db.commit()

        assert user.is_superuser is False


class TestAPIKeyRepository:
    """Test cases for APIKeyRepository."""

    def test_create_api_key(self, test_db: Session):
        """Test creating an API key."""
        user_repo = UserRepository(test_db)
        key_repo = APIKeyRepository(test_db)

        user = user_repo.create(email="apiuser@example.com")
        test_db.commit()

        api_key = key_repo.create(
            user_id=user.id,
            name="Test Key",
            key_prefix="test1234",
            key_hash="hashed_key_value",
            scopes=["read", "write"],
        )
        test_db.commit()

        assert api_key.id is not None
        assert api_key.user_id == user.id
        assert api_key.name == "Test Key"
        assert api_key.key_prefix == "test1234"
        assert api_key.scopes == ["read", "write"]
        assert api_key.is_active is True

    def test_create_api_key_with_expiry(self, test_db: Session):
        """Test creating an API key with expiration."""
        user_repo = UserRepository(test_db)
        key_repo = APIKeyRepository(test_db)

        user = user_repo.create(email="expiring@example.com")
        test_db.commit()

        expires_at = datetime.utcnow() + timedelta(days=30)
        api_key = key_repo.create(
            user_id=user.id,
            name="Expiring Key",
            key_prefix="exp12345",
            key_hash="hashed",
            expires_at=expires_at,
        )
        test_db.commit()

        assert api_key.expires_at is not None

    def test_get_by_prefix(self, test_db: Session):
        """Test getting API key by prefix."""
        user_repo = UserRepository(test_db)
        key_repo = APIKeyRepository(test_db)

        user = user_repo.create(email="prefix@example.com")
        test_db.commit()

        key_repo.create(
            user_id=user.id,
            name="Find Key",
            key_prefix="find1234",
            key_hash="hashed",
        )
        test_db.commit()

        api_key = key_repo.get_by_prefix("find1234")
        assert api_key is not None
        assert api_key.name == "Find Key"
        # Should also load user relationship
        assert api_key.user is not None
        assert api_key.user.email == "prefix@example.com"

    def test_list_by_user(self, test_db: Session):
        """Test listing API keys for a user."""
        user_repo = UserRepository(test_db)
        key_repo = APIKeyRepository(test_db)

        user = user_repo.create(email="multikey@example.com")
        test_db.commit()

        key_repo.create(user_id=user.id, name="Key 1", key_prefix="key11111", key_hash="hash1")
        key_repo.create(user_id=user.id, name="Key 2", key_prefix="key22222", key_hash="hash2")
        revoked = key_repo.create(user_id=user.id, name="Key 3", key_prefix="key33333", key_hash="hash3")
        test_db.commit()

        # Revoke one key
        key_repo.revoke(revoked.id)
        test_db.commit()

        # Default: only active keys
        keys = key_repo.list_by_user(user.id)
        assert len(keys) == 2

        # Include inactive
        all_keys = key_repo.list_by_user(user.id, include_inactive=True)
        assert len(all_keys) == 3

    def test_update_last_used(self, test_db: Session):
        """Test updating last used timestamp."""
        user_repo = UserRepository(test_db)
        key_repo = APIKeyRepository(test_db)

        user = user_repo.create(email="used@example.com")
        test_db.commit()

        api_key = key_repo.create(
            user_id=user.id,
            name="Usage Key",
            key_prefix="use12345",
            key_hash="hashed",
        )
        test_db.commit()

        assert api_key.last_used_at is None

        key_repo.update_last_used(api_key.id)
        test_db.commit()

        assert api_key.last_used_at is not None

    def test_revoke(self, test_db: Session):
        """Test revoking an API key."""
        user_repo = UserRepository(test_db)
        key_repo = APIKeyRepository(test_db)

        user = user_repo.create(email="revoke@example.com")
        test_db.commit()

        api_key = key_repo.create(
            user_id=user.id,
            name="Revoke Key",
            key_prefix="rev12345",
            key_hash="hashed",
        )
        test_db.commit()

        assert api_key.is_active is True

        key_repo.revoke(api_key.id)
        test_db.commit()

        assert api_key.is_active is False


class TestSessionRepository:
    """Test cases for SessionRepository."""

    def test_create_session(self, test_db: Session):
        """Test creating a session."""
        user_repo = UserRepository(test_db)
        session_repo = SessionRepository(test_db)

        user = user_repo.create(email="session@example.com")
        test_db.commit()

        expires_at = datetime.utcnow() + timedelta(hours=1)
        session = session_repo.create(
            session_id="sess-123-abc",
            user_id=user.id,
            expires_at=expires_at,
            user_agent="Test Agent",
            ip_address="127.0.0.1",
        )
        test_db.commit()

        assert session.id == "sess-123-abc"
        assert session.user_id == user.id
        assert session.user_agent == "Test Agent"
        assert session.ip_address == "127.0.0.1"

    def test_get_active(self, test_db: Session):
        """Test getting active session."""
        user_repo = UserRepository(test_db)
        session_repo = SessionRepository(test_db)

        user = user_repo.create(email="active@example.com")
        test_db.commit()

        # Active session
        active_expires = datetime.utcnow() + timedelta(hours=1)
        session_repo.create(
            session_id="active-sess",
            user_id=user.id,
            expires_at=active_expires,
        )

        # Expired session
        expired_expires = datetime.utcnow() - timedelta(hours=1)
        session_repo.create(
            session_id="expired-sess",
            user_id=user.id,
            expires_at=expired_expires,
        )
        test_db.commit()

        active = session_repo.get_active("active-sess")
        assert active is not None

        expired = session_repo.get_active("expired-sess")
        assert expired is None

    def test_list_by_user(self, test_db: Session):
        """Test listing sessions for a user."""
        user_repo = UserRepository(test_db)
        session_repo = SessionRepository(test_db)

        user = user_repo.create(email="multisess@example.com")
        test_db.commit()

        active_expires = datetime.utcnow() + timedelta(hours=1)
        session_repo.create(session_id="sess-1", user_id=user.id, expires_at=active_expires)
        session_repo.create(session_id="sess-2", user_id=user.id, expires_at=active_expires)
        test_db.commit()

        sessions = session_repo.list_by_user(user.id)
        assert len(sessions) == 2

    def test_delete_for_user(self, test_db: Session):
        """Test deleting all sessions for a user."""
        user_repo = UserRepository(test_db)
        session_repo = SessionRepository(test_db)

        user = user_repo.create(email="deletesess@example.com")
        test_db.commit()

        active_expires = datetime.utcnow() + timedelta(hours=1)
        session_repo.create(session_id="del-1", user_id=user.id, expires_at=active_expires)
        session_repo.create(session_id="del-2", user_id=user.id, expires_at=active_expires)
        test_db.commit()

        deleted = session_repo.delete_for_user(user.id)
        test_db.commit()

        assert deleted == 2
        assert len(session_repo.list_by_user(user.id)) == 0


class TestRefreshTokenRepository:
    """Test cases for RefreshTokenRepository."""

    def test_create_refresh_token(self, test_db: Session):
        """Test creating a refresh token."""
        user_repo = UserRepository(test_db)
        token_repo = RefreshTokenRepository(test_db)

        user = user_repo.create(email="refresh@example.com")
        test_db.commit()

        expires_at = datetime.utcnow() + timedelta(days=7)
        token = token_repo.create(
            user_id=user.id,
            token_hash="hashed_token_123",
            expires_at=expires_at,
        )
        test_db.commit()

        assert token.id is not None
        assert token.user_id == user.id
        assert token.token_hash == "hashed_token_123"
        assert token.replaced_by is None

    def test_get_valid(self, test_db: Session):
        """Test getting valid refresh token."""
        user_repo = UserRepository(test_db)
        token_repo = RefreshTokenRepository(test_db)

        user = user_repo.create(email="validtoken@example.com")
        test_db.commit()

        # Valid token
        valid_expires = datetime.utcnow() + timedelta(days=7)
        token_repo.create(user_id=user.id, token_hash="valid_hash", expires_at=valid_expires)

        # Expired token
        expired_expires = datetime.utcnow() - timedelta(days=1)
        token_repo.create(user_id=user.id, token_hash="expired_hash", expires_at=expired_expires)
        test_db.commit()

        valid = token_repo.get_valid("valid_hash")
        assert valid is not None

        expired = token_repo.get_valid("expired_hash")
        assert expired is None

    def test_delete_for_user(self, test_db: Session):
        """Test deleting all tokens for a user."""
        user_repo = UserRepository(test_db)
        token_repo = RefreshTokenRepository(test_db)

        user = user_repo.create(email="deltoken@example.com")
        test_db.commit()

        expires_at = datetime.utcnow() + timedelta(days=7)
        token_repo.create(user_id=user.id, token_hash="hash1", expires_at=expires_at)
        token_repo.create(user_id=user.id, token_hash="hash2", expires_at=expires_at)
        test_db.commit()

        deleted = token_repo.delete_for_user(user.id)
        test_db.commit()

        assert deleted == 2
