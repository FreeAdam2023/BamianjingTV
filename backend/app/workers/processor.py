"""Job processor worker.

Handles the main processing pipeline for video jobs.
"""

import json
from pathlib import Path
from typing import Callable, TYPE_CHECKING

from loguru import logger

from app.config import settings
from app.models.job import Job, JobStatus
from app.models.transcript import (
    Transcript,
    Segment,
    DiarizedTranscript,
    DiarizedSegment,
    TranslatedTranscript,
)

if TYPE_CHECKING:
    from app.services.job_manager import JobManager
    from app.services.timeline_manager import TimelineManager
    from app.services.queue import JobQueue
    from app.workers.download import DownloadWorker
    from app.workers.whisper import WhisperWorker
    from app.workers.diarization import DiarizationWorker
    from app.workers.translation import TranslationWorker


def load_json_model(path: Path, model_class):
    """Load a Pydantic model from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return model_class(**json.load(f))


async def process_job(
    job_id: str,
    job_manager: "JobManager",
    job_queue: "JobQueue",
    timeline_manager: "TimelineManager",
    download_worker: "DownloadWorker",
    whisper_worker: "WhisperWorker",
    diarization_worker: "DiarizationWorker",
    translation_worker: "TranslationWorker",
) -> None:
    """Process a job through the pipeline.

    Simplified for SceneMind (learning video factory):
    1. Download video
    2. Transcribe with Whisper
    3. Diarize speakers
    4. Translate to Chinese
    5. Create Timeline and pause for UI review

    The export stage is triggered separately via /timelines/{id}/export.
    Supports resuming from any stage if files already exist.
    """
    job = job_manager.get_job(job_id)
    if not job:
        return

    job_dir = job.get_job_dir(settings.jobs_dir)
    transcript_dir = job_dir / "transcript"
    translation_dir = job_dir / "translation"

    def check_cancelled() -> bool:
        """Check if job was cancelled and update status if so."""
        fresh_job = job_manager.get_job(job_id)
        if fresh_job and fresh_job.cancel_requested:
            return True
        return False

    try:
        # ============ Stage 1: Download (10%) ============
        await job_manager.update_status(job, JobStatus.DOWNLOADING, 0.10)
        job.start_step("download")

        # If user chose to skip diarization, try to fetch YouTube subtitles
        fetch_subtitles = job.skip_diarization
        download_result = await download_worker.download(
            url=job.url,
            output_dir=job_dir,
            fetch_subtitles=fetch_subtitles,
            subtitle_langs=["en", "en-US", "en-GB"],
        )

        job.source_video = download_result["video_path"]
        job.source_audio = download_result["audio_path"]
        job.title = download_result["title"]
        job.duration = download_result["duration"]
        job.channel = download_result["channel"]
        job.end_step("download")
        job_manager.save_job(job)

        # Track if we're using YouTube subtitles (skip Whisper)
        use_youtube_subtitles = download_result.get("has_youtube_subtitles", False)
        youtube_subtitle_path = download_result.get("subtitle_path")

        if use_youtube_subtitles:
            logger.info(f"YouTube subtitles available, will skip Whisper transcription: {job_id}")

        if check_cancelled():
            await job_manager.update_status(job, JobStatus.CANCELLED)
            logger.info(f"Job {job_id} cancelled after download stage")
            return

        # ============ Stage 2: Transcribe (30%) ============
        raw_path = transcript_dir / "raw.json"
        job.start_step("transcribe")

        if raw_path.exists():
            logger.info(f"Transcript already exists, skipping transcription: {job_id}")
            transcript = load_json_model(raw_path, Transcript)
        elif use_youtube_subtitles and youtube_subtitle_path:
            # Use YouTube subtitles instead of Whisper
            logger.info(f"Using YouTube subtitles instead of Whisper: {job_id}")
            youtube_segments = await download_worker.parse_youtube_subtitles(
                Path(youtube_subtitle_path)
            )
            # Convert to Transcript format
            transcript = Transcript(
                language="en",
                segments=[
                    Segment(
                        start=seg["start"],
                        end=seg["end"],
                        text=seg["text"],
                    )
                    for seg in youtube_segments
                ],
            )
            await whisper_worker.save_transcript(transcript, raw_path)
            logger.info(f"Saved YouTube subtitles as transcript: {len(transcript.segments)} segments")
            # Track that we used YouTube subtitles
            job.used_youtube_subtitles = True
        else:
            await job_manager.update_status(job, JobStatus.TRANSCRIBING, 0.30)
            transcript = await whisper_worker.transcribe(
                audio_path=Path(job.source_audio),
            )
            await whisper_worker.save_transcript(transcript, raw_path)

        job.transcript_raw = str(raw_path)
        job.end_step("transcribe")
        job_manager.save_job(job)

        if check_cancelled():
            await job_manager.update_status(job, JobStatus.CANCELLED)
            logger.info(f"Job {job_id} cancelled after transcription stage")
            return

        # ============ Stage 3: Diarize (50%) ============
        diarized_path = transcript_dir / "diarized.json"
        job.start_step("diarize")

        if diarized_path.exists():
            logger.info(f"Diarization file already exists, skipping diarization: {job_id}")
            diarized_transcript = load_json_model(diarized_path, DiarizedTranscript)
        elif job.skip_diarization:
            # Skip diarization - convert transcript to diarized format without speakers
            logger.info(f"User chose to skip speaker diarization: {job_id}")
            diarized_transcript = DiarizedTranscript(
                language=transcript.language,
                num_speakers=1,
                segments=[
                    DiarizedSegment(
                        start=seg.start,
                        end=seg.end,
                        text=seg.text,
                        speaker="SPEAKER_0",
                    )
                    for seg in transcript.segments
                ],
            )
            await diarization_worker.save_diarized_transcript(
                diarized_transcript, diarized_path
            )
        else:
            await job_manager.update_status(job, JobStatus.DIARIZING, 0.50)
            diarization_segments = await diarization_worker.diarize(
                audio_path=Path(job.source_audio),
            )
            diarized_transcript = await diarization_worker.merge_with_transcript(
                transcript=transcript,
                diarization_segments=diarization_segments,
            )
            await diarization_worker.save_diarized_transcript(
                diarized_transcript, diarized_path
            )

        job.transcript_diarized = str(diarized_path)
        job.end_step("diarize")
        job_manager.save_job(job)

        if check_cancelled():
            await job_manager.update_status(job, JobStatus.CANCELLED)
            logger.info(f"Job {job_id} cancelled after diarization stage")
            return

        # ============ Stage 4: Translate (70%) ============
        # Determine target language code
        # zh-TW = Traditional Chinese (default), zh-CN = Simplified Chinese
        if job.target_language == "zh":
            target_lang_code = "zh-TW" if job.use_traditional_chinese else "zh-CN"
        else:
            target_lang_code = job.target_language

        translation_path = translation_dir / f"{target_lang_code}.json"
        job.start_step("translate")

        if translation_path.exists():
            logger.info(f"Translation file already exists, skipping translation: {job_id}")
            translated_transcript = load_json_model(translation_path, TranslatedTranscript)
        else:
            await job_manager.update_status(job, JobStatus.TRANSLATING, 0.70)
            translated_transcript = await translation_worker.translate_transcript(
                transcript=diarized_transcript,
                target_language=target_lang_code,
                job=job,  # Pass job for cost tracking
            )
            await translation_worker.save_translation(
                translated_transcript, translation_path
            )

        job.translation = str(translation_path)
        job.end_step("translate")
        job_manager.save_job(job)

        if check_cancelled():
            await job_manager.update_status(job, JobStatus.CANCELLED)
            logger.info(f"Job {job_id} cancelled after translation stage")
            return

        # ============ Stage 5: Create Timeline (80%) ============
        # Check if timeline already exists
        if job.timeline_id and timeline_manager.get_timeline(job.timeline_id):
            logger.info(f"Timeline already exists, skipping creation: {job.timeline_id}")
            timeline = timeline_manager.get_timeline(job.timeline_id)
        else:
            timeline = timeline_manager.create_from_transcript(
                job_id=job.id,
                source_url=job.url,
                source_title=job.title,
                source_duration=job.duration,
                translated_transcript=translated_transcript,
                mode=job.mode.value if hasattr(job.mode, 'value') else job.mode,
            )
            job.timeline_id = timeline.timeline_id
            job_manager.save_job(job)

        # ============ PAUSE: Awaiting Review ============
        await job_manager.update_status(job, JobStatus.AWAITING_REVIEW, 0.80)
        logger.info(
            f"Job {job_id} ready for review. "
            f"Timeline: {timeline.timeline_id} ({len(timeline.segments)} segments)"
        )

        # Pipeline pauses here. Export is triggered via /timelines/{id}/export

    except Exception as e:
        logger.exception(f"Job {job_id} failed: {e}")
        # Try retry logic
        should_retry = await job_manager.handle_error(
            job, e, stage=job.status.value
        )
        if should_retry:
            # Re-queue the job
            await job_queue.add(job_id, priority=1)
