"""Repository for full-text search operations using FTS5."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from datacompass.core.models import CatalogObject, DataSource


@dataclass
class SearchResult:
    """Raw search result from FTS5 query."""

    object_id: int
    source_name: str
    schema_name: str
    object_name: str
    object_type: str
    description: str | None
    tags: list[str]
    rank: float
    highlights: dict[str, str]


class SearchRepository:
    """Repository for FTS5 search operations.

    Uses SQLite FTS5 for efficient full-text search across catalog objects.
    The FTS index is maintained in external content mode, meaning we must
    manually sync it when objects change.
    """

    def __init__(self, session: Session) -> None:
        """Initialize repository with a database session.

        Args:
            session: SQLAlchemy session for database operations.
        """
        self.session = session

    def search(
        self,
        query: str,
        source: str | None = None,
        object_type: str | None = None,
        limit: int = 50,
    ) -> list[SearchResult]:
        """Search the catalog using full-text search.

        Args:
            query: Search query string. Supports FTS5 query syntax.
            source: Filter by source name.
            object_type: Filter by object type.
            limit: Maximum number of results.

        Returns:
            List of SearchResult ordered by relevance (best first).
        """
        # Build FTS5 query with prefix matching
        # Add * to each term for prefix matching (e.g., "cust" matches "customer")
        fts_query = self._build_fts_query(query)

        # Build FTS5 query with optional filters
        # We join back to catalog_objects to ensure we only return valid objects
        filters = []
        params: dict[str, Any] = {"query": fts_query, "limit": limit}

        if source:
            filters.append("source_name = :source")
            params["source"] = source

        if object_type:
            filters.append("object_type = :object_type")
            params["object_type"] = object_type

        filter_clause = " AND ".join(filters) if filters else "1=1"

        sql = text(
            f"""
            SELECT
                object_id,
                source_name,
                schema_name,
                object_name,
                object_type,
                description,
                tags,
                rank,
                highlight(catalog_fts, 1, '<mark>', '</mark>') as hl_source,
                highlight(catalog_fts, 2, '<mark>', '</mark>') as hl_schema,
                highlight(catalog_fts, 3, '<mark>', '</mark>') as hl_object,
                highlight(catalog_fts, 5, '<mark>', '</mark>') as hl_desc,
                highlight(catalog_fts, 6, '<mark>', '</mark>') as hl_tags,
                highlight(catalog_fts, 7, '<mark>', '</mark>') as hl_columns
            FROM catalog_fts
            WHERE catalog_fts MATCH :query
              AND {filter_clause}
            ORDER BY rank
            LIMIT :limit
            """
        )

        result = self.session.execute(sql, params)
        rows = result.fetchall()

        search_results = []
        for row in rows:
            # Parse tags from space-separated string
            tags_str = row[6] or ""
            tags = tags_str.split() if tags_str else []

            # Build highlights dict
            highlights = {}
            if row[8] and "<mark>" in row[8]:
                highlights["source_name"] = row[8]
            if row[9] and "<mark>" in row[9]:
                highlights["schema_name"] = row[9]
            if row[10] and "<mark>" in row[10]:
                highlights["object_name"] = row[10]
            if row[11] and "<mark>" in row[11]:
                highlights["description"] = row[11]
            if row[12] and "<mark>" in row[12]:
                highlights["tags"] = row[12]
            if row[13] and "<mark>" in row[13]:
                highlights["column_names"] = row[13]

            search_results.append(
                SearchResult(
                    object_id=row[0],
                    source_name=row[1],
                    schema_name=row[2],
                    object_name=row[3],
                    object_type=row[4],
                    description=row[5],
                    tags=tags,
                    rank=row[7],
                    highlights=highlights,
                )
            )

        return search_results

    def reindex_object(self, object_id: int) -> None:
        """Reindex a single object in the FTS index.

        First deletes any existing entry, then inserts the current state.

        Args:
            object_id: ID of the catalog object to reindex.
        """
        # Get current object data with joins
        obj = (
            self.session.query(CatalogObject)
            .join(DataSource)
            .filter(CatalogObject.id == object_id)
            .filter(CatalogObject.deleted_at.is_(None))
            .first()
        )

        # Delete existing entry
        self.session.execute(
            text("DELETE FROM catalog_fts WHERE object_id = :object_id"),
            {"object_id": object_id},
        )

        if obj is None:
            # Object was deleted, just remove from index
            return

        # Build searchable content
        source_name = obj.source.name
        description = self._get_description(obj)
        tags = self._get_tags_string(obj)
        column_names = self._get_column_names(obj)

        # Insert into FTS index
        self.session.execute(
            text(
                """
                INSERT INTO catalog_fts(
                    object_id, source_name, schema_name, object_name,
                    object_type, description, tags, column_names
                ) VALUES (
                    :object_id, :source_name, :schema_name, :object_name,
                    :object_type, :description, :tags, :column_names
                )
                """
            ),
            {
                "object_id": obj.id,
                "source_name": source_name,
                "schema_name": obj.schema_name,
                "object_name": obj.object_name,
                "object_type": obj.object_type,
                "description": description,
                "tags": tags,
                "column_names": column_names,
            },
        )

    def reindex_all(self, source_id: int | None = None) -> int:
        """Reindex all objects in the FTS index.

        Args:
            source_id: Optional source ID to limit reindexing to one source.

        Returns:
            Number of objects indexed.
        """
        # Clear existing entries
        if source_id is not None:
            # Get source name to filter FTS table
            source = self.session.get(DataSource, source_id)
            if source:
                self.session.execute(
                    text("DELETE FROM catalog_fts WHERE source_name = :source_name"),
                    {"source_name": source.name},
                )
        else:
            self.session.execute(text("DELETE FROM catalog_fts"))

        # Query all active objects
        query = (
            self.session.query(CatalogObject)
            .join(DataSource)
            .filter(CatalogObject.deleted_at.is_(None))
        )

        if source_id is not None:
            query = query.filter(CatalogObject.source_id == source_id)

        objects = query.all()
        count = 0

        for obj in objects:
            source_name = obj.source.name
            description = self._get_description(obj)
            tags = self._get_tags_string(obj)
            column_names = self._get_column_names(obj)

            self.session.execute(
                text(
                    """
                    INSERT INTO catalog_fts(
                        object_id, source_name, schema_name, object_name,
                        object_type, description, tags, column_names
                    ) VALUES (
                        :object_id, :source_name, :schema_name, :object_name,
                        :object_type, :description, :tags, :column_names
                    )
                    """
                ),
                {
                    "object_id": obj.id,
                    "source_name": source_name,
                    "schema_name": obj.schema_name,
                    "object_name": obj.object_name,
                    "object_type": obj.object_type,
                    "description": description,
                    "tags": tags,
                    "column_names": column_names,
                },
            )
            count += 1

        return count

    def delete_object(self, object_id: int) -> None:
        """Remove an object from the FTS index.

        Args:
            object_id: ID of the catalog object to remove.
        """
        self.session.execute(
            text("DELETE FROM catalog_fts WHERE object_id = :object_id"),
            {"object_id": object_id},
        )

    def _get_description(self, obj: CatalogObject) -> str | None:
        """Get description from user_metadata or source_metadata."""
        # User description takes precedence
        if obj.user_metadata and obj.user_metadata.get("description"):
            return obj.user_metadata["description"]
        # Fall back to source description
        if obj.source_metadata and obj.source_metadata.get("description"):
            return obj.source_metadata["description"]
        return None

    def _get_tags_string(self, obj: CatalogObject) -> str:
        """Get tags as space-separated string for FTS indexing."""
        if obj.user_metadata and obj.user_metadata.get("tags"):
            tags = obj.user_metadata["tags"]
            if isinstance(tags, list):
                return " ".join(tags)
        return ""

    def _get_column_names(self, obj: CatalogObject) -> str:
        """Get column names as space-separated string for FTS indexing."""
        if hasattr(obj, "columns") and obj.columns:
            return " ".join(col.column_name for col in obj.columns)
        return ""

    def _build_fts_query(self, query: str) -> str:
        """Build FTS5 query with prefix matching.

        Converts user input into FTS5 query syntax with prefix matching.
        Each word gets a * suffix for prefix matching.

        Examples:
            "c" -> "c*"
            "cust order" -> "cust* order*"
            "daily_sales" -> "daily_sales*"

        Args:
            query: Raw user search input.

        Returns:
            FTS5 query string with prefix matching.
        """
        # Split on whitespace and filter empty tokens
        tokens = [t.strip() for t in query.split() if t.strip()]

        if not tokens:
            return query

        # Add prefix wildcard to each token
        # This allows "c" to match "customer", "category", etc.
        prefix_tokens = [f"{token}*" for token in tokens]

        return " ".join(prefix_tokens)
