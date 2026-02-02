"""Service for managing documentation on catalog objects."""

from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from datacompass.core.models import CatalogObject
from datacompass.core.repositories import (
    CatalogObjectRepository,
    DataSourceRepository,
    SearchRepository,
)
from datacompass.core.services.catalog_service import ObjectNotFoundError


class DocumentationServiceError(Exception):
    """Raised when a documentation operation fails."""

    pass


class DocumentationService:
    """Service for managing user documentation on catalog objects.

    Handles:
    - Setting/updating descriptions
    - Adding/removing tags
    - Syncing changes to FTS index
    """

    def __init__(self, session: Session) -> None:
        """Initialize documentation service.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self.source_repo = DataSourceRepository(session)
        self.object_repo = CatalogObjectRepository(session)
        self.search_repo = SearchRepository(session)

    def set_description(
        self,
        object_identifier: str,
        description: str,
    ) -> CatalogObject:
        """Set or update description for a catalog object.

        Args:
            object_identifier: Object identifier (source.schema.name or ID).
            description: New description text.

        Returns:
            Updated CatalogObject.

        Raises:
            ObjectNotFoundError: If object not found.
        """
        obj = self._resolve_object(object_identifier)
        if obj is None:
            raise ObjectNotFoundError(object_identifier)

        # Initialize or update user_metadata
        if obj.user_metadata is None:
            obj.user_metadata = {}

        obj.user_metadata["description"] = description
        obj.updated_at = datetime.utcnow()

        # Force SQLAlchemy to detect the change (JSON column)
        flag_modified(obj, "user_metadata")
        self.session.flush()

        # Reindex for search
        self.search_repo.reindex_object(obj.id)

        return obj

    def get_description(self, object_identifier: str) -> str | None:
        """Get description for a catalog object.

        Returns user description if set, otherwise source description.

        Args:
            object_identifier: Object identifier (source.schema.name or ID).

        Returns:
            Description string or None.

        Raises:
            ObjectNotFoundError: If object not found.
        """
        obj = self._resolve_object(object_identifier)
        if obj is None:
            raise ObjectNotFoundError(object_identifier)

        # User description takes precedence
        if obj.user_metadata and obj.user_metadata.get("description"):
            return obj.user_metadata["description"]

        # Fall back to source description
        if obj.source_metadata and obj.source_metadata.get("description"):
            return obj.source_metadata["description"]

        return None

    def add_tag(self, object_identifier: str, tag: str) -> CatalogObject:
        """Add a tag to a catalog object.

        Args:
            object_identifier: Object identifier (source.schema.name or ID).
            tag: Tag to add.

        Returns:
            Updated CatalogObject.

        Raises:
            ObjectNotFoundError: If object not found.
        """
        obj = self._resolve_object(object_identifier)
        if obj is None:
            raise ObjectNotFoundError(object_identifier)

        # Initialize user_metadata if needed
        if obj.user_metadata is None:
            obj.user_metadata = {}

        # Initialize tags list if needed
        if "tags" not in obj.user_metadata:
            obj.user_metadata["tags"] = []

        # Add tag if not already present
        if tag not in obj.user_metadata["tags"]:
            obj.user_metadata["tags"].append(tag)
            obj.updated_at = datetime.utcnow()

            # Force SQLAlchemy to detect the change
            flag_modified(obj, "user_metadata")
            self.session.flush()

            # Reindex for search
            self.search_repo.reindex_object(obj.id)

        return obj

    def remove_tag(self, object_identifier: str, tag: str) -> CatalogObject:
        """Remove a tag from a catalog object.

        Args:
            object_identifier: Object identifier (source.schema.name or ID).
            tag: Tag to remove.

        Returns:
            Updated CatalogObject.

        Raises:
            ObjectNotFoundError: If object not found.
        """
        obj = self._resolve_object(object_identifier)
        if obj is None:
            raise ObjectNotFoundError(object_identifier)

        if obj.user_metadata and "tags" in obj.user_metadata and tag in obj.user_metadata["tags"]:
            obj.user_metadata["tags"].remove(tag)
            obj.updated_at = datetime.utcnow()

            # Force SQLAlchemy to detect the change
            flag_modified(obj, "user_metadata")
            self.session.flush()

            # Reindex for search
            self.search_repo.reindex_object(obj.id)

        return obj

    def get_tags(self, object_identifier: str) -> list[str]:
        """Get tags for a catalog object.

        Args:
            object_identifier: Object identifier (source.schema.name or ID).

        Returns:
            List of tags.

        Raises:
            ObjectNotFoundError: If object not found.
        """
        obj = self._resolve_object(object_identifier)
        if obj is None:
            raise ObjectNotFoundError(object_identifier)

        if obj.user_metadata and obj.user_metadata.get("tags"):
            return list(obj.user_metadata["tags"])

        return []

    def add_tags(self, object_identifier: str, tags: list[str]) -> CatalogObject:
        """Add multiple tags to a catalog object.

        Args:
            object_identifier: Object identifier (source.schema.name or ID).
            tags: Tags to add.

        Returns:
            Updated CatalogObject.

        Raises:
            ObjectNotFoundError: If object not found.
        """
        obj = self._resolve_object(object_identifier)
        if obj is None:
            raise ObjectNotFoundError(object_identifier)

        # Initialize user_metadata if needed
        if obj.user_metadata is None:
            obj.user_metadata = {}

        # Initialize tags list if needed
        if "tags" not in obj.user_metadata:
            obj.user_metadata["tags"] = []

        # Add tags if not already present
        changed = False
        for tag in tags:
            if tag not in obj.user_metadata["tags"]:
                obj.user_metadata["tags"].append(tag)
                changed = True

        if changed:
            obj.updated_at = datetime.utcnow()
            flag_modified(obj, "user_metadata")
            self.session.flush()
            self.search_repo.reindex_object(obj.id)

        return obj

    def remove_tags(self, object_identifier: str, tags: list[str]) -> CatalogObject:
        """Remove multiple tags from a catalog object.

        Args:
            object_identifier: Object identifier (source.schema.name or ID).
            tags: Tags to remove.

        Returns:
            Updated CatalogObject.

        Raises:
            ObjectNotFoundError: If object not found.
        """
        obj = self._resolve_object(object_identifier)
        if obj is None:
            raise ObjectNotFoundError(object_identifier)

        if obj.user_metadata and "tags" in obj.user_metadata:
            changed = False
            for tag in tags:
                if tag in obj.user_metadata["tags"]:
                    obj.user_metadata["tags"].remove(tag)
                    changed = True

            if changed:
                obj.updated_at = datetime.utcnow()
                flag_modified(obj, "user_metadata")
                self.session.flush()
                self.search_repo.reindex_object(obj.id)

        return obj

    def _resolve_object(self, identifier: str) -> CatalogObject | None:
        """Resolve an object identifier to a CatalogObject.

        Supports:
        - Numeric ID: "123"
        - Qualified name: "source.schema.name"

        Args:
            identifier: Object identifier.

        Returns:
            CatalogObject or None if not found.
        """
        # Try as numeric ID first
        if identifier.isdigit():
            obj = self.object_repo.get_with_source(int(identifier))
            if obj:
                return obj

        # Try as qualified name (source.schema.object)
        parts = identifier.split(".")
        if len(parts) == 3:
            source_name, schema_name, object_name = parts
            source = self.source_repo.get_by_name(source_name)
            if source:
                # Get objects matching schema.name (could be multiple types)
                objects = self.object_repo.list_objects(
                    source_id=source.id,
                    schema_name=schema_name,
                )
                for obj in objects:
                    if obj.object_name == object_name:
                        return self.object_repo.get_with_source(obj.id)

        return None
