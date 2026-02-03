"""Dubbing API endpoints."""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import get_config
from app.models.timeline import Timeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/timelines/{timeline_id}/dubbing", tags=["dubbing"])

# Dependencies (set during startup)
_timeline_manager = None
_audio_separation_worker = None
_voice_clone_worker = None
_audio_mixer_worker = None


def set_timeline_manager(manager):
    global _timeline_manager
    _timeline_manager = manager


def set_audio_separation_worker(worker):
    global _audio_separation_worker
    _audio_separation_worker = worker


def set_voice_clone_worker(worker):
    global _voice_clone_worker
    _voice_clone_worker = worker


def set_audio_mixer_worker(worker):
    global _audio_mixer_worker
    _audio_mixer_worker = worker


def _get_timeline(timeline_id: str) -> Timeline:
    if _timeline_manager is None:
        raise HTTPException(status_code=503, detail="Timeline manager not initialized")
    timeline = _timeline_manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")
    return timeline


def _get_dubbing_dir(timeline_id: str) -> Path:
    config = get_config()
    return config.data_dir / "dubbing" / timeline_id


# ============ Request/Response Models ============


class DubbingConfig(BaseModel):
    """Dubbing configuration for a timeline."""
    bgm_volume: float = Field(default=0.3, ge=0, le=1)
    sfx_volume: float = Field(default=0.5, ge=0, le=1)
    vocal_volume: float = Field(default=1.0, ge=0, le=1)
    target_language: str = "zh-cn"
    keep_bgm: bool = True
    keep_sfx: bool = True


class DubbingConfigUpdate(BaseModel):
    """Request to update dubbing config."""
    bgm_volume: Optional[float] = Field(default=None, ge=0, le=1)
    sfx_volume: Optional[float] = Field(default=None, ge=0, le=1)
    vocal_volume: Optional[float] = Field(default=None, ge=0, le=1)
    target_language: Optional[str] = None
    keep_bgm: Optional[bool] = None
    keep_sfx: Optional[bool] = None


class SpeakerVoiceConfig(BaseModel):
    """Voice configuration for a speaker."""
    speaker_id: str
    display_name: str = ""
    voice_sample_path: Optional[str] = None
    is_enabled: bool = True


class SpeakerVoiceUpdate(BaseModel):
    """Request to update speaker voice config."""
    display_name: Optional[str] = None
    is_enabled: Optional[bool] = None


class SeparationStatus(BaseModel):
    """Status of audio separation."""
    status: str  # pending, processing, completed, failed
    vocals_path: Optional[str] = None
    bgm_path: Optional[str] = None
    sfx_path: Optional[str] = None
    error: Optional[str] = None


class DubbingStatus(BaseModel):
    """Status of dubbing process."""
    status: str  # pending, separating, extracting_samples, synthesizing, mixing, completed, failed
    progress: float = 0  # 0-100
    current_step: Optional[str] = None
    dubbed_segments: int = 0
    total_segments: int = 0
    error: Optional[str] = None


class PreviewRequest(BaseModel):
    """Request to preview a dubbed segment."""
    segment_id: int
    text: Optional[str] = None  # Override text


class PreviewResponse(BaseModel):
    """Response with preview audio URL."""
    segment_id: int
    audio_url: str
    duration: float


# ============ In-memory state for dubbing jobs ============

_dubbing_configs: Dict[str, DubbingConfig] = {}
_dubbing_status: Dict[str, DubbingStatus] = {}
_separation_status: Dict[str, SeparationStatus] = {}
_speaker_configs: Dict[str, Dict[str, SpeakerVoiceConfig]] = {}


# ============ Config Endpoints ============


@router.get("/config", response_model=DubbingConfig)
async def get_dubbing_config(timeline_id: str):
    """Get dubbing configuration for a timeline."""
    _get_timeline(timeline_id)  # Validate timeline exists

    if timeline_id not in _dubbing_configs:
        _dubbing_configs[timeline_id] = DubbingConfig()

    return _dubbing_configs[timeline_id]


@router.patch("/config", response_model=DubbingConfig)
async def update_dubbing_config(timeline_id: str, update: DubbingConfigUpdate):
    """Update dubbing configuration."""
    _get_timeline(timeline_id)

    if timeline_id not in _dubbing_configs:
        _dubbing_configs[timeline_id] = DubbingConfig()

    config = _dubbing_configs[timeline_id]
    update_data = update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(config, key, value)

    return config


# ============ Speaker Endpoints ============


@router.get("/speakers", response_model=List[SpeakerVoiceConfig])
async def get_speakers(timeline_id: str):
    """Get speaker list with voice configurations."""
    timeline = _get_timeline(timeline_id)

    # Get unique speakers from segments
    speakers = set()
    for seg in timeline.segments:
        if seg.speaker:
            speakers.add(seg.speaker)

    # Initialize configs if needed
    if timeline_id not in _speaker_configs:
        _speaker_configs[timeline_id] = {}

    # Build response with configs
    result = []
    for speaker_id in sorted(speakers):
        if speaker_id not in _speaker_configs[timeline_id]:
            # Use speaker_names from timeline if available
            display_name = timeline.speaker_names.get(speaker_id, f"Speaker {speaker_id}")
            _speaker_configs[timeline_id][speaker_id] = SpeakerVoiceConfig(
                speaker_id=speaker_id,
                display_name=display_name,
            )

        result.append(_speaker_configs[timeline_id][speaker_id])

    return result


@router.patch("/speakers/{speaker_id}", response_model=SpeakerVoiceConfig)
async def update_speaker(timeline_id: str, speaker_id: str, update: SpeakerVoiceUpdate):
    """Update speaker voice configuration."""
    _get_timeline(timeline_id)

    if timeline_id not in _speaker_configs:
        _speaker_configs[timeline_id] = {}

    if speaker_id not in _speaker_configs[timeline_id]:
        _speaker_configs[timeline_id][speaker_id] = SpeakerVoiceConfig(speaker_id=speaker_id)

    config = _speaker_configs[timeline_id][speaker_id]
    update_data = update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(config, key, value)

    return config


# ============ Separation Endpoints ============


@router.get("/separation/status", response_model=SeparationStatus)
async def get_separation_status(timeline_id: str):
    """Get audio separation status."""
    _get_timeline(timeline_id)

    if timeline_id not in _separation_status:
        return SeparationStatus(status="pending")

    return _separation_status[timeline_id]


@router.post("/separate")
async def trigger_separation(timeline_id: str, background_tasks: BackgroundTasks):
    """Trigger audio separation for the timeline's video."""
    timeline = _get_timeline(timeline_id)

    if _audio_separation_worker is None:
        raise HTTPException(status_code=503, detail="Audio separation worker not initialized")

    # Check if already processing
    if timeline_id in _separation_status:
        status = _separation_status[timeline_id]
        if status.status == "processing":
            return {"message": "Separation already in progress", "status": "processing"}

    # Get video path from job
    config = get_config()
    video_path = config.jobs_dir / timeline.job_id / "source" / "video.mp4"

    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Source video not found")

    # Initialize status
    _separation_status[timeline_id] = SeparationStatus(status="processing")

    # Run separation in background
    background_tasks.add_task(_run_separation, timeline_id, video_path)

    return {"message": "Audio separation started", "status": "processing"}


async def _run_separation(timeline_id: str, video_path: Path):
    """Background task to run audio separation."""
    try:
        dubbing_dir = _get_dubbing_dir(timeline_id)
        dubbing_dir.mkdir(parents=True, exist_ok=True)

        # Extract audio first
        audio_path = dubbing_dir / "audio.wav"
        await _audio_separation_worker.extract_audio(video_path, audio_path)

        # Separate audio
        vocals_path, bgm_path, sfx_path = await _audio_separation_worker.separate(
            audio_path, dubbing_dir
        )

        _separation_status[timeline_id] = SeparationStatus(
            status="completed",
            vocals_path=str(vocals_path),
            bgm_path=str(bgm_path),
            sfx_path=str(sfx_path),
        )

        logger.info(f"Audio separation completed for timeline {timeline_id}")

    except Exception as e:
        logger.error(f"Audio separation failed for {timeline_id}: {e}")
        _separation_status[timeline_id] = SeparationStatus(
            status="failed",
            error=str(e),
        )


# ============ Audio File Endpoints ============


@router.get("/audio/{audio_type}")
async def get_audio(timeline_id: str, audio_type: str):
    """
    Get separated or dubbed audio file.

    audio_type: vocals, bgm, sfx, dubbed, mixed
    """
    _get_timeline(timeline_id)
    dubbing_dir = _get_dubbing_dir(timeline_id)

    audio_files = {
        "vocals": dubbing_dir / "vocals.wav",
        "bgm": dubbing_dir / "bgm.wav",
        "sfx": dubbing_dir / "sfx.wav",
        "dubbed": dubbing_dir / "dubbed_vocals_track.wav",
        "mixed": dubbing_dir / "mixed.wav",
    }

    if audio_type not in audio_files:
        raise HTTPException(status_code=400, detail=f"Invalid audio type: {audio_type}")

    audio_path = audio_files[audio_type]
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail=f"Audio file not found: {audio_type}")

    return FileResponse(audio_path, media_type="audio/wav")


# ============ Preview Endpoint ============


@router.post("/preview", response_model=PreviewResponse)
async def preview_segment(timeline_id: str, request: PreviewRequest):
    """Preview dubbed audio for a single segment."""
    timeline = _get_timeline(timeline_id)

    if _voice_clone_worker is None:
        raise HTTPException(status_code=503, detail="Voice clone worker not initialized")

    # Find segment
    segment = None
    for seg in timeline.segments:
        if seg.id == request.segment_id:
            segment = seg
            break

    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Get speaker sample
    if timeline_id not in _speaker_configs or segment.speaker not in _speaker_configs.get(timeline_id, {}):
        raise HTTPException(status_code=400, detail="Speaker voice sample not available")

    speaker_config = _speaker_configs[timeline_id].get(segment.speaker)
    if not speaker_config or not speaker_config.voice_sample_path:
        raise HTTPException(
            status_code=400,
            detail="Speaker voice sample not extracted. Run 'generate' first to extract samples."
        )

    sample_path = Path(speaker_config.voice_sample_path)
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="Speaker sample file not found")

    # Get text to synthesize
    text = request.text or segment.zh or segment.en
    if not text:
        raise HTTPException(status_code=400, detail="No text to synthesize")

    # Synthesize preview
    dubbing_dir = _get_dubbing_dir(timeline_id)
    preview_path = dubbing_dir / "previews" / f"segment_{segment.id}_preview.wav"
    preview_path.parent.mkdir(parents=True, exist_ok=True)

    target_duration = segment.end - segment.start
    config = _dubbing_configs.get(timeline_id, DubbingConfig())

    _, duration = await _voice_clone_worker.synthesize_segment(
        text=text,
        speaker_sample_path=sample_path,
        target_duration=target_duration,
        output_path=preview_path,
        language=config.target_language,
    )

    return PreviewResponse(
        segment_id=segment.id,
        audio_url=f"/timelines/{timeline_id}/dubbing/preview/{segment.id}",
        duration=duration,
    )


@router.get("/preview/{segment_id}")
async def get_preview_audio(timeline_id: str, segment_id: int):
    """Get preview audio file for a segment."""
    dubbing_dir = _get_dubbing_dir(timeline_id)
    preview_path = dubbing_dir / "previews" / f"segment_{segment_id}_preview.wav"

    if not preview_path.exists():
        raise HTTPException(status_code=404, detail="Preview not found")

    return FileResponse(preview_path, media_type="audio/wav")


# ============ Generate Endpoint ============


@router.get("/status", response_model=DubbingStatus)
async def get_dubbing_status(timeline_id: str):
    """Get dubbing generation status."""
    _get_timeline(timeline_id)

    if timeline_id not in _dubbing_status:
        return DubbingStatus(status="pending")

    return _dubbing_status[timeline_id]


@router.post("/generate")
async def generate_dubbed_video(timeline_id: str, background_tasks: BackgroundTasks):
    """
    Generate full dubbed video.

    This runs the complete dubbing pipeline:
    1. Separate audio (if not done)
    2. Extract speaker samples
    3. Synthesize dubbed audio for each segment
    4. Mix with BGM and SFX
    5. Replace video audio
    """
    timeline = _get_timeline(timeline_id)

    # Check dependencies
    if _voice_clone_worker is None:
        raise HTTPException(status_code=503, detail="Voice clone worker not initialized")
    if _audio_mixer_worker is None:
        raise HTTPException(status_code=503, detail="Audio mixer worker not initialized")

    # Check if already processing
    if timeline_id in _dubbing_status:
        status = _dubbing_status[timeline_id]
        if status.status in ("separating", "extracting_samples", "synthesizing", "mixing"):
            return {"message": "Dubbing already in progress", "status": status.status}

    # Initialize status
    total_segments = len([s for s in timeline.segments if s.state != "drop"])
    _dubbing_status[timeline_id] = DubbingStatus(
        status="separating",
        total_segments=total_segments,
    )

    # Run dubbing in background
    background_tasks.add_task(_run_dubbing_pipeline, timeline_id)

    return {"message": "Dubbing generation started", "status": "separating"}


async def _run_dubbing_pipeline(timeline_id: str):
    """Background task to run the full dubbing pipeline."""
    try:
        timeline = _timeline_manager.get_timeline(timeline_id)
        config = _dubbing_configs.get(timeline_id, DubbingConfig())
        dubbing_dir = _get_dubbing_dir(timeline_id)

        # Step 1: Ensure audio is separated
        _dubbing_status[timeline_id].current_step = "Separating audio"
        if timeline_id not in _separation_status or _separation_status[timeline_id].status != "completed":
            video_path = get_config().jobs_dir / timeline.job_id / "source" / "video.mp4"
            await _run_separation(timeline_id, video_path)

        sep_status = _separation_status.get(timeline_id)
        if not sep_status or sep_status.status != "completed":
            raise RuntimeError("Audio separation failed")

        # Step 2: Extract speaker samples
        _dubbing_status[timeline_id].status = "extracting_samples"
        _dubbing_status[timeline_id].current_step = "Extracting speaker samples"
        _dubbing_status[timeline_id].progress = 10

        segments_data = [
            {"speaker": s.speaker, "start": s.start, "end": s.end}
            for s in timeline.segments
        ]
        speakers = set(s.speaker for s in timeline.segments if s.speaker)

        samples_dir = dubbing_dir / "speaker_samples"
        speaker_samples = {}

        for speaker_id in speakers:
            sample_path = await _voice_clone_worker.extract_speaker_sample(
                audio_path=Path(sep_status.vocals_path),
                segments=segments_data,
                speaker_id=speaker_id,
                output_dir=samples_dir,
            )
            if sample_path:
                speaker_samples[speaker_id] = sample_path
                # Update speaker config
                if timeline_id not in _speaker_configs:
                    _speaker_configs[timeline_id] = {}
                if speaker_id not in _speaker_configs[timeline_id]:
                    _speaker_configs[timeline_id][speaker_id] = SpeakerVoiceConfig(
                        speaker_id=speaker_id
                    )
                _speaker_configs[timeline_id][speaker_id].voice_sample_path = str(sample_path)

        # Step 3: Synthesize dubbed audio
        _dubbing_status[timeline_id].status = "synthesizing"
        _dubbing_status[timeline_id].current_step = "Synthesizing dubbed audio"
        _dubbing_status[timeline_id].progress = 30

        segments_to_dub = [
            {
                "id": s.id,
                "speaker": s.speaker,
                "start": s.start,
                "end": s.end,
                "zh": s.zh,
                "en": s.en,
            }
            for s in timeline.segments
            if s.state != "drop"
        ]

        dubbed_dir = dubbing_dir / "dubbed_segments"
        dubbed_segments = await _voice_clone_worker.dub_segments(
            segments=segments_to_dub,
            speaker_samples=speaker_samples,
            output_dir=dubbed_dir,
            language=config.target_language,
        )

        _dubbing_status[timeline_id].dubbed_segments = len([s for s in dubbed_segments if s.get("dubbed_path")])
        _dubbing_status[timeline_id].progress = 70

        # Step 4: Mix audio
        _dubbing_status[timeline_id].status = "mixing"
        _dubbing_status[timeline_id].current_step = "Mixing audio tracks"

        mixed_path = dubbing_dir / "mixed.wav"
        await _audio_mixer_worker.mix_dubbed_audio(
            dubbed_segments=dubbed_segments,
            bgm_path=Path(sep_status.bgm_path) if config.keep_bgm else None,
            sfx_path=Path(sep_status.sfx_path) if config.keep_sfx else None,
            output_path=mixed_path,
            total_duration=timeline.source_duration,
            bgm_volume=config.bgm_volume,
            sfx_volume=config.sfx_volume,
            vocal_volume=config.vocal_volume,
        )

        _dubbing_status[timeline_id].progress = 90

        # Step 5: Replace video audio
        _dubbing_status[timeline_id].current_step = "Finalizing video"

        video_path = get_config().jobs_dir / timeline.job_id / "source" / "video.mp4"
        output_path = dubbing_dir / "dubbed_video.mp4"

        await _audio_mixer_worker.replace_video_audio(
            video_path=video_path,
            audio_path=mixed_path,
            output_path=output_path,
        )

        _dubbing_status[timeline_id] = DubbingStatus(
            status="completed",
            progress=100,
            dubbed_segments=_dubbing_status[timeline_id].dubbed_segments,
            total_segments=_dubbing_status[timeline_id].total_segments,
        )

        logger.info(f"Dubbing completed for timeline {timeline_id}")

    except Exception as e:
        logger.error(f"Dubbing failed for {timeline_id}: {e}")
        _dubbing_status[timeline_id] = DubbingStatus(
            status="failed",
            error=str(e),
        )


# ============ Output Endpoint ============


@router.get("/output")
async def get_dubbed_video(timeline_id: str):
    """Get the final dubbed video."""
    _get_timeline(timeline_id)
    dubbing_dir = _get_dubbing_dir(timeline_id)
    output_path = dubbing_dir / "dubbed_video.mp4"

    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Dubbed video not ready")

    return FileResponse(output_path, media_type="video/mp4")
