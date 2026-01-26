"""Cleanup API endpoints.

Handles old job cleanup operations to free disk space.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.config import settings


router = APIRouter(prefix="/admin", tags=["admin"])


class CleanupRequest(BaseModel):
    """Request model for cleanup operation."""
    retention_days: int = 30
    videos_only: bool = True
    dry_run: bool = True  # Default to dry run for safety


@router.post("/cleanup")
async def cleanup_old_jobs(request: CleanupRequest):
    """
    Clean up old job files to free disk space.

    - retention_days: Keep files newer than this (default: 30)
    - videos_only: If true, only delete video files but keep metadata (default: true)
    - dry_run: If true, only report what would be deleted (default: true)

    Set dry_run=false to actually delete files.
    """
    from app.services.cleanup import run_cleanup

    stats = await run_cleanup(
        jobs_dir=settings.jobs_dir,
        retention_days=request.retention_days,
        videos_only=request.videos_only,
        dry_run=request.dry_run,
    )

    return {
        "message": "Cleanup complete" if not request.dry_run else "Dry run complete",
        "dry_run": request.dry_run,
        "retention_days": request.retention_days,
        "videos_only": request.videos_only,
        "stats": {
            "jobs_processed": stats["jobs_processed"],
            "files_removed": stats["files_removed"],
            "bytes_freed": stats["bytes_freed"],
            "gb_freed": round(stats["bytes_freed"] / 1024 / 1024 / 1024, 2),
            "errors": stats["errors"][:10],  # Limit errors in response
        },
    }


@router.get("/cleanup/preview")
async def preview_cleanup(
    retention_days: int = Query(default=30, ge=1, le=365),
):
    """
    Preview what would be cleaned up without deleting anything.

    Returns list of jobs that would be affected.
    """
    from app.services.cleanup import CleanupService

    service = CleanupService(
        jobs_dir=settings.jobs_dir,
        retention_days=retention_days,
        dry_run=True,
    )

    preview = []
    for job_dir in settings.jobs_dir.iterdir():
        if not job_dir.is_dir():
            continue

        if service.should_cleanup(job_dir):
            age = service.get_job_age(job_dir)
            video_files = service.get_video_files(job_dir)
            total_size = sum(f.stat().st_size for f in video_files)

            preview.append({
                "job_id": job_dir.name,
                "age_days": (service.cutoff_date - age).days + retention_days if age else None,
                "video_files": len(video_files),
                "total_size_mb": round(total_size / 1024 / 1024, 2),
            })

    return {
        "retention_days": retention_days,
        "cutoff_date": service.cutoff_date.isoformat(),
        "jobs_to_cleanup": preview,
        "total_jobs": len(preview),
        "total_size_mb": round(sum(j["total_size_mb"] for j in preview), 2),
    }
