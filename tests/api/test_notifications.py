"""Tests for Notifications API endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestNotificationsAPI:
    """Test cases for Notifications API."""

    # =========================================================================
    # Channel CRUD Tests
    # =========================================================================

    def test_list_channels_empty(self, client: TestClient):
        """Test listing channels when none exist."""
        response = client.get("/api/v1/notifications/channels")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_channel(self, client: TestClient):
        """Test creating a notification channel."""
        response = client.post(
            "/api/v1/notifications/channels",
            json={
                "name": "slack-alerts",
                "channel_type": "slack",
                "config": {"webhook_url": "https://hooks.slack.com/test"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "slack-alerts"
        assert data["channel_type"] == "slack"
        assert data["is_enabled"] is True

    def test_create_channel_duplicate_name(self, client: TestClient):
        """Test creating channel with duplicate name returns 409."""
        client.post(
            "/api/v1/notifications/channels",
            json={
                "name": "test-channel",
                "channel_type": "slack",
                "config": {},
            },
        )

        response = client.post(
            "/api/v1/notifications/channels",
            json={
                "name": "test-channel",
                "channel_type": "email",
                "config": {},
            },
        )
        assert response.status_code == 409

    def test_get_channel(self, client: TestClient):
        """Test getting a channel by ID."""
        create_response = client.post(
            "/api/v1/notifications/channels",
            json={
                "name": "test",
                "channel_type": "slack",
                "config": {},
            },
        )
        channel_id = create_response.json()["id"]

        response = client.get(f"/api/v1/notifications/channels/{channel_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "test"

    def test_get_channel_not_found(self, client: TestClient):
        """Test getting non-existent channel returns 404."""
        response = client.get("/api/v1/notifications/channels/9999")
        assert response.status_code == 404

    def test_update_channel(self, client: TestClient):
        """Test updating a channel."""
        create_response = client.post(
            "/api/v1/notifications/channels",
            json={
                "name": "test",
                "channel_type": "slack",
                "config": {"webhook_url": "https://old.url"},
            },
        )
        channel_id = create_response.json()["id"]

        response = client.patch(
            f"/api/v1/notifications/channels/{channel_id}",
            json={
                "name": "updated-name",
                "config": {"webhook_url": "https://new.url"},
                "is_enabled": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-name"
        assert data["is_enabled"] is False

    def test_delete_channel(self, client: TestClient):
        """Test deleting a channel."""
        create_response = client.post(
            "/api/v1/notifications/channels",
            json={
                "name": "test",
                "channel_type": "slack",
                "config": {},
            },
        )
        channel_id = create_response.json()["id"]

        response = client.delete(f"/api/v1/notifications/channels/{channel_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/api/v1/notifications/channels/{channel_id}")
        assert get_response.status_code == 404

    # =========================================================================
    # Rule CRUD Tests
    # =========================================================================

    def test_list_rules_empty(self, client: TestClient):
        """Test listing rules when none exist."""
        response = client.get("/api/v1/notifications/rules")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_rule(self, client: TestClient):
        """Test creating a notification rule."""
        # First create a channel
        channel_response = client.post(
            "/api/v1/notifications/channels",
            json={
                "name": "test-channel",
                "channel_type": "slack",
                "config": {},
            },
        )
        channel_id = channel_response.json()["id"]

        # Create rule
        response = client.post(
            "/api/v1/notifications/rules",
            json={
                "name": "dq-breach-alerts",
                "event_type": "dq_breach",
                "channel_id": channel_id,
                "conditions": {"priority": "critical"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "dq-breach-alerts"
        assert data["event_type"] == "dq_breach"
        assert data["is_enabled"] is True

    def test_create_rule_channel_not_found(self, client: TestClient):
        """Test creating rule with non-existent channel returns 404."""
        response = client.post(
            "/api/v1/notifications/rules",
            json={
                "name": "test-rule",
                "event_type": "dq_breach",
                "channel_id": 9999,
            },
        )
        assert response.status_code == 404

    def test_get_rule(self, client: TestClient):
        """Test getting a rule by ID."""
        channel_response = client.post(
            "/api/v1/notifications/channels",
            json={
                "name": "test-channel",
                "channel_type": "slack",
                "config": {},
            },
        )
        channel_id = channel_response.json()["id"]

        create_response = client.post(
            "/api/v1/notifications/rules",
            json={
                "name": "test-rule",
                "event_type": "dq_breach",
                "channel_id": channel_id,
            },
        )
        rule_id = create_response.json()["id"]

        response = client.get(f"/api/v1/notifications/rules/{rule_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "test-rule"

    def test_get_rule_not_found(self, client: TestClient):
        """Test getting non-existent rule returns 404."""
        response = client.get("/api/v1/notifications/rules/9999")
        assert response.status_code == 404

    def test_update_rule(self, client: TestClient):
        """Test updating a rule."""
        channel_response = client.post(
            "/api/v1/notifications/channels",
            json={
                "name": "test-channel",
                "channel_type": "slack",
                "config": {},
            },
        )
        channel_id = channel_response.json()["id"]

        create_response = client.post(
            "/api/v1/notifications/rules",
            json={
                "name": "test-rule",
                "event_type": "dq_breach",
                "channel_id": channel_id,
            },
        )
        rule_id = create_response.json()["id"]

        response = client.patch(
            f"/api/v1/notifications/rules/{rule_id}",
            json={
                "name": "updated-rule",
                "conditions": {"priority": "high"},
                "is_enabled": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-rule"
        assert data["conditions"] == {"priority": "high"}
        assert data["is_enabled"] is False

    def test_delete_rule(self, client: TestClient):
        """Test deleting a rule."""
        channel_response = client.post(
            "/api/v1/notifications/channels",
            json={
                "name": "test-channel",
                "channel_type": "slack",
                "config": {},
            },
        )
        channel_id = channel_response.json()["id"]

        create_response = client.post(
            "/api/v1/notifications/rules",
            json={
                "name": "test-rule",
                "event_type": "dq_breach",
                "channel_id": channel_id,
            },
        )
        rule_id = create_response.json()["id"]

        response = client.delete(f"/api/v1/notifications/rules/{rule_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/api/v1/notifications/rules/{rule_id}")
        assert get_response.status_code == 404

    # =========================================================================
    # Notification Log Tests
    # =========================================================================

    def test_get_notification_log_empty(self, client: TestClient):
        """Test getting notification log when empty."""
        response = client.get("/api/v1/notifications/log")
        assert response.status_code == 200
        assert response.json() == []
