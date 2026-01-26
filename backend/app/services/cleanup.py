"""
Automatic cleanup service for old job files.

Removes video files and job data older than the configured retention period
to save disk space.
"""

import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger


class CleanupService:
    """Service for automatic cleanup of old job files."""

    def __init__(
        self,
        jobs_dir: Path,
        retention_days: int = 30,
        dry_run: bool = False,
    ):
        """
        Initialize cleanup service.

        Args:
            jobs_dir: Path to jobs directory
            retention_days: Number of days to keep files (default: 30)
            dry_run: If True, only log what would be deleted without actually deleting
        """
        self.jobs_dir = jobs_dir
        self.retention_days = retention_days
        self.dry_run = dry_run
        self.cutoff_date = datetime.now() - timedelta(days=retention_days)

    def get_job_age(self, job_dir: Path) -> Optional[datetime]:
        """Get the creation/modification date of a job."""
        meta_file = job_dir / "meta.json"
        if meta_file.exists():
            # Use meta.json modification time
            return datetime.fromtimestamp(meta_file.stat().st_mtime)
        elif job_dir.exists():
            # Fall back to directory modification time
            return datetime.fromtimestamp(job_dir.stat().st_mtime)
        return None

    def should_cleanup(self, job_dir: Path) -> bool:
        """Check if a job should be cleaned up based on age."""
        age = self.get_job_age(job_dir)
        if age is None:
            return False
        return age < self.cutoff_date

    def get_video_files(self, job_dir: Path) -> list[Path]:
        """Get all video files in a job directory."""
        video_extensions = {".mp4", ".webm", ".mkv", ".avi", ".mov", ".wav", ".mp3"}
        video_files = []

        for root, _, files in os.walk(job_dir):
            for file in files:
                if Path(file).suffix.lower() in video_extensions:
                    video_files.append(Path(root) / file)

        return video_files

    def cleanup_job_videos(self, job_dir: Path) -> dict:
        """
        Remove video files from a job directory but keep metadata.

        Returns dict with cleanup stats.
        """
        stats = {
            "files_removed": 0,
            "bytes_freed": 0,
            "errors": [],
        }

        video_files = self.get_video_files(job_dir)

        for video_file in video_files:
            try:
                file_size = video_file.stat().st_size
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would delete: {video_file} ({file_size / 1024 / 1024:.2f} MB)")
                else:
                    video_file.unlink()
                    logger.info(f"Deleted: {video_file} ({file_size / 1024 / 1024:.2f} MB)")
                stats["files_removed"] += 1
                stats["bytes_freed"] += file_size
            except Exception as e:
                stats["errors"].append(f"{video_file}: {e}")
                logger.error(f"Failed to delete {video_file}: {e}")

        return stats

    def cleanup_entire_job(self, job_dir: Path) -> dict:
        """
        Remove entire job directory.

        Returns dict with cleanup stats.
        """
        stats = {
            "files_removed": 0,
            "bytes_freed": 0,
            "errors": [],
        }

        try:
            # Calculate size before deletion
            total_size = sum(
                f.stat().st_size for f in job_dir.rglob("*") if f.is_file()
            )
            file_count = sum(1 for _ in job_dir.rglob("*") if _.is_file())

            if self.dry_run:
                logger.info(f"[DRY RUN] Would delete job: {job_dir.name} ({total_size / 1024 / 1024:.2f} MB, {file_count} files)")
            else:
                shutil.rmtree(job_dir)
                logger.info(f"Deleted job: {job_dir.name} ({total_size / 1024 / 1024:.2f} MB, {file_count} files)")

            stats["files_removed"] = file_count
            stats["bytes_freed"] = total_size
        except Exception as e:
            stats["errors"].append(f"{job_dir}: {e}")
            logger.error(f"Failed to delete job {job_dir}: {e}")

        return stats

    def run(self, videos_only: bool = True) -> dict:
        """
        Run cleanup on all old jobs.

        Args:
            videos_only: If True, only remove video files but keep metadata.
                        If False, remove entire job directories.

        Returns dict with total cleanup stats.
        """
        total_stats = {
            "jobs_processed": 0,
            "files_removed": 0,
            "bytes_freed": 0,
            "errors": [],
        }

        if not self.jobs_dir.exists():
            logger.warning(f"Jobs directory does not exist: {self.jobs_dir}")
            return total_stats

        logger.info(f"Starting cleanup (retention: {self.retention_days} days, cutoff: {self.cutoff_date})")
        logger.info(f"Mode: {'videos only' if videos_only else 'entire jobs'}, Dry run: {self.dry_run}")

        for job_dir in self.jobs_dir.iterdir():
            if not job_dir.is_dir():
                continue

            if not self.should_cleanup(job_dir):
                continue

            age = self.get_job_age(job_dir)
            logger.info(f"Processing old job: {job_dir.name} (age: {age})")

            if videos_only:
                stats = self.cleanup_job_videos(job_dir)
            else:
                stats = self.cleanup_entire_job(job_dir)

            total_stats["jobs_processed"] += 1
            total_stats["files_removed"] += stats["files_removed"]
            total_stats["bytes_freed"] += stats["bytes_freed"]
            total_stats["errors"].extend(stats["errors"])

        # Log summary
        freed_mb = total_stats["bytes_freed"] / 1024 / 1024
        freed_gb = freed_mb / 1024
        logger.info(
            f"Cleanup complete: {total_stats['jobs_processed']} jobs, "
            f"{total_stats['files_removed']} files, "
            f"{freed_gb:.2f} GB freed"
        )

        if total_stats["errors"]:
            logger.warning(f"Cleanup had {len(total_stats['errors'])} errors")

        return total_stats


async def run_cleanup(
    jobs_dir: Path,
    retention_days: int = 30,
    videos_only: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Convenience function to run cleanup.

    Args:
        jobs_dir: Path to jobs directory
        retention_days: Number of days to keep files
        videos_only: If True, only remove video files
        dry_run: If True, only log what would be deleted

    Returns cleanup stats.
    """
    service = CleanupService(
        jobs_dir=jobs_dir,
        retention_days=retention_days,
        dry_run=dry_run,
    )
    return service.run(videos_only=videos_only)
