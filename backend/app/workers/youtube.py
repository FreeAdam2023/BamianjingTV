"""YouTube upload worker using YouTube Data API v3."""

import os
import pickle
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timedelta
from loguru import logger

from app.config import settings


class YouTubeUploadError(Exception):
    """YouTube upload error."""
    pass


class YouTubeWorker:
    """Worker for uploading videos to YouTube."""

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

    def __init__(self):
        self.credentials_file = Path(settings.youtube_credentials_file)
        self.token_file = Path(settings.youtube_token_file)
        self.service = None

    def _get_authenticated_service(self):
        """Get authenticated YouTube API service."""
        if self.service is not None:
            return self.service

        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        credentials = None

        # Load existing token
        if self.token_file.exists():
            with open(self.token_file, "rb") as f:
                credentials = pickle.load(f)

        # Refresh or get new credentials
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}")
                credentials = None

        if not credentials or not credentials.valid:
            if not self.credentials_file.exists():
                raise YouTubeUploadError(
                    f"YouTube credentials file not found: {self.credentials_file}\n"
                    "Please download OAuth 2.0 credentials from Google Cloud Console"
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_file),
                self.SCOPES,
            )
            credentials = flow.run_local_server(port=0)

            # Save token
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_file, "wb") as f:
                pickle.dump(credentials, f)

        self.service = build("youtube", "v3", credentials=credentials)
        return self.service

    async def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str] = None,
        category_id: str = "22",  # People & Blogs
        privacy_status: str = "private",
        thumbnail_path: Optional[Path] = None,
        publish_at: Optional[datetime] = None,
        default_language: str = "zh",
        made_for_kids: bool = False,
    ) -> dict:
        """
        Upload a video to YouTube.

        Args:
            video_path: Path to video file
            title: Video title (max 100 chars)
            description: Video description (max 5000 chars)
            tags: List of tags
            category_id: YouTube category ID
            privacy_status: private, public, or unlisted
            thumbnail_path: Custom thumbnail image
            publish_at: Scheduled publish time (requires private status)
            default_language: Default language code
            made_for_kids: Whether video is made for kids

        Returns:
            Dict with video_id and URL
        """
        from googleapiclient.http import MediaFileUpload

        video_path = Path(video_path)
        if not video_path.exists():
            raise YouTubeUploadError(f"Video file not found: {video_path}")

        service = self._get_authenticated_service()

        # Truncate title and description if needed
        title = title[:100]
        description = description[:5000]

        # Build video metadata
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": category_id,
                "defaultLanguage": default_language,
                "defaultAudioLanguage": default_language,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": made_for_kids,
            },
        }

        # Handle scheduled publishing
        if publish_at and privacy_status == "private":
            body["status"]["publishAt"] = publish_at.isoformat() + "Z"
            body["status"]["privacyStatus"] = "private"

        logger.info(f"Uploading video: {title}")

        # Upload video
        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 10,  # 10MB chunks
        )

        request = service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                logger.debug(f"Upload progress: {progress}%")

        video_id = response["id"]
        logger.info(f"Video uploaded: {video_id}")

        # Upload thumbnail if provided
        if thumbnail_path:
            await self.set_thumbnail(video_id, thumbnail_path)

        return {
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "status": privacy_status,
            "publish_at": publish_at.isoformat() if publish_at else None,
        }

    async def set_thumbnail(
        self,
        video_id: str,
        thumbnail_path: Path,
    ) -> bool:
        """
        Set custom thumbnail for a video.

        Args:
            video_id: YouTube video ID
            thumbnail_path: Path to thumbnail image

        Returns:
            True if successful
        """
        from googleapiclient.http import MediaFileUpload

        thumbnail_path = Path(thumbnail_path)
        if not thumbnail_path.exists():
            logger.warning(f"Thumbnail not found: {thumbnail_path}")
            return False

        service = self._get_authenticated_service()

        media = MediaFileUpload(
            str(thumbnail_path),
            mimetype="image/jpeg" if thumbnail_path.suffix.lower() in [".jpg", ".jpeg"] else "image/png",
        )

        try:
            service.thumbnails().set(
                videoId=video_id,
                media_body=media,
            ).execute()

            logger.info(f"Thumbnail set for video: {video_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to set thumbnail: {e}")
            return False

    async def update_video(
        self,
        video_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        privacy_status: Optional[str] = None,
    ) -> dict:
        """
        Update video metadata.

        Args:
            video_id: YouTube video ID
            title: New title
            description: New description
            tags: New tags
            privacy_status: New privacy status

        Returns:
            Updated video info
        """
        service = self._get_authenticated_service()

        # Get current video info
        current = service.videos().list(
            part="snippet,status",
            id=video_id,
        ).execute()

        if not current.get("items"):
            raise YouTubeUploadError(f"Video not found: {video_id}")

        video = current["items"][0]

        # Update fields
        if title:
            video["snippet"]["title"] = title[:100]
        if description:
            video["snippet"]["description"] = description[:5000]
        if tags:
            video["snippet"]["tags"] = tags
        if privacy_status:
            video["status"]["privacyStatus"] = privacy_status

        # Update video
        response = service.videos().update(
            part="snippet,status",
            body=video,
        ).execute()

        logger.info(f"Video updated: {video_id}")
        return {
            "video_id": response["id"],
            "title": response["snippet"]["title"],
            "status": response["status"]["privacyStatus"],
        }

    async def get_upload_quota(self) -> dict:
        """
        Get remaining upload quota.

        Returns:
            Dict with quota information
        """
        service = self._get_authenticated_service()

        # Get channel info to verify authentication
        response = service.channels().list(
            part="snippet,statistics",
            mine=True,
        ).execute()

        if not response.get("items"):
            raise YouTubeUploadError("No channel found")

        channel = response["items"][0]

        return {
            "channel_id": channel["id"],
            "channel_title": channel["snippet"]["title"],
            "subscriber_count": channel["statistics"].get("subscriberCount"),
            "video_count": channel["statistics"].get("videoCount"),
        }

    def calculate_publish_time(
        self,
        delay_hours: int = 0,
        preferred_hour: int = 18,  # 6 PM
        timezone_offset: int = 8,  # UTC+8 for China
    ) -> datetime:
        """
        Calculate optimal publish time.

        Args:
            delay_hours: Minimum hours to delay
            preferred_hour: Preferred hour of day (local time)
            timezone_offset: Hours offset from UTC

        Returns:
            Datetime for scheduled publishing
        """
        now = datetime.utcnow()
        target = now + timedelta(hours=delay_hours)

        # Adjust to preferred hour
        local_hour = (target.hour + timezone_offset) % 24

        if local_hour < preferred_hour:
            hours_to_add = preferred_hour - local_hour
        else:
            hours_to_add = 24 - local_hour + preferred_hour

        if hours_to_add < delay_hours:
            hours_to_add += 24

        return now + timedelta(hours=hours_to_add)
