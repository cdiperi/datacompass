"""Data access repositories for Data Compass."""

from datacompass.core.repositories.base import BaseRepository
from datacompass.core.repositories.catalog_object import CatalogObjectRepository
from datacompass.core.repositories.column import ColumnRepository
from datacompass.core.repositories.data_source import DataSourceRepository
from datacompass.core.repositories.dependency import DependencyRepository
from datacompass.core.repositories.deprecation import DeprecationRepository
from datacompass.core.repositories.dq import DQRepository
from datacompass.core.repositories.scheduling import (
    NotificationRepository,
    SchedulingRepository,
)
from datacompass.core.repositories.search import SearchRepository, SearchResult
from datacompass.core.repositories.auth import (
    APIKeyRepository,
    RefreshTokenRepository,
    SessionRepository,
    UserRepository,
)

__all__ = [
    "BaseRepository",
    "DataSourceRepository",
    "CatalogObjectRepository",
    "ColumnRepository",
    "DependencyRepository",
    "DeprecationRepository",
    "DQRepository",
    "SchedulingRepository",
    "NotificationRepository",
    "SearchRepository",
    "SearchResult",
    # Auth repositories
    "UserRepository",
    "APIKeyRepository",
    "SessionRepository",
    "RefreshTokenRepository",
]
