"""Tests for authentication API endpoints."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from datacompass.api.app import create_app
from datacompass.api.dependencies import get_db
from datacompass.config.settings import Settings
from datacompass.core.models import Base
from datacompass.core.models.auth import (
    User,
)
from datacompass.core.services.auth_service import AuthService


@pytest.fixture
def auth_engine():
    """Create an in-memory SQLite engine for auth testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables
    Base.metadata.create_all(engine)

    # Create FTS5 virtual table
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS catalog_fts USING fts5(
                    object_id UNINDEXED,
                    source_name,
                    schema_name,
                    object_name,
                    object_type,
                    description,
                    tags,
                    column_names,
                    tokenize='porter unicode61'
                )
                """
            )
        )
        conn.commit()

    yield engine
    engine.dispose()


@pytest.fixture
def auth_session_factory(auth_engine):
    """Create a session factory bound to the auth test engine."""
    return sessionmaker(bind=auth_engine, autocommit=False, autoflush=False)


@pytest.fixture
def auth_disabled_settings():
    """Settings with auth disabled."""
    return Settings(auth_mode="disabled", auth_secret_key="test-secret-key")


@pytest.fixture
def auth_enabled_settings():
    """Settings with local auth enabled."""
    return Settings(auth_mode="local", auth_secret_key="test-secret-key-for-jwt")


@pytest.fixture
def client_auth_disabled(
    auth_session_factory, auth_disabled_settings
) -> Generator[TestClient, None, None]:
    """Test client with auth disabled."""
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        session = auth_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with patch("datacompass.api.dependencies.get_settings", return_value=auth_disabled_settings):
        with patch(
            "datacompass.core.services.auth_service.get_settings",
            return_value=auth_disabled_settings,
        ):
            with TestClient(app) as test_client:
                yield test_client


@pytest.fixture
def client_auth_enabled(
    auth_session_factory, auth_enabled_settings
) -> Generator[TestClient, None, None]:
    """Test client with local auth enabled."""
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        session = auth_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with patch("datacompass.api.dependencies.get_settings", return_value=auth_enabled_settings):
        with patch(
            "datacompass.core.services.auth_service.get_settings",
            return_value=auth_enabled_settings,
        ):
            with patch(
                "datacompass.core.auth.get_settings",
                return_value=auth_enabled_settings,
            ):
                with patch(
                    "datacompass.core.auth.providers.local.get_settings",
                    return_value=auth_enabled_settings,
                ):
                    with TestClient(app) as test_client:
                        yield test_client


@pytest.fixture
def test_user(auth_session_factory, auth_enabled_settings) -> User:
    """Create a test user."""
    session = auth_session_factory()
    try:
        with patch(
            "datacompass.core.services.auth_service.get_settings",
            return_value=auth_enabled_settings,
        ):
            auth_service = AuthService(session)
            from datacompass.core.models.auth import UserCreate

            user = auth_service.create_local_user(
                UserCreate(
                    email="test@example.com",
                    password="testpassword123",
                    username="testuser",
                    display_name="Test User",
                )
            )
            session.commit()
            return user
    finally:
        session.close()


@pytest.fixture
def superuser(auth_session_factory, auth_enabled_settings) -> User:
    """Create a superuser for admin tests."""
    session = auth_session_factory()
    try:
        with patch(
            "datacompass.core.services.auth_service.get_settings",
            return_value=auth_enabled_settings,
        ):
            auth_service = AuthService(session)
            from datacompass.core.models.auth import UserCreate

            user = auth_service.create_local_user(
                UserCreate(
                    email="admin@example.com",
                    password="adminpassword123",
                    username="admin",
                    display_name="Admin User",
                    is_superuser=True,
                )
            )
            session.commit()
            return user
    finally:
        session.close()


class TestAuthStatus:
    """Tests for /auth/status endpoint."""

    def test_status_auth_disabled(self, client_auth_disabled):
        """Test auth status when auth is disabled."""
        response = client_auth_disabled.get("/api/v1/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["auth_mode"] == "disabled"
        assert data["is_authenticated"] is False
        assert data["user"] is None

    def test_status_auth_enabled(self, client_auth_enabled):
        """Test auth status when auth is enabled."""
        response = client_auth_enabled.get("/api/v1/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["auth_mode"] == "local"
        assert data["is_authenticated"] is False


class TestLogin:
    """Tests for /auth/login endpoint."""

    def test_login_auth_disabled(self, client_auth_disabled):
        """Test login fails when auth is disabled."""
        response = client_auth_disabled.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "password"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "auth_disabled"

    def test_login_success(self, client_auth_enabled, test_user, auth_enabled_settings):
        """Test successful login."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "testpassword123"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    def test_login_invalid_password(self, client_auth_enabled, test_user, auth_enabled_settings):
        """Test login with wrong password."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "wrongpassword"},
            )
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "invalid_credentials"

    def test_login_user_not_found(self, client_auth_enabled, auth_enabled_settings):
        """Test login with non-existent user."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "nonexistent@example.com", "password": "password"},
            )
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "invalid_credentials"


class TestRefreshToken:
    """Tests for /auth/refresh endpoint."""

    def test_refresh_auth_disabled(self, client_auth_disabled):
        """Test refresh fails when auth is disabled."""
        response = client_auth_disabled.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "some-token"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "auth_disabled"

    def test_refresh_success(self, client_auth_enabled, test_user, auth_enabled_settings):
        """Test successful token refresh."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            # First login to get tokens
            login_response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "testpassword123"},
            )
            assert login_response.status_code == 200
            tokens = login_response.json()

            # Refresh the tokens
            refresh_response = client_auth_enabled.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": tokens["refresh_token"]},
            )
        assert refresh_response.status_code == 200
        data = refresh_response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_invalid_token(self, client_auth_enabled, auth_enabled_settings):
        """Test refresh with invalid token."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            response = client_auth_enabled.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "invalid-token"},
            )
        assert response.status_code == 401


class TestGetCurrentUser:
    """Tests for /auth/me endpoint."""

    def test_me_auth_disabled(self, client_auth_disabled):
        """Test /me returns dummy user when auth is disabled."""
        response = client_auth_disabled.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["auth_mode"] == "disabled"
        assert data["is_authenticated"] is True
        assert data["user"]["email"] == "dev@localhost"
        assert data["user"]["is_superuser"] is True

    def test_me_not_authenticated(self, client_auth_enabled):
        """Test /me returns 401 when not authenticated."""
        response = client_auth_enabled.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_me_with_token(self, client_auth_enabled, test_user, auth_enabled_settings):
        """Test /me with valid token."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            # Login first
            login_response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "testpassword123"},
            )
            tokens = login_response.json()

            # Get current user
            response = client_auth_enabled.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["is_authenticated"] is True
        assert data["user"]["email"] == "test@example.com"


class TestAPIKeys:
    """Tests for API key endpoints."""

    def test_create_api_key_auth_disabled(self, client_auth_disabled):
        """Test creating API key when auth is disabled returns 400.

        When auth is disabled, API key creation is not allowed because
        there's no real user to associate the key with.
        """
        response = client_auth_disabled.post(
            "/api/v1/auth/apikeys",
            json={"name": "test-key"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "auth_disabled"

    def test_create_api_key_authenticated(
        self, client_auth_enabled, test_user, auth_enabled_settings
    ):
        """Test creating API key when authenticated."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            # Login first
            login_response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "testpassword123"},
            )
            tokens = login_response.json()

            # Create API key
            response = client_auth_enabled.post(
                "/api/v1/auth/apikeys",
                json={"name": "my-api-key", "expires_days": 30},
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "my-api-key"
        assert "key" in data
        assert data["expires_at"] is not None

    def test_list_api_keys(self, client_auth_enabled, test_user, auth_enabled_settings):
        """Test listing API keys."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            # Login first
            login_response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "testpassword123"},
            )
            tokens = login_response.json()

            # Create a key
            client_auth_enabled.post(
                "/api/v1/auth/apikeys",
                json={"name": "test-key"},
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )

            # List keys
            response = client_auth_enabled.get(
                "/api/v1/auth/apikeys",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(k["name"] == "test-key" for k in data)

    def test_revoke_api_key(self, client_auth_enabled, test_user, auth_enabled_settings):
        """Test revoking an API key."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            # Login first
            login_response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "testpassword123"},
            )
            tokens = login_response.json()

            # Create a key
            create_response = client_auth_enabled.post(
                "/api/v1/auth/apikeys",
                json={"name": "key-to-revoke"},
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            key_id = create_response.json()["id"]

            # Revoke the key
            response = client_auth_enabled.delete(
                f"/api/v1/auth/apikeys/{key_id}",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
        assert response.status_code == 204

    def test_authenticate_with_api_key(
        self, client_auth_enabled, test_user, auth_enabled_settings
    ):
        """Test authenticating with X-API-Key header."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            # Login first
            login_response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "testpassword123"},
            )
            tokens = login_response.json()

            # Create a key
            create_response = client_auth_enabled.post(
                "/api/v1/auth/apikeys",
                json={"name": "auth-key"},
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            api_key = create_response.json()["key"]

            # Use API key for auth
            response = client_auth_enabled.get(
                "/api/v1/auth/me",
                headers={"X-API-Key": api_key},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "test@example.com"


class TestUserManagement:
    """Tests for user management endpoints (superuser only)."""

    def test_create_user_not_authenticated(self, client_auth_enabled):
        """Test creating user without auth returns 401."""
        response = client_auth_enabled.post(
            "/api/v1/auth/users",
            json={"email": "new@example.com", "password": "password123"},
        )
        assert response.status_code == 401

    def test_create_user_not_superuser(
        self, client_auth_enabled, test_user, auth_enabled_settings
    ):
        """Test creating user without superuser returns 403."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            # Login as regular user
            login_response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "testpassword123"},
            )
            tokens = login_response.json()

            response = client_auth_enabled.post(
                "/api/v1/auth/users",
                json={"email": "new@example.com", "password": "password123"},
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
        assert response.status_code == 403

    def test_create_user_as_superuser(
        self, client_auth_enabled, superuser, auth_enabled_settings
    ):
        """Test creating user as superuser."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            # Login as superuser
            login_response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "admin@example.com", "password": "adminpassword123"},
            )
            tokens = login_response.json()

            response = client_auth_enabled.post(
                "/api/v1/auth/users",
                json={
                    "email": "newuser@example.com",
                    "password": "newpassword123",
                    "display_name": "New User",
                },
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"

    def test_create_user_duplicate(
        self, client_auth_enabled, superuser, test_user, auth_enabled_settings
    ):
        """Test creating duplicate user returns 409."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            # Login as superuser
            login_response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "admin@example.com", "password": "adminpassword123"},
            )
            tokens = login_response.json()

            response = client_auth_enabled.post(
                "/api/v1/auth/users",
                json={"email": "test@example.com", "password": "password123"},
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
        assert response.status_code == 409
        assert response.json()["error"] == "user_exists"

    def test_list_users(self, client_auth_enabled, superuser, auth_enabled_settings):
        """Test listing users as superuser."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            # Login as superuser
            login_response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "admin@example.com", "password": "adminpassword123"},
            )
            tokens = login_response.json()

            response = client_auth_enabled.get(
                "/api/v1/auth/users",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_get_user(self, client_auth_enabled, superuser, test_user, auth_enabled_settings):
        """Test getting a specific user."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            # Login as superuser
            login_response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "admin@example.com", "password": "adminpassword123"},
            )
            tokens = login_response.json()

            response = client_auth_enabled.get(
                "/api/v1/auth/users/test@example.com",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"

    def test_get_user_not_found(self, client_auth_enabled, superuser, auth_enabled_settings):
        """Test getting non-existent user returns 404."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            # Login as superuser
            login_response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "admin@example.com", "password": "adminpassword123"},
            )
            tokens = login_response.json()

            response = client_auth_enabled.get(
                "/api/v1/auth/users/nonexistent@example.com",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
        assert response.status_code == 404
        assert response.json()["error"] == "user_not_found"

    def test_disable_user(self, client_auth_enabled, superuser, test_user, auth_enabled_settings):
        """Test disabling a user."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            # Login as superuser
            login_response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "admin@example.com", "password": "adminpassword123"},
            )
            tokens = login_response.json()

            response = client_auth_enabled.post(
                "/api/v1/auth/users/test@example.com/disable",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    def test_enable_user(self, client_auth_enabled, superuser, test_user, auth_enabled_settings):
        """Test enabling a user."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            # Login as superuser
            login_response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "admin@example.com", "password": "adminpassword123"},
            )
            tokens = login_response.json()

            # First disable
            client_auth_enabled.post(
                "/api/v1/auth/users/test@example.com/disable",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )

            # Then enable
            response = client_auth_enabled.post(
                "/api/v1/auth/users/test@example.com/enable",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True

    def test_set_superuser(self, client_auth_enabled, superuser, test_user, auth_enabled_settings):
        """Test setting superuser status."""
        with patch(
            "datacompass.core.auth.providers.local.get_settings",
            return_value=auth_enabled_settings,
        ):
            # Login as superuser
            login_response = client_auth_enabled.post(
                "/api/v1/auth/login",
                json={"email": "admin@example.com", "password": "adminpassword123"},
            )
            tokens = login_response.json()

            # Promote to superuser
            response = client_auth_enabled.post(
                "/api/v1/auth/users/test@example.com/set-superuser?is_superuser=true",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["is_superuser"] is True

    def test_user_management_auth_disabled(self, client_auth_disabled):
        """Test user management works with auth disabled (dummy superuser)."""
        # List users should work
        response = client_auth_disabled.get("/api/v1/auth/users")
        assert response.status_code == 200
