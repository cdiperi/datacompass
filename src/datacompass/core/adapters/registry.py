"""Adapter registry for discovering and instantiating adapters."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from datacompass.core.adapters.base import SourceAdapter
from datacompass.core.adapters.exceptions import AdapterNotFoundError


@dataclass
class AdapterInfo:
    """Metadata about a registered adapter."""

    source_type: str
    display_name: str
    adapter_class: type[SourceAdapter]
    config_schema: type[BaseModel]
    supported_object_types: list[str]
    supported_dq_metrics: list[str]


class AdapterRegistry:
    """Registry for data source adapters.

    Adapters register themselves using the @register decorator, making them
    discoverable and instantiable by type name.

    Usage:
        @AdapterRegistry.register(
            source_type="databricks",
            display_name="Databricks Unity Catalog",
            config_schema=DatabricksConfig,
        )
        class DatabricksAdapter(SourceAdapter):
            ...

        # Get adapter by type
        adapter = AdapterRegistry.get_adapter("databricks", config_dict)
    """

    _adapters: dict[str, AdapterInfo] = {}

    @classmethod
    def register(
        cls,
        source_type: str,
        display_name: str,
        config_schema: type[BaseModel],
    ) -> Callable[[type[SourceAdapter]], type[SourceAdapter]]:
        """Decorator to register an adapter class.

        Args:
            source_type: Unique identifier for the adapter type (e.g., 'databricks').
            display_name: Human-readable name for display.
            config_schema: Pydantic model class for configuration validation.

        Returns:
            Decorator function.
        """

        def decorator(adapter_class: type[SourceAdapter]) -> type[SourceAdapter]:
            cls._adapters[source_type] = AdapterInfo(
                source_type=source_type,
                display_name=display_name,
                adapter_class=adapter_class,
                config_schema=config_schema,
                supported_object_types=adapter_class.SUPPORTED_OBJECT_TYPES,
                supported_dq_metrics=adapter_class.SUPPORTED_DQ_METRICS,
            )
            return adapter_class

        return decorator

    @classmethod
    def get_adapter(cls, source_type: str, config: dict[str, Any]) -> SourceAdapter:
        """Instantiate an adapter by type.

        Args:
            source_type: The registered adapter type.
            config: Configuration dict to validate and pass to adapter.

        Returns:
            Instantiated adapter.

        Raises:
            AdapterNotFoundError: If source_type is not registered.
            ValidationError: If config is invalid.
        """
        if source_type not in cls._adapters:
            raise AdapterNotFoundError(source_type)

        info = cls._adapters[source_type]
        validated_config = info.config_schema(**config)
        return info.adapter_class(validated_config)

    @classmethod
    def get_adapter_info(cls, source_type: str) -> AdapterInfo:
        """Get metadata about a registered adapter.

        Args:
            source_type: The registered adapter type.

        Returns:
            AdapterInfo with metadata.

        Raises:
            AdapterNotFoundError: If source_type is not registered.
        """
        if source_type not in cls._adapters:
            raise AdapterNotFoundError(source_type)
        return cls._adapters[source_type]

    @classmethod
    def list_adapters(cls) -> list[AdapterInfo]:
        """List all registered adapters.

        Returns:
            List of AdapterInfo for all registered adapters.
        """
        return list(cls._adapters.values())

    @classmethod
    def get_config_schema(cls, source_type: str) -> type[BaseModel]:
        """Get the configuration schema for an adapter type.

        Args:
            source_type: The registered adapter type.

        Returns:
            Pydantic model class for configuration.

        Raises:
            AdapterNotFoundError: If source_type is not registered.
        """
        if source_type not in cls._adapters:
            raise AdapterNotFoundError(source_type)
        return cls._adapters[source_type].config_schema

    @classmethod
    def is_registered(cls, source_type: str) -> bool:
        """Check if an adapter type is registered.

        Args:
            source_type: The adapter type to check.

        Returns:
            True if registered, False otherwise.
        """
        return source_type in cls._adapters

    @classmethod
    def available_types(cls) -> list[str]:
        """Get list of available adapter type names.

        Returns:
            List of registered adapter type names.
        """
        return list(cls._adapters.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered adapters.

        Primarily for testing purposes.
        """
        cls._adapters.clear()
