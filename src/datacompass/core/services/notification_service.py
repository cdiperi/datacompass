"""Service for Notification operations."""

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from datacompass.core.events import Event, get_event_bus
from datacompass.core.models.scheduling import (
    NotificationChannel,
    NotificationChannelResponse,
    NotificationLogResponse,
    NotificationRule,
    NotificationRuleDetailResponse,
    NotificationRuleResponse,
    YAMLSchedulingConfig,
)
from datacompass.core.notifications import (
    NotificationResult,
    get_handler_for_channel,
)
from datacompass.core.repositories.scheduling import NotificationRepository


class NotificationServiceError(Exception):
    """Base exception for notification service errors."""

    pass


class ChannelNotFoundError(NotificationServiceError):
    """Raised when a notification channel is not found."""

    def __init__(self, identifier: str | int) -> None:
        self.identifier = identifier
        super().__init__(f"Notification channel not found: {identifier}")


class ChannelExistsError(NotificationServiceError):
    """Raised when a channel with the same name exists."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Notification channel already exists: {name}")


class RuleNotFoundError(NotificationServiceError):
    """Raised when a notification rule is not found."""

    def __init__(self, identifier: int) -> None:
        self.identifier = identifier
        super().__init__(f"Notification rule not found: {identifier}")


class NotificationService:
    """Service for notification management and delivery.

    Handles:
    - Notification channel CRUD
    - Notification rule CRUD
    - Event handling and notification dispatch
    - Notification logging
    """

    def __init__(self, session: Session) -> None:
        """Initialize notification service.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self.notification_repo = NotificationRepository(session)

    # =========================================================================
    # Channel Management
    # =========================================================================

    def get_channel(self, channel_id: int) -> NotificationChannelResponse:
        """Get notification channel by ID.

        Args:
            channel_id: ID of the channel.

        Returns:
            NotificationChannelResponse with channel details.

        Raises:
            ChannelNotFoundError: If channel not found.
        """
        channel = self.notification_repo.get_by_id(channel_id)
        if channel is None:
            raise ChannelNotFoundError(channel_id)

        return NotificationChannelResponse.model_validate(channel)

    def get_channel_by_name(self, name: str) -> NotificationChannelResponse:
        """Get notification channel by name.

        Args:
            name: Channel name.

        Returns:
            NotificationChannelResponse with channel details.

        Raises:
            ChannelNotFoundError: If channel not found.
        """
        channel = self.notification_repo.get_channel_by_name(name)
        if channel is None:
            raise ChannelNotFoundError(name)

        return NotificationChannelResponse.model_validate(channel)

    def list_channels(
        self,
        channel_type: str | None = None,
        enabled_only: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[NotificationChannelResponse]:
        """List notification channels.

        Args:
            channel_type: Filter by channel type.
            enabled_only: Only return enabled channels.
            limit: Maximum results.
            offset: Number to skip.

        Returns:
            List of NotificationChannelResponse.
        """
        channels = self.notification_repo.list_channels(
            channel_type=channel_type,
            enabled_only=enabled_only,
            limit=limit,
            offset=offset,
        )

        return [NotificationChannelResponse.model_validate(c) for c in channels]

    def create_channel(
        self,
        name: str,
        channel_type: str,
        config: dict[str, Any],
    ) -> NotificationChannelResponse:
        """Create a notification channel.

        Args:
            name: Unique channel name.
            channel_type: Channel type (email, slack, webhook).
            config: Channel-specific configuration.

        Returns:
            Created NotificationChannelResponse.

        Raises:
            ChannelExistsError: If channel with name exists.
        """
        # Check for existing
        existing = self.notification_repo.get_channel_by_name(name)
        if existing is not None:
            raise ChannelExistsError(name)

        # Validate channel type
        if channel_type not in ("email", "slack", "webhook"):
            raise NotificationServiceError(f"Invalid channel type: {channel_type}")

        channel = self.notification_repo.create_channel(
            name=name,
            channel_type=channel_type,
            config=config,
        )

        return NotificationChannelResponse.model_validate(channel)

    def update_channel(
        self,
        channel_id: int,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        is_enabled: bool | None = None,
    ) -> NotificationChannelResponse:
        """Update a notification channel.

        Args:
            channel_id: ID of the channel.
            name: New name.
            config: New configuration.
            is_enabled: New enabled status.

        Returns:
            Updated NotificationChannelResponse.

        Raises:
            ChannelNotFoundError: If channel not found.
            ChannelExistsError: If new name conflicts.
        """
        # Check name conflict if changing name
        if name is not None:
            existing = self.notification_repo.get_channel_by_name(name)
            if existing is not None and existing.id != channel_id:
                raise ChannelExistsError(name)

        channel = self.notification_repo.update_channel(
            channel_id=channel_id,
            name=name,
            config=config,
            is_enabled=is_enabled,
        )

        if channel is None:
            raise ChannelNotFoundError(channel_id)

        return NotificationChannelResponse.model_validate(channel)

    def delete_channel(self, channel_id: int) -> bool:
        """Delete a notification channel.

        Args:
            channel_id: ID of the channel.

        Returns:
            True if deleted.

        Raises:
            ChannelNotFoundError: If channel not found.
        """
        if not self.notification_repo.delete_channel(channel_id):
            raise ChannelNotFoundError(channel_id)
        return True

    def test_channel(self, channel_id: int) -> NotificationResult:
        """Test a notification channel connection.

        Args:
            channel_id: ID of the channel.

        Returns:
            NotificationResult indicating success or failure.

        Raises:
            ChannelNotFoundError: If channel not found.
        """
        channel = self.notification_repo.get_by_id(channel_id)
        if channel is None:
            raise ChannelNotFoundError(channel_id)

        handler = get_handler_for_channel(channel)
        return handler.test_connection()

    # =========================================================================
    # Rule Management
    # =========================================================================

    def get_rule(self, rule_id: int) -> NotificationRuleDetailResponse:
        """Get notification rule by ID.

        Args:
            rule_id: ID of the rule.

        Returns:
            NotificationRuleDetailResponse with rule details.

        Raises:
            RuleNotFoundError: If rule not found.
        """
        rule = self.notification_repo.get_rule_with_channel(rule_id)
        if rule is None:
            raise RuleNotFoundError(rule_id)

        return self._rule_to_detail_response(rule)

    def list_rules(
        self,
        event_type: str | None = None,
        channel_id: int | None = None,
        enabled_only: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[NotificationRuleDetailResponse]:
        """List notification rules.

        Args:
            event_type: Filter by event type.
            channel_id: Filter by channel ID.
            enabled_only: Only return enabled rules.
            limit: Maximum results.
            offset: Number to skip.

        Returns:
            List of NotificationRuleDetailResponse.
        """
        rules = self.notification_repo.list_rules(
            event_type=event_type,
            channel_id=channel_id,
            enabled_only=enabled_only,
            limit=limit,
            offset=offset,
        )

        return [self._rule_to_detail_response(r) for r in rules]

    def create_rule(
        self,
        name: str,
        event_type: str,
        channel_id: int,
        conditions: dict[str, Any] | None = None,
        template_override: str | None = None,
    ) -> NotificationRuleResponse:
        """Create a notification rule.

        Args:
            name: Rule name.
            event_type: Event type to match.
            channel_id: Channel to send notifications to.
            conditions: Optional filtering conditions.
            template_override: Optional custom message template.

        Returns:
            Created NotificationRuleResponse.

        Raises:
            ChannelNotFoundError: If channel not found.
        """
        # Verify channel exists
        channel = self.notification_repo.get_by_id(channel_id)
        if channel is None:
            raise ChannelNotFoundError(channel_id)

        # Validate event type
        valid_event_types = ("dq_breach", "scan_failed", "scan_completed", "deprecation_deadline")
        if event_type not in valid_event_types:
            raise NotificationServiceError(f"Invalid event type: {event_type}")

        rule = self.notification_repo.create_rule(
            name=name,
            event_type=event_type,
            channel_id=channel_id,
            conditions=conditions,
            template_override=template_override,
        )

        return NotificationRuleResponse.model_validate(rule)

    def update_rule(
        self,
        rule_id: int,
        name: str | None = None,
        event_type: str | None = None,
        conditions: dict[str, Any] | None = None,
        channel_id: int | None = None,
        template_override: str | None = None,
        is_enabled: bool | None = None,
    ) -> NotificationRuleResponse:
        """Update a notification rule.

        Args:
            rule_id: ID of the rule.
            name: New name.
            event_type: New event type.
            conditions: New conditions.
            channel_id: New channel ID.
            template_override: New template.
            is_enabled: New enabled status.

        Returns:
            Updated NotificationRuleResponse.

        Raises:
            RuleNotFoundError: If rule not found.
            ChannelNotFoundError: If new channel not found.
        """
        # Verify channel exists if changing
        if channel_id is not None:
            channel = self.notification_repo.get_by_id(channel_id)
            if channel is None:
                raise ChannelNotFoundError(channel_id)

        rule = self.notification_repo.update_rule(
            rule_id=rule_id,
            name=name,
            event_type=event_type,
            conditions=conditions,
            channel_id=channel_id,
            template_override=template_override,
            is_enabled=is_enabled,
        )

        if rule is None:
            raise RuleNotFoundError(rule_id)

        return NotificationRuleResponse.model_validate(rule)

    def delete_rule(self, rule_id: int) -> bool:
        """Delete a notification rule.

        Args:
            rule_id: ID of the rule.

        Returns:
            True if deleted.

        Raises:
            RuleNotFoundError: If rule not found.
        """
        if not self.notification_repo.delete_rule(rule_id):
            raise RuleNotFoundError(rule_id)
        return True

    # =========================================================================
    # Event Handling
    # =========================================================================

    def handle_event(self, event: Event) -> list[NotificationLogResponse]:
        """Handle an event by dispatching notifications to matching rules.

        Args:
            event: Event to handle.

        Returns:
            List of NotificationLogResponse for sent notifications.
        """
        # Get matching rules
        rules = self.notification_repo.get_rules_for_event(event.event_type)
        logs: list[NotificationLogResponse] = []

        for rule in rules:
            # Check conditions
            if not self._check_conditions(rule.conditions, event):
                continue

            # Get channel and verify enabled
            channel = rule.channel
            if not channel.is_enabled:
                continue

            # Send notification
            handler = get_handler_for_channel(channel)
            result = handler.send(event, rule.template_override)

            # Log the notification
            log_entry = self.notification_repo.create_log_entry(
                event_type=event.event_type,
                event_payload=event.payload,
                status="sent" if result.success else "failed",
                rule_id=rule.id,
                channel_id=channel.id,
                error_message=result.error_message,
            )

            logs.append(NotificationLogResponse.model_validate(log_entry))

        return logs

    def register_with_event_bus(self) -> None:
        """Register this service as a global event handler.

        After calling this, all events emitted to the global event bus
        will be processed by this service.
        """
        event_bus = get_event_bus()
        event_bus.subscribe_all(self._on_event)

    def _on_event(self, event: Event) -> None:
        """Internal event handler callback."""
        self.handle_event(event)

    def _check_conditions(
        self,
        conditions: dict[str, Any] | None,
        event: Event,
    ) -> bool:
        """Check if event matches rule conditions.

        Args:
            conditions: Rule conditions dict.
            event: Event to check.

        Returns:
            True if event matches conditions or no conditions.
        """
        if not conditions:
            return True

        payload = event.payload

        # Support simple equality conditions
        for key, value in conditions.items():
            if key in payload:
                if isinstance(value, list):
                    # Value must be in list
                    if payload[key] not in value:
                        return False
                elif payload[key] != value:
                    return False

        return True

    # =========================================================================
    # Notification Log
    # =========================================================================

    def get_notification_log(
        self,
        event_type: str | None = None,
        status: str | None = None,
        channel_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[NotificationLogResponse]:
        """Get notification log entries.

        Args:
            event_type: Filter by event type.
            status: Filter by status.
            channel_id: Filter by channel ID.
            limit: Maximum results.
            offset: Number to skip.

        Returns:
            List of NotificationLogResponse.
        """
        logs = self.notification_repo.list_log_entries(
            event_type=event_type,
            status=status,
            channel_id=channel_id,
            limit=limit,
            offset=offset,
        )

        return [NotificationLogResponse.model_validate(log) for log in logs]

    # =========================================================================
    # YAML Configuration
    # =========================================================================

    def apply_from_yaml(self, yaml_path: Path) -> dict[str, Any]:
        """Apply notification configuration from YAML file.

        Creates or updates channels and rules defined in the YAML file.

        Args:
            yaml_path: Path to YAML configuration file.

        Returns:
            Summary of applied changes.

        Raises:
            FileNotFoundError: If YAML file not found.
        """
        from datacompass.core.services import load_yaml_config

        if not yaml_path.exists():
            raise FileNotFoundError(yaml_path)

        raw_config = load_yaml_config(yaml_path)
        config = YAMLSchedulingConfig.model_validate(raw_config)

        channels_created = 0
        channels_updated = 0
        rules_created = 0
        rules_updated = 0

        # Process channels first
        channel_name_to_id: dict[str, int] = {}

        for yaml_channel in config.channels:
            existing = self.notification_repo.get_channel_by_name(yaml_channel.name)

            if existing:
                self.notification_repo.update_channel(
                    channel_id=existing.id,
                    config=yaml_channel.config,
                    is_enabled=yaml_channel.enabled,
                )
                channel_name_to_id[yaml_channel.name] = existing.id
                channels_updated += 1
            else:
                channel = self.notification_repo.create_channel(
                    name=yaml_channel.name,
                    channel_type=yaml_channel.type,
                    config=yaml_channel.config,
                )
                channel_name_to_id[yaml_channel.name] = channel.id
                channels_created += 1

        # Process rules
        for yaml_rule in config.rules:
            # Resolve channel name to ID
            channel_id = channel_name_to_id.get(yaml_rule.channel)
            if channel_id is None:
                # Try to find existing channel
                existing_channel = self.notification_repo.get_channel_by_name(yaml_rule.channel)
                if existing_channel:
                    channel_id = existing_channel.id
                else:
                    continue  # Skip rule if channel not found

            # Check if rule with same name exists for this event type
            existing_rules = self.notification_repo.list_rules(
                event_type=yaml_rule.event,
                channel_id=channel_id,
            )
            existing_rule = next(
                (r for r in existing_rules if r.name == yaml_rule.name),
                None,
            )

            if existing_rule:
                self.notification_repo.update_rule(
                    rule_id=existing_rule.id,
                    conditions=yaml_rule.conditions,
                    template_override=yaml_rule.template,
                    is_enabled=yaml_rule.enabled,
                )
                rules_updated += 1
            else:
                self.notification_repo.create_rule(
                    name=yaml_rule.name,
                    event_type=yaml_rule.event,
                    channel_id=channel_id,
                    conditions=yaml_rule.conditions,
                    template_override=yaml_rule.template,
                )
                rules_created += 1

        return {
            "channels_created": channels_created,
            "channels_updated": channels_updated,
            "rules_created": rules_created,
            "rules_updated": rules_updated,
        }

    # =========================================================================
    # Helpers
    # =========================================================================

    def _rule_to_detail_response(self, rule: NotificationRule) -> NotificationRuleDetailResponse:
        """Convert NotificationRule to NotificationRuleDetailResponse."""
        return NotificationRuleDetailResponse(
            id=rule.id,
            name=rule.name,
            event_type=rule.event_type,
            conditions=rule.conditions,
            channel_id=rule.channel_id,
            template_override=rule.template_override,
            is_enabled=rule.is_enabled,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
            channel_name=rule.channel.name,
            channel_type=rule.channel.channel_type,
        )
