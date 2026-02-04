"""Source adapters for Data Compass."""

from datacompass.core.adapters.base import SourceAdapter
from datacompass.core.adapters.databricks import DatabricksAdapter
from datacompass.core.adapters.exceptions import (
    AdapterAuthenticationError,
    AdapterConfigurationError,
    AdapterConnectionError,
    AdapterError,
    AdapterNotFoundError,
    AdapterQueryError,
)
from datacompass.core.adapters.postgresql import PostgreSQLAdapter
from datacompass.core.adapters.registry import AdapterInfo, AdapterRegistry
from datacompass.core.adapters.schemas import (
    AuthMethod,
    DatabricksConfig,
    PostgreSQLConfig,
    SnowflakeConfig,
    SSLMode,
)
from datacompass.core.adapters.snowflake import SnowflakeAdapter

__all__ = [
    # Base
    "SourceAdapter",
    # Registry
    "AdapterRegistry",
    "AdapterInfo",
    # Exceptions
    "AdapterError",
    "AdapterConnectionError",
    "AdapterAuthenticationError",
    "AdapterConfigurationError",
    "AdapterQueryError",
    "AdapterNotFoundError",
    # Config schemas
    "AuthMethod",
    "DatabricksConfig",
    "PostgreSQLConfig",
    "SnowflakeConfig",
    "SSLMode",
    # Adapters
    "DatabricksAdapter",
    "PostgreSQLAdapter",
    "SnowflakeAdapter",
]
