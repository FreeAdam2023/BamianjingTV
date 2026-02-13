"""Tests for the ambient sound library service."""

import pytest
from pathlib import Path

from app.services.ambient_library import AmbientLibrary, AMBIENT_SOUNDS


@pytest.fixture
def tmp_ambient_dir(tmp_path):
    """Create a temporary ambient directory."""
    d = tmp_path / "ambient"
    d.mkdir()
    return d


@pytest.fixture
def library(tmp_ambient_dir):
    """Create an AmbientLibrary with a temp directory."""
    return AmbientLibrary(tmp_ambient_dir)


def _create_fake_wav(path: Path):
    """Create a minimal file to simulate a WAV file."""
    path.write_bytes(b"RIFF" + b"\x00" * 40)


class TestAmbientSoundsRegistry:
    """Tests for the AMBIENT_SOUNDS constant."""

    def test_has_15_sounds(self):
        assert len(AMBIENT_SOUNDS) == 15

    def test_each_sound_has_labels(self):
        for name, meta in AMBIENT_SOUNDS.items():
            assert "label" in meta, f"{name} missing label"
            assert "label_zh" in meta, f"{name} missing label_zh"
            assert isinstance(meta["label"], str)
            assert isinstance(meta["label_zh"], str)

    def test_known_sounds_present(self):
        expected = {"rain", "thunder", "ocean", "fireplace", "birds", "whale"}
        assert expected.issubset(set(AMBIENT_SOUNDS.keys()))


class TestAmbientLibraryListSounds:
    """Tests for list_sounds()."""

    def test_empty_directory(self, library):
        sounds = library.list_sounds()
        assert len(sounds) == 15
        assert all(s["available"] is False for s in sounds)

    def test_some_files_present(self, library, tmp_ambient_dir):
        _create_fake_wav(tmp_ambient_dir / "rain.wav")
        _create_fake_wav(tmp_ambient_dir / "ocean.wav")

        sounds = library.list_sounds()
        rain = next(s for s in sounds if s["name"] == "rain")
        ocean = next(s for s in sounds if s["name"] == "ocean")
        thunder = next(s for s in sounds if s["name"] == "thunder")

        assert rain["available"] is True
        assert ocean["available"] is True
        assert thunder["available"] is False

    def test_sound_metadata_fields(self, library, tmp_ambient_dir):
        _create_fake_wav(tmp_ambient_dir / "rain.wav")
        sounds = library.list_sounds()
        rain = next(s for s in sounds if s["name"] == "rain")

        assert rain["name"] == "rain"
        assert rain["label"] == "Rain"
        assert rain["label_zh"] == "雨声"
        assert "available" in rain
        assert "duration_seconds" in rain

    def test_supports_mp3(self, library, tmp_ambient_dir):
        (tmp_ambient_dir / "wind.mp3").write_bytes(b"\x00" * 10)
        sounds = library.list_sounds()
        wind = next(s for s in sounds if s["name"] == "wind")
        assert wind["available"] is True

    def test_supports_flac(self, library, tmp_ambient_dir):
        (tmp_ambient_dir / "forest.flac").write_bytes(b"\x00" * 10)
        sounds = library.list_sounds()
        forest = next(s for s in sounds if s["name"] == "forest")
        assert forest["available"] is True


class TestAmbientLibraryGetSoundPath:
    """Tests for get_sound_path()."""

    def test_returns_none_for_missing(self, library):
        assert library.get_sound_path("rain") is None

    def test_returns_path_when_exists(self, library, tmp_ambient_dir):
        _create_fake_wav(tmp_ambient_dir / "rain.wav")
        path = library.get_sound_path("rain")
        assert path is not None
        assert path.name == "rain.wav"

    def test_returns_none_for_unknown_name(self, library):
        assert library.get_sound_path("nonexistent_sound") is None

    def test_prefers_wav_over_mp3(self, library, tmp_ambient_dir):
        _create_fake_wav(tmp_ambient_dir / "rain.wav")
        (tmp_ambient_dir / "rain.mp3").write_bytes(b"\x00" * 10)
        path = library.get_sound_path("rain")
        assert path is not None
        assert path.suffix == ".wav"


class TestAmbientLibraryIsAvailable:
    """Tests for is_available()."""

    def test_not_available(self, library):
        assert library.is_available("rain") is False

    def test_available(self, library, tmp_ambient_dir):
        _create_fake_wav(tmp_ambient_dir / "rain.wav")
        assert library.is_available("rain") is True

    def test_unknown_name(self, library):
        assert library.is_available("aliens") is False


class TestAmbientLibraryGetAvailableSounds:
    """Tests for get_available_sounds()."""

    def test_empty_list(self, library):
        assert library.get_available_sounds([]) == []

    def test_filters_unavailable(self, library, tmp_ambient_dir):
        _create_fake_wav(tmp_ambient_dir / "rain.wav")
        paths = library.get_available_sounds(["rain", "thunder", "ocean"])
        assert len(paths) == 1
        assert paths[0].name == "rain.wav"

    def test_all_available(self, library, tmp_ambient_dir):
        _create_fake_wav(tmp_ambient_dir / "rain.wav")
        _create_fake_wav(tmp_ambient_dir / "ocean.wav")
        paths = library.get_available_sounds(["rain", "ocean"])
        assert len(paths) == 2


class TestAmbientLibraryDirCreation:
    """Tests for directory auto-creation."""

    def test_creates_directory_on_init(self, tmp_path):
        new_dir = tmp_path / "new_ambient"
        assert not new_dir.exists()
        AmbientLibrary(new_dir)
        assert new_dir.exists()
