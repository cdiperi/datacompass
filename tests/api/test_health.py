"""Tests for health endpoint."""

from fastapi.testclient import TestClient

from datacompass import __version__


def test_health_check(client: TestClient):
    """Health endpoint returns 200 with status and version."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == __version__


def test_health_check_content_type(client: TestClient):
    """Health endpoint returns JSON content type."""
    response = client.get("/health")

    assert response.headers["content-type"] == "application/json"
