"""Tests for AuthService."""

import os
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from datacompass.core.models.auth import UserCreate
from datacompass.core.services.auth_service import (
    APIKeyNotFoundError,
    AuthDisabledError,
    AuthService,
    InvalidCredentialsError,
    TokenExpiredError,
    UserExistsError,
    UserNotFoundError,
)


@pytest.fixture
def auth_enabled():
    """Enable local auth for tests."""
    old_value = os.environ.get("DATACOMPASS_AUTH_MODE")
    os.environ["DATACOMPASS_AUTH_MODE"] = "local"

    # Clear settings cache
    from datacompass.config.settings import get_settings
    get_settings.cache_clear()

    yield

    if old_value is not None:
        os.environ["DATACOMPASS_AUTH_MODE"] = old_value
    else:
        os.environ.pop("DATACOMPASS_AUTH_MODE", None)

    get_settings.cache_clear()


@pytest.fixture
def auth_disabled():
    """Disable auth for tests."""
    old_value = os.environ.get("DATACOMPASS_AUTH_MODE")
    os.environ["DATACOMPASS_AUTH_MODE"] = "disabled"

    # Clear settings cache
    from datacompass.config.settings import get_settings
    get_settings.cache_clear()

    yield

    if old_value is not None:
        os.environ["DATACOMPASS_AUTH_MODE"] = old_value
    else:
        os.environ.pop("DATACOMPASS_AUTH_MODE", None)

    get_settings.cache_clear()


class TestUserManagement:
    """Test cases for user management."""

    def test_create_local_user(self, test_db: Session, auth_enabled):
        """Test creating a local user."""
        service = AuthService(test_db)

        user_data = UserCreate(
            email="newuser@example.com",
            password="secretpassword",
            display_name="New User",
        )

        user = service.create_local_user(user_data)
        test_db.commit()

        assert user.id is not None
        assert user.email == "newuser@example.com"
        assert user.display_name == "New User"
        assert user.password_hash is not None
        assert user.password_hash != "secretpassword"  # Should be hashed

    def test_create_user_without_password(self, test_db: Session, auth_enabled):
        """Test creating a user without password."""
        service = AuthService(test_db)

        user_data = UserCreate(
            email="nopass@example.com",
        )

        user = service.create_local_user(user_data)
        test_db.commit()

        assert user.password_hash is None

    def test_create_superuser(self, test_db: Session, auth_enabled):
        """Test creating a superuser."""
        service = AuthService(test_db)

        user_data = UserCreate(
            email="admin@example.com",
            password="adminpass",
            is_superuser=True,
        )

        user = service.create_local_user(user_data)
        test_db.commit()

        assert user.is_superuser is True

    def test_create_duplicate_user_raises(self, test_db: Session, auth_enabled):
        """Test that creating duplicate user raises error."""
        service = AuthService(test_db)

        user_data = UserCreate(email="dupe@example.com", password="pass")
        service.create_local_user(user_data)
        test_db.commit()

        with pytest.raises(UserExistsError) as exc_info:
            service.create_local_user(user_data)

        assert "dupe@example.com" in str(exc_info.value)

    def test_get_user_by_email(self, test_db: Session, auth_enabled):
        """Test getting user by email."""
        service = AuthService(test_db)

        user_data = UserCreate(email="findme@example.com", password="pass")
        service.create_local_user(user_data)
        test_db.commit()

        user = service.get_user_by_email("findme@example.com")
        assert user.email == "findme@example.com"

    def test_get_user_not_found_raises(self, test_db: Session, auth_enabled):
        """Test that getting non-existent user raises error."""
        service = AuthService(test_db)

        with pytest.raises(UserNotFoundError):
            service.get_user_by_email("notfound@example.com")

    def test_list_users(self, test_db: Session, auth_enabled):
        """Test listing users."""
        service = AuthService(test_db)

        service.create_local_user(UserCreate(email="user1@example.com"))
        service.create_local_user(UserCreate(email="user2@example.com"))
        test_db.commit()

        users = service.list_users()
        assert len(users) == 2

    def test_disable_user(self, test_db: Session, auth_enabled):
        """Test disabling a user."""
        service = AuthService(test_db)

        service.create_local_user(UserCreate(email="disable@example.com", password="pass"))
        test_db.commit()

        user = service.disable_user("disable@example.com")
        test_db.commit()

        assert user.is_active is False

    def test_enable_user(self, test_db: Session, auth_enabled):
        """Test enabling a user."""
        service = AuthService(test_db)

        service.create_local_user(UserCreate(email="enable@example.com"))
        test_db.commit()

        service.disable_user("enable@example.com")
        test_db.commit()

        user = service.enable_user("enable@example.com")
        test_db.commit()

        assert user.is_active is True

    def test_set_superuser(self, test_db: Session, auth_enabled):
        """Test setting superuser status."""
        service = AuthService(test_db)

        service.create_local_user(UserCreate(email="promote@example.com"))
        test_db.commit()

        # Grant superuser
        user = service.set_superuser("promote@example.com", True)
        test_db.commit()
        assert user.is_superuser is True

        # Revoke superuser
        user = service.set_superuser("promote@example.com", False)
        test_db.commit()
        assert user.is_superuser is False


class TestAuthentication:
    """Test cases for authentication."""

    def test_authenticate_valid_credentials(self, test_db: Session, auth_enabled):
        """Test authenticating with valid credentials."""
        service = AuthService(test_db)

        service.create_local_user(UserCreate(
            email="auth@example.com",
            password="correctpassword",
        ))
        test_db.commit()

        response = service.authenticate("auth@example.com", "correctpassword")
        test_db.commit()

        assert response.access_token is not None
        assert response.refresh_token is not None
        assert response.token_type == "bearer"
        assert response.expires_in > 0

    def test_authenticate_invalid_password(self, test_db: Session, auth_enabled):
        """Test authenticating with wrong password."""
        service = AuthService(test_db)

        service.create_local_user(UserCreate(
            email="wrongpass@example.com",
            password="correctpassword",
        ))
        test_db.commit()

        with pytest.raises(InvalidCredentialsError):
            service.authenticate("wrongpass@example.com", "wrongpassword")

    def test_authenticate_nonexistent_user(self, test_db: Session, auth_enabled):
        """Test authenticating non-existent user."""
        service = AuthService(test_db)

        with pytest.raises(InvalidCredentialsError):
            service.authenticate("nobody@example.com", "anypassword")

    def test_authenticate_disabled_user(self, test_db: Session, auth_enabled):
        """Test authenticating disabled user."""
        service = AuthService(test_db)

        service.create_local_user(UserCreate(
            email="disabled@example.com",
            password="password",
        ))
        test_db.commit()

        service.disable_user("disabled@example.com")
        test_db.commit()

        with pytest.raises(InvalidCredentialsError):
            service.authenticate("disabled@example.com", "password")

    def test_authenticate_auth_disabled_raises(self, test_db: Session, auth_disabled):
        """Test that auth operations fail when auth is disabled."""
        service = AuthService(test_db)

        with pytest.raises(AuthDisabledError):
            service.authenticate("any@example.com", "password")

    def test_validate_access_token(self, test_db: Session, auth_enabled):
        """Test validating access token."""
        service = AuthService(test_db)

        service.create_local_user(UserCreate(
            email="token@example.com",
            password="password",
        ))
        test_db.commit()

        response = service.authenticate("token@example.com", "password")
        test_db.commit()

        user = service.validate_access_token(response.access_token)
        assert user.email == "token@example.com"

    def test_validate_invalid_token(self, test_db: Session, auth_enabled):
        """Test validating invalid token."""
        service = AuthService(test_db)

        with pytest.raises(InvalidCredentialsError):
            service.validate_access_token("invalid.token.here")


class TestAPIKeys:
    """Test cases for API key management."""

    def test_create_api_key(self, test_db: Session, auth_enabled):
        """Test creating an API key."""
        service = AuthService(test_db)

        user = service.create_local_user(UserCreate(email="apikey@example.com"))
        test_db.commit()

        api_key = service.create_api_key(
            user=user,
            name="Test Key",
            scopes=["read", "write"],
            expires_days=30,
        )
        test_db.commit()

        assert api_key.id is not None
        assert api_key.name == "Test Key"
        assert api_key.key is not None
        assert len(api_key.key) > 8  # prefix + secret
        assert api_key.key_prefix == api_key.key[:8]
        assert api_key.scopes == ["read", "write"]
        assert api_key.expires_at is not None

    def test_authenticate_api_key(self, test_db: Session, auth_enabled):
        """Test authenticating with API key."""
        service = AuthService(test_db)

        user = service.create_local_user(UserCreate(email="apiauth@example.com"))
        test_db.commit()

        api_key = service.create_api_key(user=user, name="Auth Key")
        test_db.commit()

        authenticated_user = service.authenticate_api_key(api_key.key)
        assert authenticated_user.email == "apiauth@example.com"

    def test_authenticate_invalid_api_key(self, test_db: Session, auth_enabled):
        """Test authenticating with invalid API key."""
        service = AuthService(test_db)

        with pytest.raises(InvalidCredentialsError):
            service.authenticate_api_key("invalid_key_value")

    def test_list_api_keys(self, test_db: Session, auth_enabled):
        """Test listing API keys."""
        service = AuthService(test_db)

        user = service.create_local_user(UserCreate(email="listkeys@example.com"))
        test_db.commit()

        service.create_api_key(user=user, name="Key 1")
        service.create_api_key(user=user, name="Key 2")
        test_db.commit()

        keys = service.list_api_keys(user)
        assert len(keys) == 2

    def test_revoke_api_key(self, test_db: Session, auth_enabled):
        """Test revoking an API key."""
        service = AuthService(test_db)

        user = service.create_local_user(UserCreate(email="revoke@example.com"))
        test_db.commit()

        api_key = service.create_api_key(user=user, name="Revoke Key")
        test_db.commit()

        full_key = api_key.key  # Save before revoke

        revoked = service.revoke_api_key(api_key.id, user)
        test_db.commit()

        assert revoked.is_active is False

        # Should fail to authenticate with revoked key
        with pytest.raises(InvalidCredentialsError):
            service.authenticate_api_key(full_key)

    def test_revoke_other_users_key_fails(self, test_db: Session, auth_enabled):
        """Test that non-superuser can't revoke another user's key."""
        service = AuthService(test_db)

        user1 = service.create_local_user(UserCreate(email="user1@example.com"))
        user2 = service.create_local_user(UserCreate(email="user2@example.com"))
        test_db.commit()

        api_key = service.create_api_key(user=user1, name="User1 Key")
        test_db.commit()

        with pytest.raises(APIKeyNotFoundError):
            service.revoke_api_key(api_key.id, user2)

    def test_superuser_can_revoke_any_key(self, test_db: Session, auth_enabled):
        """Test that superuser can revoke any key."""
        service = AuthService(test_db)

        user = service.create_local_user(UserCreate(email="regular@example.com"))
        admin = service.create_local_user(UserCreate(
            email="admin@example.com",
            is_superuser=True,
        ))
        test_db.commit()

        api_key = service.create_api_key(user=user, name="User Key")
        test_db.commit()

        revoked = service.revoke_api_key(api_key.id, admin)
        test_db.commit()

        assert revoked.is_active is False


class TestAuthStatus:
    """Test cases for auth status."""

    def test_get_auth_status_enabled(self, test_db: Session, auth_enabled):
        """Test getting auth status when enabled."""
        service = AuthService(test_db)

        status = service.get_auth_status()

        assert status["auth_mode"] == "local"
        assert status["auth_enabled"] is True
        assert status["supports_local_auth"] is True

    def test_get_auth_status_disabled(self, test_db: Session, auth_disabled):
        """Test getting auth status when disabled."""
        service = AuthService(test_db)

        status = service.get_auth_status()

        assert status["auth_mode"] == "disabled"
        assert status["auth_enabled"] is False
