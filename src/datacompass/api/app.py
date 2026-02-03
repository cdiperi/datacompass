"""FastAPI application factory and configuration."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from datacompass import __version__
from datacompass.api.exceptions import register_exception_handlers
from datacompass.api.routes import (
    auth_router,
    deprecation_router,
    dq_router,
    health_router,
    lineage_router,
    notifications_router,
    objects_router,
    schedules_router,
    search_router,
    sources_router,
)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="Data Compass API",
        description="Metadata catalog with data quality monitoring and lineage visualization",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure CORS for web clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register exception handlers
    register_exception_handlers(app)

    # Mount routers
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(sources_router, prefix="/api/v1")
    app.include_router(objects_router, prefix="/api/v1")
    app.include_router(lineage_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(dq_router, prefix="/api/v1")
    app.include_router(deprecation_router, prefix="/api/v1")
    app.include_router(schedules_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")

    return app


# Default app instance for uvicorn
app = create_app()
