"""Tests for the FastAPI application."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_root(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "MirrorFlow"
    assert "version" in data
    assert data["status"] == "running"


def test_health(client):
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_list_jobs_empty(client):
    """Test listing jobs when empty."""
    response = client.get("/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_nonexistent_job(client):
    """Test getting a nonexistent job."""
    response = client.get("/jobs/nonexistent")
    assert response.status_code == 404
