"""Tests for Lofi Video Factory data models."""

import pytest
from pydantic import ValidationError

from app.models.lofi import (
    LofiImageInfo,
    LofiMetadata,
    LofiSession,
    LofiSessionCreate,
    LofiSessionStatus,
    LofiSessionUpdate,
    LofiTheme,
    LofiThemeInfo,
    MusicConfig,
    MusicSource,
    VisualConfig,
    VisualMode,
)


class TestLofiSessionStatus:
    def test_all_statuses(self):
        assert LofiSessionStatus.PENDING == "pending"
        assert LofiSessionStatus.GENERATING_MUSIC == "generating_music"
        assert LofiSessionStatus.MIXING_AUDIO == "mixing_audio"
        assert LofiSessionStatus.GENERATING_VISUALS == "generating_visuals"
        assert LofiSessionStatus.COMPOSITING == "compositing"
        assert LofiSessionStatus.GENERATING_THUMBNAIL == "generating_thumbnail"
        assert LofiSessionStatus.GENERATING_METADATA == "generating_metadata"
        assert LofiSessionStatus.AWAITING_REVIEW == "awaiting_review"
        assert LofiSessionStatus.PUBLISHING == "publishing"
        assert LofiSessionStatus.PUBLISHED == "published"
        assert LofiSessionStatus.FAILED == "failed"
        assert LofiSessionStatus.CANCELLED == "cancelled"
        assert len(LofiSessionStatus) == 12


class TestLofiTheme:
    def test_all_themes(self):
        assert LofiTheme.LOFI_HIP_HOP == "lofi_hip_hop"
        assert LofiTheme.JAZZ == "jazz"
        assert LofiTheme.PIANO == "piano"
        assert len(LofiTheme) == 11

    def test_musicgen_prompt(self):
        prompt = LofiTheme.LOFI_HIP_HOP.musicgen_prompt
        assert "lofi" in prompt.lower()
        assert isinstance(prompt, str)
        assert len(prompt) > 10

    def test_label(self):
        assert LofiTheme.LOFI_HIP_HOP.label == "Lofi Hip Hop"
        assert LofiTheme.COFFEE_SHOP.label == "Coffee Shop"
        assert LofiTheme.RAIN.label == "Rainy Day"

    def test_all_themes_have_prompt(self):
        for theme in LofiTheme:
            assert isinstance(theme.musicgen_prompt, str)
            assert len(theme.musicgen_prompt) > 0

    def test_all_themes_have_label(self):
        for theme in LofiTheme:
            assert isinstance(theme.label, str)
            assert len(theme.label) > 0


class TestVisualMode:
    def test_modes(self):
        assert VisualMode.STATIC_KEN_BURNS == "static_ken_burns"
        assert VisualMode.REMOTION_TEMPLATE == "remotion_template"
        assert VisualMode.AI_GENERATED == "ai_generated"
        assert VisualMode.MIXED == "mixed"
        assert len(VisualMode) == 4


class TestMusicSource:
    def test_sources(self):
        assert MusicSource.MUSICGEN == "musicgen"
        assert MusicSource.SUNO == "suno"
        assert MusicSource.UDIO == "udio"
        assert len(MusicSource) == 3


class TestMusicConfig:
    def test_defaults(self):
        config = MusicConfig()
        assert config.source == MusicSource.MUSICGEN
        assert config.theme == LofiTheme.LOFI_HIP_HOP
        assert config.custom_prompt is None
        assert config.model_size == "medium"
        assert config.segment_duration == 120.0
        assert config.crossfade_duration == 5.0
        assert config.ambient_sounds == []
        assert config.ambient_volume == 0.3

    def test_custom(self):
        config = MusicConfig(
            source=MusicSource.SUNO,
            theme=LofiTheme.JAZZ,
            custom_prompt="my custom prompt",
            model_size="large",
            segment_duration=60.0,
            crossfade_duration=3.0,
            ambient_sounds=["rain", "fireplace"],
            ambient_volume=0.5,
        )
        assert config.source == MusicSource.SUNO
        assert config.theme == LofiTheme.JAZZ
        assert config.custom_prompt == "my custom prompt"
        assert config.ambient_sounds == ["rain", "fireplace"]

    def test_segment_duration_bounds(self):
        MusicConfig(segment_duration=30.0)
        MusicConfig(segment_duration=300.0)
        with pytest.raises(ValidationError):
            MusicConfig(segment_duration=10.0)
        with pytest.raises(ValidationError):
            MusicConfig(segment_duration=400.0)

    def test_crossfade_bounds(self):
        MusicConfig(crossfade_duration=1.0)
        MusicConfig(crossfade_duration=15.0)
        with pytest.raises(ValidationError):
            MusicConfig(crossfade_duration=0.5)
        with pytest.raises(ValidationError):
            MusicConfig(crossfade_duration=20.0)

    def test_ambient_volume_bounds(self):
        MusicConfig(ambient_volume=0.0)
        MusicConfig(ambient_volume=1.0)
        with pytest.raises(ValidationError):
            MusicConfig(ambient_volume=-0.1)
        with pytest.raises(ValidationError):
            MusicConfig(ambient_volume=1.5)


class TestVisualConfig:
    def test_defaults(self):
        config = VisualConfig()
        assert config.mode == VisualMode.STATIC_KEN_BURNS
        assert config.image_path is None
        assert config.ken_burns_speed == 0.0001

    def test_custom(self):
        config = VisualConfig(
            mode=VisualMode.AI_GENERATED,
            image_path="/path/to/image.jpg",
            ken_burns_speed=0.0005,
        )
        assert config.mode == VisualMode.AI_GENERATED
        assert config.image_path == "/path/to/image.jpg"

    def test_ken_burns_speed_bounds(self):
        VisualConfig(ken_burns_speed=0.00001)
        VisualConfig(ken_burns_speed=0.001)
        with pytest.raises(ValidationError):
            VisualConfig(ken_burns_speed=0.0)
        with pytest.raises(ValidationError):
            VisualConfig(ken_burns_speed=0.01)


class TestLofiMetadata:
    def test_defaults(self):
        m = LofiMetadata()
        assert m.title == ""
        assert m.description == ""
        assert m.tags == []
        assert m.privacy_status == "private"
        assert m.category_id == "10"
        assert m.thumbnail_path is None

    def test_custom(self):
        m = LofiMetadata(
            title="My Video",
            description="A description",
            tags=["lofi", "chill"],
            privacy_status="public",
        )
        assert m.title == "My Video"
        assert m.tags == ["lofi", "chill"]


class TestLofiSession:
    def test_defaults(self):
        session = LofiSession()
        assert len(session.id) == 12
        assert session.status == LofiSessionStatus.PENDING
        assert session.progress == 0.0
        assert session.error is None
        assert session.target_duration == 3600.0
        assert isinstance(session.music_config, MusicConfig)
        assert isinstance(session.visual_config, VisualConfig)
        assert isinstance(session.metadata, LofiMetadata)
        assert session.channel_id is None
        assert session.music_segments == []
        assert session.final_audio_path is None
        assert session.final_video_path is None
        assert session.thumbnail_path is None
        assert session.youtube_video_id is None
        assert session.youtube_url is None
        assert session.step_timings == {}
        assert session.triggered_by == "manual"

    def test_custom(self):
        session = LofiSession(
            target_duration=7200.0,
            music_config=MusicConfig(theme=LofiTheme.JAZZ),
            triggered_by="n8n",
        )
        assert session.target_duration == 7200.0
        assert session.music_config.theme == LofiTheme.JAZZ
        assert session.triggered_by == "n8n"

    def test_duration_bounds(self):
        LofiSession(target_duration=300.0)
        LofiSession(target_duration=10800.0)
        with pytest.raises(ValidationError):
            LofiSession(target_duration=100.0)
        with pytest.raises(ValidationError):
            LofiSession(target_duration=20000.0)

    def test_progress_bounds(self):
        LofiSession(progress=0.0)
        LofiSession(progress=100.0)
        with pytest.raises(ValidationError):
            LofiSession(progress=-1.0)
        with pytest.raises(ValidationError):
            LofiSession(progress=101.0)

    def test_serialization_roundtrip(self):
        session = LofiSession(
            target_duration=5400.0,
            music_config=MusicConfig(
                theme=LofiTheme.RAIN,
                ambient_sounds=["rain"],
            ),
            visual_config=VisualConfig(
                image_path="rainy_window.jpg",
            ),
        )
        data = session.model_dump(mode="json")
        restored = LofiSession(**data)
        assert restored.id == session.id
        assert restored.target_duration == 5400.0
        assert restored.music_config.theme == LofiTheme.RAIN
        assert restored.music_config.ambient_sounds == ["rain"]
        assert restored.visual_config.image_path == "rainy_window.jpg"

    def test_unique_ids(self):
        ids = {LofiSession().id for _ in range(100)}
        assert len(ids) == 100


class TestLofiSessionCreate:
    def test_defaults(self):
        req = LofiSessionCreate()
        assert req.target_duration == 3600.0
        assert req.theme == LofiTheme.LOFI_HIP_HOP
        assert req.visual_mode == VisualMode.STATIC_KEN_BURNS
        assert req.music_source == MusicSource.MUSICGEN
        assert req.model_size == "medium"
        assert req.triggered_by == "manual"

    def test_custom(self):
        req = LofiSessionCreate(
            target_duration=7200.0,
            theme=LofiTheme.JAZZ,
            ambient_sounds=["rain", "fireplace"],
            triggered_by="n8n",
        )
        assert req.target_duration == 7200.0
        assert req.theme == LofiTheme.JAZZ
        assert req.ambient_sounds == ["rain", "fireplace"]

    def test_duration_bounds(self):
        with pytest.raises(ValidationError):
            LofiSessionCreate(target_duration=100.0)
        with pytest.raises(ValidationError):
            LofiSessionCreate(target_duration=20000.0)

    def test_from_string(self):
        req = LofiSessionCreate(theme="jazz")
        assert req.theme == LofiTheme.JAZZ

    def test_invalid_theme(self):
        with pytest.raises(ValidationError):
            LofiSessionCreate(theme="nonexistent")


class TestLofiSessionUpdate:
    def test_empty(self):
        update = LofiSessionUpdate()
        assert update.title is None
        assert update.description is None
        assert update.tags is None
        assert update.privacy_status is None

    def test_partial(self):
        update = LofiSessionUpdate(title="New Title")
        assert update.title == "New Title"
        assert update.description is None

    def test_full(self):
        update = LofiSessionUpdate(
            title="Title",
            description="Desc",
            tags=["a", "b"],
            privacy_status="public",
        )
        assert update.tags == ["a", "b"]
        assert update.privacy_status == "public"


class TestLofiThemeInfo:
    def test_structure(self):
        info = LofiThemeInfo(
            value="lofi_hip_hop",
            label="Lofi Hip Hop",
            musicgen_prompt="test prompt",
        )
        assert info.value == "lofi_hip_hop"
        assert info.label == "Lofi Hip Hop"


class TestLofiImageInfo:
    def test_structure(self):
        info = LofiImageInfo(name="cozy_room", path="/path/to/img.jpg")
        assert info.name == "cozy_room"
        assert info.width is None
