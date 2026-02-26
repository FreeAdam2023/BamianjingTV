"""Music Commentary Video Factory pipeline worker.

Orchestrates the full pipeline: download → transcribe → translate → annotate
→ script → TTS → assemble audio → generate visual → thumbnail → metadata → review.
"""

import asyncio
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from app.config import settings
from app.models.music_commentary import (
    MusicCommentarySession,
    MusicCommentaryStatus,
)
from app.services.music_commentary_manager import MusicCommentarySessionManager
from app.workers.download import DownloadWorker
from app.workers.whisper import WhisperWorker
from app.workers.translation import TranslationWorker
from app.workers.youtube import YouTubeWorker

_pipeline_executor = ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="mc-pipeline"
)


class MusicCommentaryPipelineWorker:
    """Orchestrates the full music commentary video generation pipeline."""

    def __init__(
        self,
        session_manager: MusicCommentarySessionManager,
        download_worker: DownloadWorker,
        whisper_worker: WhisperWorker,
        translation_worker: TranslationWorker,
        card_generator=None,
        youtube_worker: Optional[YouTubeWorker] = None,
        voice_clone_worker=None,
    ):
        self.session_manager = session_manager
        self.download_worker = download_worker
        self.whisper_worker = whisper_worker
        self.translation_worker = translation_worker
        self.card_generator = card_generator
        self.youtube_worker = youtube_worker
        self.voice_clone_worker = voice_clone_worker

    async def run_pipeline(self, session_id: str) -> None:
        """Run the full pipeline for a session."""
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.error(f"Music commentary session not found: {session_id}")
            return

        logger.info(
            f"Starting music commentary pipeline for session {session_id} "
            f"(url={session.song_config.url[:60]})"
        )

        try:
            session_dir = self.session_manager.get_session_dir(session_id)

            # Stage 1: Download (0-10%)
            await self._download(session, session_dir)

            # Stage 2: Transcribe (10-25%)
            await self._transcribe(session, session_dir)

            # Stage 3: Translate (25-35%)
            await self._translate(session, session_dir)

            # Stage 4: Annotate (35-45%)
            await self._annotate(session, session_dir)

            # Stage 5: Script (45-55%)
            await self._generate_script(session, session_dir)

            # Stage 6: TTS (55-70%)
            await self._generate_tts(session, session_dir)

            # Stage 7: Assemble Audio (70-80%)
            await self._assemble_audio(session, session_dir)

            # Stage 8: Generate Visual (80-90%)
            await self._generate_visual(session, session_dir)

            # Stage 9: Thumbnail (90-93%)
            await self._generate_thumbnail(session, session_dir)

            # Stage 10: Metadata (93-97%)
            await self._generate_metadata(session, session_dir)

            # Stage 11: Awaiting Review
            self.session_manager.update_session(
                session_id,
                status=MusicCommentaryStatus.AWAITING_REVIEW,
                progress=100.0,
            )
            logger.info(
                f"Music commentary pipeline complete for session {session_id} "
                f"— awaiting review"
            )

        except Exception as e:
            logger.error(
                f"Music commentary pipeline failed for session {session_id}: {e}"
            )
            self.session_manager.update_session(
                session_id,
                status=MusicCommentaryStatus.FAILED,
                error=str(e),
            )

    # ========== Stage 1: Download ==========

    async def _download(
        self, session: MusicCommentarySession, session_dir: Path
    ) -> None:
        """Download the song audio/video from URL."""
        self.session_manager.update_session(
            session.id,
            status=MusicCommentaryStatus.DOWNLOADING,
            progress=0.0,
        )
        start = time.time()

        source_dir = session_dir / "source"
        source_dir.mkdir(parents=True, exist_ok=True)

        result = await self.download_worker.download(
            url=session.song_config.url,
            output_dir=source_dir,
            extract_audio=True,
        )

        audio_path = result.get("audio_path")
        video_path = result.get("video_path")

        # Update session with downloaded metadata
        updates = {"progress": 10.0}
        if audio_path:
            updates["source_audio_path"] = str(audio_path)
        if video_path:
            updates["source_video_path"] = str(video_path)

        # Extract song metadata from download result
        title = result.get("title") or session.song_config.title
        artist = result.get("artist") or session.song_config.artist

        self.session_manager.update_session(session.id, **updates)

        # Update song_config with discovered metadata
        if title and not session.song_config.title:
            session.song_config.title = title
        if artist and not session.song_config.artist:
            session.song_config.artist = artist

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id, step_timings={"download": round(elapsed, 1)}
        )
        logger.info(f"Downloaded song for session {session.id}: {title}")

    # ========== Stage 2: Transcribe ==========

    async def _transcribe(
        self, session: MusicCommentarySession, session_dir: Path
    ) -> None:
        """Transcribe lyrics using Whisper."""
        self.session_manager.update_session(
            session.id,
            status=MusicCommentaryStatus.TRANSCRIBING,
            progress=10.0,
        )
        start = time.time()

        # Reload session to get audio path
        session = self.session_manager.get_session(session.id)
        audio_path = Path(session.source_audio_path)

        transcript = await self.whisper_worker.transcribe(
            audio_path=audio_path,
            language="en",
        )

        transcript_path = session_dir / "transcript" / "raw.json"
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(transcript.model_dump(mode="json"), f, indent=2, default=str)

        self.session_manager.update_session(
            session.id,
            transcript_path=str(transcript_path),
            progress=25.0,
        )

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id, step_timings={"transcribe": round(elapsed, 1)}
        )
        logger.info(
            f"Transcribed {len(transcript.segments)} segments for session {session.id}"
        )

    # ========== Stage 3: Translate ==========

    async def _translate(
        self, session: MusicCommentarySession, session_dir: Path
    ) -> None:
        """Translate lyrics to Chinese."""
        self.session_manager.update_session(
            session.id,
            status=MusicCommentaryStatus.TRANSLATING,
            progress=25.0,
        )
        start = time.time()

        session = self.session_manager.get_session(session.id)
        with open(session.transcript_path, "r", encoding="utf-8") as f:
            transcript_data = json.load(f)

        # Translate each segment's text
        segments = transcript_data.get("segments", [])
        translations = []
        for seg in segments:
            text = seg.get("text", "").strip()
            if not text:
                translations.append({"en": text, "zh": ""})
                continue
            zh_text, _, _ = await self.translation_worker.translate_text(
                text, target_language="zh-CN"
            )
            translations.append({"en": text, "zh": zh_text})

        translation_path = session_dir / "transcript" / "translations.json"
        with open(translation_path, "w", encoding="utf-8") as f:
            json.dump(translations, f, indent=2, ensure_ascii=False)

        self.session_manager.update_session(
            session.id,
            translation_path=str(translation_path),
            progress=35.0,
        )

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id, step_timings={"translate": round(elapsed, 1)}
        )
        logger.info(
            f"Translated {len(translations)} lines for session {session.id}"
        )

    # ========== Stage 4: Annotate ==========

    async def _annotate(
        self, session: MusicCommentarySession, session_dir: Path
    ) -> None:
        """Generate word/entity/idiom annotations for lyrics."""
        self.session_manager.update_session(
            session.id,
            status=MusicCommentaryStatus.ANNOTATING,
            progress=35.0,
        )
        start = time.time()

        session = self.session_manager.get_session(session.id)
        with open(session.translation_path, "r", encoding="utf-8") as f:
            translations = json.load(f)

        annotations = []
        if self.card_generator:
            for item in translations:
                en_text = item.get("en", "")
                if not en_text:
                    annotations.append({"words": [], "entities": [], "idioms": []})
                    continue
                try:
                    result = await self.card_generator.get_segment_annotations(
                        en_text
                    )
                    annotations.append(result.model_dump(mode="json"))
                except Exception as e:
                    logger.warning(f"Annotation failed for '{en_text[:50]}': {e}")
                    annotations.append({"words": [], "entities": [], "idioms": []})
        else:
            annotations = [
                {"words": [], "entities": [], "idioms": []}
                for _ in translations
            ]

        annotations_path = session_dir / "annotations" / "annotations.json"
        annotations_path.parent.mkdir(parents=True, exist_ok=True)
        with open(annotations_path, "w", encoding="utf-8") as f:
            json.dump(annotations, f, indent=2, ensure_ascii=False)

        self.session_manager.update_session(
            session.id,
            annotations_path=str(annotations_path),
            progress=45.0,
        )

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id, step_timings={"annotate": round(elapsed, 1)}
        )
        logger.info(f"Generated annotations for session {session.id}")

    # ========== Stage 5: Generate Script ==========

    async def _generate_script(
        self, session: MusicCommentarySession, session_dir: Path
    ) -> None:
        """Generate the commentary script using Grok LLM."""
        self.session_manager.update_session(
            session.id,
            status=MusicCommentaryStatus.SCRIPTING,
            progress=45.0,
        )
        start = time.time()

        session = self.session_manager.get_session(session.id)
        with open(session.translation_path, "r", encoding="utf-8") as f:
            translations = json.load(f)

        # Select lyrics lines (up to max_lyrics_lines)
        max_lines = session.script_config.max_lyrics_lines
        lyrics_lines = [
            t for t in translations if t.get("en", "").strip()
        ][:max_lines]

        lyrics_text = "\n".join(
            f"EN: {t['en']}\nZH: {t['zh']}" for t in lyrics_lines
        )

        title = session.song_config.title or "Unknown Song"
        artist = session.song_config.artist or "Unknown Artist"
        difficulty = session.script_config.difficulty.label

        prompt = (
            f"你是一位英语教学博主,正在制作一期解说视频,用中文解说英文歌曲的歌词。\n\n"
            f"歌曲信息:\n"
            f"- 歌名: {title}\n"
            f"- 歌手: {artist}\n"
            f"- 类型: {session.song_config.genre.label}\n"
            f"- 学习难度: {difficulty}\n\n"
            f"歌词(英中对照):\n{lyrics_text}\n\n"
            f"请用中文生成解说脚本,以下是 JSON 格式要求:\n"
            f'{{\n'
            f'  "hook_text": "开场白,吸引观众(2-3句话)",\n'
            f'  "background_text": "歌曲背景介绍(3-5句话)",\n'
            f'  "lyrics_explanations": [\n'
            f'    {{\n'
            f'      "lyric_en": "原始英文歌词",\n'
            f'      "lyric_zh": "中文翻译",\n'
            f'      "explanation": "中文讲解,包含词汇/语法/文化知识点(2-4句话)",\n'
            f'      "vocabulary": ["重点词汇1", "重点词汇2"]\n'
            f'    }}\n'
            f'  ],\n'
            f'  "deep_dive_text": "深入讲解一个核心知识点(3-5句话)",\n'
            f'  "outro_text": "结尾总结与号召(2-3句话)"\n'
            f'}}\n\n'
            f"请只返回 JSON,不要 markdown 代码块。"
        )

        script_data = await self._call_llm(prompt)

        script_path = session_dir / "script" / "script.json"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script_data, f, indent=2, ensure_ascii=False)

        self.session_manager.update_session(
            session.id,
            script_path=str(script_path),
            script=script_data,
            progress=55.0,
        )

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id, step_timings={"script": round(elapsed, 1)}
        )
        logger.info(f"Generated script for session {session.id}")

    # ========== Stage 6: TTS ==========

    async def _generate_tts(
        self, session: MusicCommentarySession, session_dir: Path
    ) -> None:
        """Generate Chinese narration audio using TTS."""
        self.session_manager.update_session(
            session.id,
            status=MusicCommentaryStatus.GENERATING_TTS,
            progress=55.0,
        )
        start = time.time()

        session = self.session_manager.get_session(session.id)
        if not session.script:
            raise RuntimeError("Script not generated yet")

        tts_dir = session_dir / "tts"
        tts_dir.mkdir(parents=True, exist_ok=True)

        # Collect all narration texts
        narration_parts = []
        if session.script.hook_text:
            narration_parts.append(("hook", session.script.hook_text))
        if session.script.background_text:
            narration_parts.append(("background", session.script.background_text))
        for i, exp in enumerate(session.script.lyrics_explanations):
            narration_parts.append((f"explanation_{i}", exp.explanation))
        if session.script.deep_dive_text:
            narration_parts.append(("deep_dive", session.script.deep_dive_text))
        if session.script.outro_text:
            narration_parts.append(("outro", session.script.outro_text))

        tts_segments = []
        if self.voice_clone_worker:
            reference_audio = session.tts_config.reference_audio
            if reference_audio:
                ref_path = Path(reference_audio)
            else:
                # Use the song audio as reference for voice consistency
                ref_path = Path(session.source_audio_path) if session.source_audio_path else None

            for name, text in narration_parts:
                output_path = tts_dir / f"{name}.wav"
                if ref_path and ref_path.exists():
                    await self.voice_clone_worker.synthesize(
                        text=text,
                        speaker_sample_path=ref_path,
                        output_path=output_path,
                        language="zh-cn",
                        speed=session.tts_config.speed,
                    )
                else:
                    # Generate silence placeholder
                    await self._generate_silence(3.0, output_path)
                tts_segments.append(str(output_path))
        else:
            # Generate silence placeholders if TTS not available
            for name, text in narration_parts:
                output_path = tts_dir / f"{name}.wav"
                estimated_duration = len(text) * 0.15  # rough estimate
                await self._generate_silence(max(1.0, estimated_duration), output_path)
                tts_segments.append(str(output_path))

        # Concatenate all TTS segments
        if tts_segments:
            combined_tts = tts_dir / "narration.wav"
            await self._concat_audio(tts_segments, combined_tts)
            self.session_manager.update_session(
                session.id, tts_audio_path=str(combined_tts)
            )

        self.session_manager.update_session(session.id, progress=70.0)

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id, step_timings={"tts": round(elapsed, 1)}
        )
        logger.info(
            f"Generated {len(tts_segments)} TTS segments for session {session.id}"
        )

    # ========== Stage 7: Assemble Audio ==========

    async def _assemble_audio(
        self, session: MusicCommentarySession, session_dir: Path
    ) -> None:
        """Mix song audio with narration (song low during narration, high during playback)."""
        self.session_manager.update_session(
            session.id,
            status=MusicCommentaryStatus.ASSEMBLING_AUDIO,
            progress=70.0,
        )
        start = time.time()

        session = self.session_manager.get_session(session.id)
        song_path = Path(session.source_audio_path)
        narration_path = Path(session.tts_audio_path) if session.tts_audio_path else None

        output_path = session_dir / "output" / "mixed_audio.wav"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if narration_path and narration_path.exists():
            song_vol_narration = session.audio_mix_config.song_volume_during_narration
            narration_vol = session.audio_mix_config.narration_volume

            # Simple overlay: song at reduced volume + narration at full volume
            cmd = [
                "ffmpeg", "-y",
                "-i", str(song_path),
                "-i", str(narration_path),
                "-filter_complex",
                f"[0:a]volume={song_vol_narration}[song];"
                f"[1:a]volume={narration_vol}[narr];"
                f"[song][narr]amix=inputs=2:duration=longest:normalize=0[out]",
                "-map", "[out]",
                str(output_path),
            ]
            await self._run_ffmpeg(cmd, timeout=300)
        else:
            # No narration — just use song audio
            import shutil
            shutil.copy2(str(song_path), str(output_path))

        self.session_manager.update_session(
            session.id,
            final_audio_path=str(output_path),
            progress=80.0,
        )

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id, step_timings={"assemble_audio": round(elapsed, 1)}
        )
        logger.info(f"Assembled audio for session {session.id}")

    # ========== Stage 8: Generate Visual ==========

    async def _generate_visual(
        self, session: MusicCommentarySession, session_dir: Path
    ) -> None:
        """Generate video: source video with subtitles or album art + Ken Burns."""
        self.session_manager.update_session(
            session.id,
            status=MusicCommentaryStatus.GENERATING_VISUAL,
            progress=80.0,
        )
        start = time.time()

        session = self.session_manager.get_session(session.id)
        audio_path = Path(session.final_audio_path)
        output_path = session_dir / "output" / "final.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        source_video = (
            Path(session.source_video_path)
            if session.source_video_path
            else None
        )

        if source_video and source_video.exists():
            # Use source video with new audio track
            cmd = [
                "ffmpeg", "-y",
                "-i", str(source_video),
                "-i", str(audio_path),
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                "-movflags", "+faststart",
                str(output_path),
            ]
        else:
            # Generate a simple video from solid background + audio
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i",
                "color=c=0x1a1a2e:s=1920x1080:d=600",
                "-i", str(audio_path),
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                "-movflags", "+faststart",
                str(output_path),
            ]

        if settings.ffmpeg_nvenc:
            cmd = self._try_nvenc(cmd)

        await self._run_ffmpeg(cmd, timeout=3600)

        self.session_manager.update_session(
            session.id,
            final_video_path=str(output_path),
            progress=90.0,
        )

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id, step_timings={"visual": round(elapsed, 1)}
        )
        logger.info(f"Generated video for session {session.id}")

    # ========== Stage 9: Thumbnail ==========

    async def _generate_thumbnail(
        self, session: MusicCommentarySession, session_dir: Path
    ) -> None:
        """Generate thumbnail from video frame + text overlay."""
        self.session_manager.update_session(session.id, progress=90.0)
        start = time.time()

        session = self.session_manager.get_session(session.id)
        video_path = Path(session.final_video_path)
        thumbnail_path = session_dir / "output" / "thumbnail.png"

        cmd = [
            "ffmpeg", "-y",
            "-ss", "5",
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(thumbnail_path),
        ]
        await self._run_ffmpeg(cmd, timeout=60)

        # Add text overlay
        title = session.song_config.title or "English Song"
        await self._add_thumbnail_text(thumbnail_path, title)

        self.session_manager.update_session(
            session.id,
            thumbnail_path=str(thumbnail_path),
            progress=93.0,
        )

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id, step_timings={"thumbnail": round(elapsed, 1)}
        )

    async def _add_thumbnail_text(self, thumbnail_path: Path, title: str) -> None:
        """Add text overlay to thumbnail using PIL."""
        try:
            from PIL import Image, ImageDraw, ImageFont

            img = Image.open(thumbnail_path)
            draw = ImageDraw.Draw(img)

            font_size = img.width // 20
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    font_size,
                )
            except (OSError, IOError):
                font = ImageFont.load_default()

            text = f"🎵 {title} | 听歌学英语"

            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            x = (img.width - text_width) // 2
            y = img.height - font_size * 2

            draw.text((x + 2, y + 2), text, fill="black", font=font)
            draw.text((x, y), text, fill="white", font=font)

            img.save(thumbnail_path)
        except ImportError:
            logger.warning("PIL not available, skipping thumbnail text overlay")

    # ========== Stage 10: Metadata ==========

    async def _generate_metadata(
        self, session: MusicCommentarySession, session_dir: Path
    ) -> None:
        """Generate YouTube title, description, and tags using LLM."""
        self.session_manager.update_session(
            session.id,
            status=MusicCommentaryStatus.GENERATING_METADATA,
            progress=93.0,
        )
        start = time.time()

        session = self.session_manager.get_session(session.id)
        metadata = await self._generate_youtube_metadata(session)

        self.session_manager.update_session(
            session.id,
            title=metadata.get("title", ""),
            description=metadata.get("description", ""),
            tags=metadata.get("tags", []),
            progress=97.0,
        )

        elapsed = time.time() - start
        self.session_manager.update_session(
            session.id, step_timings={"metadata": round(elapsed, 1)}
        )

    async def _generate_youtube_metadata(
        self, session: MusicCommentarySession
    ) -> dict:
        """Call LLM to generate YouTube metadata."""
        title = session.song_config.title or "English Song"
        artist = session.song_config.artist or "Unknown Artist"
        genre = session.song_config.genre.label
        difficulty = session.script_config.difficulty.label

        prompt = (
            f"为一个英语学习 YouTube 短视频生成元数据。\n\n"
            f"歌曲: {title} by {artist}\n"
            f"类型: {genre}\n"
            f"难度: {difficulty}\n\n"
            f"返回 JSON:\n"
            f'{{\n'
            f'  "title": "吸引人的中文标题(最多80字符),包含歌名和学英语",\n'
            f'  "description": "SEO 优化的描述(200-500字符),含 hashtags",\n'
            f'  "tags": ["10-15个标签,中英文混合"]\n'
            f'}}\n\n'
            f"只返回 JSON,不要 markdown。"
        )

        try:
            return await self._call_llm(prompt)
        except Exception as e:
            logger.warning(f"LLM metadata generation failed: {e}, using defaults")
            return {
                "title": f"听歌学英语 | {title} - {artist}",
                "description": (
                    f"通过 {artist} 的经典歌曲 {title} 来学习英语！"
                    f"本期我们将逐句解析歌词中的实用表达和语法知识点。\n\n"
                    f"#英语学习 #听歌学英语 #{genre}"
                ),
                "tags": [
                    "英语学习", "听歌学英语", "English learning",
                    "learn English with songs", title, artist, genre,
                    "英文歌曲", "歌词解析", "英语教学",
                ],
            }

    # ========== YouTube Publishing ==========

    async def publish_to_youtube(self, session_id: str) -> dict:
        """Publish a reviewed session to YouTube."""
        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if session.status not in (
            MusicCommentaryStatus.AWAITING_REVIEW,
            MusicCommentaryStatus.FAILED,
        ):
            raise ValueError(
                f"Session not in reviewable state: {session.status.value}"
            )

        if not session.final_video_path or not Path(session.final_video_path).exists():
            raise ValueError("No video file available for upload")

        if not self.youtube_worker:
            raise RuntimeError("YouTube worker not available")

        self.session_manager.update_session(
            session_id,
            status=MusicCommentaryStatus.PUBLISHING,
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
                thumbnail_path=(
                    Path(session.thumbnail_path) if session.thumbnail_path else None
                ),
                default_language="zh",
            )

            self.session_manager.update_session(
                session_id,
                status=MusicCommentaryStatus.PUBLISHED,
                youtube_video_id=result.get("video_id"),
                youtube_url=result.get("url"),
                progress=100.0,
            )
            logger.info(
                f"Published music commentary session {session_id} "
                f"to YouTube: {result.get('url')}"
            )
            return result

        except Exception as e:
            logger.error(
                f"YouTube publish failed for session {session_id}: {e}"
            )
            self.session_manager.update_session(
                session_id,
                status=MusicCommentaryStatus.FAILED,
                error=f"YouTube upload failed: {e}",
            )
            raise

    # ========== Utility Methods ==========

    async def _call_llm(self, prompt: str) -> dict:
        """Call Grok/OpenAI LLM and parse JSON response."""
        import httpx

        async with httpx.AsyncClient(timeout=60.0) as client:
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

            # Handle potential markdown code blocks
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content.strip())

    async def _generate_silence(self, duration: float, output_path: Path) -> None:
        """Generate a silence WAV file as a placeholder."""
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
            "-t", str(duration),
            str(output_path),
        ]
        await self._run_ffmpeg(cmd, timeout=30)

    async def _concat_audio(
        self, segment_paths: List[str], output_path: Path
    ) -> None:
        """Concatenate audio files using ffmpeg."""
        if len(segment_paths) == 1:
            import shutil
            shutil.copy2(segment_paths[0], str(output_path))
            return

        # Create concat list file
        list_path = output_path.parent / "concat_list.txt"
        with open(list_path, "w") as f:
            for sp in segment_paths:
                f.write(f"file '{sp}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            str(output_path),
        ]
        await self._run_ffmpeg(cmd, timeout=120)
        list_path.unlink(missing_ok=True)

    def _try_nvenc(self, cmd: list) -> list:
        """Replace libx264 with h264_nvenc if possible."""
        new_cmd = []
        for item in cmd:
            if item == "libx264":
                new_cmd.append("h264_nvenc")
            elif item == "-crf":
                new_cmd.append("-cq")
            else:
                new_cmd.append(item)
        return new_cmd

    async def _run_ffmpeg(self, cmd: list, timeout: int = 300) -> None:
        """Run an ffmpeg command asynchronously."""
        loop = asyncio.get_event_loop()

        def _run():
            logger.debug(f"Running ffmpeg: {' '.join(cmd[:10])}...")
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"ffmpeg failed (rc={result.returncode}): "
                    f"{result.stderr[-500:]}"
                )

        await loop.run_in_executor(_pipeline_executor, _run)
