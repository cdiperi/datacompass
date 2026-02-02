"""Tests for config loader."""

import os
from pathlib import Path

import pytest

from datacompass.core.services.config_loader import (
    ConfigLoadError,
    load_yaml_config,
    mask_sensitive_values,
    substitute_env_vars,
)


class TestSubstituteEnvVars:
    """Test cases for environment variable substitution."""

    def test_substitute_simple_var(self):
        """Test substituting a simple variable."""
        os.environ["TEST_VAR"] = "hello"
        try:
            result = substitute_env_vars("${TEST_VAR}")
            assert result == "hello"
        finally:
            del os.environ["TEST_VAR"]

    def test_substitute_with_default(self):
        """Test substituting with default value."""
        # Variable not set, should use default
        result = substitute_env_vars("${NONEXISTENT_VAR:-default_value}")
        assert result == "default_value"

    def test_substitute_set_var_ignores_default(self):
        """Test that set variable ignores default."""
        os.environ["SET_VAR"] = "actual"
        try:
            result = substitute_env_vars("${SET_VAR:-default}")
            assert result == "actual"
        finally:
            del os.environ["SET_VAR"]

    def test_substitute_missing_var_raises(self):
        """Test that missing required var raises error."""
        with pytest.raises(ConfigLoadError) as exc_info:
            substitute_env_vars("${DEFINITELY_NOT_SET}")

        assert "DEFINITELY_NOT_SET" in str(exc_info.value)

    def test_substitute_in_dict(self):
        """Test substitution in nested dict."""
        os.environ["DB_HOST"] = "localhost"
        try:
            result = substitute_env_vars({
                "connection": {
                    "host": "${DB_HOST}",
                    "port": 5432,
                }
            })
            assert result["connection"]["host"] == "localhost"
            assert result["connection"]["port"] == 5432
        finally:
            del os.environ["DB_HOST"]

    def test_substitute_in_list(self):
        """Test substitution in list."""
        os.environ["ITEM1"] = "first"
        try:
            result = substitute_env_vars(["${ITEM1}", "second"])
            assert result == ["first", "second"]
        finally:
            del os.environ["ITEM1"]

    def test_substitute_mixed_string(self):
        """Test substitution in mixed string."""
        os.environ["HOST"] = "example.com"
        os.environ["PORT"] = "8080"
        try:
            result = substitute_env_vars("https://${HOST}:${PORT}/api")
            assert result == "https://example.com:8080/api"
        finally:
            del os.environ["HOST"]
            del os.environ["PORT"]


class TestLoadYamlConfig:
    """Test cases for YAML loading."""

    def test_load_valid_yaml(self, tmp_path: Path):
        """Test loading valid YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
host: localhost
port: 5432
database: mydb
""")
        config = load_yaml_config(config_file)
        assert config["host"] == "localhost"
        assert config["port"] == 5432

    def test_load_with_env_substitution(self, tmp_path: Path):
        """Test loading YAML with environment variable substitution."""
        os.environ["DB_PASSWORD"] = "secret123"
        try:
            config_file = tmp_path / "config.yaml"
            config_file.write_text("""
host: localhost
password: ${DB_PASSWORD}
""")
            config = load_yaml_config(config_file)
            assert config["password"] == "secret123"
        finally:
            del os.environ["DB_PASSWORD"]

    def test_load_nonexistent_file(self, tmp_path: Path):
        """Test loading non-existent file raises error."""
        with pytest.raises(ConfigLoadError) as exc_info:
            load_yaml_config(tmp_path / "nonexistent.yaml")

        assert "not found" in str(exc_info.value)

    def test_load_invalid_yaml(self, tmp_path: Path):
        """Test loading invalid YAML raises error."""
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("{ invalid yaml [")

        with pytest.raises(ConfigLoadError) as exc_info:
            load_yaml_config(config_file)

        assert "Invalid YAML" in str(exc_info.value)

    def test_load_empty_yaml(self, tmp_path: Path):
        """Test loading empty YAML raises error."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        with pytest.raises(ConfigLoadError) as exc_info:
            load_yaml_config(config_file)

        assert "Empty" in str(exc_info.value)


class TestMaskSensitiveValues:
    """Test cases for masking sensitive values."""

    def test_mask_password(self):
        """Test that password fields are masked."""
        config = {"username": "admin", "password": "secret123"}
        masked = mask_sensitive_values(config)
        assert masked["username"] == "admin"
        assert masked["password"] == "***"

    def test_mask_token(self):
        """Test that token fields are masked."""
        config = {"access_token": "abc123", "refresh_token": "xyz789"}
        masked = mask_sensitive_values(config)
        assert masked["access_token"] == "***"
        assert masked["refresh_token"] == "***"

    def test_mask_secret(self):
        """Test that secret fields are masked."""
        config = {"client_secret": "mysecret", "api_key": "key123"}
        masked = mask_sensitive_values(config)
        assert masked["client_secret"] == "***"
        assert masked["api_key"] == "***"

    def test_mask_nested(self):
        """Test masking in nested structures."""
        config = {
            "connection": {
                "host": "localhost",
                "password": "secret",
            }
        }
        masked = mask_sensitive_values(config)
        assert masked["connection"]["host"] == "localhost"
        assert masked["connection"]["password"] == "***"

    def test_mask_preserves_none(self):
        """Test that None values are preserved."""
        config = {"password": None, "username": "admin"}
        masked = mask_sensitive_values(config)
        assert masked["password"] is None
