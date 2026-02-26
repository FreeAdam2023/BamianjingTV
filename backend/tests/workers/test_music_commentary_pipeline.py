"""Tests for MusicCommentaryPipelineWorker."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.music_commentary import (
    AudioMixConfig,
    CommentaryScript,
    DifficultyLevel,
    LyricsExplanation,
    MusicCommentarySession,
    MusicCommentaryStatus,
    MusicGenre,
    ScriptConfig,
    SongConfig,
    TTSConfig,
)
from app.services.music_commentary_manager import MusicCommentarySessionManager
from app.workers.music_commentary_pipeline import MusicCommentaryPipelineWorker


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def mock_session_manager(temp_dir):
    manager = MagicMock(spec=MusicCommentarySessionManager)
    manager.get_session_dir.return_value = temp_dir
    return manager


@pytest.fixture
def mock_download_worker():
    worker = MagicMock()
    worker.download = AsyncMock(
        return_value={
            "audio_path": "/tmp/audio.wav",
            "video_path": "/tmp/video.mp4",
            "title": "Test Song",
            "artist": "Test Artist",
        }
    )
    return worker


@pytest.fixture
def mock_whisper_worker():
    worker = MagicMock()
    transcript = MagicMock()
    transcript.segments = [
        MagicMock(text="Never gonna give you up"),
        MagicMock(text="Never gonna let you down"),
    ]
    transcript.model_dump.return_value = {
        "segments": [
            {"text": "Never gonna give you up", "start": 0.0, "end": 3.0},
            {"text": "Never gonna let you down", "start": 3.0, "end": 6.0},
        ]
    }
    worker.transcribe = AsyncMock(return_value=transcript)
    return worker


@pytest.fixture
def mock_translation_worker():
    worker = MagicMock()
    worker.translate_text = AsyncMock(return_value=("翻译结果", 0, 0))
    return worker


@pytest.fixture
def mock_card_generator():
    gen = MagicMock()
    result = MagicMock()
    result.model_dump.return_value = {
        "words": ["give up"],
        "entities": [],
        "idioms": [],
    }
    gen.get_segment_annotations = AsyncMock(return_value=result)
    return gen


@pytest.fixture
def mock_youtube_worker():
    worker = MagicMock()
    worker.upload = AsyncMock(
        return_value={
            "video_id": "yt_abc123",
            "url": "https://youtube.com/watch?v=yt_abc123",
        }
    )
    return worker


@pytest.fixture
def mock_voice_clone_worker():
    worker = MagicMock()
    worker.synthesize = AsyncMock()
    return worker


@pytest.fixture
def worker(
    mock_session_manager,
    mock_download_worker,
    mock_whisper_worker,
    mock_translation_worker,
    mock_card_generator,
    mock_youtube_worker,
    mock_voice_clone_worker,
):
    return MusicCommentaryPipelineWorker(
        session_manager=mock_session_manager,
        download_worker=mock_download_worker,
        whisper_worker=mock_whisper_worker,
        translation_worker=mock_translation_worker,
        card_generator=mock_card_generator,
        youtube_worker=mock_youtube_worker,
        voice_clone_worker=mock_voice_clone_worker,
    )


def _make_session(**kwargs) -> MusicCommentarySession:
    """Helper with defaults for tests."""
    defaults = {
        "song_config": SongConfig(url="https://youtube.com/watch?v=test123"),
        "script_config": ScriptConfig(
            difficulty=DifficultyLevel.INTERMEDIATE,
            target_duration=180.0,
            max_lyrics_lines=8,
        ),
        "tts_config": TTSConfig(),
        "audio_mix_config": AudioMixConfig(),
    }
    defaults.update(kwargs)
    return MusicCommentarySession(**defaults)


class TestRunPipeline:
    @pytest.mark.asyncio
    async def test_session_not_found(self, worker, mock_session_manager):
        mock_session_manager.get_session.return_value = None
        await worker.run_pipeline("nonexistent")
        mock_session_manager.update_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_error(self, worker, mock_session_manager):
        session = _make_session()
        mock_session_manager.get_session.return_value = session

        with patch.object(
            worker, "_download", new_callable=AsyncMock, side_effect=RuntimeError("boom")
        ):
            await worker.run_pipeline(session.id)

        calls = mock_session_manager.update_session.call_args_list
        last_call = calls[-1]
        assert last_call.kwargs.get("status") == MusicCommentaryStatus.FAILED
        assert "boom" in last_call.kwargs.get("error", "")

    @pytest.mark.asyncio
    async def test_full_pipeline_calls_all_stages(self, worker, mock_session_manager):
        session = _make_session()
        mock_session_manager.get_session.return_value = session

        with patch.object(worker, "_download", new_callable=AsyncMock) as dl, \
             patch.object(worker, "_transcribe", new_callable=AsyncMock) as tr, \
             patch.object(worker, "_translate", new_callable=AsyncMock) as tl, \
             patch.object(worker, "_annotate", new_callable=AsyncMock) as an, \
             patch.object(worker, "_generate_script", new_callable=AsyncMock) as sc, \
             patch.object(worker, "_generate_tts", new_callable=AsyncMock) as tts, \
             patch.object(worker, "_assemble_audio", new_callable=AsyncMock) as aa, \
             patch.object(worker, "_generate_visual", new_callable=AsyncMock) as gv, \
             patch.object(worker, "_generate_thumbnail", new_callable=AsyncMock) as gt, \
             patch.object(worker, "_generate_metadata", new_callable=AsyncMock) as gm:
            await worker.run_pipeline(session.id)

        dl.assert_called_once()
        tr.assert_called_once()
        tl.assert_called_once()
        an.assert_called_once()
        sc.assert_called_once()
        tts.assert_called_once()
        aa.assert_called_once()
        gv.assert_called_once()
        gt.assert_called_once()
        gm.assert_called_once()

        # Should end with AWAITING_REVIEW
        calls = mock_session_manager.update_session.call_args_list
        last_call = calls[-1]
        assert last_call.kwargs.get("status") == MusicCommentaryStatus.AWAITING_REVIEW
        assert last_call.kwargs.get("progress") == 100.0


class TestDownload:
    @pytest.mark.asyncio
    async def test_updates_status(self, worker, mock_session_manager, temp_dir):
        session = _make_session()
        mock_session_manager.get_session.return_value = session

        await worker._download(session, temp_dir)

        calls = mock_session_manager.update_session.call_args_list
        first_call = calls[0]
        assert first_call.kwargs.get("status") == MusicCommentaryStatus.DOWNLOADING

    @pytest.mark.asyncio
    async def test_calls_download_worker(
        self, worker, mock_download_worker, mock_session_manager, temp_dir
    ):
        session = _make_session()
        mock_session_manager.get_session.return_value = session

        await worker._download(session, temp_dir)
        mock_download_worker.download.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_song_metadata(
        self, worker, mock_session_manager, temp_dir
    ):
        session = _make_session()
        mock_session_manager.get_session.return_value = session

        await worker._download(session, temp_dir)
        assert session.song_config.title == "Test Song"
        assert session.song_config.artist == "Test Artist"


class TestTranscribe:
    @pytest.mark.asyncio
    async def test_updates_status(self, worker, mock_session_manager, temp_dir):
        session = _make_session(source_audio_path="/tmp/audio.wav")
        mock_session_manager.get_session.return_value = session

        await worker._transcribe(session, temp_dir)

        calls = mock_session_manager.update_session.call_args_list
        first_call = calls[0]
        assert first_call.kwargs.get("status") == MusicCommentaryStatus.TRANSCRIBING

    @pytest.mark.asyncio
    async def test_saves_transcript(
        self, worker, mock_whisper_worker, mock_session_manager, temp_dir
    ):
        session = _make_session(source_audio_path="/tmp/audio.wav")
        mock_session_manager.get_session.return_value = session

        await worker._transcribe(session, temp_dir)

        transcript_path = temp_dir / "transcript" / "raw.json"
        assert transcript_path.exists()


class TestTranslate:
    @pytest.mark.asyncio
    async def test_translates_segments(
        self, worker, mock_translation_worker, mock_session_manager, temp_dir
    ):
        # Create a transcript file
        transcript_dir = temp_dir / "transcript"
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = transcript_dir / "raw.json"
        with open(transcript_path, "w") as f:
            json.dump(
                {
                    "segments": [
                        {"text": "Hello world", "start": 0.0, "end": 2.0},
                        {"text": "Goodbye world", "start": 2.0, "end": 4.0},
                    ]
                },
                f,
            )

        session = _make_session(transcript_path=str(transcript_path))
        mock_session_manager.get_session.return_value = session

        await worker._translate(session, temp_dir)

        assert mock_translation_worker.translate_text.call_count == 2

    @pytest.mark.asyncio
    async def test_saves_translations(
        self, worker, mock_session_manager, temp_dir
    ):
        transcript_dir = temp_dir / "transcript"
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = transcript_dir / "raw.json"
        with open(transcript_path, "w") as f:
            json.dump(
                {"segments": [{"text": "Hello", "start": 0.0, "end": 1.0}]},
                f,
            )

        session = _make_session(transcript_path=str(transcript_path))
        mock_session_manager.get_session.return_value = session

        await worker._translate(session, temp_dir)

        translation_path = transcript_dir / "translations.json"
        assert translation_path.exists()
        with open(translation_path) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["zh"] == "翻译结果"


class TestAnnotate:
    @pytest.mark.asyncio
    async def test_generates_annotations(
        self, worker, mock_card_generator, mock_session_manager, temp_dir
    ):
        translation_path = temp_dir / "translations.json"
        with open(translation_path, "w") as f:
            json.dump(
                [{"en": "Hello world", "zh": "你好世界"}],
                f,
            )

        session = _make_session(translation_path=str(translation_path))
        mock_session_manager.get_session.return_value = session

        await worker._annotate(session, temp_dir)

        mock_card_generator.get_segment_annotations.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_card_generator(
        self, mock_session_manager, mock_download_worker, mock_whisper_worker,
        mock_translation_worker, mock_youtube_worker, temp_dir
    ):
        """Without card_generator, annotations should be empty lists."""
        w = MusicCommentaryPipelineWorker(
            session_manager=mock_session_manager,
            download_worker=mock_download_worker,
            whisper_worker=mock_whisper_worker,
            translation_worker=mock_translation_worker,
            card_generator=None,
            youtube_worker=mock_youtube_worker,
        )
        translation_path = temp_dir / "translations.json"
        with open(translation_path, "w") as f:
            json.dump([{"en": "Hello", "zh": "你好"}], f)

        session = _make_session(translation_path=str(translation_path))
        mock_session_manager.get_session.return_value = session

        await w._annotate(session, temp_dir)

        annotations_path = temp_dir / "annotations" / "annotations.json"
        assert annotations_path.exists()
        with open(annotations_path) as f:
            data = json.load(f)
        assert data[0]["words"] == []


class TestGenerateScript:
    @pytest.mark.asyncio
    async def test_calls_llm(self, worker, mock_session_manager, temp_dir):
        translation_path = temp_dir / "translations.json"
        with open(translation_path, "w") as f:
            json.dump(
                [
                    {"en": "Never gonna give you up", "zh": "永远不会放弃你"},
                    {"en": "Never gonna let you down", "zh": "永远不会让你失望"},
                ],
                f,
            )

        session = _make_session(translation_path=str(translation_path))
        mock_session_manager.get_session.return_value = session

        fake_script = {
            "hook_text": "Hook",
            "background_text": "Background",
            "lyrics_explanations": [
                {
                    "lyric_en": "Never gonna give you up",
                    "lyric_zh": "永远不会放弃你",
                    "explanation": "give up means 放弃",
                    "vocabulary": ["give up"],
                }
            ],
            "deep_dive_text": "Deep dive",
            "outro_text": "Outro",
        }

        with patch.object(
            worker, "_call_llm", new_callable=AsyncMock, return_value=fake_script
        ):
            await worker._generate_script(session, temp_dir)

        # Script should be saved
        script_path = temp_dir / "script" / "script.json"
        assert script_path.exists()

        # Session should be updated with script
        update_calls = mock_session_manager.update_session.call_args_list
        script_updates = [
            c for c in update_calls if c.kwargs.get("script") is not None
        ]
        assert len(script_updates) == 1


class TestGenerateTTS:
    @pytest.mark.asyncio
    async def test_no_voice_clone(self, mock_session_manager, mock_download_worker,
                                   mock_whisper_worker, mock_translation_worker,
                                   mock_youtube_worker, temp_dir):
        """Without voice_clone_worker, should generate silence placeholders."""
        w = MusicCommentaryPipelineWorker(
            session_manager=mock_session_manager,
            download_worker=mock_download_worker,
            whisper_worker=mock_whisper_worker,
            translation_worker=mock_translation_worker,
            youtube_worker=mock_youtube_worker,
            voice_clone_worker=None,
        )

        session = _make_session(
            source_audio_path="/tmp/audio.wav",
        )
        session.script = CommentaryScript(
            hook_text="开场白",
            outro_text="结尾",
        )
        mock_session_manager.get_session.return_value = session

        with patch.object(w, "_generate_silence", new_callable=AsyncMock), \
             patch.object(w, "_concat_audio", new_callable=AsyncMock):
            await w._generate_tts(session, temp_dir)

    @pytest.mark.asyncio
    async def test_with_voice_clone(
        self, worker, mock_voice_clone_worker, mock_session_manager, temp_dir
    ):
        session = _make_session(source_audio_path="/tmp/audio.wav")
        session.script = CommentaryScript(
            hook_text="开场白",
            background_text="背景介绍",
        )
        mock_session_manager.get_session.return_value = session

        # Mock the audio file exists
        with patch("pathlib.Path.exists", return_value=True), \
             patch.object(worker, "_concat_audio", new_callable=AsyncMock):
            await worker._generate_tts(session, temp_dir)

        assert mock_voice_clone_worker.synthesize.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_without_script(
        self, worker, mock_session_manager, temp_dir
    ):
        session = _make_session()
        session.script = None
        mock_session_manager.get_session.return_value = session

        with pytest.raises(RuntimeError, match="Script not generated"):
            await worker._generate_tts(session, temp_dir)


class TestAssembleAudio:
    @pytest.mark.asyncio
    async def test_with_narration(self, worker, mock_session_manager, temp_dir):
        song_path = temp_dir / "song.wav"
        song_path.write_bytes(b"fake song")
        narr_path = temp_dir / "narration.wav"
        narr_path.write_bytes(b"fake narr")

        session = _make_session(
            source_audio_path=str(song_path),
        )
        session.tts_audio_path = str(narr_path)
        mock_session_manager.get_session.return_value = session

        with patch.object(worker, "_run_ffmpeg", new_callable=AsyncMock):
            await worker._assemble_audio(session, temp_dir)

        calls = mock_session_manager.update_session.call_args_list
        audio_updates = [
            c for c in calls if c.kwargs.get("final_audio_path") is not None
        ]
        assert len(audio_updates) == 1

    @pytest.mark.asyncio
    async def test_without_narration(self, worker, mock_session_manager, temp_dir):
        song_path = temp_dir / "song.wav"
        song_path.write_bytes(b"fake song")

        session = _make_session(source_audio_path=str(song_path))
        session.tts_audio_path = None
        mock_session_manager.get_session.return_value = session

        await worker._assemble_audio(session, temp_dir)

        output = temp_dir / "output" / "mixed_audio.wav"
        assert output.exists()


class TestGenerateVisual:
    @pytest.mark.asyncio
    async def test_with_source_video(self, worker, mock_session_manager, temp_dir):
        video_path = temp_dir / "video.mp4"
        video_path.write_bytes(b"fake video")
        audio_path = temp_dir / "audio.wav"
        audio_path.write_bytes(b"fake audio")

        session = _make_session(
            source_video_path=str(video_path),
        )
        session.final_audio_path = str(audio_path)
        mock_session_manager.get_session.return_value = session

        with patch.object(worker, "_run_ffmpeg", new_callable=AsyncMock):
            await worker._generate_visual(session, temp_dir)

    @pytest.mark.asyncio
    async def test_without_source_video(
        self, worker, mock_session_manager, temp_dir
    ):
        audio_path = temp_dir / "audio.wav"
        audio_path.write_bytes(b"fake audio")

        session = _make_session()
        session.source_video_path = None
        session.final_audio_path = str(audio_path)
        mock_session_manager.get_session.return_value = session

        with patch.object(worker, "_run_ffmpeg", new_callable=AsyncMock):
            await worker._generate_visual(session, temp_dir)


class TestGenerateThumbnail:
    @pytest.mark.asyncio
    async def test_generates_thumbnail(self, worker, mock_session_manager, temp_dir):
        video_path = temp_dir / "output" / "final.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"fake video")

        session = _make_session()
        session.final_video_path = str(video_path)
        mock_session_manager.get_session.return_value = session

        with patch.object(worker, "_run_ffmpeg", new_callable=AsyncMock), \
             patch.object(worker, "_add_thumbnail_text", new_callable=AsyncMock):
            await worker._generate_thumbnail(session, temp_dir)

        calls = mock_session_manager.update_session.call_args_list
        thumb_updates = [
            c for c in calls if c.kwargs.get("thumbnail_path") is not None
        ]
        assert len(thumb_updates) == 1


class TestGenerateMetadata:
    @pytest.mark.asyncio
    async def test_generates_metadata(self, worker, mock_session_manager, temp_dir):
        session = _make_session()
        mock_session_manager.get_session.return_value = session

        with patch.object(
            worker,
            "_generate_youtube_metadata",
            new_callable=AsyncMock,
            return_value={
                "title": "Test Title",
                "description": "Test desc",
                "tags": ["english"],
            },
        ):
            await worker._generate_metadata(session, temp_dir)

        calls = mock_session_manager.update_session.call_args_list
        title_updates = [c for c in calls if c.kwargs.get("title") is not None]
        assert len(title_updates) == 1
        assert title_updates[0].kwargs["title"] == "Test Title"


class TestGenerateYouTubeMetadata:
    @pytest.mark.asyncio
    async def test_fallback_on_error(self, worker):
        session = _make_session(
            song_config=SongConfig(
                url="https://youtube.com/watch?v=abc",
                title="Test Song",
                artist="Test Artist",
            )
        )
        with patch.object(
            worker, "_call_llm", new_callable=AsyncMock, side_effect=Exception("API error")
        ):
            result = await worker._generate_youtube_metadata(session)

        assert "Test Song" in result["title"]
        assert "Test Artist" in result["title"]
        assert len(result["tags"]) > 0


class TestPublishToYouTube:
    @pytest.mark.asyncio
    async def test_publishes(self, worker, mock_session_manager, mock_youtube_worker, temp_dir):
        video_path = temp_dir / "video.mp4"
        video_path.write_bytes(b"fake video")

        session = _make_session()
        session.status = MusicCommentaryStatus.AWAITING_REVIEW
        session.final_video_path = str(video_path)
        mock_session_manager.get_session.return_value = session

        result = await worker.publish_to_youtube(session.id)
        assert result["video_id"] == "yt_abc123"
        mock_youtube_worker.upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_not_found(self, worker, mock_session_manager):
        mock_session_manager.get_session.return_value = None
        with pytest.raises(ValueError, match="not found"):
            await worker.publish_to_youtube("nonexistent")

    @pytest.mark.asyncio
    async def test_wrong_status(self, worker, mock_session_manager):
        session = _make_session()
        session.status = MusicCommentaryStatus.PENDING
        mock_session_manager.get_session.return_value = session

        with pytest.raises(ValueError, match="not in reviewable state"):
            await worker.publish_to_youtube(session.id)

    @pytest.mark.asyncio
    async def test_no_video_file(self, worker, mock_session_manager):
        session = _make_session()
        session.status = MusicCommentaryStatus.AWAITING_REVIEW
        session.final_video_path = None
        mock_session_manager.get_session.return_value = session

        with pytest.raises(ValueError, match="No video file"):
            await worker.publish_to_youtube(session.id)

    @pytest.mark.asyncio
    async def test_no_youtube_worker(self, mock_session_manager, mock_download_worker,
                                       mock_whisper_worker, mock_translation_worker, temp_dir):
        w = MusicCommentaryPipelineWorker(
            session_manager=mock_session_manager,
            download_worker=mock_download_worker,
            whisper_worker=mock_whisper_worker,
            translation_worker=mock_translation_worker,
            youtube_worker=None,
        )
        video_path = temp_dir / "video.mp4"
        video_path.write_bytes(b"fake")

        session = _make_session()
        session.status = MusicCommentaryStatus.AWAITING_REVIEW
        session.final_video_path = str(video_path)
        mock_session_manager.get_session.return_value = session

        with pytest.raises(RuntimeError, match="YouTube worker not available"):
            await w.publish_to_youtube(session.id)

    @pytest.mark.asyncio
    async def test_upload_failure(
        self, worker, mock_session_manager, mock_youtube_worker, temp_dir
    ):
        video_path = temp_dir / "video.mp4"
        video_path.write_bytes(b"fake")

        session = _make_session()
        session.status = MusicCommentaryStatus.AWAITING_REVIEW
        session.final_video_path = str(video_path)
        mock_session_manager.get_session.return_value = session
        mock_youtube_worker.upload = AsyncMock(side_effect=Exception("Upload failed"))

        with pytest.raises(Exception, match="Upload failed"):
            await worker.publish_to_youtube(session.id)

        calls = mock_session_manager.update_session.call_args_list
        last_call = calls[-1]
        assert last_call.kwargs.get("status") == MusicCommentaryStatus.FAILED


class TestTryNvenc:
    def test_replaces_libx264(self, worker):
        cmd = ["ffmpeg", "-c:v", "libx264", "-crf", "20"]
        result = worker._try_nvenc(cmd)
        assert "h264_nvenc" in result
        assert "-cq" in result
        assert "libx264" not in result

    def test_no_libx264(self, worker):
        cmd = ["ffmpeg", "-i", "input.mp4"]
        result = worker._try_nvenc(cmd)
        assert result == cmd


class TestConcatAudio:
    @pytest.mark.asyncio
    async def test_single_segment(self, worker, temp_dir):
        seg = temp_dir / "seg.wav"
        seg.write_bytes(b"fake wav")
        output = temp_dir / "output.wav"

        await worker._concat_audio([str(seg)], output)
        assert output.exists()

    @pytest.mark.asyncio
    async def test_multiple_segments(self, worker, temp_dir):
        segs = []
        for i in range(3):
            seg = temp_dir / f"seg_{i}.wav"
            seg.write_bytes(b"fake wav")
            segs.append(str(seg))

        output = temp_dir / "output.wav"
        with patch.object(worker, "_run_ffmpeg", new_callable=AsyncMock):
            await worker._concat_audio(segs, output)


class TestCallLlm:
    @pytest.mark.asyncio
    async def test_parses_json_response(self, worker):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": '{"key": "value"}'}}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await worker._call_llm("test prompt")
            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_handles_markdown_code_blocks(self, worker):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": '```json\n{"key": "value"}\n```'}}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await worker._call_llm("test prompt")
            assert result == {"key": "value"}
