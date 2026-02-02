"""Health check endpoint."""

from fastapi import APIRouter

from datacompass import __version__
from datacompass.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check API health status.

    Returns basic health information including service status and version.
    """
    return HealthResponse(status="healthy", version=__version__)
