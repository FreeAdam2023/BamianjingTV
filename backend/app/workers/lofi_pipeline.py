"""Lofi Video Factory pipeline worker.

Orchestrates the full pipeline: music generation → audio mixing → visual generation
→ compositing → thumbnail → metadata → review/publish.
"""

import asyncio
import math
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional

from loguru import logger

from app.config import settings
from app.models.lofi import (
    LofiSession,
    LofiSessionStatus,
    LofiTheme,
    MusicSource,
    VisualMode,
)
from app.models.music import MusicModelSize
from app.services.ambient_library import AmbientLibrary
from app.services.lofi_manager import LofiSessionManager
from app.workers.music_generator import MusicGeneratorWorker, AUDIOCRAFT_AVAILABLE
from app.workers.youtube import YouTubeWorker

_pipeline_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="lofi-pipeline")


class LofiPipelineWorker:
    """Orchestrates the full lofi video generation pipeline."""

    def __init__(
        self,
        session_manager: LofiSessionManager,
        music_generator: MusicGeneratorWorker,
        ambient_library: Optional[AmbientLibrary] = None,
        youtube_worker: Optional[YouTubeWorker] = None,
        image_pool=None,
    ):
        self.session_manager = session_manager
        self.music_generator = music_generator
        self.ambient_library = ambient_library
        self.youtube_worker = youtube_worker
        self.image_pool = image_pool

    async def run_pipeline(self, session_id: str) -> None:
        """Run the full pipeline for a session."""
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.error(f"Lofi session not found: {session_id}")
            return

        logger.info(f"Starting lofi pipeline for session {session_id} "
                     f"(theme={session.music_config.theme.value}, "
                     f"duration={session.target_duration}s)")

        try:
            session_dir = self.session_manager.get_session_dir(session_id)

            # Stage 1: Generate music segments (0-50%)
            await self._generate_music(session, session_dir)

            # Stage 2: Concatenate segments with crossfade (50-60%)
            await self._concatenate_segments(session, session_dir)

            # Stage 3: Mix ambient sounds (60-65%)
            await self._mix_ambient(session, session_dir)

            # Stage 4: Generate visuals (65-85%)
            await self._generate_visuals(session, session_dir)

            # Stage 5: Composite audio + video (85-90%)
            await self._composite(session, session_dir)

            # Stage 6: Generate thumbnail (90-93%)
            await self._generate_thumbnail(session, session_dir)

            # Stage 7: Generate metadata via LLM (93-97%)
            await self._generate_metadata(session, session_dir)

            # Done — awaiting review
            self.session_manager.update_session(
                session_id,
                status=LofiSessionStatus.AWAITING_REVIEW,
                progress=100.0,
            )
            logger.info(f"Lofi pipeline complete for session {session_id} — awaiting review")

        except Exception as e:
            logger.error(f"Lofi pipeline failed for session {session_id}: {e}")
            self.session_manager.update_session(
                session_id,
                status=LofiSessionStatus.FAILED,
                error=str(e),
            )

    async def _generate_music(self, session: LofiSession, session_dir: Path) -> None:
        """Stage 1: Generate music segments using MusicGen."""
        self.session_manager.update_session(
            session.id,
            status=LofiSessionStatus.GENERATING_MUSIC,
            progress=0.0,
        )
        start = time.time()

        segment_duration = session.music_config.segment_duration
        crossfade = session.music_config.crossfade_duration
        total_duration = session.target_duration

        # Calculate number of segments needed
        # Each segment contributes (segment_duration - crossfade) except the last
        effective_per_segment = segment_duration - crossfade
        num_segments = max(1, math.ceil(total_duration / effective_per_segment))

        prompt = session.music_config.custom_prompt or session.music_config.theme.musicgen_prompt
        model_size = MusicModelSize(session.music_config.model_size)

        segments_dir = session_dir / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)
        segment_paths: List[str] = []

        for i in range(num_segments):
            segment_path = segments_dir / f"segment_{i:03d}.wav"

            if AUDIOCRAFT_AVAILABLE and session.music_config.source == MusicSource.MUSICGEN:
                await self._generate_single_segment(
                    prompt=prompt,
                    duration=segment_duration,
                    model_size=model_size,
                    output_path=segment_path,
                )
            else:
                # Generate silence placeholder if MusicGen not available
                await self._generate_silence(segment_duration, segment_path)

            segment_paths.append(str(segment_path))

            progress = ((i + 1) / num_segments) * 50.0
            self.session_manager.update_session(
                session.id,
                progress=progress,
                music_segments=segment_paths,
            )
            logger.info(f"Generated segment {i + 1}/{num_segments} for session {session.id}")

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id,
            step_timings={"music_generation": round(elapsed, 1)},
        )

    async def _generate_single_segment(
        self,
        prompt: str,
        duration: float,
        model_size: MusicModelSize,
        output_path: Path,
    ) -> None:
        """Generate a single music segment using MusicGen."""
        await self.music_generator._ensure_model_loaded(model_size)

        loop = asyncio.get_event_loop()

        def _generate_and_save():
            import torchaudio
            wav = self.music_generator._generate_sync(prompt, duration)
            audio_data = wav[0].cpu()
            sample_rate = self.music_generator.model.sample_rate
            torchaudio.save(str(output_path), audio_data, sample_rate)

        await loop.run_in_executor(_pipeline_executor, _generate_and_save)

    async def _generate_silence(self, duration: float, output_path: Path) -> None:
        """Generate a silence WAV file as a placeholder."""
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anullsrc=r=32000:cl=mono",
            "-t", str(duration),
            str(output_path),
        ]
        await self._run_ffmpeg(cmd, timeout=30)

    async def _concatenate_segments(self, session: LofiSession, session_dir: Path) -> None:
        """Stage 2: Concatenate music segments with crossfade."""
        self.session_manager.update_session(
            session.id,
            status=LofiSessionStatus.MIXING_AUDIO,
            progress=50.0,
        )
        start = time.time()

        segments = session.music_segments
        if not segments:
            raise RuntimeError("No music segments to concatenate")

        if len(segments) == 1:
            # Single segment — just copy
            import shutil
            output_path = session_dir / "audio.wav"
            shutil.copy2(segments[0], output_path)
            self.session_manager.update_session(
                session.id,
                final_audio_path=str(output_path),
            )
            return

        crossfade = session.music_config.crossfade_duration
        output_path = session_dir / "audio.wav"

        # For large segment counts, batch in groups to avoid filter chain limits
        batch_size = 5
        if len(segments) <= batch_size:
            await self._crossfade_concat(segments, crossfade, output_path)
        else:
            # Batch processing
            temp_outputs = []
            for batch_start in range(0, len(segments), batch_size):
                batch = segments[batch_start:batch_start + batch_size]
                if len(batch) == 1 and temp_outputs:
                    # Append single remaining segment to previous batch output
                    batch = [temp_outputs[-1]] + batch
                    temp_outputs.pop()

                temp_output = session_dir / f"batch_{batch_start}.wav"
                await self._crossfade_concat(batch, crossfade, temp_output)
                temp_outputs.append(str(temp_output))

            # Final merge of batch outputs
            if len(temp_outputs) > 1:
                await self._crossfade_concat(temp_outputs, crossfade, output_path)
            else:
                import shutil
                shutil.move(temp_outputs[0], output_path)

            # Clean up temp batch files
            for tp in temp_outputs:
                Path(tp).unlink(missing_ok=True)

        self.session_manager.update_session(
            session.id,
            final_audio_path=str(output_path),
            progress=60.0,
        )

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id,
            step_timings={"concatenation": round(elapsed, 1)},
        )

    async def _crossfade_concat(
        self, segment_paths: List[str], crossfade_duration: float, output_path: Path
    ) -> None:
        """Crossfade concatenate segments using ffmpeg acrossfade filter."""
        if len(segment_paths) < 2:
            import shutil
            shutil.copy2(segment_paths[0], output_path)
            return

        inputs = []
        for sp in segment_paths:
            inputs += ["-i", sp]

        # Build acrossfade chain
        filter_parts = []
        n = len(segment_paths)
        prev = "[0:a]"
        for i in range(1, n):
            out_label = f"[a{i:02d}]" if i < n - 1 else "[final]"
            filter_parts.append(
                f"{prev}[{i}:a]acrossfade=d={crossfade_duration}:c1=tri:c2=tri{out_label}"
            )
            prev = out_label

        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[final]",
            str(output_path),
        ]
        await self._run_ffmpeg(cmd, timeout=300)

    async def _mix_ambient(self, session: LofiSession, session_dir: Path) -> None:
        """Stage 3: Mix ambient sounds into the final audio."""
        ambient_sounds = session.music_config.ambient_sounds
        if not ambient_sounds or not self.ambient_library:
            self.session_manager.update_session(session.id, progress=65.0)
            return

        start = time.time()
        sound_paths = self.ambient_library.get_available_sounds(ambient_sounds)
        if not sound_paths:
            self.session_manager.update_session(session.id, progress=65.0)
            return

        audio_path = Path(session.final_audio_path)
        mixed_path = session_dir / "audio_mixed.wav"
        volume = session.music_config.ambient_volume
        duration = session.target_duration

        # Build ffmpeg mix command
        inputs = ["-i", str(audio_path)]
        for sp in sound_paths:
            inputs += ["-i", str(sp)]

        filter_parts = []
        mix_inputs = "[0:a]"
        for i, _ in enumerate(sound_paths):
            idx = i + 1
            filter_parts.append(
                f"[{idx}:a]aloop=loop=-1:size=2e9,atrim=0:{duration},volume={volume}[a{idx}]"
            )
            mix_inputs += f"[a{idx}]"

        n_total = 1 + len(sound_paths)
        filter_parts.append(
            f"{mix_inputs}amix=inputs={n_total}:duration=first:normalize=0[out]"
        )
        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            str(mixed_path),
        ]
        await self._run_ffmpeg(cmd, timeout=600)

        # Replace audio with mixed version
        import shutil
        shutil.move(str(mixed_path), str(audio_path))

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id,
            progress=65.0,
            step_timings={"ambient_mixing": round(elapsed, 1)},
        )
        logger.info(f"Mixed {len(sound_paths)} ambient sound(s) for session {session.id}")

    async def _generate_visuals(self, session: LofiSession, session_dir: Path) -> None:
        """Stage 4: Generate video from static image using Ken Burns effect."""
        self.session_manager.update_session(
            session.id,
            status=LofiSessionStatus.GENERATING_VISUALS,
            progress=65.0,
        )
        start = time.time()

        if session.visual_config.mode != VisualMode.STATIC_KEN_BURNS:
            logger.warning(f"Visual mode {session.visual_config.mode.value} not yet implemented, "
                          f"falling back to static_ken_burns")

        # Find image
        image_path = self._resolve_image_path(session)
        if not image_path or not image_path.exists():
            raise RuntimeError(f"Background image not found: {session.visual_config.image_path}")

        audio_path = Path(session.final_audio_path)
        video_path = session_dir / "video_visual.mp4"
        speed = session.visual_config.ken_burns_speed

        # Ken Burns effect using ffmpeg zoompan
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(image_path),
            "-i", str(audio_path),
            "-filter_complex",
            f"[0:v]scale=3840:-1,zoompan=z='min(zoom+{speed},1.3)'"
            f":d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":s=1920x1080:fps=24[v]",
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(video_path),
        ]

        # Use NVENC if available
        if settings.ffmpeg_nvenc:
            cmd = self._try_nvenc(cmd)

        await self._run_ffmpeg(cmd, timeout=7200)  # Up to 2 hours for long videos

        self.session_manager.update_session(
            session.id,
            final_video_path=str(video_path),
            progress=85.0,
        )

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id,
            step_timings={"visual_generation": round(elapsed, 1)},
        )

    async def _composite(self, session: LofiSession, session_dir: Path) -> None:
        """Stage 5: Final compositing (already done in visual stage for Ken Burns)."""
        self.session_manager.update_session(
            session.id,
            status=LofiSessionStatus.COMPOSITING,
            progress=88.0,
        )
        # For Ken Burns mode, visual stage already produces the final video
        # Future modes (remotion, AI) would need separate compositing
        self.session_manager.update_session(session.id, progress=90.0)

    async def _generate_thumbnail(self, session: LofiSession, session_dir: Path) -> None:
        """Stage 6: Generate thumbnail from video frame + text overlay."""
        self.session_manager.update_session(
            session.id,
            status=LofiSessionStatus.GENERATING_THUMBNAIL,
            progress=90.0,
        )
        start = time.time()

        video_path = Path(session.final_video_path)
        thumbnail_path = session_dir / "thumbnail.png"

        # Capture frame at 10 seconds
        cmd = [
            "ffmpeg", "-y",
            "-ss", "10",
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(thumbnail_path),
        ]
        await self._run_ffmpeg(cmd, timeout=60)

        # Add text overlay using PIL if available
        theme_label = session.music_config.theme.label
        await self._add_thumbnail_text(thumbnail_path, theme_label)

        self.session_manager.update_session(
            session.id,
            thumbnail_path=str(thumbnail_path),
            progress=93.0,
        )

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id,
            step_timings={"thumbnail": round(elapsed, 1)},
        )

    async def _add_thumbnail_text(self, thumbnail_path: Path, theme_label: str) -> None:
        """Add text overlay to thumbnail using PIL."""
        try:
            from PIL import Image, ImageDraw, ImageFont

            img = Image.open(thumbnail_path)
            draw = ImageDraw.Draw(img)

            # Try to load a nice font, fall back to default
            font_size = img.width // 20
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except (OSError, IOError):
                font = ImageFont.load_default()

            text = f"{theme_label} | Lofi Music"

            # Draw text with shadow
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            x = (img.width - text_width) // 2
            y = img.height - font_size * 2

            # Shadow
            draw.text((x + 2, y + 2), text, fill="black", font=font)
            # Main text
            draw.text((x, y), text, fill="white", font=font)

            img.save(thumbnail_path)
        except ImportError:
            logger.warning("PIL not available, skipping thumbnail text overlay")

    async def _generate_metadata(self, session: LofiSession, session_dir: Path) -> None:
        """Stage 7: Generate title, description, and tags using LLM."""
        self.session_manager.update_session(
            session.id,
            status=LofiSessionStatus.GENERATING_METADATA,
            progress=93.0,
        )
        start = time.time()

        theme = session.music_config.theme
        duration_hours = session.target_duration / 3600
        ambient = ", ".join(session.music_config.ambient_sounds) if session.music_config.ambient_sounds else "none"

        metadata = await self._call_llm_for_metadata(theme, duration_hours, ambient)

        self.session_manager.update_session(
            session.id,
            title=metadata.get("title", f"{theme.label} - Lofi Music"),
            description=metadata.get("description", ""),
            tags=metadata.get("tags", []),
            progress=97.0,
        )

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id,
            step_timings={"metadata": round(elapsed, 1)},
        )

    async def _call_llm_for_metadata(
        self, theme: LofiTheme, duration_hours: float, ambient: str
    ) -> dict:
        """Call Grok/OpenAI LLM to generate YouTube metadata."""
        try:
            import httpx

            prompt = (
                f"Generate YouTube metadata for a {duration_hours:.1f}-hour "
                f"lofi {theme.label.lower()} music video.\n"
                f"Ambient sounds: {ambient}\n\n"
                f"Return a JSON object with:\n"
                f"- title: catchy YouTube title (max 80 chars), include duration\n"
                f"- description: SEO-optimized description (200-500 chars) with timestamps and hashtags\n"
                f"- tags: array of 10-15 relevant YouTube tags\n\n"
                f"Return ONLY the JSON, no markdown."
            )

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.llm_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                    json={
                        "model": settings.llm_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]

                # Parse JSON from response
                import json
                # Handle potential markdown code blocks
                if "```" in content:
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                return json.loads(content.strip())

        except Exception as e:
            logger.warning(f"LLM metadata generation failed: {e}, using defaults")
            duration_str = f"{duration_hours:.0f} Hour" if duration_hours >= 1 else f"{int(duration_hours * 60)} Min"
            return {
                "title": f"{theme.label} Lofi Music | {duration_str} Study & Relax",
                "description": (
                    f"Relax and study with this {duration_str.lower()} {theme.label.lower()} "
                    f"lofi music mix. Perfect for studying, working, or unwinding.\n\n"
                    f"#lofi #studymusic #{theme.value.replace('_', '')}"
                ),
                "tags": [
                    "lofi", "lofi hip hop", "study music", "chill beats",
                    theme.value.replace("_", " "), "relaxing music",
                    "focus music", "background music",
                ],
            }

    async def publish_to_youtube(self, session_id: str) -> dict:
        """Publish a reviewed session to YouTube."""
        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if session.status not in (LofiSessionStatus.AWAITING_REVIEW, LofiSessionStatus.FAILED):
            raise ValueError(f"Session not in reviewable state: {session.status.value}")

        if not session.final_video_path or not Path(session.final_video_path).exists():
            raise ValueError("No video file available for upload")

        if not self.youtube_worker:
            raise RuntimeError("YouTube worker not available")

        self.session_manager.update_session(
            session_id,
            status=LofiSessionStatus.PUBLISHING,
            progress=97.0,
        )

        try:
            result = await self.youtube_worker.upload(
                video_path=Path(session.final_video_path),
                title=session.metadata.title,
                description=session.metadata.description,
                tags=session.metadata.tags,
                category_id=session.metadata.category_id,
                privacy_status=session.metadata.privacy_status,
                thumbnail_path=Path(session.thumbnail_path) if session.thumbnail_path else None,
                default_language="en",
            )

            self.session_manager.update_session(
                session_id,
                status=LofiSessionStatus.PUBLISHED,
                youtube_video_id=result.get("video_id"),
                youtube_url=result.get("url"),
                progress=100.0,
            )
            logger.info(f"Published lofi session {session_id} to YouTube: {result.get('url')}")
            return result

        except Exception as e:
            logger.error(f"YouTube publish failed for session {session_id}: {e}")
            self.session_manager.update_session(
                session_id,
                status=LofiSessionStatus.FAILED,
                error=f"YouTube upload failed: {e}",
            )
            raise

    def _resolve_image_path(self, session: LofiSession) -> Optional[Path]:
        """Resolve the background image path.

        Priority:
        1. Explicit image_path in session config
        2. Random approved image from pool matching session theme
        3. Random approved image from pool (any theme)
        4. Legacy fallback: first file in lofi_images_dir
        """
        if session.visual_config.image_path:
            path = Path(session.visual_config.image_path)
            if path.is_absolute():
                return path
            return settings.lofi_images_dir / session.visual_config.image_path

        # Try image pool
        if self.image_pool:
            theme = session.music_config.theme
            img = self.image_pool.get_random_approved(theme)
            if not img:
                img = self.image_pool.get_random_approved(None)
            if img:
                return settings.lofi_images_dir / img.filename

        # Legacy fallback
        images_dir = settings.lofi_images_dir
        if images_dir.exists():
            for ext in ("*.jpg", "*.jpeg", "*.png"):
                images = sorted(images_dir.glob(ext))
                if images:
                    return images[0]
        return None

    def _try_nvenc(self, cmd: list) -> list:
        """Replace libx264 with h264_nvenc if possible."""
        try:
            new_cmd = []
            for item in cmd:
                if item == "libx264":
                    new_cmd.append("h264_nvenc")
                elif item == "-crf":
                    new_cmd.append("-cq")
                else:
                    new_cmd.append(item)
            return new_cmd
        except Exception:
            return cmd

    async def _run_ffmpeg(self, cmd: list, timeout: int = 300) -> None:
        """Run an ffmpeg command asynchronously."""
        loop = asyncio.get_event_loop()

        def _run():
            logger.debug(f"Running ffmpeg: {' '.join(cmd[:10])}...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed (rc={result.returncode}): {result.stderr[-500:]}")

        await loop.run_in_executor(_pipeline_executor, _run)
