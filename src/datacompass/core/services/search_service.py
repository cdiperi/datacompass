"""Service for catalog search operations."""

from sqlalchemy.orm import Session

from datacompass.core.models import SearchResultResponse
from datacompass.core.repositories import (
    DataSourceRepository,
    SearchRepository,
)


class SearchServiceError(Exception):
    """Raised when a search operation fails."""

    pass


class SearchService:
    """Service for searching the catalog.

    Handles:
    - Full-text search with filters
    - Reindexing operations
    """

    def __init__(self, session: Session) -> None:
        """Initialize search service.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self.source_repo = DataSourceRepository(session)
        self.search_repo = SearchRepository(session)

    def search(
        self,
        query: str,
        source: str | None = None,
        object_type: str | None = None,
        limit: int = 50,
    ) -> list[SearchResultResponse]:
        """Search the catalog using full-text search.

        Args:
            query: Search query string.
            source: Filter by source name.
            object_type: Filter by object type (TABLE, VIEW, etc.).
            limit: Maximum number of results.

        Returns:
            List of SearchResultResponse ordered by relevance.
        """
        results = self.search_repo.search(
            query=query,
            source=source,
            object_type=object_type,
            limit=limit,
        )

        return [
            SearchResultResponse(
                id=r.object_id,
                source_name=r.source_name,
                schema_name=r.schema_name,
                object_name=r.object_name,
                object_type=r.object_type,
                description=r.description,
                tags=r.tags,
                rank=r.rank,
                highlights=r.highlights,
            )
            for r in results
        ]

    def reindex(self, source: str | None = None) -> int:
        """Reindex the FTS index.

        Args:
            source: Optional source name to reindex only that source.

        Returns:
            Number of objects indexed.
        """
        source_id = None
        if source:
            source_obj = self.source_repo.get_by_name(source)
            if source_obj:
                source_id = source_obj.id

        return self.search_repo.reindex_all(source_id=source_id)
