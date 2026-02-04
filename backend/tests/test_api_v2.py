"""Tests for the SceneMind v2 API endpoints."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.source_manager import SourceManager
from app.services.item_manager import ItemManager
from app.services.pipeline_manager import PipelineManager
from app.services.job_manager import JobManager
from app.api import (
    set_source_manager,
    set_item_manager,
    set_pipeline_manager,
    set_overview_managers,
)


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def setup_managers(temp_data_dir):
    """Set up v2 managers with temporary storage."""
    with patch("app.services.source_manager.settings") as mock_source_settings, \
         patch("app.services.item_manager.settings") as mock_item_settings, \
         patch("app.services.pipeline_manager.settings") as mock_pipeline_settings:

        mock_source_settings.sources_file = temp_data_dir / "sources.json"
        mock_item_settings.items_dir = temp_data_dir / "items"
        mock_item_settings.items_dir.mkdir(parents=True, exist_ok=True)
        mock_pipeline_settings.pipelines_file = temp_data_dir / "pipelines.json"

        source_manager = SourceManager()
        item_manager = ItemManager()
        pipeline_manager = PipelineManager()
        job_manager = JobManager(item_manager=item_manager)

        # Set managers in API modules
        set_source_manager(source_manager)
        set_item_manager(item_manager)
        set_pipeline_manager(pipeline_manager)
        set_overview_managers(source_manager, item_manager, pipeline_manager, job_manager)

        yield {
            "source": source_manager,
            "item": item_manager,
            "pipeline": pipeline_manager,
            "job": job_manager,
        }


@pytest.fixture
def client(setup_managers):
    """Create test client with managers."""
    return TestClient(app)


class TestSourcesAPI:
    """Tests for Sources API endpoints."""

    def test_list_sources_empty(self, client):
        """Test listing sources when empty."""
        response = client.get("/sources")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_source(self, client):
        """Test creating a source."""
        response = client.post("/sources", json={
            "source_id": "yt_test",
            "source_type": "youtube",
            "sub_type": "channel",
            "display_name": "Test Channel",
            "fetcher": "youtube_rss",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["source_id"] == "yt_test"
        assert data["source_type"] == "youtube"

    def test_get_source(self, client):
        """Test getting a source."""
        # Create first
        client.post("/sources", json={
            "source_id": "yt_get",
            "source_type": "youtube",
            "sub_type": "channel",
            "display_name": "Get Test",
            "fetcher": "youtube_rss",
        })

        response = client.get("/sources/yt_get")
        assert response.status_code == 200
        assert response.json()["source_id"] == "yt_get"

    def test_get_nonexistent_source(self, client):
        """Test getting a nonexistent source."""
        response = client.get("/sources/nonexistent")
        assert response.status_code == 404

    def test_update_source(self, client):
        """Test updating a source."""
        # Create first
        client.post("/sources", json={
            "source_id": "yt_update",
            "source_type": "youtube",
            "sub_type": "channel",
            "display_name": "Original",
            "fetcher": "youtube_rss",
        })

        response = client.put("/sources/yt_update", json={
            "display_name": "Updated Name",
        })

        assert response.status_code == 200
        assert response.json()["display_name"] == "Updated Name"

    def test_delete_source(self, client):
        """Test deleting a source."""
        # Create first
        client.post("/sources", json={
            "source_id": "yt_delete",
            "source_type": "youtube",
            "sub_type": "channel",
            "display_name": "Delete Me",
            "fetcher": "youtube_rss",
        })

        response = client.delete("/sources/yt_delete")
        assert response.status_code == 200

        # Verify deleted
        response = client.get("/sources/yt_delete")
        assert response.status_code == 404

    def test_list_sources_filtered(self, client):
        """Test filtering sources by type."""
        # Create YouTube source
        client.post("/sources", json={
            "source_id": "yt_filter",
            "source_type": "youtube",
            "sub_type": "channel",
            "display_name": "YouTube",
            "fetcher": "youtube_rss",
        })

        # Create RSS source
        client.post("/sources", json={
            "source_id": "rss_filter",
            "source_type": "rss",
            "sub_type": "website",
            "display_name": "RSS",
            "fetcher": "rss_fetcher",
        })

        response = client.get("/sources?source_type=youtube")
        assert response.status_code == 200
        sources = response.json()
        assert len(sources) == 1
        assert sources[0]["source_type"] == "youtube"


class TestItemsAPI:
    """Tests for Items API endpoints."""

    def test_list_items_empty(self, client):
        """Test listing items when empty."""
        response = client.get("/items")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_item(self, client):
        """Test creating an item."""
        response = client.post("/items", json={
            "source_type": "youtube",
            "source_id": "yt_test",
            "original_url": "https://youtube.com/watch?v=test123",
            "original_title": "Test Video",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["is_new"] is True
        assert data["item"]["source_type"] == "youtube"

    def test_create_duplicate_item(self, client):
        """Test creating a duplicate item returns existing."""
        # Create first
        client.post("/items", json={
            "source_type": "youtube",
            "source_id": "yt_dup",
            "original_url": "https://youtube.com/watch?v=dup123",
            "original_title": "Duplicate Video",
        })

        # Try to create again
        response = client.post("/items", json={
            "source_type": "youtube",
            "source_id": "yt_dup",
            "original_url": "https://youtube.com/watch?v=dup123",
            "original_title": "Duplicate Video",
        })

        assert response.status_code == 200
        assert response.json()["is_new"] is False

    def test_get_item(self, client):
        """Test getting an item."""
        # Create first
        response = client.post("/items", json={
            "source_type": "youtube",
            "source_id": "yt_get",
            "original_url": "https://youtube.com/watch?v=get123",
            "original_title": "Get Test",
        })
        item_id = response.json()["item"]["item_id"]

        response = client.get(f"/items/{item_id}")
        assert response.status_code == 200
        assert response.json()["item_id"] == item_id

    def test_get_nonexistent_item(self, client):
        """Test getting a nonexistent item."""
        response = client.get("/items/nonexistent")
        assert response.status_code == 404

    def test_delete_item(self, client):
        """Test deleting an item."""
        # Create first
        response = client.post("/items", json={
            "source_type": "youtube",
            "source_id": "yt_delete",
            "original_url": "https://youtube.com/watch?v=delete123",
            "original_title": "Delete Me",
        })
        item_id = response.json()["item"]["item_id"]

        response = client.delete(f"/items/{item_id}")
        assert response.status_code == 200

        # Verify deleted
        response = client.get(f"/items/{item_id}")
        assert response.status_code == 404

    def test_get_item_pipelines(self, client):
        """Test getting item pipeline statuses."""
        # Create item
        response = client.post("/items", json={
            "source_type": "youtube",
            "source_id": "yt_pipelines",
            "original_url": "https://youtube.com/watch?v=pipe123",
            "original_title": "Pipeline Test",
        })
        item_id = response.json()["item"]["item_id"]

        response = client.get(f"/items/{item_id}/pipelines")
        assert response.status_code == 200
        data = response.json()
        assert data["item_id"] == item_id
        assert "pipelines" in data


class TestPipelinesAPI:
    """Tests for Pipelines API endpoints."""

    def test_list_pipelines_has_default(self, client):
        """Test that default pipeline exists."""
        response = client.get("/pipelines")
        assert response.status_code == 200
        pipelines = response.json()
        assert any(p["pipeline_id"] == "default_zh" for p in pipelines)

    def test_get_default_pipeline(self, client):
        """Test getting the default pipeline."""
        response = client.get("/pipelines/default_zh")
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_id"] == "default_zh"
        assert data["target_language"] == "zh"

    def test_create_pipeline(self, client):
        """Test creating a pipeline."""
        response = client.post("/pipelines", json={
            "pipeline_id": "test_pipeline",
            "pipeline_type": "full_dub",
            "display_name": "Test Pipeline",
            "target": {
                "target_type": "local",
                "target_id": "output",
                "display_name": "Local Output",
            },
        })

        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_id"] == "test_pipeline"

    def test_update_pipeline(self, client):
        """Test updating a pipeline."""
        # Create first
        client.post("/pipelines", json={
            "pipeline_id": "update_pipeline",
            "pipeline_type": "full_dub",
            "display_name": "Original",
            "target": {
                "target_type": "local",
                "target_id": "output",
                "display_name": "Local",
            },
        })

        response = client.put("/pipelines/update_pipeline", json={
            "display_name": "Updated Name",
        })

        assert response.status_code == 200
        assert response.json()["display_name"] == "Updated Name"

    def test_delete_pipeline(self, client):
        """Test deleting a pipeline."""
        # Create first
        client.post("/pipelines", json={
            "pipeline_id": "delete_pipeline",
            "pipeline_type": "full_dub",
            "display_name": "Delete Me",
            "target": {
                "target_type": "local",
                "target_id": "output",
                "display_name": "Local",
            },
        })

        response = client.delete("/pipelines/delete_pipeline")
        assert response.status_code == 200

    def test_cannot_delete_default_pipeline(self, client):
        """Test that default pipeline cannot be deleted."""
        response = client.delete("/pipelines/default_zh")
        assert response.status_code == 400


class TestOverviewAPI:
    """Tests for Overview API endpoints."""

    def test_get_overview(self, client):
        """Test getting system overview."""
        response = client.get("/overview")
        assert response.status_code == 200
        data = response.json()
        assert "total_sources" in data
        assert "total_items" in data
        assert "total_pipelines" in data
        assert "by_source_type" in data

    def test_get_source_type_overview(self, client):
        """Test getting source type overview."""
        response = client.get("/overview/youtube")
        assert response.status_code == 200
        data = response.json()
        assert data["source_type"] == "youtube"
        assert "sources" in data
        assert "summary" in data

    def test_get_combined_stats(self, client):
        """Test getting combined statistics."""
        response = client.get("/overview/stats/combined")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert "items" in data
        assert "pipelines" in data
        assert "jobs" in data

    def test_get_recent_activity(self, client):
        """Test getting recent activity."""
        response = client.get("/overview/activity/recent?hours=24")
        assert response.status_code == 200
        data = response.json()
        assert data["hours"] == 24
        assert "new_items" in data
        assert "items" in data

    def test_get_health(self, client):
        """Test system health check."""
        response = client.get("/overview/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert "components" in data


class TestRootEndpoint:
    """Tests for root endpoint v2 indicator."""

    def test_root_shows_v2_features(self, client):
        """Test that root endpoint shows v2 features."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "v2" in data
        assert data["v2"]["sources"] is True
        assert data["v2"]["items"] is True
        assert data["v2"]["pipelines"] is True
        assert data["v2"]["overview"] is True
