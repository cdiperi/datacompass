"""CLI helper functions for session management and error handling."""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any

from rich.console import Console
from sqlalchemy.orm import Session

from datacompass.core.adapters import AdapterError, AdapterNotFoundError
from datacompass.core.database import init_database, session_scope
from datacompass.core.services import ConfigLoadError, SourceExistsError, SourceNotFoundError

err_console = Console(stderr=True)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get a database session, initializing the database if needed.

    This context manager:
    - Ensures the database is initialized (tables created)
    - Provides a session that auto-commits on success
    - Rolls back on exception

    Yields:
        SQLAlchemy Session instance.
    """
    # Initialize database (creates tables if needed)
    init_database()

    with session_scope() as session:
        yield session


def handle_error(error: Exception) -> int:
    """Handle an exception and print appropriate error message.

    Args:
        error: The exception to handle.

    Returns:
        Exit code (1 for handled errors, 2 for unexpected errors).
    """
    if isinstance(error, SourceNotFoundError):
        err_console.print(f"[red]Error:[/red] Data source not found: {error.name!r}")
        err_console.print("[dim]Run 'datacompass source list' to see available sources.[/dim]")
        return 1

    elif isinstance(error, SourceExistsError):
        err_console.print(f"[red]Error:[/red] Data source already exists: {error.name!r}")
        return 1

    elif isinstance(error, AdapterNotFoundError):
        err_console.print(f"[red]Error:[/red] Unknown source type: {error.source_type!r}")
        # Import here to avoid circular imports
        from datacompass.core.adapters import AdapterRegistry

        available = AdapterRegistry.available_types()
        if available:
            err_console.print(f"[dim]Available types: {', '.join(available)}[/dim]")
        return 1

    elif isinstance(error, AdapterError):
        err_console.print(f"[red]Error:[/red] {error.message}")
        return 1

    elif isinstance(error, ConfigLoadError):
        err_console.print(f"[red]Configuration error:[/red] {error}")
        return 1

    elif isinstance(error, FileNotFoundError):
        err_console.print(f"[red]Error:[/red] File not found: {error.filename}")
        return 1

    else:
        err_console.print(f"[red]Unexpected error:[/red] {error}")
        err_console.print("[dim]This may be a bug. Please report it.[/dim]")
        return 2


def serialize_for_json(obj: Any) -> Any:
    """Serialize an object to JSON-compatible format.

    Handles datetime objects and other non-serializable types.

    Args:
        obj: Object to serialize.

    Returns:
        JSON-serializable object.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    elif hasattr(obj, "__dict__"):
        return {k: serialize_for_json(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj
