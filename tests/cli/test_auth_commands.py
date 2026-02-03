"""Tests for auth CLI commands."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from datacompass.cli.main import app


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def auth_enabled_env(temp_data_dir: Path):
    """Enable local auth via environment."""
    old_value = os.environ.get("DATACOMPASS_AUTH_MODE")
    os.environ["DATACOMPASS_AUTH_MODE"] = "local"

    # Clear settings cache
    from datacompass.config.settings import get_settings
    get_settings.cache_clear()

    yield temp_data_dir

    if old_value is not None:
        os.environ["DATACOMPASS_AUTH_MODE"] = old_value
    else:
        os.environ.pop("DATACOMPASS_AUTH_MODE", None)

    get_settings.cache_clear()


@pytest.fixture
def auth_disabled_env(temp_data_dir: Path):
    """Disable auth via environment."""
    old_value = os.environ.get("DATACOMPASS_AUTH_MODE")
    os.environ["DATACOMPASS_AUTH_MODE"] = "disabled"

    # Clear settings cache
    from datacompass.config.settings import get_settings
    get_settings.cache_clear()

    yield temp_data_dir

    if old_value is not None:
        os.environ["DATACOMPASS_AUTH_MODE"] = old_value
    else:
        os.environ.pop("DATACOMPASS_AUTH_MODE", None)

    get_settings.cache_clear()


class TestAuthStatus:
    """Test auth status command."""

    def test_auth_status_disabled(self, cli_runner: CliRunner, auth_disabled_env):
        """Test auth status when disabled."""
        result = cli_runner.invoke(app, ["auth", "status"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["auth_mode"] == "disabled"
        assert data["auth_enabled"] is False

    def test_auth_status_enabled(self, cli_runner: CliRunner, auth_enabled_env):
        """Test auth status when enabled."""
        result = cli_runner.invoke(app, ["auth", "status"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["auth_mode"] == "local"
        assert data["auth_enabled"] is True

    def test_auth_status_table_format(self, cli_runner: CliRunner, auth_enabled_env):
        """Test auth status in table format."""
        result = cli_runner.invoke(app, ["auth", "status", "--format", "table"])

        assert result.exit_code == 0
        assert "Auth Mode" in result.stdout
        assert "local" in result.stdout


class TestUserCommands:
    """Test user management commands."""

    def test_user_create(self, cli_runner: CliRunner, auth_enabled_env):
        """Test creating a user."""
        result = cli_runner.invoke(app, [
            "auth", "user", "create",
            "newuser@example.com",
            "--display-name", "New User",
        ])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["email"] == "newuser@example.com"
        assert data["display_name"] == "New User"

    def test_user_create_with_password(self, cli_runner: CliRunner, auth_enabled_env):
        """Test creating a user with password prompt."""
        result = cli_runner.invoke(app, [
            "auth", "user", "create",
            "passuser@example.com",
            "--password",
        ], input="secret123\nsecret123\n")

        assert result.exit_code == 0

    def test_user_create_superuser(self, cli_runner: CliRunner, auth_enabled_env):
        """Test creating a superuser."""
        result = cli_runner.invoke(app, [
            "auth", "user", "create",
            "admin@example.com",
            "--superuser",
        ])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["is_superuser"] is True

    def test_user_create_duplicate_fails(self, cli_runner: CliRunner, auth_enabled_env):
        """Test that creating duplicate user fails."""
        # First create succeeds
        cli_runner.invoke(app, ["auth", "user", "create", "dupe@example.com"])

        # Second create fails
        result = cli_runner.invoke(app, ["auth", "user", "create", "dupe@example.com"])
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_user_list(self, cli_runner: CliRunner, auth_enabled_env):
        """Test listing users."""
        # Create some users
        cli_runner.invoke(app, ["auth", "user", "create", "user1@example.com"])
        cli_runner.invoke(app, ["auth", "user", "create", "user2@example.com"])

        result = cli_runner.invoke(app, ["auth", "user", "list"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) >= 2
        emails = [u["email"] for u in data]
        assert "user1@example.com" in emails
        assert "user2@example.com" in emails

    def test_user_show(self, cli_runner: CliRunner, auth_enabled_env):
        """Test showing user details."""
        cli_runner.invoke(app, [
            "auth", "user", "create",
            "show@example.com",
            "--display-name", "Show User",
        ])

        result = cli_runner.invoke(app, ["auth", "user", "show", "show@example.com"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["email"] == "show@example.com"
        assert data["display_name"] == "Show User"

    def test_user_show_not_found(self, cli_runner: CliRunner, auth_enabled_env):
        """Test showing non-existent user."""
        result = cli_runner.invoke(app, ["auth", "user", "show", "notfound@example.com"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_user_disable(self, cli_runner: CliRunner, auth_enabled_env):
        """Test disabling a user."""
        cli_runner.invoke(app, ["auth", "user", "create", "disable@example.com"])

        result = cli_runner.invoke(app, ["auth", "user", "disable", "disable@example.com"])

        assert result.exit_code == 0
        assert "success" in result.stdout.lower() or "disabled" in result.stdout.lower()

    def test_user_enable(self, cli_runner: CliRunner, auth_enabled_env):
        """Test enabling a user."""
        cli_runner.invoke(app, ["auth", "user", "create", "enable@example.com"])
        cli_runner.invoke(app, ["auth", "user", "disable", "enable@example.com"])

        result = cli_runner.invoke(app, ["auth", "user", "enable", "enable@example.com"])

        assert result.exit_code == 0

    def test_user_set_superuser(self, cli_runner: CliRunner, auth_enabled_env):
        """Test granting superuser privileges."""
        cli_runner.invoke(app, ["auth", "user", "create", "promote@example.com"])

        result = cli_runner.invoke(app, ["auth", "user", "set-superuser", "promote@example.com"])

        assert result.exit_code == 0

        # Verify
        show_result = cli_runner.invoke(app, ["auth", "user", "show", "promote@example.com"])
        data = json.loads(show_result.stdout)
        assert data["is_superuser"] is True

    def test_user_remove_superuser(self, cli_runner: CliRunner, auth_enabled_env):
        """Test revoking superuser privileges."""
        cli_runner.invoke(app, ["auth", "user", "create", "demote@example.com", "--superuser"])

        result = cli_runner.invoke(app, [
            "auth", "user", "set-superuser",
            "demote@example.com",
            "--remove",
        ])

        assert result.exit_code == 0


class TestLoginLogout:
    """Test login and logout commands."""

    def test_login_success(self, cli_runner: CliRunner, auth_enabled_env):
        """Test successful login."""
        # Create user with password
        cli_runner.invoke(app, [
            "auth", "user", "create",
            "login@example.com",
            "--password",
        ], input="testpass\ntestpass\n")

        result = cli_runner.invoke(app, [
            "auth", "login",
            "--email", "login@example.com",
            "--password", "testpass",
        ])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True

    def test_login_invalid_password(self, cli_runner: CliRunner, auth_enabled_env):
        """Test login with wrong password."""
        cli_runner.invoke(app, [
            "auth", "user", "create",
            "wrongpass@example.com",
            "--password",
        ], input="correctpass\ncorrectpass\n")

        result = cli_runner.invoke(app, [
            "auth", "login",
            "--email", "wrongpass@example.com",
            "--password", "incorrectpass",
        ])

        assert result.exit_code == 1

    def test_login_auth_disabled(self, cli_runner: CliRunner, auth_disabled_env):
        """Test login when auth is disabled."""
        result = cli_runner.invoke(app, [
            "auth", "login",
            "--email", "any@example.com",
            "--password", "anypass",
        ])

        assert result.exit_code == 1
        assert "disabled" in result.output.lower()

    def test_logout(self, cli_runner: CliRunner, auth_enabled_env):
        """Test logout command."""
        result = cli_runner.invoke(app, ["auth", "logout"])

        assert result.exit_code == 0


class TestWhoami:
    """Test whoami command."""

    def test_whoami_not_authenticated(self, cli_runner: CliRunner, auth_enabled_env):
        """Test whoami when not authenticated."""
        result = cli_runner.invoke(app, ["auth", "whoami"])

        # Should return non-zero exit code (1 for not authenticated)
        assert result.exit_code in (1, 2)  # Could be 1 or 2 depending on error handling
        assert "not authenticated" in result.output.lower() or "auth" in result.output.lower()

    def test_whoami_auth_disabled(self, cli_runner: CliRunner, auth_disabled_env):
        """Test whoami when auth is disabled."""
        result = cli_runner.invoke(app, ["auth", "whoami"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["auth_mode"] == "disabled"


class TestAPIKeyCommands:
    """Test API key management commands."""

    def _login_user(self, cli_runner: CliRunner, email: str, password: str):
        """Helper to create and login a user."""
        cli_runner.invoke(app, [
            "auth", "user", "create",
            email,
            "--password",
        ], input=f"{password}\n{password}\n")

        cli_runner.invoke(app, [
            "auth", "login",
            "--email", email,
            "--password", password,
        ])

    def test_apikey_create(self, cli_runner: CliRunner, auth_enabled_env):
        """Test creating an API key."""
        self._login_user(cli_runner, "apikey@example.com", "testpass")

        result = cli_runner.invoke(app, [
            "auth", "apikey", "create",
            "Test Key",
            "--scopes", "read,write",
        ])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "Test Key"
        assert "key" in data  # Full key should be present
        assert data["scopes"] == ["read", "write"]

    def test_apikey_create_with_expiry(self, cli_runner: CliRunner, auth_enabled_env):
        """Test creating an API key with expiration."""
        self._login_user(cli_runner, "expiry@example.com", "testpass")

        result = cli_runner.invoke(app, [
            "auth", "apikey", "create",
            "Expiring Key",
            "--expires-days", "30",
        ])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["expires_at"] is not None

    def test_apikey_list(self, cli_runner: CliRunner, auth_enabled_env):
        """Test listing API keys."""
        self._login_user(cli_runner, "listkeys@example.com", "testpass")

        # Create some keys
        cli_runner.invoke(app, ["auth", "apikey", "create", "Key 1"])
        cli_runner.invoke(app, ["auth", "apikey", "create", "Key 2"])

        result = cli_runner.invoke(app, ["auth", "apikey", "list"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) >= 2
        names = [k["name"] for k in data]
        assert "Key 1" in names
        assert "Key 2" in names

    def test_apikey_revoke(self, cli_runner: CliRunner, auth_enabled_env):
        """Test revoking an API key."""
        self._login_user(cli_runner, "revoke@example.com", "testpass")

        # Create a key
        create_result = cli_runner.invoke(app, ["auth", "apikey", "create", "Revoke Key"])
        key_data = json.loads(create_result.stdout)
        key_id = key_data["id"]

        # Revoke it
        result = cli_runner.invoke(app, ["auth", "apikey", "revoke", str(key_id)])

        assert result.exit_code == 0

    def test_apikey_not_authenticated(self, cli_runner: CliRunner, auth_enabled_env):
        """Test API key commands require authentication."""
        # Logout first
        cli_runner.invoke(app, ["auth", "logout"])

        result = cli_runner.invoke(app, ["auth", "apikey", "list"])

        assert result.exit_code in (1, 2)  # Could be 1 or 2 depending on error handling
        assert "not authenticated" in result.output.lower() or "auth" in result.output.lower()
