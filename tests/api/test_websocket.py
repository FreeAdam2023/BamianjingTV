"""Tests for WebSocket real-time updates API."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

from app.api.websocket import ConnectionManager, get_connection_manager


class TestConnectionManager:
    """Tests for the WebSocket ConnectionManager."""

    def test_init(self):
        """Test ConnectionManager initialization."""
        manager = ConnectionManager()
        assert len(manager.active_connections) == 0
        assert len(manager.job_subscriptions) == 0
        assert len(manager.source_subscriptions) == 0
        assert "jobs" in manager.topic_subscriptions
        assert "items" in manager.topic_subscriptions
        assert "all" in manager.topic_subscriptions

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connecting a WebSocket."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()

        await manager.connect(mock_ws)

        assert mock_ws in manager.active_connections
        mock_ws.accept.assert_called_once()

    def test_disconnect(self):
        """Test disconnecting a WebSocket."""
        manager = ConnectionManager()
        mock_ws = MagicMock()

        # Add to various subscriptions
        manager.active_connections.add(mock_ws)
        manager.job_subscriptions["job1"] = {mock_ws}
        manager.source_subscriptions["source1"] = {mock_ws}
        manager.topic_subscriptions["jobs"].add(mock_ws)

        # Disconnect
        manager.disconnect(mock_ws)

        assert mock_ws not in manager.active_connections
        assert "job1" not in manager.job_subscriptions
        assert "source1" not in manager.source_subscriptions
        assert mock_ws not in manager.topic_subscriptions["jobs"]

    def test_subscribe_job(self):
        """Test subscribing to a specific job."""
        manager = ConnectionManager()
        mock_ws = MagicMock()

        manager.subscribe_job(mock_ws, "job123")

        assert "job123" in manager.job_subscriptions
        assert mock_ws in manager.job_subscriptions["job123"]

    def test_subscribe_source(self):
        """Test subscribing to a specific source."""
        manager = ConnectionManager()
        mock_ws = MagicMock()

        manager.subscribe_source(mock_ws, "source456")

        assert "source456" in manager.source_subscriptions
        assert mock_ws in manager.source_subscriptions["source456"]

    def test_subscribe_topic(self):
        """Test subscribing to a topic."""
        manager = ConnectionManager()
        mock_ws = MagicMock()

        manager.subscribe_topic(mock_ws, "jobs")

        assert mock_ws in manager.topic_subscriptions["jobs"]

    def test_subscribe_invalid_topic(self):
        """Test subscribing to an invalid topic does nothing."""
        manager = ConnectionManager()
        mock_ws = MagicMock()

        manager.subscribe_topic(mock_ws, "invalid_topic")

        assert "invalid_topic" not in manager.topic_subscriptions

    @pytest.mark.asyncio
    async def test_send_personal(self):
        """Test sending a personal message."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        manager.active_connections.add(mock_ws)

        message = {"type": "test", "data": "hello"}
        await manager.send_personal(mock_ws, message)

        mock_ws.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_send_personal_handles_error(self):
        """Test sending handles WebSocket errors."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        mock_ws.send_json.side_effect = Exception("Connection closed")
        manager.active_connections.add(mock_ws)

        await manager.send_personal(mock_ws, {"test": "data"})

        # Should disconnect on error
        assert mock_ws not in manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast(self):
        """Test broadcasting to all connections."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        manager.active_connections.add(ws1)
        manager.active_connections.add(ws2)

        message = {"type": "broadcast", "data": "hello all"}
        await manager.broadcast(message)

        ws1.send_json.assert_called_once_with(message)
        ws2.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_job_update(self):
        """Test broadcasting job update to subscribers."""
        manager = ConnectionManager()

        # Create mock WebSockets
        job_subscriber = AsyncMock()
        topic_subscriber = AsyncMock()
        all_subscriber = AsyncMock()

        # Subscribe
        manager.subscribe_job(job_subscriber, "job123")
        manager.subscribe_topic(topic_subscriber, "jobs")
        manager.subscribe_topic(all_subscriber, "all")

        # Broadcast
        await manager.broadcast_job_update("job123", {
            "status": "processing",
            "progress": 0.5,
        })

        # All three should receive the update
        assert job_subscriber.send_json.called
        assert topic_subscriber.send_json.called
        assert all_subscriber.send_json.called

        # Check message structure
        call_args = job_subscriber.send_json.call_args[0][0]
        assert call_args["type"] == "job_update"
        assert call_args["job_id"] == "job123"
        assert call_args["data"]["status"] == "processing"

    @pytest.mark.asyncio
    async def test_broadcast_item_update(self):
        """Test broadcasting item update to subscribers."""
        manager = ConnectionManager()

        source_subscriber = AsyncMock()
        topic_subscriber = AsyncMock()

        manager.subscribe_source(source_subscriber, "yt_lex")
        manager.subscribe_topic(topic_subscriber, "items")

        await manager.broadcast_item_update("item123", "yt_lex", {
            "status": "processing",
        })

        assert source_subscriber.send_json.called
        assert topic_subscriber.send_json.called

        call_args = source_subscriber.send_json.call_args[0][0]
        assert call_args["type"] == "item_update"
        assert call_args["item_id"] == "item123"
        assert call_args["source_id"] == "yt_lex"

    @pytest.mark.asyncio
    async def test_broadcast_source_update(self):
        """Test broadcasting source update to subscribers."""
        manager = ConnectionManager()

        source_subscriber = AsyncMock()
        manager.subscribe_source(source_subscriber, "yt_lex")

        await manager.broadcast_source_update("yt_lex", {
            "last_fetched_at": "2024-01-01T00:00:00",
        })

        assert source_subscriber.send_json.called
        call_args = source_subscriber.send_json.call_args[0][0]
        assert call_args["type"] == "source_update"
        assert call_args["source_id"] == "yt_lex"

    @pytest.mark.asyncio
    async def test_broadcast_overview_update(self):
        """Test broadcasting overview update."""
        manager = ConnectionManager()

        overview_subscriber = AsyncMock()
        manager.subscribe_topic(overview_subscriber, "overview")

        await manager.broadcast_overview_update({
            "total_sources": 5,
            "total_items": 100,
        })

        assert overview_subscriber.send_json.called
        call_args = overview_subscriber.send_json.call_args[0][0]
        assert call_args["type"] == "overview_update"
        assert call_args["data"]["total_sources"] == 5

    def test_get_stats(self):
        """Test getting connection statistics."""
        manager = ConnectionManager()

        # Add some connections and subscriptions
        ws1 = MagicMock()
        ws2 = MagicMock()
        manager.active_connections.add(ws1)
        manager.active_connections.add(ws2)
        manager.job_subscriptions["job1"] = {ws1}
        manager.source_subscriptions["source1"] = {ws1, ws2}
        manager.topic_subscriptions["jobs"].add(ws1)

        stats = manager.get_stats()

        assert stats["total_connections"] == 2
        assert stats["job_subscriptions"] == 1
        assert stats["source_subscriptions"] == 1
        assert stats["topic_subscriptions"]["jobs"] == 1


class TestGlobalConnectionManager:
    """Tests for the global connection manager."""

    def test_get_connection_manager(self):
        """Test getting the global connection manager."""
        manager = get_connection_manager()
        assert isinstance(manager, ConnectionManager)

    def test_get_connection_manager_singleton(self):
        """Test that get_connection_manager returns the same instance."""
        manager1 = get_connection_manager()
        manager2 = get_connection_manager()
        assert manager1 is manager2


class TestWebSocketCleanup:
    """Tests for WebSocket cleanup on disconnect."""

    def test_cleanup_removes_from_all_subscriptions(self):
        """Test that disconnect cleans up all subscriptions."""
        manager = ConnectionManager()
        mock_ws = MagicMock()

        # Subscribe to everything
        manager.active_connections.add(mock_ws)
        manager.subscribe_job(mock_ws, "job1")
        manager.subscribe_job(mock_ws, "job2")
        manager.subscribe_source(mock_ws, "source1")
        manager.subscribe_topic(mock_ws, "jobs")
        manager.subscribe_topic(mock_ws, "items")
        manager.subscribe_topic(mock_ws, "all")

        # Verify subscriptions
        assert mock_ws in manager.job_subscriptions["job1"]
        assert mock_ws in manager.job_subscriptions["job2"]
        assert mock_ws in manager.source_subscriptions["source1"]

        # Disconnect
        manager.disconnect(mock_ws)

        # Verify cleanup
        assert mock_ws not in manager.active_connections
        assert "job1" not in manager.job_subscriptions
        assert "job2" not in manager.job_subscriptions
        assert "source1" not in manager.source_subscriptions
        assert mock_ws not in manager.topic_subscriptions["jobs"]
        assert mock_ws not in manager.topic_subscriptions["items"]
        assert mock_ws not in manager.topic_subscriptions["all"]

    @pytest.mark.asyncio
    async def test_broadcast_handles_disconnect(self):
        """Test that broadcast handles disconnected clients."""
        manager = ConnectionManager()

        # One good, one bad
        good_ws = AsyncMock()
        bad_ws = AsyncMock()
        bad_ws.send_json.side_effect = Exception("Disconnected")

        manager.active_connections.add(good_ws)
        manager.active_connections.add(bad_ws)

        # Broadcast
        await manager.broadcast({"test": "data"})

        # Good one should still be connected
        assert good_ws in manager.active_connections
        # Bad one should be removed
        assert bad_ws not in manager.active_connections
