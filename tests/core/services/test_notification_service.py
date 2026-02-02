"""Tests for NotificationService."""

import pytest
from sqlalchemy.orm import Session

from datacompass.core.events import DQBreachEvent, ScanCompletedEvent, get_event_bus, reset_event_bus
from datacompass.core.services.notification_service import (
    ChannelExistsError,
    ChannelNotFoundError,
    NotificationService,
    RuleNotFoundError,
)


class TestNotificationService:
    """Test cases for NotificationService."""

    @pytest.fixture(autouse=True)
    def reset_events(self):
        """Reset event bus before each test."""
        reset_event_bus()
        yield
        reset_event_bus()

    @pytest.fixture
    def service(self, test_db: Session) -> NotificationService:
        """Create a notification service."""
        return NotificationService(test_db)

    # =========================================================================
    # Channel Tests
    # =========================================================================

    def test_create_channel(
        self, test_db: Session, service: NotificationService
    ):
        """Test creating a notification channel."""
        channel = service.create_channel(
            name="slack-alerts",
            channel_type="slack",
            config={"webhook_url": "https://hooks.slack.com/test"},
        )
        test_db.commit()

        assert channel.id is not None
        assert channel.name == "slack-alerts"
        assert channel.channel_type == "slack"
        assert channel.config["webhook_url"] == "https://hooks.slack.com/test"
        assert channel.is_enabled is True

    def test_create_channel_duplicate_name(
        self, test_db: Session, service: NotificationService
    ):
        """Test creating channel with duplicate name raises error."""
        service.create_channel(
            name="test-channel",
            channel_type="slack",
            config={},
        )
        test_db.commit()

        with pytest.raises(ChannelExistsError):
            service.create_channel(
                name="test-channel",
                channel_type="email",
                config={},
            )

    def test_get_channel(
        self, test_db: Session, service: NotificationService
    ):
        """Test getting channel by ID."""
        created = service.create_channel(
            name="test",
            channel_type="slack",
            config={},
        )
        test_db.commit()

        channel = service.get_channel(created.id)

        assert channel.id == created.id
        assert channel.name == "test"

    def test_get_channel_not_found(
        self, test_db: Session, service: NotificationService
    ):
        """Test getting non-existent channel raises error."""
        with pytest.raises(ChannelNotFoundError):
            service.get_channel(9999)

    def test_list_channels(
        self, test_db: Session, service: NotificationService
    ):
        """Test listing channels."""
        service.create_channel(name="slack-1", channel_type="slack", config={})
        service.create_channel(name="email-1", channel_type="email", config={})
        service.create_channel(name="webhook-1", channel_type="webhook", config={})
        test_db.commit()

        channels = service.list_channels()
        assert len(channels) == 3

    def test_list_channels_filter_by_type(
        self, test_db: Session, service: NotificationService
    ):
        """Test listing channels filtered by type."""
        service.create_channel(name="slack-1", channel_type="slack", config={})
        service.create_channel(name="email-1", channel_type="email", config={})
        test_db.commit()

        slack_channels = service.list_channels(channel_type="slack")
        assert len(slack_channels) == 1
        assert slack_channels[0].channel_type == "slack"

    def test_update_channel(
        self, test_db: Session, service: NotificationService
    ):
        """Test updating a channel."""
        created = service.create_channel(
            name="test",
            channel_type="slack",
            config={"webhook_url": "https://old.url"},
        )
        test_db.commit()

        updated = service.update_channel(
            created.id,
            name="updated-name",
            config={"webhook_url": "https://new.url"},
            is_enabled=False,
        )
        test_db.commit()

        assert updated.name == "updated-name"
        assert updated.config["webhook_url"] == "https://new.url"
        assert updated.is_enabled is False

    def test_delete_channel(
        self, test_db: Session, service: NotificationService
    ):
        """Test deleting a channel."""
        created = service.create_channel(
            name="test",
            channel_type="slack",
            config={},
        )
        test_db.commit()

        result = service.delete_channel(created.id)
        test_db.commit()

        assert result is True

        with pytest.raises(ChannelNotFoundError):
            service.get_channel(created.id)

    # =========================================================================
    # Rule Tests
    # =========================================================================

    def test_create_rule(
        self, test_db: Session, service: NotificationService
    ):
        """Test creating a notification rule."""
        channel = service.create_channel(
            name="slack-alerts",
            channel_type="slack",
            config={},
        )
        test_db.commit()

        rule = service.create_rule(
            name="dq-breach-alerts",
            event_type="dq_breach",
            channel_id=channel.id,
            conditions={"priority": "critical"},
        )
        test_db.commit()

        assert rule.id is not None
        assert rule.name == "dq-breach-alerts"
        assert rule.event_type == "dq_breach"
        assert rule.channel_id == channel.id
        assert rule.conditions == {"priority": "critical"}
        assert rule.is_enabled is True

    def test_create_rule_channel_not_found(
        self, test_db: Session, service: NotificationService
    ):
        """Test creating rule with non-existent channel raises error."""
        with pytest.raises(ChannelNotFoundError):
            service.create_rule(
                name="test-rule",
                event_type="dq_breach",
                channel_id=9999,
            )

    def test_get_rule(
        self, test_db: Session, service: NotificationService
    ):
        """Test getting rule by ID."""
        channel = service.create_channel(name="test", channel_type="slack", config={})
        created = service.create_rule(
            name="test-rule",
            event_type="dq_breach",
            channel_id=channel.id,
        )
        test_db.commit()

        rule = service.get_rule(created.id)

        assert rule.id == created.id
        assert rule.name == "test-rule"

    def test_get_rule_not_found(
        self, test_db: Session, service: NotificationService
    ):
        """Test getting non-existent rule raises error."""
        with pytest.raises(RuleNotFoundError):
            service.get_rule(9999)

    def test_list_rules(
        self, test_db: Session, service: NotificationService
    ):
        """Test listing rules."""
        channel = service.create_channel(name="test", channel_type="slack", config={})
        service.create_rule(name="rule-1", event_type="dq_breach", channel_id=channel.id)
        service.create_rule(name="rule-2", event_type="scan_failed", channel_id=channel.id)
        test_db.commit()

        rules = service.list_rules()
        assert len(rules) == 2

    def test_list_rules_filter_by_event_type(
        self, test_db: Session, service: NotificationService
    ):
        """Test listing rules filtered by event type."""
        channel = service.create_channel(name="test", channel_type="slack", config={})
        service.create_rule(name="rule-1", event_type="dq_breach", channel_id=channel.id)
        service.create_rule(name="rule-2", event_type="scan_failed", channel_id=channel.id)
        test_db.commit()

        dq_rules = service.list_rules(event_type="dq_breach")
        assert len(dq_rules) == 1
        assert dq_rules[0].event_type == "dq_breach"

    def test_update_rule(
        self, test_db: Session, service: NotificationService
    ):
        """Test updating a rule."""
        channel = service.create_channel(name="test", channel_type="slack", config={})
        created = service.create_rule(
            name="test-rule",
            event_type="dq_breach",
            channel_id=channel.id,
        )
        test_db.commit()

        updated = service.update_rule(
            created.id,
            name="updated-rule",
            conditions={"priority": "high"},
            is_enabled=False,
        )
        test_db.commit()

        assert updated.name == "updated-rule"
        assert updated.conditions == {"priority": "high"}
        assert updated.is_enabled is False

    def test_delete_rule(
        self, test_db: Session, service: NotificationService
    ):
        """Test deleting a rule."""
        channel = service.create_channel(name="test", channel_type="slack", config={})
        created = service.create_rule(
            name="test-rule",
            event_type="dq_breach",
            channel_id=channel.id,
        )
        test_db.commit()

        result = service.delete_rule(created.id)
        test_db.commit()

        assert result is True

        with pytest.raises(RuleNotFoundError):
            service.get_rule(created.id)

    # =========================================================================
    # Event Handling Tests
    # =========================================================================

    def test_handle_event_matching_rule(
        self, test_db: Session, service: NotificationService
    ):
        """Test handling event with matching rule logs notification."""
        channel = service.create_channel(
            name="test",
            channel_type="webhook",
            config={"url": "https://test.example.com"},
        )
        service.create_rule(
            name="dq-alerts",
            event_type="dq_breach",
            channel_id=channel.id,
        )
        test_db.commit()

        event = DQBreachEvent.create(
            breach_id=1,
            expectation_id=1,
            object_name="test_table",
            schema_name="analytics",
            source_name="demo",
            expectation_type="row_count",
            column_name=None,
            metric_value=100.0,
            threshold_value=1000.0,
            breach_direction="low",
            deviation_percent=90.0,
            priority="critical",
            snapshot_date="2025-01-15",
        )

        service.handle_event(event)
        test_db.commit()

        # Check notification was logged
        log = service.get_notification_log()
        assert len(log) >= 1
        assert log[0].event_type == "dq_breach"

    def test_handle_event_no_matching_rule(
        self, test_db: Session, service: NotificationService
    ):
        """Test handling event with no matching rule does nothing."""
        event = ScanCompletedEvent.create(
            source_name="demo",
            source_id=1,
            objects_discovered=10,
            objects_updated=5,
            objects_deleted=0,
            columns_discovered=50,
            duration_seconds=10.5,
        )

        service.handle_event(event)
        test_db.commit()

        # Check no notification was logged (no rules)
        log = service.get_notification_log()
        assert len(log) == 0

    def test_handle_event_disabled_rule(
        self, test_db: Session, service: NotificationService
    ):
        """Test handling event with disabled rule does not send."""
        channel = service.create_channel(
            name="test",
            channel_type="slack",
            config={},
        )
        rule = service.create_rule(
            name="dq-alerts",
            event_type="dq_breach",
            channel_id=channel.id,
        )
        service.update_rule(rule.id, is_enabled=False)
        test_db.commit()

        event = DQBreachEvent.create(
            breach_id=1,
            expectation_id=1,
            object_name="test_table",
            schema_name="analytics",
            source_name="demo",
            expectation_type="row_count",
            column_name=None,
            metric_value=100.0,
            threshold_value=1000.0,
            breach_direction="low",
            deviation_percent=90.0,
            priority="critical",
            snapshot_date="2025-01-15",
        )

        service.handle_event(event)
        test_db.commit()

        # Check no notification was logged
        log = service.get_notification_log()
        assert len(log) == 0

    def test_handle_event_with_conditions(
        self, test_db: Session, service: NotificationService
    ):
        """Test handling event with conditions filters correctly."""
        channel = service.create_channel(
            name="test",
            channel_type="slack",
            config={},
        )
        # Rule only for critical priority
        service.create_rule(
            name="critical-only",
            event_type="dq_breach",
            channel_id=channel.id,
            conditions={"priority": "critical"},
        )
        test_db.commit()

        # High priority event (should not match)
        event = DQBreachEvent.create(
            breach_id=1,
            expectation_id=1,
            object_name="test_table",
            schema_name="analytics",
            source_name="demo",
            expectation_type="row_count",
            column_name=None,
            metric_value=100.0,
            threshold_value=1000.0,
            breach_direction="low",
            deviation_percent=90.0,
            priority="high",  # Not critical
            snapshot_date="2025-01-15",
        )

        service.handle_event(event)
        test_db.commit()

        # Check no notification was logged (condition not met)
        log = service.get_notification_log()
        assert len(log) == 0

    # =========================================================================
    # Notification Log Tests
    # =========================================================================

    def test_get_notification_log_filter_by_event_type(
        self, test_db: Session, service: NotificationService
    ):
        """Test filtering notification log by event type."""
        channel = service.create_channel(name="test", channel_type="webhook", config={})
        service.create_rule(name="dq-rule", event_type="dq_breach", channel_id=channel.id)
        service.create_rule(name="scan-rule", event_type="scan_completed", channel_id=channel.id)
        test_db.commit()

        # Send both types of events
        dq_event = DQBreachEvent.create(
            breach_id=1,
            expectation_id=1,
            object_name="test",
            schema_name="test",
            source_name="test",
            expectation_type="row_count",
            column_name=None,
            metric_value=100.0,
            threshold_value=1000.0,
            breach_direction="low",
            deviation_percent=90.0,
            priority="high",
            snapshot_date="2025-01-15",
        )
        scan_event = ScanCompletedEvent.create(
            source_name="demo",
            source_id=1,
            objects_discovered=10,
            objects_updated=5,
            objects_deleted=0,
            columns_discovered=50,
            duration_seconds=10.5,
        )

        service.handle_event(dq_event)
        service.handle_event(scan_event)
        test_db.commit()

        # Filter by event type
        dq_log = service.get_notification_log(event_type="dq_breach")
        assert len(dq_log) == 1
        assert dq_log[0].event_type == "dq_breach"
