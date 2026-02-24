"""Tests for LofiPipelineWorker."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.lofi import (
    LofiSession,
    LofiSessionStatus,
    LofiTheme,
    MusicConfig,
    MusicSource,
    VisualConfig,
    VisualMode,
)
from app.services.lofi_manager import LofiSessionManager
from app.workers.lofi_pipeline import LofiPipelineWorker


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def mock_session_manager(temp_dir):
    manager = MagicMock(spec=LofiSessionManager)
    manager.get_session_dir.return_value = temp_dir
    return manager


@pytest.fixture
def mock_music_generator():
    gen = MagicMock()
    gen.is_available = True
    gen._ensure_model_loaded = AsyncMock()
    gen._generate_sync = MagicMock()
    gen.model = MagicMock()
    gen.model.sample_rate = 32000
    return gen


@pytest.fixture
def mock_ambient_library():
    lib = MagicMock()
    lib.get_available_sounds.return_value = []
    return lib


@pytest.fixture
def mock_youtube_worker():
    worker = MagicMock()
    worker.upload = AsyncMock(return_value={
        "video_id": "yt_abc123",
        "url": "https://youtube.com/watch?v=yt_abc123",
    })
    return worker


@pytest.fixture
def worker(mock_session_manager, mock_music_generator, mock_ambient_library, mock_youtube_worker):
    return LofiPipelineWorker(
        session_manager=mock_session_manager,
        music_generator=mock_music_generator,
        ambient_library=mock_ambient_library,
        youtube_worker=mock_youtube_worker,
    )


def _make_session(**kwargs) -> LofiSession:
    defaults = {
        "target_duration": 300.0,  # Short for tests
        "music_config": MusicConfig(
            theme=LofiTheme.LOFI_HIP_HOP,
            source=MusicSource.MUSICGEN,
            segment_duration=120.0,
            crossfade_duration=5.0,
        ),
        "visual_config": VisualConfig(
            mode=VisualMode.STATIC_KEN_BURNS,
            image_path="test.jpg",
        ),
    }
    defaults.update(kwargs)
    return LofiSession(**defaults)


class TestRunPipeline:
    @pytest.mark.asyncio
    async def test_session_not_found(self, worker, mock_session_manager):
        mock_session_manager.get_session.return_value = None
        await worker.run_pipeline("nonexistent")
        mock_session_manager.update_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_pipeline_failure_sets_failed_status(self, worker, mock_session_manager, temp_dir):
        session = _make_session()
        mock_session_manager.get_session.return_value = session

        # Make music generation fail
        with patch.object(worker, "_generate_music", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
            await worker.run_pipeline(session.id)

        # Should have set status to FAILED
        calls = mock_session_manager.update_session.call_args_list
        last_call = calls[-1]
        assert last_call.kwargs.get("status") == LofiSessionStatus.FAILED or \
               (len(last_call.args) > 1 and last_call.args[1] == LofiSessionStatus.FAILED)


class TestGenerateMusic:
    @pytest.mark.asyncio
    async def test_updates_status_to_generating(self, worker, mock_session_manager, temp_dir):
        session = _make_session(target_duration=300.0)
        mock_session_manager.get_session.return_value = session

        # Mock the actual generation
        with patch.object(worker, "_generate_single_segment", new_callable=AsyncMock):
            await worker._generate_music(session, temp_dir)

        # Check that status was set to GENERATING_MUSIC
        first_call = mock_session_manager.update_session.call_args_list[0]
        assert first_call.kwargs.get("status") == LofiSessionStatus.GENERATING_MUSIC

    @pytest.mark.asyncio
    async def test_generates_correct_number_of_segments(self, worker, mock_session_manager, temp_dir):
        session = _make_session(
            target_duration=300.0,
            music_config=MusicConfig(segment_duration=120.0, crossfade_duration=5.0),
        )

        # Mock _generate_silence since AUDIOCRAFT_AVAILABLE is False in test env
        call_count = 0
        original_generate_silence = worker._generate_silence

        async def mock_silence(duration, output_path):
            nonlocal call_count
            call_count += 1
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake wav data")

        with patch.object(worker, "_generate_silence", side_effect=mock_silence):
            await worker._generate_music(session, temp_dir)

        # 300s / (120s - 5s) = 2.6 → 3 segments
        assert call_count == 3


class TestConcatenateSegments:
    @pytest.mark.asyncio
    async def test_single_segment_copies(self, worker, mock_session_manager, temp_dir):
        session = _make_session()
        seg_path = temp_dir / "segments" / "segment_000.wav"
        seg_path.parent.mkdir(parents=True, exist_ok=True)
        seg_path.write_bytes(b"fake wav data")
        session.music_segments = [str(seg_path)]

        await worker._concatenate_segments(session, temp_dir)

        output = temp_dir / "audio.wav"
        assert output.exists()
        assert output.read_bytes() == b"fake wav data"

    @pytest.mark.asyncio
    async def test_no_segments_raises(self, worker, mock_session_manager, temp_dir):
        session = _make_session()
        session.music_segments = []

        with pytest.raises(RuntimeError, match="No music segments"):
            await worker._concatenate_segments(session, temp_dir)


class TestMixAmbient:
    @pytest.mark.asyncio
    async def test_no_ambient_sounds_skips(self, worker, mock_session_manager, temp_dir):
        session = _make_session()
        session.music_config.ambient_sounds = []

        await worker._mix_ambient(session, temp_dir)

        # Just progress update, no ffmpeg call
        mock_session_manager.update_session.assert_called()


class TestGenerateVisuals:
    @pytest.mark.asyncio
    async def test_updates_status(self, worker, mock_session_manager, temp_dir):
        session = _make_session()
        session.final_audio_path = str(temp_dir / "audio.wav")

        with patch.object(worker, "_resolve_image_path", return_value=temp_dir / "image.jpg"):
            with patch.object(worker, "_run_ffmpeg", new_callable=AsyncMock):
                # Create mock image
                (temp_dir / "image.jpg").write_bytes(b"fake image")
                await worker._generate_visuals(session, temp_dir)

        # Check status was set to GENERATING_VISUALS
        calls = mock_session_manager.update_session.call_args_list
        assert any(
            c.kwargs.get("status") == LofiSessionStatus.GENERATING_VISUALS
            for c in calls
        )

    @pytest.mark.asyncio
    async def test_missing_image_raises(self, worker, mock_session_manager, temp_dir):
        session = _make_session()
        session.final_audio_path = str(temp_dir / "audio.wav")

        with patch.object(worker, "_resolve_image_path", return_value=None):
            with pytest.raises(RuntimeError, match="Background image not found"):
                await worker._generate_visuals(session, temp_dir)


class TestGenerateThumbnail:
    @pytest.mark.asyncio
    async def test_updates_status_and_path(self, worker, mock_session_manager, temp_dir):
        session = _make_session()
        video_path = temp_dir / "video_visual.mp4"
        video_path.write_bytes(b"fake video")
        session.final_video_path = str(video_path)

        with patch.object(worker, "_run_ffmpeg", new_callable=AsyncMock):
            with patch.object(worker, "_add_thumbnail_text", new_callable=AsyncMock):
                await worker._generate_thumbnail(session, temp_dir)

        calls = mock_session_manager.update_session.call_args_list
        assert any(
            c.kwargs.get("status") == LofiSessionStatus.GENERATING_THUMBNAIL
            for c in calls
        )
        assert any(
            c.kwargs.get("thumbnail_path") is not None
            for c in calls
        )


class TestGenerateMetadata:
    @pytest.mark.asyncio
    async def test_calls_llm_and_updates(self, worker, mock_session_manager, temp_dir):
        session = _make_session()

        with patch.object(worker, "_call_llm_for_metadata", new_callable=AsyncMock, return_value={
            "title": "Test Title",
            "description": "Test Description",
            "tags": ["lofi", "chill"],
        }):
            await worker._generate_metadata(session, temp_dir)

        calls = mock_session_manager.update_session.call_args_list
        assert any(c.kwargs.get("title") == "Test Title" for c in calls)
        assert any(c.kwargs.get("tags") == ["lofi", "chill"] for c in calls)


class TestCallLlmForMetadata:
    @pytest.mark.asyncio
    async def test_fallback_on_error(self, worker):
        """When LLM call fails, should return sensible defaults."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(side_effect=RuntimeError("API error"))
            mock_client.return_value.__aexit__ = AsyncMock()

            result = await worker._call_llm_for_metadata(
                LofiTheme.LOFI_HIP_HOP, 1.0, "rain"
            )

        assert "title" in result
        assert "description" in result
        assert "tags" in result
        assert isinstance(result["tags"], list)


class TestPublishToYouTube:
    @pytest.mark.asyncio
    async def test_success(self, worker, mock_session_manager, mock_youtube_worker, temp_dir):
        session = _make_session()
        session.status = LofiSessionStatus.AWAITING_REVIEW
        video_path = temp_dir / "video.mp4"
        video_path.write_bytes(b"fake video")
        session.final_video_path = str(video_path)
        session.metadata.title = "Test"
        session.metadata.description = "Desc"
        mock_session_manager.get_session.return_value = session

        result = await worker.publish_to_youtube(session.id)

        assert result["video_id"] == "yt_abc123"
        mock_youtube_worker.upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_not_found(self, worker, mock_session_manager):
        mock_session_manager.get_session.return_value = None
        with pytest.raises(ValueError, match="Session not found"):
            await worker.publish_to_youtube("nonexistent")

    @pytest.mark.asyncio
    async def test_wrong_status(self, worker, mock_session_manager):
        session = _make_session()
        session.status = LofiSessionStatus.PENDING
        mock_session_manager.get_session.return_value = session

        with pytest.raises(ValueError, match="not in reviewable state"):
            await worker.publish_to_youtube(session.id)

    @pytest.mark.asyncio
    async def test_no_video_file(self, worker, mock_session_manager):
        session = _make_session()
        session.status = LofiSessionStatus.AWAITING_REVIEW
        session.final_video_path = None
        mock_session_manager.get_session.return_value = session

        with pytest.raises(ValueError, match="No video file"):
            await worker.publish_to_youtube(session.id)

    @pytest.mark.asyncio
    async def test_no_youtube_worker(self, mock_session_manager, mock_music_generator, temp_dir):
        worker = LofiPipelineWorker(
            session_manager=mock_session_manager,
            music_generator=mock_music_generator,
            youtube_worker=None,
        )
        session = _make_session()
        session.status = LofiSessionStatus.AWAITING_REVIEW
        video_path = temp_dir / "video.mp4"
        video_path.write_bytes(b"fake")
        session.final_video_path = str(video_path)
        mock_session_manager.get_session.return_value = session

        with pytest.raises(RuntimeError, match="YouTube worker not available"):
            await worker.publish_to_youtube(session.id)

    @pytest.mark.asyncio
    async def test_upload_failure(self, worker, mock_session_manager, mock_youtube_worker, temp_dir):
        session = _make_session()
        session.status = LofiSessionStatus.AWAITING_REVIEW
        video_path = temp_dir / "video.mp4"
        video_path.write_bytes(b"fake")
        session.final_video_path = str(video_path)
        mock_session_manager.get_session.return_value = session
        mock_youtube_worker.upload = AsyncMock(side_effect=RuntimeError("Upload failed"))

        with pytest.raises(RuntimeError, match="Upload failed"):
            await worker.publish_to_youtube(session.id)

        # Should have set status to FAILED
        calls = mock_session_manager.update_session.call_args_list
        assert any(
            c.kwargs.get("status") == LofiSessionStatus.FAILED
            for c in calls
        )


class TestResolveImagePath:
    def test_absolute_path(self, worker):
        session = _make_session()
        session.visual_config.image_path = "/absolute/path/image.jpg"
        result = worker._resolve_image_path(session)
        assert result == Path("/absolute/path/image.jpg")

    def test_relative_path(self, worker):
        session = _make_session()
        session.visual_config.image_path = "cozy_room.jpg"
        result = worker._resolve_image_path(session)
        assert result is not None
        assert result.name == "cozy_room.jpg"

    def test_no_path_uses_default(self, worker, temp_dir):
        session = _make_session()
        session.visual_config.image_path = None

        # Create a fake images dir with an image
        with patch("app.workers.lofi_pipeline.settings") as mock_settings:
            mock_settings.lofi_images_dir = temp_dir
            (temp_dir / "default.jpg").write_bytes(b"fake")
            result = worker._resolve_image_path(session)
        assert result is not None
        assert result.name == "default.jpg"

    def test_no_path_no_images(self, worker, temp_dir):
        session = _make_session()
        session.visual_config.image_path = None

        with patch("app.workers.lofi_pipeline.settings") as mock_settings:
            empty_dir = temp_dir / "empty_images"
            empty_dir.mkdir()
            mock_settings.lofi_images_dir = empty_dir
            result = worker._resolve_image_path(session)
        assert result is None


class TestTryNvenc:
    def test_replaces_codec(self, worker):
        cmd = ["ffmpeg", "-y", "-c:v", "libx264", "-crf", "20"]
        result = worker._try_nvenc(cmd)
        assert "h264_nvenc" in result
        assert "-cq" in result
        assert "libx264" not in result

    def test_no_codec_unchanged(self, worker):
        cmd = ["ffmpeg", "-y", "-i", "input.mp4"]
        result = worker._try_nvenc(cmd)
        assert result == cmd


class TestCrossfadeConcat:
    @pytest.mark.asyncio
    async def test_single_segment_copies(self, worker, temp_dir):
        seg = temp_dir / "seg.wav"
        seg.write_bytes(b"fake data")
        output = temp_dir / "output.wav"

        await worker._crossfade_concat([str(seg)], 5.0, output)

        assert output.exists()
        assert output.read_bytes() == b"fake data"
