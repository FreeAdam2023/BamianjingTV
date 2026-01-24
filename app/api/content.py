"""Content generation API endpoints."""

from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from app.workers.thumbnail import ThumbnailWorker
from app.workers.content import ContentWorker, VideoContent


router = APIRouter(prefix="/content", tags=["content"])

# Workers
thumbnail_worker = ThumbnailWorker()
content_worker = ContentWorker()


# ============ Request/Response Models ============

class ThumbnailRequest(BaseModel):
    """Request for thumbnail generation."""
    prompt: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    keywords: List[str] = []
    style: str = "modern"
    output_path: str


class ThumbnailFromVideoRequest(BaseModel):
    """Request for extracting thumbnail from video."""
    video_path: str
    output_path: str
    timestamp: Optional[float] = None
    add_text: Optional[str] = None


class ContentRequest(BaseModel):
    """Request for content generation."""
    original_title: str
    original_description: Optional[str] = None
    transcript_summary: str
    channel_name: Optional[str] = None
    video_duration: Optional[float] = None


class ChaptersRequest(BaseModel):
    """Request for chapter generation."""
    segments: List[dict]
    min_chapter_duration: float = 60.0


# ============ Endpoints ============

@router.post("/thumbnail/generate")
async def generate_thumbnail(request: ThumbnailRequest):
    """Generate AI thumbnail from prompt or content summary."""
    try:
        output_path = Path(request.output_path)

        if request.prompt:
            # Use direct prompt
            result = await thumbnail_worker.generate(
                prompt=request.prompt,
                output_path=output_path,
            )
        elif request.title:
            # Generate from content
            result = await thumbnail_worker.generate_from_summary(
                title=request.title,
                summary=request.summary or "",
                keywords=request.keywords,
                output_path=output_path,
                style=request.style,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Either 'prompt' or 'title' is required"
            )

        return {
            "success": True,
            "thumbnail_path": str(result),
        }

    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/thumbnail/extract")
async def extract_thumbnail(request: ThumbnailFromVideoRequest):
    """Extract frame from video as thumbnail."""
    try:
        result = await thumbnail_worker.extract_frame_thumbnail(
            video_path=Path(request.video_path),
            output_path=Path(request.output_path),
            timestamp=request.timestamp,
        )

        # Add text overlay if requested
        if request.add_text:
            result = await thumbnail_worker.add_text_overlay(
                image_path=result,
                text=request.add_text,
                output_path=result,
            )

        return {
            "success": True,
            "thumbnail_path": str(result),
        }

    except Exception as e:
        logger.error(f"Thumbnail extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate", response_model=VideoContent)
async def generate_content(request: ContentRequest):
    """Generate video title, description, and tags."""
    try:
        content = await content_worker.generate_content(
            original_title=request.original_title,
            original_description=request.original_description,
            transcript_summary=request.transcript_summary,
            channel_name=request.channel_name,
            video_duration=request.video_duration,
        )

        return content

    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chapters")
async def generate_chapters(request: ChaptersRequest):
    """Generate video chapters from transcript segments."""
    try:
        chapters = await content_worker.generate_chapters(
            segments=request.segments,
            min_chapter_duration=request.min_chapter_duration,
        )

        return {
            "success": True,
            "chapters": chapters,
            "count": len(chapters),
        }

    except Exception as e:
        logger.error(f"Chapter generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summary")
async def generate_summary(segments: List[dict]):
    """Generate transcript summary."""
    try:
        summary = await content_worker.generate_transcript_summary(
            segments=segments,
        )

        return {
            "success": True,
            "summary": summary,
        }

    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
