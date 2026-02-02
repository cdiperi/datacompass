"""Business logic services for Data Compass."""

from datacompass.core.services.catalog_service import (
    CatalogService,
    CatalogServiceError,
    ObjectNotFoundError,
)
from datacompass.core.services.config_loader import (
    ConfigLoadError,
    load_source_config,
    load_yaml_config,
    mask_sensitive_values,
    substitute_env_vars,
)
from datacompass.core.services.documentation_service import (
    DocumentationService,
    DocumentationServiceError,
)
from datacompass.core.services.deprecation_service import (
    CampaignExistsError,
    CampaignNotFoundError,
    DeprecationNotFoundError,
    DeprecationService,
    DeprecationServiceError,
    ObjectAlreadyDeprecatedError,
)
from datacompass.core.services.dq_service import (
    DQBreachNotFoundError,
    DQConfigExistsError,
    DQConfigNotFoundError,
    DQExpectationNotFoundError,
    DQService,
    DQServiceError,
)
from datacompass.core.services.lineage_service import (
    LineageService,
    LineageServiceError,
)
from datacompass.core.services.notification_service import (
    ChannelExistsError,
    ChannelNotFoundError,
    NotificationService,
    NotificationServiceError,
    RuleNotFoundError,
)
from datacompass.core.services.scheduling_service import (
    ScheduleExistsError,
    ScheduleNotFoundError,
    SchedulingService,
    SchedulingServiceError,
)
from datacompass.core.services.search_service import (
    SearchService,
    SearchServiceError,
)
from datacompass.core.services.source_service import (
    SourceExistsError,
    SourceNotFoundError,
    SourceService,
    SourceServiceError,
)

__all__ = [
    # Source service
    "SourceService",
    "SourceServiceError",
    "SourceNotFoundError",
    "SourceExistsError",
    # Catalog service
    "CatalogService",
    "CatalogServiceError",
    "ObjectNotFoundError",
    # Search service
    "SearchService",
    "SearchServiceError",
    # Documentation service
    "DocumentationService",
    "DocumentationServiceError",
    # Lineage service
    "LineageService",
    "LineageServiceError",
    # DQ service
    "DQService",
    "DQServiceError",
    "DQConfigNotFoundError",
    "DQConfigExistsError",
    "DQExpectationNotFoundError",
    "DQBreachNotFoundError",
    # Deprecation service
    "DeprecationService",
    "DeprecationServiceError",
    "CampaignNotFoundError",
    "CampaignExistsError",
    "DeprecationNotFoundError",
    "ObjectAlreadyDeprecatedError",
    # Scheduling service
    "SchedulingService",
    "SchedulingServiceError",
    "ScheduleNotFoundError",
    "ScheduleExistsError",
    # Notification service
    "NotificationService",
    "NotificationServiceError",
    "ChannelNotFoundError",
    "ChannelExistsError",
    "RuleNotFoundError",
    # Config loader
    "load_yaml_config",
    "load_source_config",
    "substitute_env_vars",
    "mask_sensitive_values",
    "ConfigLoadError",
]
