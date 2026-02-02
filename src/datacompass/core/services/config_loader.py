"""Configuration file loader with environment variable substitution."""

import os
import re
from pathlib import Path
from typing import Any

import yaml


class ConfigLoadError(Exception):
    """Raised when configuration loading fails."""

    pass


def substitute_env_vars(value: Any) -> Any:
    """Recursively substitute ${VAR} patterns with environment variables.

    Supports:
    - ${VAR} - Required variable (raises if not set)
    - ${VAR:-default} - Variable with default value

    Args:
        value: String, dict, or list to process.

    Returns:
        Value with environment variables substituted.

    Raises:
        ConfigLoadError: If required variable is not set.
    """
    if isinstance(value, str):
        # Pattern matches ${VAR} or ${VAR:-default}
        pattern = r"\$\{([^}:-]+)(?::-([^}]*))?\}"

        def replace(match: re.Match) -> str:
            var_name = match.group(1)
            default = match.group(2)

            env_value = os.environ.get(var_name)
            if env_value is not None:
                return env_value
            elif default is not None:
                return default
            else:
                raise ConfigLoadError(
                    f"Environment variable '{var_name}' is not set and no default provided"
                )

        return re.sub(pattern, replace, value)

    elif isinstance(value, dict):
        return {k: substitute_env_vars(v) for k, v in value.items()}

    elif isinstance(value, list):
        return [substitute_env_vars(item) for item in value]

    else:
        return value


def load_yaml_config(path: Path) -> dict[str, Any]:
    """Load a YAML configuration file with environment variable substitution.

    Args:
        path: Path to YAML file.

    Returns:
        Parsed configuration dict.

    Raises:
        ConfigLoadError: If file cannot be loaded or parsed.
    """
    if not path.exists():
        raise ConfigLoadError(f"Configuration file not found: {path}")

    try:
        with open(path) as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigLoadError(f"Invalid YAML in {path}: {e}") from e

    if config is None:
        raise ConfigLoadError(f"Empty configuration file: {path}")

    # Substitute environment variables
    return substitute_env_vars(config)


def load_source_config(path: Path) -> dict[str, Any]:
    """Load a data source configuration file.

    The file should contain connection configuration for a single source.
    This is used with `datacompass source add --config <file>`.

    Example config file:
        host: ${DATABRICKS_HOST}
        http_path: /sql/1.0/warehouses/abc123
        catalog: main
        access_token: ${DATABRICKS_TOKEN}

    Args:
        path: Path to source configuration YAML.

    Returns:
        Configuration dict ready to pass to adapter.

    Raises:
        ConfigLoadError: If file cannot be loaded.
    """
    return load_yaml_config(path)


def mask_sensitive_values(config: dict[str, Any]) -> dict[str, Any]:
    """Mask sensitive values in a configuration dict for display.

    Replaces values of keys containing 'secret', 'token', 'password', 'key'
    with '***'.

    Args:
        config: Configuration dict to mask.

    Returns:
        New dict with sensitive values masked.
    """
    sensitive_patterns = ["secret", "token", "password", "key", "credential"]

    def should_mask(key: str) -> bool:
        key_lower = key.lower()
        return any(pattern in key_lower for pattern in sensitive_patterns)

    def mask_value(key: str, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: mask_value(k, v) for k, v in value.items()}
        elif isinstance(value, list):
            return [mask_value(key, item) for item in value]
        elif should_mask(key) and value is not None:
            return "***"
        else:
            return value

    return {k: mask_value(k, v) for k, v in config.items()}
