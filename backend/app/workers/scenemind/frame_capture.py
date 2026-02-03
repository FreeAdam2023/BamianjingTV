"""Frame capture worker for SceneMind screenshots."""

import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from loguru import logger

from app.models.scenemind import CropRegion


class FrameCaptureWorker:
    """Worker for capturing video frames using FFmpeg."""

    async def capture_frame(
        self,
        video_path: str,
        timecode: float,
        output_path: Path,
    ) -> Path:
        """Capture a single frame from video.

        Args:
            video_path: Path to the video file
            timecode: Timestamp in seconds
            output_path: Output path for the PNG file

        Returns:
            Path to the captured frame

        Raises:
            RuntimeError: If frame capture fails
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # FFmpeg command for single frame capture
        # -ss before -i for faster seeking
        # -frames:v 1 for single frame
        # -q:v 2 for high quality
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-ss", str(timecode),
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            str(output_path),
        ]

        logger.debug(f"Capturing frame at {timecode}s: {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise RuntimeError(f"FFmpeg frame capture failed: {error_msg}")

            if not output_path.exists():
                raise RuntimeError(f"Frame file not created: {output_path}")

            logger.info(f"Captured frame at {timecode}s -> {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Frame capture failed: {e}")
            raise

    async def capture_crop(
        self,
        input_path: Path,
        crop_region: CropRegion,
        output_path: Path,
    ) -> Path:
        """Crop a region from an existing frame.

        Args:
            input_path: Path to the input image
            crop_region: Region to crop (x, y, width, height)
            output_path: Output path for the cropped PNG

        Returns:
            Path to the cropped image

        Raises:
            RuntimeError: If crop fails
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # FFmpeg crop filter: crop=w:h:x:y
        crop_filter = f"crop={crop_region.width}:{crop_region.height}:{crop_region.x}:{crop_region.y}"

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-vf", crop_filter,
            "-q:v", "2",
            str(output_path),
        ]

        logger.debug(f"Cropping frame: {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise RuntimeError(f"FFmpeg crop failed: {error_msg}")

            if not output_path.exists():
                raise RuntimeError(f"Cropped file not created: {output_path}")

            logger.info(
                f"Cropped region ({crop_region.x},{crop_region.y}) "
                f"{crop_region.width}x{crop_region.height} -> {output_path}"
            )
            return output_path

        except Exception as e:
            logger.error(f"Crop failed: {e}")
            raise

    async def capture_observation(
        self,
        video_path: str,
        timecode: float,
        output_dir: Path,
        observation_id: str,
        crop_region: Optional[CropRegion] = None,
    ) -> Tuple[Path, Optional[Path]]:
        """Capture frame for an observation with optional crop.

        Args:
            video_path: Path to the video file
            timecode: Timestamp in seconds
            output_dir: Directory to save frames
            observation_id: ID for naming files
            crop_region: Optional region to crop

        Returns:
            Tuple of (full_frame_path, crop_path or None)

        Raises:
            RuntimeError: If capture fails
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Capture full frame
        full_frame_path = output_dir / f"obs_{observation_id}_full.png"
        await self.capture_frame(video_path, timecode, full_frame_path)

        # Capture crop if region specified
        crop_path = None
        if crop_region:
            crop_path = output_dir / f"obs_{observation_id}_crop.png"
            await self.capture_crop(full_frame_path, crop_region, crop_path)

        return full_frame_path, crop_path

    async def get_video_duration(self, video_path: str) -> float:
        """Get video duration using FFprobe.

        Args:
            video_path: Path to the video file

        Returns:
            Duration in seconds

        Raises:
            RuntimeError: If probe fails
        """
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise RuntimeError(f"FFprobe failed: {error_msg}")

            duration = float(stdout.decode().strip())
            logger.info(f"Video duration: {duration}s")
            return duration

        except Exception as e:
            logger.error(f"Get duration failed: {e}")
            raise

    async def get_video_info(self, video_path: str) -> dict:
        """Get video information using FFprobe.

        Args:
            video_path: Path to the video file

        Returns:
            Dict with duration, width, height

        Raises:
            RuntimeError: If probe fails
        """
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height:format=duration",
            "-of", "json",
            video_path,
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise RuntimeError(f"FFprobe failed: {error_msg}")

            import json
            data = json.loads(stdout.decode())

            info = {
                "duration": float(data.get("format", {}).get("duration", 0)),
                "width": 0,
                "height": 0,
            }

            streams = data.get("streams", [])
            if streams:
                info["width"] = streams[0].get("width", 0)
                info["height"] = streams[0].get("height", 0)

            logger.info(f"Video info: {info}")
            return info

        except Exception as e:
            logger.error(f"Get video info failed: {e}")
            raise
