"""Adapter-specific exceptions."""


class AdapterError(Exception):
    """Base exception for adapter errors."""

    def __init__(self, message: str, source_type: str | None = None) -> None:
        self.message = message
        self.source_type = source_type
        super().__init__(message)


class AdapterConnectionError(AdapterError):
    """Raised when an adapter cannot connect to the data source."""

    pass


class AdapterAuthenticationError(AdapterError):
    """Raised when authentication to the data source fails."""

    pass


class AdapterConfigurationError(AdapterError):
    """Raised when adapter configuration is invalid."""

    pass


class AdapterQueryError(AdapterError):
    """Raised when a query execution fails."""

    def __init__(
        self,
        message: str,
        query: str | None = None,
        source_type: str | None = None,
    ) -> None:
        super().__init__(message, source_type)
        self.query = query


class AdapterNotFoundError(AdapterError):
    """Raised when a requested adapter type is not registered."""

    def __init__(self, source_type: str) -> None:
        super().__init__(
            f"Unknown adapter type: {source_type!r}",
            source_type=source_type,
        )
