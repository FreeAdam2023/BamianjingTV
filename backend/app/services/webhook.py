"""Webhook service for external integrations (n8n, etc.)."""

import asyncio
from typing import Optional, Dict, List
from datetime import datetime
import httpx
from loguru import logger

from app.models.job import Job, JobStatus


class WebhookService:
    """
    Service for sending webhook notifications.

    Integrates with n8n and other automation platforms.
    """

    def __init__(
        self,
        callback_url: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        self.callback_url = callback_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        self._registered_webhooks: Dict[str, str] = {}  # job_id -> callback_url

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def register_webhook(self, job_id: str, callback_url: str) -> None:
        """Register a webhook callback for a specific job."""
        self._registered_webhooks[job_id] = callback_url
        logger.debug(f"Registered webhook for job {job_id}: {callback_url}")

    def unregister_webhook(self, job_id: str) -> None:
        """Unregister webhook for a job."""
        self._registered_webhooks.pop(job_id, None)

    def _get_callback_url(self, job: Job) -> Optional[str]:
        """Get callback URL for a job."""
        # Check job-specific webhook first
        if job.id in self._registered_webhooks:
            return self._registered_webhooks[job.id]
        # Fall back to default
        return self.callback_url

    async def notify(
        self,
        job: Job,
        event_type: str = "status_update",
        extra_data: Optional[Dict] = None,
    ) -> bool:
        """
        Send webhook notification for a job.

        Args:
            job: Job to notify about
            event_type: Type of event (status_update, completed, failed)
            extra_data: Additional data to include

        Returns:
            True if notification sent successfully
        """
        callback_url = self._get_callback_url(job)
        if not callback_url:
            return False

        payload = {
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            "job": {
                "id": job.id,
                "url": job.url,
                "status": job.status.value,
                "progress": job.progress,
                "title": job.title,
                "duration": job.duration,
                "error": job.error,
                "output_video": job.output_video,
            },
        }

        if extra_data:
            payload["data"] = extra_data

        # Retry logic
        for attempt in range(self.max_retries):
            try:
                client = await self._get_client()
                response = await client.post(callback_url, json=payload)

                if response.status_code in (200, 201, 202, 204):
                    logger.debug(
                        f"Webhook sent for job {job.id}: {event_type}"
                    )
                    return True

                logger.warning(
                    f"Webhook failed for job {job.id}: "
                    f"status={response.status_code}"
                )

            except httpx.TimeoutException:
                logger.warning(
                    f"Webhook timeout for job {job.id} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
            except Exception as e:
                logger.error(f"Webhook error for job {job.id}: {e}")

            # Wait before retry
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)

        return False

    async def notify_status_change(self, job: Job) -> bool:
        """Send notification when job status changes."""
        event_type = "status_update"

        # Use specific event types for terminal states
        if job.status == JobStatus.COMPLETED:
            event_type = "job_completed"
        elif job.status == JobStatus.FAILED:
            event_type = "job_failed"

        return await self.notify(job, event_type)

    async def notify_batch_complete(
        self,
        job_ids: List[str],
        callback_url: str,
        stats: Dict,
    ) -> bool:
        """Notify when a batch of jobs is complete."""
        payload = {
            "event": "batch_completed",
            "timestamp": datetime.now().isoformat(),
            "job_ids": job_ids,
            "stats": stats,
        }

        try:
            client = await self._get_client()
            response = await client.post(callback_url, json=payload)
            return response.status_code in (200, 201, 202, 204)
        except Exception as e:
            logger.error(f"Batch webhook error: {e}")
            return False


# Global webhook service instance
webhook_service: Optional[WebhookService] = None


def get_webhook_service() -> WebhookService:
    """Get or create the global webhook service."""
    global webhook_service
    if webhook_service is None:
        webhook_service = WebhookService()
    return webhook_service


async def job_status_callback(job: Job) -> None:
    """Callback function for job status updates."""
    service = get_webhook_service()
    await service.notify_status_change(job)
