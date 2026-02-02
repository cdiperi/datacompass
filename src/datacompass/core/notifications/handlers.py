"""Notification handlers for different channel types.

Each handler implements the logic for sending notifications through
a specific channel (email, Slack, webhook).
"""

import json
import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from datacompass.core.events import Event
from datacompass.core.models.scheduling import NotificationChannel

logger = logging.getLogger(__name__)


# =============================================================================
# Result Type
# =============================================================================


@dataclass
class NotificationResult:
    """Result of a notification send attempt."""

    success: bool
    error_message: str | None = None

    @classmethod
    def ok(cls) -> "NotificationResult":
        """Create a successful result."""
        return cls(success=True)

    @classmethod
    def fail(cls, message: str) -> "NotificationResult":
        """Create a failed result."""
        return cls(success=False, error_message=message)


# =============================================================================
# Base Handler
# =============================================================================


class BaseNotificationHandler(ABC):
    """Abstract base class for notification handlers.

    Subclasses implement the logic for sending notifications through
    a specific channel type.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the handler.

        Args:
            config: Channel-specific configuration.
        """
        self.config = config

    @abstractmethod
    def send(
        self,
        event: Event,
        template_override: str | None = None,
    ) -> NotificationResult:
        """Send a notification for an event.

        Args:
            event: Event that triggered the notification.
            template_override: Optional custom message template.

        Returns:
            NotificationResult indicating success or failure.
        """
        pass

    @abstractmethod
    def test_connection(self) -> NotificationResult:
        """Test the connection to the notification channel.

        Returns:
            NotificationResult indicating success or failure.
        """
        pass

    def format_message(
        self,
        event: Event,
        template_override: str | None = None,
    ) -> str:
        """Format the notification message.

        Args:
            event: Event to format.
            template_override: Optional custom template.

        Returns:
            Formatted message string.
        """
        if template_override:
            # Simple template substitution
            message = template_override
            for key, value in event.payload.items():
                message = message.replace(f"{{{key}}}", str(value))
            return message

        return self._default_format(event)

    def _default_format(self, event: Event) -> str:
        """Create default message format for an event.

        Args:
            event: Event to format.

        Returns:
            Default formatted message.
        """
        event_type = event.event_type
        payload = event.payload

        if event_type == "dq_breach":
            direction = "above" if payload.get("breach_direction") == "high" else "below"
            return (
                f"🚨 DQ Breach Detected\n\n"
                f"Object: {payload.get('full_name', 'Unknown')}\n"
                f"Metric: {payload.get('expectation_type', 'Unknown')}"
                f"{' (' + payload.get('column_name') + ')' if payload.get('column_name') else ''}\n"
                f"Value: {payload.get('metric_value', 'N/A')} ({direction} threshold of {payload.get('threshold_value', 'N/A')})\n"
                f"Deviation: {payload.get('deviation_percent', 0):.1f}%\n"
                f"Priority: {payload.get('priority', 'Unknown')}\n"
                f"Date: {payload.get('snapshot_date', 'Unknown')}"
            )

        elif event_type == "scan_completed":
            return (
                f"✅ Scan Completed\n\n"
                f"Source: {payload.get('source_name', 'Unknown')}\n"
                f"Objects: {payload.get('objects_discovered', 0)} discovered, "
                f"{payload.get('objects_updated', 0)} updated\n"
                f"Columns: {payload.get('columns_discovered', 0)}\n"
                f"Duration: {payload.get('duration_seconds', 0):.1f}s"
            )

        elif event_type == "scan_failed":
            return (
                f"❌ Scan Failed\n\n"
                f"Source: {payload.get('source_name', 'Unknown')}\n"
                f"Error: {payload.get('error_message', 'Unknown error')}"
            )

        elif event_type == "deprecation_deadline":
            return (
                f"⏰ Deprecation Deadline Approaching\n\n"
                f"Campaign: {payload.get('campaign_name', 'Unknown')}\n"
                f"Source: {payload.get('source_name', 'Unknown')}\n"
                f"Target Date: {payload.get('target_date', 'Unknown')}\n"
                f"Days Remaining: {payload.get('days_remaining', 'Unknown')}\n"
                f"Objects: {payload.get('object_count', 0)}"
            )

        else:
            # Generic format for unknown event types
            return (
                f"📢 {event_type}\n\n"
                f"Timestamp: {event.timestamp.isoformat()}\n"
                f"Details: {json.dumps(payload, indent=2)}"
            )


# =============================================================================
# Email Handler
# =============================================================================


class EmailHandler(BaseNotificationHandler):
    """Handler for sending email notifications via SMTP."""

    def send(
        self,
        event: Event,
        template_override: str | None = None,
    ) -> NotificationResult:
        """Send an email notification.

        Args:
            event: Event that triggered the notification.
            template_override: Optional custom message template.

        Returns:
            NotificationResult indicating success or failure.
        """
        try:
            smtp_host = self.config.get("smtp_host")
            smtp_port = self.config.get("smtp_port", 587)
            smtp_user = self.config.get("smtp_user")
            smtp_password = self.config.get("smtp_password")
            from_address = self.config.get("from_address")
            to_addresses = self.config.get("to_addresses", [])
            use_tls = self.config.get("use_tls", True)

            if not smtp_host or not from_address or not to_addresses:
                return NotificationResult.fail("Missing required email configuration")

            # Create message
            message = self.format_message(event, template_override)
            subject = self._get_subject(event)

            msg = MIMEMultipart()
            msg["From"] = from_address
            msg["To"] = ", ".join(to_addresses)
            msg["Subject"] = subject
            msg.attach(MIMEText(message, "plain"))

            # Send email
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if use_tls:
                    server.starttls()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(from_address, to_addresses, msg.as_string())

            logger.info(f"Email sent successfully for event {event.event_type}")
            return NotificationResult.ok()

        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {e}"
            logger.error(error_msg)
            return NotificationResult.fail(error_msg)
        except Exception as e:
            error_msg = f"Email send failed: {e}"
            logger.error(error_msg)
            return NotificationResult.fail(error_msg)

    def test_connection(self) -> NotificationResult:
        """Test SMTP connection.

        Returns:
            NotificationResult indicating success or failure.
        """
        try:
            smtp_host = self.config.get("smtp_host")
            smtp_port = self.config.get("smtp_port", 587)
            smtp_user = self.config.get("smtp_user")
            smtp_password = self.config.get("smtp_password")
            use_tls = self.config.get("use_tls", True)

            if not smtp_host:
                return NotificationResult.fail("Missing SMTP host configuration")

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                if use_tls:
                    server.starttls()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)

            return NotificationResult.ok()

        except smtplib.SMTPException as e:
            return NotificationResult.fail(f"SMTP connection test failed: {e}")
        except Exception as e:
            return NotificationResult.fail(f"Connection test failed: {e}")

    def _get_subject(self, event: Event) -> str:
        """Generate email subject from event.

        Args:
            event: Event to get subject for.

        Returns:
            Email subject line.
        """
        event_type = event.event_type
        payload = event.payload

        if event_type == "dq_breach":
            return f"[Data Compass] DQ Breach: {payload.get('full_name', 'Unknown')}"
        elif event_type == "scan_completed":
            return f"[Data Compass] Scan Completed: {payload.get('source_name', 'Unknown')}"
        elif event_type == "scan_failed":
            return f"[Data Compass] Scan Failed: {payload.get('source_name', 'Unknown')}"
        elif event_type == "deprecation_deadline":
            return f"[Data Compass] Deprecation Deadline: {payload.get('campaign_name', 'Unknown')}"
        else:
            return f"[Data Compass] {event_type}"


# =============================================================================
# Slack Handler
# =============================================================================


class SlackHandler(BaseNotificationHandler):
    """Handler for sending Slack notifications via webhook."""

    def send(
        self,
        event: Event,
        template_override: str | None = None,
    ) -> NotificationResult:
        """Send a Slack notification.

        Args:
            event: Event that triggered the notification.
            template_override: Optional custom message template.

        Returns:
            NotificationResult indicating success or failure.
        """
        try:
            webhook_url = self.config.get("webhook_url")
            if not webhook_url:
                return NotificationResult.fail("Missing Slack webhook URL")

            message = self.format_message(event, template_override)

            # Build Slack payload
            slack_payload: dict[str, Any] = {"text": message}

            if self.config.get("channel"):
                slack_payload["channel"] = self.config["channel"]
            if self.config.get("username"):
                slack_payload["username"] = self.config["username"]
            if self.config.get("icon_emoji"):
                slack_payload["icon_emoji"] = self.config["icon_emoji"]

            # Send to Slack
            data = json.dumps(slack_payload).encode("utf-8")
            request = Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )

            with urlopen(request, timeout=30) as response:
                if response.status != 200:
                    return NotificationResult.fail(
                        f"Slack API returned status {response.status}"
                    )

            logger.info(f"Slack notification sent successfully for event {event.event_type}")
            return NotificationResult.ok()

        except HTTPError as e:
            error_msg = f"Slack API error: {e.code} {e.reason}"
            logger.error(error_msg)
            return NotificationResult.fail(error_msg)
        except URLError as e:
            error_msg = f"Slack connection error: {e.reason}"
            logger.error(error_msg)
            return NotificationResult.fail(error_msg)
        except Exception as e:
            error_msg = f"Slack notification failed: {e}"
            logger.error(error_msg)
            return NotificationResult.fail(error_msg)

    def test_connection(self) -> NotificationResult:
        """Test Slack webhook connection.

        Returns:
            NotificationResult indicating success or failure.
        """
        try:
            webhook_url = self.config.get("webhook_url")
            if not webhook_url:
                return NotificationResult.fail("Missing Slack webhook URL")

            # Send a test message
            test_payload = {"text": "🔔 Data Compass notification test"}
            data = json.dumps(test_payload).encode("utf-8")
            request = Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )

            with urlopen(request, timeout=10) as response:
                if response.status != 200:
                    return NotificationResult.fail(
                        f"Slack API returned status {response.status}"
                    )

            return NotificationResult.ok()

        except HTTPError as e:
            return NotificationResult.fail(f"Slack webhook test failed: {e.code}")
        except URLError as e:
            return NotificationResult.fail(f"Slack connection test failed: {e.reason}")
        except Exception as e:
            return NotificationResult.fail(f"Connection test failed: {e}")


# =============================================================================
# Webhook Handler
# =============================================================================


class WebhookHandler(BaseNotificationHandler):
    """Handler for sending notifications to generic webhooks."""

    def send(
        self,
        event: Event,
        template_override: str | None = None,
    ) -> NotificationResult:
        """Send a webhook notification.

        Args:
            event: Event that triggered the notification.
            template_override: Optional custom message template.

        Returns:
            NotificationResult indicating success or failure.
        """
        try:
            url = self.config.get("url")
            if not url:
                return NotificationResult.fail("Missing webhook URL")

            method = self.config.get("method", "POST")
            headers = self.config.get("headers", {})
            timeout = self.config.get("timeout_seconds", 30)

            # Build payload
            payload = {
                "event": event.to_dict(),
                "message": self.format_message(event, template_override),
            }

            # Merge default headers
            request_headers = {
                "Content-Type": "application/json",
                **headers,
            }

            data = json.dumps(payload).encode("utf-8")
            request = Request(
                url,
                data=data if method in ("POST", "PUT", "PATCH") else None,
                headers=request_headers,
                method=method,
            )

            with urlopen(request, timeout=timeout) as response:
                if response.status >= 400:
                    return NotificationResult.fail(
                        f"Webhook returned status {response.status}"
                    )

            logger.info(f"Webhook notification sent successfully for event {event.event_type}")
            return NotificationResult.ok()

        except HTTPError as e:
            error_msg = f"Webhook HTTP error: {e.code} {e.reason}"
            logger.error(error_msg)
            return NotificationResult.fail(error_msg)
        except URLError as e:
            error_msg = f"Webhook connection error: {e.reason}"
            logger.error(error_msg)
            return NotificationResult.fail(error_msg)
        except Exception as e:
            error_msg = f"Webhook notification failed: {e}"
            logger.error(error_msg)
            return NotificationResult.fail(error_msg)

    def test_connection(self) -> NotificationResult:
        """Test webhook connection.

        Note: This sends a HEAD request to check connectivity without
        triggering any action on the webhook endpoint.

        Returns:
            NotificationResult indicating success or failure.
        """
        try:
            url = self.config.get("url")
            if not url:
                return NotificationResult.fail("Missing webhook URL")

            timeout = self.config.get("timeout_seconds", 30)
            headers = self.config.get("headers", {})

            # Try HEAD request first
            request = Request(
                url,
                headers=headers,
                method="HEAD",
            )

            try:
                with urlopen(request, timeout=min(timeout, 10)) as response:
                    if response.status < 400:
                        return NotificationResult.ok()
                    return NotificationResult.fail(f"Webhook returned status {response.status}")
            except HTTPError as e:
                # Some webhooks don't support HEAD, try GET
                if e.code == 405:  # Method Not Allowed
                    request = Request(url, headers=headers, method="GET")
                    with urlopen(request, timeout=min(timeout, 10)) as response:
                        if response.status < 400:
                            return NotificationResult.ok()
                raise

        except HTTPError as e:
            return NotificationResult.fail(f"Webhook test failed: {e.code}")
        except URLError as e:
            return NotificationResult.fail(f"Webhook connection test failed: {e.reason}")
        except Exception as e:
            return NotificationResult.fail(f"Connection test failed: {e}")


# =============================================================================
# Handler Factory
# =============================================================================


def get_handler_for_channel(channel: NotificationChannel) -> BaseNotificationHandler:
    """Get the appropriate handler for a notification channel.

    Args:
        channel: NotificationChannel instance.

    Returns:
        Handler instance for the channel type.

    Raises:
        ValueError: If channel type is not supported.
    """
    handlers = {
        "email": EmailHandler,
        "slack": SlackHandler,
        "webhook": WebhookHandler,
    }

    handler_class = handlers.get(channel.channel_type)
    if handler_class is None:
        raise ValueError(f"Unsupported channel type: {channel.channel_type}")

    return handler_class(channel.config)
