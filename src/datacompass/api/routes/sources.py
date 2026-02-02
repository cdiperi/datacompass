"""Source management endpoints."""

from fastapi import APIRouter, status

from datacompass.api.dependencies import CatalogServiceDep, SourceServiceDep
from datacompass.api.schemas import SourceCreateRequest
from datacompass.core.models import DataSourceResponse, ScanResult

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[DataSourceResponse])
async def list_sources(
    source_service: SourceServiceDep,
    active_only: bool = False,
) -> list[DataSourceResponse]:
    """List all configured data sources.

    Args:
        active_only: If true, only return active sources.

    Returns:
        List of data source configurations.
    """
    sources = source_service.list_sources(active_only=active_only)
    return [DataSourceResponse.model_validate(s) for s in sources]


@router.post("", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    request: SourceCreateRequest,
    source_service: SourceServiceDep,
) -> DataSourceResponse:
    """Create a new data source.

    Args:
        request: Source creation request with name, type, and connection info.

    Returns:
        Created data source.

    Raises:
        409: If source with name already exists.
        400: If source_type is not a valid adapter type.
    """
    source = source_service.add_source_from_dict(
        name=request.name,
        source_type=request.source_type,
        connection_info=request.connection_info,
        display_name=request.display_name,
    )
    return DataSourceResponse.model_validate(source)


@router.get("/{name}", response_model=DataSourceResponse)
async def get_source(
    name: str,
    source_service: SourceServiceDep,
) -> DataSourceResponse:
    """Get a data source by name.

    Args:
        name: Source name.

    Returns:
        Data source details.

    Raises:
        404: If source not found.
    """
    source = source_service.get_source(name)
    return DataSourceResponse.model_validate(source)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    name: str,
    source_service: SourceServiceDep,
) -> None:
    """Delete a data source.

    Args:
        name: Source name to delete.

    Raises:
        404: If source not found.
    """
    source_service.remove_source(name)


@router.post("/{name}/scan", response_model=ScanResult)
async def scan_source(
    name: str,
    catalog_service: CatalogServiceDep,
    full: bool = False,
) -> ScanResult:
    """Trigger a scan of a data source.

    Scans the source to discover and update catalog objects.

    Args:
        name: Source name to scan.
        full: If true, perform full scan (soft-delete missing objects).

    Returns:
        Scan result with statistics.

    Raises:
        404: If source not found.
    """
    return catalog_service.scan_source(name, full=full)
