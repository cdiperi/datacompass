"""Base repository with common CRUD operations."""

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from datacompass.core.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Base repository providing common CRUD operations.

    Subclasses should set the `model` class attribute to the SQLAlchemy model class.
    """

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        """Initialize repository with a database session.

        Args:
            session: SQLAlchemy session for database operations.
        """
        self.session = session

    def get_by_id(self, id: int) -> ModelT | None:
        """Get a record by primary key.

        Args:
            id: Primary key value.

        Returns:
            Model instance or None if not found.
        """
        return self.session.get(self.model, id)

    def get_all(self, limit: int | None = None, offset: int = 0) -> list[ModelT]:
        """Get all records with optional pagination.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            List of model instances.
        """
        stmt = select(self.model).offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def add(self, entity: ModelT) -> ModelT:
        """Add a new record to the session.

        Args:
            entity: Model instance to add.

        Returns:
            The added entity (may be modified after flush).
        """
        self.session.add(entity)
        return entity

    def add_all(self, entities: list[ModelT]) -> list[ModelT]:
        """Add multiple records to the session.

        Args:
            entities: List of model instances to add.

        Returns:
            The added entities.
        """
        self.session.add_all(entities)
        return entities

    def delete(self, entity: ModelT) -> None:
        """Delete a record from the session.

        Args:
            entity: Model instance to delete.
        """
        self.session.delete(entity)

    def count(self) -> int:
        """Count all records.

        Returns:
            Total number of records.
        """
        stmt = select(self.model)
        return len(list(self.session.scalars(stmt)))

    def flush(self) -> None:
        """Flush pending changes to the database."""
        self.session.flush()

    def refresh(self, entity: ModelT) -> ModelT:
        """Refresh an entity from the database.

        Args:
            entity: Model instance to refresh.

        Returns:
            The refreshed entity.
        """
        self.session.refresh(entity)
        return entity
