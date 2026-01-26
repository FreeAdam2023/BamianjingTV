"""Channel and Publication API endpoints."""

import pickle
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import RedirectResponse
from loguru import logger
from pydantic import BaseModel

from app.models.channel import (
    Channel,
    ChannelCreate,
    ChannelStatus,
    ChannelSummary,
    ChannelType,
    ChannelUpdate,
    Publication,
    PublicationCreate,
    PublicationStatus,
    PublicationSummary,
    PublicationUpdate,
)
from app.services.channel_manager import ChannelManager
from app.config import settings

router = APIRouter(tags=["channels"])

# Singleton manager
_channel_manager: Optional[ChannelManager] = None


def _get_manager() -> ChannelManager:
    """Get or create the channel manager singleton."""
    global _channel_manager
    if _channel_manager is None:
        from pathlib import Path
        data_dir = Path(settings.data_dir)
        _channel_manager = ChannelManager(data_dir)
    return _channel_manager


# ============ Channel Endpoints ============


@router.get("/channels", response_model=List[ChannelSummary])
async def list_channels(
    type: Optional[ChannelType] = None,
    status: Optional[ChannelStatus] = None,
):
    """List all publishing channels."""
    manager = _get_manager()
    return manager.list_channels(channel_type=type, status=status)


@router.get("/channels/{channel_id}", response_model=Channel)
async def get_channel(channel_id: str):
    """Get a channel by ID."""
    manager = _get_manager()
    channel = manager.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.post("/channels", response_model=Channel)
async def create_channel(create: ChannelCreate):
    """Create a new publishing channel."""
    from loguru import logger
    manager = _get_manager()

    logger.info(f"Creating channel: {create.name} ({create.type.value})")
    channel = manager.create_channel(create)
    return channel


@router.patch("/channels/{channel_id}", response_model=Channel)
async def update_channel(channel_id: str, update: ChannelUpdate):
    """Update a channel."""
    manager = _get_manager()
    channel = manager.update_channel(channel_id, update)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: str):
    """Delete a channel."""
    manager = _get_manager()
    if not manager.delete_channel(channel_id):
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"message": "Channel deleted"}


# ============ Publication Endpoints ============


@router.get("/publications", response_model=List[PublicationSummary])
async def list_publications(
    timeline_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    status: Optional[PublicationStatus] = None,
    limit: int = Query(default=100, le=500),
):
    """List publications with optional filters."""
    manager = _get_manager()
    return manager.list_publications(
        timeline_id=timeline_id,
        channel_id=channel_id,
        status=status,
        limit=limit,
    )


@router.get("/publications/{publication_id}", response_model=Publication)
async def get_publication(publication_id: str):
    """Get a publication by ID."""
    manager = _get_manager()
    pub = manager.get_publication(publication_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    return pub


@router.post("/publications", response_model=Publication)
async def create_publication(create: PublicationCreate):
    """Create a new publication draft."""
    from loguru import logger
    manager = _get_manager()

    # Verify channel exists
    channel = manager.get_channel(create.channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    logger.info(
        f"Creating publication draft: timeline={create.timeline_id}, "
        f"channel={create.channel_id}"
    )
    publication = manager.create_publication(create)
    return publication


@router.patch("/publications/{publication_id}", response_model=Publication)
async def update_publication(publication_id: str, update: PublicationUpdate):
    """Update a publication."""
    manager = _get_manager()
    pub = manager.update_publication(publication_id, update)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    return pub


@router.delete("/publications/{publication_id}")
async def delete_publication(publication_id: str):
    """Delete a publication."""
    manager = _get_manager()
    if not manager.delete_publication(publication_id):
        raise HTTPException(status_code=404, detail="Publication not found")
    return {"message": "Publication deleted"}


# ============ Publishing Action ============


class PublishRequest(BaseModel):
    """Request to publish a draft."""
    pass  # No additional params needed, uses publication settings


class PublishResponse(BaseModel):
    """Response for publish action."""
    publication_id: str
    status: str
    message: str


@router.post("/publications/{publication_id}/publish", response_model=PublishResponse)
async def publish(
    publication_id: str,
    request: PublishRequest,
    background_tasks: BackgroundTasks,
):
    """Publish a draft to its channel."""
    from loguru import logger
    manager = _get_manager()

    pub = manager.get_publication(publication_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    if pub.status == PublicationStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Already published")

    if pub.status == PublicationStatus.PUBLISHING:
        raise HTTPException(status_code=400, detail="Already publishing")

    channel = manager.get_channel(pub.channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Update status to publishing
    manager.update_publication_status(publication_id, PublicationStatus.PUBLISHING)

    # Start background publishing task
    background_tasks.add_task(
        _run_publish,
        publication_id=publication_id,
        channel=channel,
    )

    logger.info(f"Started publishing: {publication_id} to channel {channel.name}")

    return PublishResponse(
        publication_id=publication_id,
        status="publishing",
        message=f"Publishing to {channel.name}...",
    )


async def _run_publish(publication_id: str, channel: Channel) -> None:
    """Background task to publish to a channel."""
    from loguru import logger

    manager = _get_manager()
    pub = manager.get_publication(publication_id)
    if not pub:
        return

    try:
        if channel.type == ChannelType.YOUTUBE:
            await _publish_to_youtube(pub, channel, manager)
        elif channel.type == ChannelType.TELEGRAM:
            # Future: implement Telegram publishing
            raise NotImplementedError("Telegram publishing not yet implemented")
        else:
            raise ValueError(f"Unsupported channel type: {channel.type}")

    except Exception as e:
        logger.exception(f"Publishing failed for {publication_id}: {e}")
        manager.update_publication_status(
            publication_id,
            PublicationStatus.FAILED,
            error_message=str(e),
        )


async def _publish_to_youtube(
    pub: Publication,
    channel: Channel,
    manager: ChannelManager,
) -> None:
    """Publish to YouTube."""
    from loguru import logger
    from app.api.timelines import _get_manager as get_timeline_manager
    from app.workers.youtube import YouTubeWorker

    # Get timeline for video path
    timeline_manager = get_timeline_manager()
    timeline = timeline_manager.get_timeline(pub.timeline_id)
    if not timeline:
        raise ValueError(f"Timeline not found: {pub.timeline_id}")

    if not timeline.output_full_path:
        raise ValueError("Video not exported yet. Export the video first.")

    from pathlib import Path
    video_path = Path(timeline.output_full_path)
    if not video_path.exists():
        raise ValueError(f"Video file not found: {video_path}")

    # Initialize YouTube worker
    youtube_worker = YouTubeWorker()

    logger.info(f"Uploading to YouTube: {pub.title}")

    # Upload video
    upload_result = await youtube_worker.upload(
        video_path=video_path,
        title=pub.title,
        description=pub.description,
        tags=pub.tags,
        privacy_status=pub.privacy,
    )

    # Update publication with result
    manager.update_publication_status(
        pub.publication_id,
        PublicationStatus.PUBLISHED,
        platform_video_id=upload_result["video_id"],
        platform_url=upload_result["url"],
    )

    logger.info(f"Published to YouTube: {upload_result['url']}")


# ============ Timeline-specific endpoints ============


@router.get("/timelines/{timeline_id}/publications", response_model=List[PublicationSummary])
async def get_timeline_publications(timeline_id: str):
    """Get all publications for a timeline."""
    manager = _get_manager()
    return manager.get_publications_for_timeline(timeline_id)


@router.get("/channels/{channel_id}/publications", response_model=List[PublicationSummary])
async def get_channel_publications(channel_id: str):
    """Get all publications for a channel."""
    manager = _get_manager()
    return manager.get_publications_for_channel(channel_id)


# ============ Generate channel-specific metadata ============


class GenerateMetadataRequest(BaseModel):
    """Request for generating channel-specific metadata."""
    channel_id: str
    instruction: Optional[str] = None


class GenerateMetadataResponse(BaseModel):
    """Generated metadata for a channel."""
    timeline_id: str
    channel_id: str
    channel_name: str
    title: str
    description: str
    tags: List[str]
    thumbnail_candidates: List[dict]
    message: str


@router.post(
    "/timelines/{timeline_id}/generate-for-channel",
    response_model=GenerateMetadataResponse,
)
async def generate_metadata_for_channel(
    timeline_id: str,
    request: GenerateMetadataRequest,
):
    """Generate channel-specific metadata for a timeline.

    This allows generating different titles/descriptions optimized
    for different channels/audiences.
    """
    from loguru import logger
    from app.api.timelines import _get_manager as get_timeline_manager
    from app.api.timelines import _get_thumbnail_worker

    manager = _get_manager()
    timeline_manager = get_timeline_manager()

    timeline = timeline_manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    channel = manager.get_channel(request.channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    thumbnail_worker = _get_thumbnail_worker()

    # Build channel-aware instruction
    instruction_parts = []
    if request.instruction:
        instruction_parts.append(request.instruction)

    # Add channel context
    channel_context = f"目标渠道: {channel.name}"
    if channel.type == ChannelType.YOUTUBE:
        channel_context += " (YouTube)"
    instruction_parts.append(channel_context)

    # Add channel's default tags as context
    if channel.default_tags:
        instruction_parts.append(f"频道常用标签: {', '.join(channel.default_tags)}")

    combined_instruction = "\n".join(instruction_parts) if instruction_parts else None

    # Extract subtitles
    subtitles = [
        {"start": seg.start, "end": seg.end, "en": seg.en}
        for seg in timeline.segments if seg.en
    ]

    try:
        result = await thumbnail_worker.generate_unified_metadata(
            title=timeline.source_title,
            subtitles=subtitles,
            source_url=timeline.source_url,
            duration=timeline.source_duration,
            num_title_candidates=5,
            user_instruction=combined_instruction,
        )

        youtube = result.get("youtube", {})
        candidates = result.get("thumbnail_candidates", [])

        # Apply channel's default tags if available
        tags = youtube.get("tags", [])
        if channel.default_tags:
            # Add channel default tags to front
            tags = list(channel.default_tags) + [t for t in tags if t not in channel.default_tags]

        # Apply description template if available
        description = youtube.get("description", "")
        if channel.description_template:
            description = channel.description_template.replace("{description}", description)
            description = description.replace("{title}", youtube.get("title", ""))
            description = description.replace("{source_url}", timeline.source_url or "")

        logger.info(
            f"Generated metadata for timeline {timeline_id}, channel {channel.name}"
        )

        return GenerateMetadataResponse(
            timeline_id=timeline_id,
            channel_id=channel.channel_id,
            channel_name=channel.name,
            title=youtube.get("title", timeline.source_title),
            description=description,
            tags=tags,
            thumbnail_candidates=candidates,
            message=f"Generated metadata for {channel.name}",
        )

    except Exception as e:
        logger.exception(f"Failed to generate metadata for channel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ YouTube OAuth Endpoints ============


# In-memory store for OAuth state (in production, use Redis or database)
_oauth_states: dict = {}


class OAuthStartResponse(BaseModel):
    """Response for starting OAuth flow."""
    auth_url: str
    state: str
    message: str


class OAuthStatusResponse(BaseModel):
    """Response for OAuth status check."""
    channel_id: str
    is_authorized: bool
    youtube_channel_id: Optional[str] = None
    youtube_channel_name: Optional[str] = None
    authorized_at: Optional[str] = None
    message: str


@router.get("/channels/{channel_id}/oauth/start", response_model=OAuthStartResponse)
async def start_youtube_oauth(channel_id: str):
    """Start YouTube OAuth flow for a channel.

    Returns an authorization URL to redirect the user to.
    After authorization, Google will redirect back to /channels/oauth/callback.
    """
    import secrets
    from google_auth_oauthlib.flow import Flow

    manager = _get_manager()
    channel = manager.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if channel.type != ChannelType.YOUTUBE:
        raise HTTPException(status_code=400, detail="OAuth only supported for YouTube channels")

    # Check for credentials file
    credentials_file = Path(settings.youtube_credentials_file)
    if not credentials_file.exists():
        raise HTTPException(
            status_code=500,
            detail=f"YouTube OAuth credentials file not found: {credentials_file}. "
                   "Please download from Google Cloud Console."
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "channel_id": channel_id,
        "created_at": datetime.now().isoformat(),
    }

    # Create OAuth flow
    # Callback URL should match what's registered in Google Cloud Console
    redirect_uri = f"{settings.frontend_url.rstrip('/')}/channels/oauth/callback"

    flow = Flow.from_client_secrets_file(
        str(credentials_file),
        scopes=[
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly",
        ],
        redirect_uri=redirect_uri,
    )

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # Always show consent screen to get refresh token
        state=state,
    )

    logger.info(f"Started OAuth flow for channel {channel_id}, state: {state[:8]}...")

    return OAuthStartResponse(
        auth_url=auth_url,
        state=state,
        message="Redirect user to auth_url to authorize",
    )


@router.get("/channels/oauth/callback")
async def youtube_oauth_callback(code: str, state: str):
    """Handle YouTube OAuth callback.

    This is called by Google after user authorizes.
    Exchanges the code for tokens and saves them.
    """
    from google_auth_oauthlib.flow import Flow
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    # Validate state
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    state_data = _oauth_states.pop(state)
    channel_id = state_data["channel_id"]

    manager = _get_manager()
    channel = manager.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    credentials_file = Path(settings.youtube_credentials_file)
    redirect_uri = f"{settings.frontend_url.rstrip('/')}/channels/oauth/callback"

    try:
        # Exchange code for tokens
        flow = Flow.from_client_secrets_file(
            str(credentials_file),
            scopes=[
                "https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube.readonly",
            ],
            redirect_uri=redirect_uri,
        )

        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Get YouTube channel info
        service = build("youtube", "v3", credentials=credentials)
        channel_response = service.channels().list(
            part="snippet",
            mine=True,
        ).execute()

        youtube_channel_id = None
        youtube_channel_name = None

        if channel_response.get("items"):
            yt_channel = channel_response["items"][0]
            youtube_channel_id = yt_channel["id"]
            youtube_channel_name = yt_channel["snippet"]["title"]

        # Save token to channel-specific file
        token_dir = Path(settings.data_dir) / "channel_tokens"
        token_dir.mkdir(parents=True, exist_ok=True)
        token_file = token_dir / f"{channel_id}_youtube_token.pickle"

        with open(token_file, "wb") as f:
            pickle.dump(credentials, f)

        # Update channel with OAuth info
        channel.is_authorized = True
        channel.oauth_token_file = str(token_file)
        channel.youtube_channel_id = youtube_channel_id
        channel.youtube_channel_name = youtube_channel_name
        channel.authorized_at = datetime.now()
        channel.status = ChannelStatus.ACTIVE
        channel.updated_at = datetime.now()
        manager._save_channels()

        logger.info(
            f"OAuth completed for channel {channel_id}: "
            f"YouTube channel={youtube_channel_name} ({youtube_channel_id})"
        )

        # Redirect back to frontend channels page with success
        return RedirectResponse(
            url=f"{settings.frontend_url}/channels?oauth=success&channel={channel_id}",
            status_code=302,
        )

    except Exception as e:
        logger.exception(f"OAuth callback failed for channel {channel_id}: {e}")
        # Redirect back with error
        return RedirectResponse(
            url=f"{settings.frontend_url}/channels?oauth=error&message={str(e)[:100]}",
            status_code=302,
        )


@router.get("/channels/{channel_id}/oauth/status", response_model=OAuthStatusResponse)
async def get_oauth_status(channel_id: str):
    """Check OAuth authorization status for a channel."""
    manager = _get_manager()
    channel = manager.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    return OAuthStatusResponse(
        channel_id=channel_id,
        is_authorized=channel.is_authorized,
        youtube_channel_id=channel.youtube_channel_id,
        youtube_channel_name=channel.youtube_channel_name,
        authorized_at=channel.authorized_at.isoformat() if channel.authorized_at else None,
        message="Authorized" if channel.is_authorized else "Not authorized",
    )


@router.post("/channels/{channel_id}/oauth/revoke")
async def revoke_oauth(channel_id: str):
    """Revoke OAuth authorization for a channel."""
    manager = _get_manager()
    channel = manager.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Delete token file if exists
    if channel.oauth_token_file:
        token_file = Path(channel.oauth_token_file)
        if token_file.exists():
            token_file.unlink()
            logger.info(f"Deleted token file for channel {channel_id}")

    # Update channel
    channel.is_authorized = False
    channel.oauth_token_file = None
    channel.authorized_at = None
    channel.status = ChannelStatus.DISCONNECTED
    channel.updated_at = datetime.now()
    manager._save_channels()

    logger.info(f"Revoked OAuth for channel {channel_id}")

    return {"message": "OAuth authorization revoked"}
