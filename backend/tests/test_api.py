"""Tests for the FastAPI application."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
import app.main as main_module
from app.services.source_manager import SourceManager
from app.services.item_manager import ItemManager
from app.services.pipeline_manager import PipelineManager
from app.services.job_manager import JobManager
from app.services.queue import JobQueue
from app.api import (
    set_source_manager,
    set_item_manager,
    set_pipeline_manager,
    set_overview_managers,
    set_job_manager,
    set_job_queue,
    set_queue_job_queue,
)


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def setup_managers(temp_data_dir):
    """Set up managers with temporary storage."""
    with patch("app.services.source_manager.settings") as mock_source_settings, \
         patch("app.services.item_manager.settings") as mock_item_settings, \
         patch("app.services.pipeline_manager.settings") as mock_pipeline_settings, \
         patch("app.services.job_manager.settings") as mock_job_settings:

        mock_source_settings.sources_file = temp_data_dir / "sources.json"
        mock_item_settings.items_dir = temp_data_dir / "items"
        mock_item_settings.items_dir.mkdir(parents=True, exist_ok=True)
        mock_pipeline_settings.pipelines_file = temp_data_dir / "pipelines.json"
        mock_job_settings.jobs_dir = temp_data_dir / "jobs"
        mock_job_settings.jobs_dir.mkdir(parents=True, exist_ok=True)

        source_manager = SourceManager()
        item_manager = ItemManager()
        pipeline_manager = PipelineManager()
        job_manager = JobManager(item_manager=item_manager)

        # Set managers in main module
        main_module.job_manager = job_manager
        main_module.source_manager = source_manager
        main_module.item_manager = item_manager
        main_module.pipeline_manager = pipeline_manager

        # Set managers in API modules
        set_source_manager(source_manager)
        set_item_manager(item_manager)
        set_pipeline_manager(pipeline_manager)
        set_overview_managers(source_manager, item_manager, pipeline_manager, job_manager)
        set_job_manager(job_manager)

        # Create a mock job queue for tests
        async def noop_process(job_id: str):
            pass
        job_queue = JobQueue(max_concurrent=1, process_func=noop_process)
        set_job_queue(job_queue)
        set_queue_job_queue(job_queue)

        yield {
            "source": source_manager,
            "item": item_manager,
            "pipeline": pipeline_manager,
            "job": job_manager,
            "queue": job_queue,
        }


@pytest.fixture
def client(setup_managers):
    """Create test client with managers."""
    return TestClient(app)


def test_root(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Hardcore Player"
    assert "version" in data
    assert data["status"] == "running"


def test_health(client):
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    # Note: queue is None in tests, so we just check status exists
    assert "status" in response.json()


def test_list_jobs_empty(client):
    """Test listing jobs when empty."""
    response = client.get("/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_nonexistent_job(client):
    """Test getting a nonexistent job."""
    response = client.get("/jobs/nonexistent")
    assert response.status_code == 404
