"""Remotion renderer service for creative mode video export."""

import asyncio
import json
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from loguru import logger

from app.config import settings


@dataclass
class RenderOptions:
    """Options for Remotion render."""
    width: int = 1920
    height: int = 1080
    fps: int = 30
    codec: str = "h264"
    crf: int = 18
    concurrency: int = 2


@dataclass
class RenderProgress:
    """Progress information for a render job."""
    status: str  # bundling, bundled, composition_selected, rendering, complete, error
    progress: int  # 0-100
    render_progress: Optional[float] = None  # 0.0-1.0 (during rendering phase)
    message: Optional[str] = None
    error: Optional[str] = None


@dataclass
class RenderResult:
    """Result of a completed render job."""
    success: bool
    output_path: Optional[str] = None
    duration_in_frames: Optional[int] = None
    fps: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    error: Optional[str] = None


class RemotionRenderer:
    """Service for rendering Remotion compositions to video files."""

    def __init__(self):
        self.frontend_dir = settings.frontend_dir
        self.node_executable = "node"  # Assumes node is in PATH

    def _get_render_script_path(self) -> Path:
        """Get path to the Remotion render script."""
        return self.frontend_dir / "remotion" / "render.mjs"

    async def render(
        self,
        segments: List[Dict[str, Any]],
        config: Dict[str, Any],
        video_src: Optional[str],
        duration_in_frames: int,
        output_path: Path,
        options: Optional[RenderOptions] = None,
        progress_callback: Optional[Callable[[RenderProgress], None]] = None,
    ) -> RenderResult:
        """
        Render a Remotion composition to a video file.

        Args:
            segments: List of subtitle segments with timing info
            config: RemotionConfig dictionary
            video_src: Optional path to source video (for overlay mode)
            duration_in_frames: Total duration in frames
            output_path: Path for output video file
            options: Render options (resolution, fps, etc.)
            progress_callback: Optional callback for progress updates

        Returns:
            RenderResult with success status and output info
        """
        options = options or RenderOptions()
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create input JSON file
        input_data = {
            "segments": segments,
            "config": config,
            "videoSrc": str(video_src) if video_src else None,
            "durationInFrames": duration_in_frames,
            "fps": options.fps,
            "width": options.width,
            "height": options.height,
        }

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            dir=output_path.parent
        ) as f:
            json.dump(input_data, f)
            input_path = Path(f.name)

        try:
            # Build command
            render_script = self._get_render_script_path()
            cmd = [
                self.node_executable,
                str(render_script),
                "--input", str(input_path),
                "--output", str(output_path),
                "--codec", options.codec,
                "--crf", str(options.crf),
                "--concurrency", str(options.concurrency),
            ]

            logger.info(f"Starting Remotion render: {' '.join(cmd)}")

            # Report initial progress
            if progress_callback:
                progress_callback(RenderProgress(status="starting", progress=0))

            # Run the render process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.frontend_dir),
            )

            result = None

            # Process stdout line by line for progress updates
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                try:
                    data = json.loads(line.decode().strip())
                    msg_type = data.get("type")

                    if msg_type == "progress":
                        if progress_callback:
                            progress_callback(RenderProgress(
                                status=data.get("status", "rendering"),
                                progress=data.get("progress", 0),
                                render_progress=data.get("renderProgress"),
                            ))
                    elif msg_type == "complete":
                        result = RenderResult(
                            success=True,
                            output_path=data.get("outputPath"),
                            duration_in_frames=data.get("durationInFrames"),
                            fps=data.get("fps"),
                            width=data.get("width"),
                            height=data.get("height"),
                        )
                    elif msg_type == "error":
                        error_msg = data.get("message", "Unknown error")
                        error_detail = data.get("error", "")
                        logger.error(f"Remotion render error: {error_msg} - {error_detail}")
                        if progress_callback:
                            progress_callback(RenderProgress(
                                status="error",
                                progress=0,
                                error=f"{error_msg}: {error_detail}",
                            ))

                except json.JSONDecodeError:
                    # Non-JSON output, log as debug
                    logger.debug(f"Remotion output: {line.decode().strip()}")

            # Wait for process to complete
            await process.wait()

            # Check stderr for errors
            stderr = await process.stderr.read()
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Remotion render failed with code {process.returncode}: {error_msg}")
                return RenderResult(
                    success=False,
                    error=f"Render process failed: {error_msg}",
                )

            if result:
                logger.info(f"Remotion render complete: {result.output_path}")
                if progress_callback:
                    progress_callback(RenderProgress(status="complete", progress=100))
                return result
            else:
                return RenderResult(
                    success=False,
                    error="Render completed but no result received",
                )

        finally:
            # Clean up input file
            try:
                input_path.unlink()
            except Exception:
                pass

    async def render_creative_export(
        self,
        timeline_id: str,
        job_id: str,
        segments: List[Dict[str, Any]],
        config: Dict[str, Any],
        source_video_path: Path,
        output_dir: Path,
        fps: int = 30,
        progress_callback: Optional[Callable[[RenderProgress], None]] = None,
    ) -> RenderResult:
        """
        Render creative mode export for a timeline.

        This renders the Remotion composition with dynamic subtitles
        overlaid on the source video.

        Args:
            timeline_id: Timeline ID for logging
            job_id: Job ID for locating source video
            segments: Subtitle segments converted to Remotion format
            config: RemotionConfig from creative mode
            source_video_path: Path to source video
            output_dir: Directory for output files
            fps: Frames per second
            progress_callback: Optional callback for progress updates

        Returns:
            RenderResult with success status and output path
        """
        output_path = output_dir / "creative_export.mp4"

        # Calculate total duration from segments
        if segments:
            last_segment = max(segments, key=lambda s: s.get("endFrame", 0))
            duration_in_frames = last_segment.get("endFrame", 300)
        else:
            duration_in_frames = 300  # Default 10 seconds at 30fps

        # Get video dimensions from source
        width, height = self._get_video_dimensions(source_video_path)

        options = RenderOptions(
            width=width,
            height=height,
            fps=fps,
        )

        logger.info(
            f"Starting creative export for timeline {timeline_id}: "
            f"{duration_in_frames} frames at {fps}fps ({width}x{height})"
        )

        return await self.render(
            segments=segments,
            config=config,
            video_src=str(source_video_path),
            duration_in_frames=duration_in_frames,
            output_path=output_path,
            options=options,
            progress_callback=progress_callback,
        )

    def _get_video_dimensions(self, video_path: Path) -> tuple[int, int]:
        """Get video width and height using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"ffprobe failed, using default 1920x1080: {result.stderr}")
            return 1920, 1080
        try:
            w, h = result.stdout.strip().split("x")
            return int(w), int(h)
        except Exception:
            return 1920, 1080

    def convert_timeline_to_remotion_segments(
        self,
        segments: List[Dict[str, Any]],
        fps: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Convert timeline segments to Remotion segment format.

        Args:
            segments: Timeline segments with start/end in seconds
            fps: Frames per second for frame calculation

        Returns:
            List of segments in Remotion format with frame timings
        """
        remotion_segments = []

        for seg in segments:
            start_time = seg.get("start", 0)
            end_time = seg.get("end", start_time + 1)

            # Convert word timings if present
            words = seg.get("words", [])
            remotion_words = []
            for word in words:
                word_start = word.get("start", start_time)
                word_end = word.get("end", word_start + 0.1)
                remotion_words.append({
                    "word": word.get("word", ""),
                    "start": word_start,
                    "end": word_end,
                    "startFrame": int(word_start * fps),
                    "endFrame": int(word_end * fps),
                    "confidence": word.get("confidence"),
                })

            remotion_segments.append({
                "id": seg.get("id", 0),
                "startFrame": int(start_time * fps),
                "endFrame": int(end_time * fps),
                "en": seg.get("en", ""),
                "zh": seg.get("zh", ""),
                "speaker": seg.get("speaker"),
                "words": remotion_words if remotion_words else None,
                "highlightedWords": seg.get("highlighted_words"),
                "entityWords": seg.get("entity_words"),
            })

        return remotion_segments


# Singleton instance
remotion_renderer = RemotionRenderer()
