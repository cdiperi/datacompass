"""API route modules."""

from datacompass.api.routes.deprecation import router as deprecation_router
from datacompass.api.routes.dq import router as dq_router
from datacompass.api.routes.health import router as health_router
from datacompass.api.routes.lineage import router as lineage_router
from datacompass.api.routes.notifications import router as notifications_router
from datacompass.api.routes.objects import router as objects_router
from datacompass.api.routes.schedules import router as schedules_router
from datacompass.api.routes.search import router as search_router
from datacompass.api.routes.sources import router as sources_router

__all__ = [
    "deprecation_router",
    "dq_router",
    "health_router",
    "lineage_router",
    "notifications_router",
    "objects_router",
    "schedules_router",
    "search_router",
    "sources_router",
]
