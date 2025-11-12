"""Tests for main application."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "failure-ingestion"


def test_readiness_check(client):
    """Test readiness check endpoint."""
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "failure-ingestion"
    assert "version" in data
    assert "endpoints" in data


def test_github_health(client):
    """Test GitHub webhooks health check."""
    response = client.get("/webhooks/github/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_gitlab_health(client):
    """Test GitLab webhooks health check."""
    response = client.get("/webhooks/gitlab/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
