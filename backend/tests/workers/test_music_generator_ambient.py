"""Tests for ambient sound mixing in the music generator worker."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.music import AmbientMode
from app.services.ambient_library import AmbientLibrary
from app.workers.music_generator import MusicGeneratorWorker


@pytest.fixture
def tmp_ambient_dir(tmp_path):
    d = tmp_path / "ambient"
    d.mkdir()
    return d


@pytest.fixture
def ambient_library(tmp_ambient_dir):
    return AmbientLibrary(tmp_ambient_dir)


@pytest.fixture
def music_manager():
    manager = MagicMock()
    manager._track_dir.return_value = Path("/tmp/test_track")
    return manager


@pytest.fixture
def worker(music_manager, ambient_library):
    return MusicGeneratorWorker(music_manager=music_manager, ambient_library=ambient_library)


class TestMixAmbientSimultaneous:
    """Tests for simultaneous (mix) mode FFmpeg command construction."""

    @patch("app.workers.music_generator.subprocess.run")
    def test_single_ambient_sound(self, mock_run, worker, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        music_path = tmp_path / "audio.wav"
        music_path.write_bytes(b"\x00" * 100)
        sound_path = tmp_path / "rain.wav"
        sound_path.write_bytes(b"\x00" * 100)
        output_path = tmp_path / "mixed.wav"

        worker._mix_ambient_simultaneous(
            music_path=music_path,
            sound_paths=[sound_path],
            ambient_volume=0.3,
            duration=30.0,
            output_path=output_path,
        )

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]

        # Check inputs
        assert "-i" in cmd
        assert str(music_path) in cmd
        assert str(sound_path) in cmd

        # Check filter contains amix, aloop, volume
        filter_idx = cmd.index("-filter_complex")
        filter_str = cmd[filter_idx + 1]
        assert "aloop" in filter_str
        assert "volume=0.3" in filter_str
        assert "amix=inputs=2" in filter_str

    @patch("app.workers.music_generator.subprocess.run")
    def test_multiple_ambient_sounds(self, mock_run, worker, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        music_path = tmp_path / "audio.wav"
        music_path.write_bytes(b"\x00" * 100)
        rain = tmp_path / "rain.wav"
        rain.write_bytes(b"\x00" * 100)
        fire = tmp_path / "fireplace.wav"
        fire.write_bytes(b"\x00" * 100)
        output = tmp_path / "mixed.wav"

        worker._mix_ambient_simultaneous(
            music_path=music_path,
            sound_paths=[rain, fire],
            ambient_volume=0.5,
            duration=60.0,
            output_path=output,
        )

        cmd = mock_run.call_args[0][0]
        filter_idx = cmd.index("-filter_complex")
        filter_str = cmd[filter_idx + 1]
        assert "amix=inputs=3" in filter_str
        assert "volume=0.5" in filter_str

    @patch("app.workers.music_generator.subprocess.run")
    def test_ffmpeg_failure_raises(self, mock_run, worker, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stderr="Error: something went wrong")
        music_path = tmp_path / "audio.wav"
        sound_path = tmp_path / "rain.wav"
        output = tmp_path / "mixed.wav"

        with pytest.raises(RuntimeError, match="FFmpeg ambient mix failed"):
            worker._mix_ambient_simultaneous(
                music_path=music_path,
                sound_paths=[sound_path],
                ambient_volume=0.3,
                duration=30.0,
                output_path=output,
            )


class TestMixAmbientSequence:
    """Tests for sequence mode FFmpeg command construction."""

    @patch("app.workers.music_generator.subprocess.run")
    def test_sequence_creates_concat_then_mixes(self, mock_run, worker, tmp_path):
        # Both ffmpeg calls succeed
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        music_path = tmp_path / "audio.wav"
        music_path.write_bytes(b"\x00" * 100)
        rain = tmp_path / "rain.wav"
        rain.write_bytes(b"\x00" * 100)
        fire = tmp_path / "fireplace.wav"
        fire.write_bytes(b"\x00" * 100)
        output = tmp_path / "mixed.wav"

        worker._mix_ambient_sequence(
            music_path=music_path,
            sound_paths=[rain, fire],
            ambient_volume=0.4,
            duration=30.0,
            output_path=output,
        )

        # Two FFmpeg calls: concat + mix
        assert mock_run.call_count == 2

        # First call: concat
        concat_cmd = mock_run.call_args_list[0][0][0]
        assert "-f" in concat_cmd
        assert "concat" in concat_cmd

        # Second call: amix
        mix_cmd = mock_run.call_args_list[1][0][0]
        filter_idx = mix_cmd.index("-filter_complex")
        filter_str = mix_cmd[filter_idx + 1]
        assert "amix=inputs=2" in filter_str
        assert "volume=0.4" in filter_str

    @patch("app.workers.music_generator.subprocess.run")
    def test_sequence_concat_failure_raises(self, mock_run, worker, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stderr="concat error")

        music_path = tmp_path / "audio.wav"
        rain = tmp_path / "rain.wav"
        fire = tmp_path / "fireplace.wav"
        output = tmp_path / "mixed.wav"

        with pytest.raises(RuntimeError, match="FFmpeg concat failed"):
            worker._mix_ambient_sequence(
                music_path=music_path,
                sound_paths=[rain, fire],
                ambient_volume=0.3,
                duration=30.0,
                output_path=output,
            )


class TestMixAmbientSync:
    """Tests for the dispatch method _mix_ambient_sync."""

    @patch.object(MusicGeneratorWorker, "_mix_ambient_simultaneous")
    def test_mix_mode_calls_simultaneous(self, mock_sim, worker, tmp_path):
        music_path = tmp_path / "audio.wav"
        sound_paths = [tmp_path / "rain.wav"]
        output = tmp_path / "mixed.wav"

        worker._mix_ambient_sync(
            music_path, sound_paths, AmbientMode.MIX, 0.3, 30.0, output,
        )
        mock_sim.assert_called_once()

    @patch.object(MusicGeneratorWorker, "_mix_ambient_sequence")
    def test_sequence_mode_with_multiple_sounds(self, mock_seq, worker, tmp_path):
        music_path = tmp_path / "audio.wav"
        sound_paths = [tmp_path / "rain.wav", tmp_path / "fire.wav"]
        output = tmp_path / "mixed.wav"

        worker._mix_ambient_sync(
            music_path, sound_paths, AmbientMode.SEQUENCE, 0.3, 30.0, output,
        )
        mock_seq.assert_called_once()

    @patch.object(MusicGeneratorWorker, "_mix_ambient_simultaneous")
    def test_sequence_mode_single_sound_falls_back_to_simultaneous(self, mock_sim, worker, tmp_path):
        """Sequence with 1 sound degrades to mix mode."""
        music_path = tmp_path / "audio.wav"
        sound_paths = [tmp_path / "rain.wav"]
        output = tmp_path / "mixed.wav"

        worker._mix_ambient_sync(
            music_path, sound_paths, AmbientMode.SEQUENCE, 0.3, 30.0, output,
        )
        mock_sim.assert_called_once()


class TestWorkerInitialization:
    """Tests for worker initialization with ambient library."""

    def test_worker_accepts_ambient_library(self, music_manager, ambient_library):
        worker = MusicGeneratorWorker(music_manager=music_manager, ambient_library=ambient_library)
        assert worker.ambient_library is ambient_library

    def test_worker_works_without_ambient_library(self, music_manager):
        worker = MusicGeneratorWorker(music_manager=music_manager)
        assert worker.ambient_library is None
