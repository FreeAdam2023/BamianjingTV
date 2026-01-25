"""WebSocket API for real-time status updates.

Provides WebSocket endpoints for live dashboard visualization
and job status monitoring.
"""

import asyncio
import json
from typing import Dict, Set, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger


router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        # All active connections (for broadcast)
        self.active_connections: Set[WebSocket] = set()

        # Job-specific subscriptions: job_id -> set of websockets
        self.job_subscriptions: Dict[str, Set[WebSocket]] = {}

        # Source-specific subscriptions: source_id -> set of websockets
        self.source_subscriptions: Dict[str, Set[WebSocket]] = {}

        # Topic subscriptions: topic -> set of websockets
        # Topics: "jobs", "items", "sources", "overview"
        self.topic_subscriptions: Dict[str, Set[WebSocket]] = {
            "jobs": set(),
            "items": set(),
            "sources": set(),
            "overview": set(),
            "all": set(),
        }

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.debug(f"WebSocket connected: {len(self.active_connections)} total")

    def disconnect(self, websocket: WebSocket):
        """Remove a disconnected WebSocket."""
        self.active_connections.discard(websocket)

        # Remove from all job subscriptions
        for job_id, sockets in list(self.job_subscriptions.items()):
            sockets.discard(websocket)
            if not sockets:
                del self.job_subscriptions[job_id]

        # Remove from all source subscriptions
        for source_id, sockets in list(self.source_subscriptions.items()):
            sockets.discard(websocket)
            if not sockets:
                del self.source_subscriptions[source_id]

        # Remove from all topic subscriptions
        for topic, sockets in self.topic_subscriptions.items():
            sockets.discard(websocket)

        logger.debug(f"WebSocket disconnected: {len(self.active_connections)} remaining")

    def subscribe_job(self, websocket: WebSocket, job_id: str):
        """Subscribe to updates for a specific job."""
        if job_id not in self.job_subscriptions:
            self.job_subscriptions[job_id] = set()
        self.job_subscriptions[job_id].add(websocket)
        logger.debug(f"WebSocket subscribed to job {job_id}")

    def subscribe_source(self, websocket: WebSocket, source_id: str):
        """Subscribe to updates for a specific source."""
        if source_id not in self.source_subscriptions:
            self.source_subscriptions[source_id] = set()
        self.source_subscriptions[source_id].add(websocket)
        logger.debug(f"WebSocket subscribed to source {source_id}")

    def subscribe_topic(self, websocket: WebSocket, topic: str):
        """Subscribe to a topic (jobs, items, sources, overview, all)."""
        if topic in self.topic_subscriptions:
            self.topic_subscriptions[topic].add(websocket)
            logger.debug(f"WebSocket subscribed to topic {topic}")

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send a message to a specific WebSocket."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send WebSocket message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        disconnected = []
        for websocket in self.active_connections:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)

        for ws in disconnected:
            self.disconnect(ws)

    async def broadcast_job_update(self, job_id: str, data: dict):
        """Broadcast a job status update to subscribers."""
        message = {
            "type": "job_update",
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        # Send to job-specific subscribers
        if job_id in self.job_subscriptions:
            disconnected = []
            for websocket in self.job_subscriptions[job_id]:
                try:
                    await websocket.send_json(message)
                except Exception:
                    disconnected.append(websocket)

            for ws in disconnected:
                self.disconnect(ws)

        # Send to topic subscribers
        await self._broadcast_to_topic("jobs", message)
        await self._broadcast_to_topic("all", message)

    async def broadcast_item_update(self, item_id: str, source_id: str, data: dict):
        """Broadcast an item status update to subscribers."""
        message = {
            "type": "item_update",
            "item_id": item_id,
            "source_id": source_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        # Send to source-specific subscribers
        if source_id in self.source_subscriptions:
            disconnected = []
            for websocket in self.source_subscriptions[source_id]:
                try:
                    await websocket.send_json(message)
                except Exception:
                    disconnected.append(websocket)

            for ws in disconnected:
                self.disconnect(ws)

        # Send to topic subscribers
        await self._broadcast_to_topic("items", message)
        await self._broadcast_to_topic("all", message)

    async def broadcast_source_update(self, source_id: str, data: dict):
        """Broadcast a source update to subscribers."""
        message = {
            "type": "source_update",
            "source_id": source_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        # Send to source-specific subscribers
        if source_id in self.source_subscriptions:
            disconnected = []
            for websocket in self.source_subscriptions[source_id]:
                try:
                    await websocket.send_json(message)
                except Exception:
                    disconnected.append(websocket)

            for ws in disconnected:
                self.disconnect(ws)

        # Send to topic subscribers
        await self._broadcast_to_topic("sources", message)
        await self._broadcast_to_topic("all", message)

    async def broadcast_overview_update(self, data: dict):
        """Broadcast overview statistics update."""
        message = {
            "type": "overview_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        await self._broadcast_to_topic("overview", message)
        await self._broadcast_to_topic("all", message)

    async def _broadcast_to_topic(self, topic: str, message: dict):
        """Broadcast to all subscribers of a topic."""
        if topic not in self.topic_subscriptions:
            return

        disconnected = []
        for websocket in self.topic_subscriptions[topic]:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)

        for ws in disconnected:
            self.disconnect(ws)

    def get_stats(self) -> dict:
        """Get WebSocket connection statistics."""
        return {
            "total_connections": len(self.active_connections),
            "job_subscriptions": len(self.job_subscriptions),
            "source_subscriptions": len(self.source_subscriptions),
            "topic_subscriptions": {
                topic: len(sockets)
                for topic, sockets in self.topic_subscriptions.items()
            },
        }


# Global connection manager instance
manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    return manager


# ============ WebSocket Endpoints ============

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time updates.

    Clients can subscribe to specific topics or resources by sending:

    ```json
    {"action": "subscribe", "topic": "all"}
    {"action": "subscribe", "topic": "jobs"}
    {"action": "subscribe", "topic": "items"}
    {"action": "subscribe", "job_id": "abc123"}
    {"action": "subscribe", "source_id": "yt_lex"}
    {"action": "unsubscribe", "topic": "jobs"}
    {"action": "ping"}
    ```

    Server sends updates in the format:

    ```json
    {
        "type": "job_update|item_update|source_update|overview_update",
        "timestamp": "2024-01-01T00:00:00",
        "data": {...}
    }
    ```
    """
    await manager.connect(websocket)

    # Send welcome message
    await manager.send_personal(websocket, {
        "type": "connected",
        "message": "WebSocket connected to Hardcore Player",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    try:
        while True:
            # Receive and parse message
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                action = message.get("action", "")

                if action == "subscribe":
                    # Handle subscription requests
                    if "topic" in message:
                        manager.subscribe_topic(websocket, message["topic"])
                        await manager.send_personal(websocket, {
                            "type": "subscribed",
                            "topic": message["topic"],
                        })
                    elif "job_id" in message:
                        manager.subscribe_job(websocket, message["job_id"])
                        await manager.send_personal(websocket, {
                            "type": "subscribed",
                            "job_id": message["job_id"],
                        })
                    elif "source_id" in message:
                        manager.subscribe_source(websocket, message["source_id"])
                        await manager.send_personal(websocket, {
                            "type": "subscribed",
                            "source_id": message["source_id"],
                        })

                elif action == "unsubscribe":
                    # Handle unsubscribe (remove from topic)
                    if "topic" in message:
                        topic = message["topic"]
                        if topic in manager.topic_subscriptions:
                            manager.topic_subscriptions[topic].discard(websocket)
                        await manager.send_personal(websocket, {
                            "type": "unsubscribed",
                            "topic": topic,
                        })

                elif action == "ping":
                    # Respond to ping with pong
                    await manager.send_personal(websocket, {
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                elif action == "stats":
                    # Return connection statistics
                    await manager.send_personal(websocket, {
                        "type": "stats",
                        "data": manager.get_stats(),
                    })

            except json.JSONDecodeError:
                await manager.send_personal(websocket, {
                    "type": "error",
                    "message": "Invalid JSON",
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.websocket("/ws/jobs/{job_id}")
async def job_websocket(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for a specific job's updates.

    Automatically subscribes to the specified job.
    """
    await manager.connect(websocket)
    manager.subscribe_job(websocket, job_id)

    # Send subscription confirmation
    await manager.send_personal(websocket, {
        "type": "subscribed",
        "job_id": job_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    try:
        while True:
            # Just keep the connection alive
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                if message.get("action") == "ping":
                    await manager.send_personal(websocket, {
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.websocket("/ws/sources/{source_id}")
async def source_websocket(websocket: WebSocket, source_id: str):
    """WebSocket endpoint for a specific source's updates.

    Automatically subscribes to the specified source and its items.
    """
    await manager.connect(websocket)
    manager.subscribe_source(websocket, source_id)

    # Send subscription confirmation
    await manager.send_personal(websocket, {
        "type": "subscribed",
        "source_id": source_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                if message.get("action") == "ping":
                    await manager.send_personal(websocket, {
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ============ HTTP Endpoints for WebSocket Status ============

@router.get("/ws/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics."""
    return manager.get_stats()
