"""Search endpoint."""

from fastapi import APIRouter, Query

from datacompass.api.dependencies import SearchServiceDep
from datacompass.core.models import SearchResultResponse

router = APIRouter(tags=["search"])


@router.get("/search", response_model=list[SearchResultResponse])
async def search(
    search_service: SearchServiceDep,
    q: str = Query(..., min_length=1, description="Search query string"),
    source: str | None = Query(None, description="Filter by source name"),
    object_type: str | None = Query(None, description="Filter by object type (TABLE, VIEW, etc.)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
) -> list[SearchResultResponse]:
    """Search the catalog using full-text search.

    Searches across object names, schema names, descriptions, tags,
    and column names. Results are ranked by relevance.

    Args:
        q: Search query string.
        source: Filter by source name.
        object_type: Filter by object type.
        limit: Maximum results (1-200, default 50).

    Returns:
        List of search results ordered by relevance.
    """
    return search_service.search(
        query=q,
        source=source,
        object_type=object_type,
        limit=limit,
    )
