"""Tests for Music Commentary data models."""

import pytest
from pydantic import ValidationError

from app.models.music_commentary import (
    AudioMixConfig,
    CommentaryScript,
    DifficultyLevel,
    LyricsExplanation,
    MusicCommentarySession,
    MusicCommentarySessionCreate,
    MusicCommentarySessionUpdate,
    MusicCommentaryStatus,
    MusicGenre,
    MusicGenreInfo,
    ScriptConfig,
    SongConfig,
    TTSConfig,
    YouTubeMetadata,
)


class TestMusicCommentaryStatus:
    def test_has_14_statuses(self):
        assert len(MusicCommentaryStatus) == 14

    def test_values(self):
        assert MusicCommentaryStatus.PENDING == "pending"
        assert MusicCommentaryStatus.DOWNLOADING == "downloading"
        assert MusicCommentaryStatus.TRANSCRIBING == "transcribing"
        assert MusicCommentaryStatus.TRANSLATING == "translating"
        assert MusicCommentaryStatus.ANNOTATING == "annotating"
        assert MusicCommentaryStatus.SCRIPTING == "scripting"
        assert MusicCommentaryStatus.GENERATING_TTS == "generating_tts"
        assert MusicCommentaryStatus.ASSEMBLING_AUDIO == "assembling_audio"
        assert MusicCommentaryStatus.GENERATING_VISUAL == "generating_visual"
        assert MusicCommentaryStatus.GENERATING_METADATA == "generating_metadata"
        assert MusicCommentaryStatus.AWAITING_REVIEW == "awaiting_review"
        assert MusicCommentaryStatus.PUBLISHING == "publishing"
        assert MusicCommentaryStatus.PUBLISHED == "published"
        assert MusicCommentaryStatus.FAILED == "failed"


class TestMusicGenre:
    def test_has_10_genres(self):
        assert len(MusicGenre) == 10

    def test_labels(self):
        assert MusicGenre.POP.label == "Pop"
        assert MusicGenre.HIP_HOP.label == "Hip Hop"
        assert MusicGenre.RNB.label == "R&B"
        assert MusicGenre.CLASSICAL.label == "Classical"

    def test_values(self):
        assert MusicGenre.POP == "pop"
        assert MusicGenre.HIP_HOP == "hip_hop"


class TestDifficultyLevel:
    def test_has_3_levels(self):
        assert len(DifficultyLevel) == 3

    def test_labels(self):
        assert "A1-A2" in DifficultyLevel.BEGINNER.label
        assert "B1-B2" in DifficultyLevel.INTERMEDIATE.label
        assert "C1-C2" in DifficultyLevel.ADVANCED.label


class TestSongConfig:
    def test_url_required(self):
        with pytest.raises(ValidationError):
            SongConfig()

    def test_minimal(self):
        config = SongConfig(url="https://youtube.com/watch?v=abc")
        assert config.url == "https://youtube.com/watch?v=abc"
        assert config.title is None
        assert config.artist is None
        assert config.genre == MusicGenre.POP

    def test_full(self):
        config = SongConfig(
            url="https://youtube.com/watch?v=abc",
            title="Never Gonna Give You Up",
            artist="Rick Astley",
            genre=MusicGenre.POP,
            highlight_start=30.0,
            highlight_end=60.0,
        )
        assert config.title == "Never Gonna Give You Up"
        assert config.highlight_start == 30.0


class TestScriptConfig:
    def test_defaults(self):
        config = ScriptConfig()
        assert config.narration_language == "zh-CN"
        assert config.difficulty == DifficultyLevel.INTERMEDIATE
        assert config.max_lyrics_lines == 12
        assert config.target_duration == 240.0

    def test_max_lyrics_lines_bounds(self):
        ScriptConfig(max_lyrics_lines=4)  # min valid
        ScriptConfig(max_lyrics_lines=30)  # max valid
        with pytest.raises(ValidationError):
            ScriptConfig(max_lyrics_lines=3)
        with pytest.raises(ValidationError):
            ScriptConfig(max_lyrics_lines=31)

    def test_target_duration_bounds(self):
        ScriptConfig(target_duration=120.0)  # min valid
        ScriptConfig(target_duration=600.0)  # max valid
        with pytest.raises(ValidationError):
            ScriptConfig(target_duration=60.0)
        with pytest.raises(ValidationError):
            ScriptConfig(target_duration=700.0)


class TestTTSConfig:
    def test_defaults(self):
        config = TTSConfig()
        assert config.engine == "xtts_v2"
        assert config.speed == 1.0

    def test_speed_bounds(self):
        TTSConfig(speed=0.5)
        TTSConfig(speed=2.0)
        with pytest.raises(ValidationError):
            TTSConfig(speed=0.3)
        with pytest.raises(ValidationError):
            TTSConfig(speed=2.5)


class TestAudioMixConfig:
    def test_defaults(self):
        config = AudioMixConfig()
        assert config.song_volume_during_narration == 0.15
        assert config.song_volume_during_playback == 0.8
        assert config.narration_volume == 1.0

    def test_volume_bounds(self):
        AudioMixConfig(song_volume_during_narration=0.0)
        AudioMixConfig(song_volume_during_narration=1.0)
        with pytest.raises(ValidationError):
            AudioMixConfig(song_volume_during_narration=-0.1)
        with pytest.raises(ValidationError):
            AudioMixConfig(song_volume_during_narration=1.1)

    def test_narration_volume_max(self):
        AudioMixConfig(narration_volume=2.0)
        with pytest.raises(ValidationError):
            AudioMixConfig(narration_volume=2.1)


class TestYouTubeMetadata:
    def test_defaults(self):
        meta = YouTubeMetadata()
        assert meta.title == ""
        assert meta.privacy_status == "private"
        assert meta.category_id == "27"  # Education
        assert meta.tags == []

    def test_custom(self):
        meta = YouTubeMetadata(
            title="Learn English with Songs",
            tags=["english", "songs"],
        )
        assert meta.title == "Learn English with Songs"
        assert len(meta.tags) == 2


class TestLyricsExplanation:
    def test_minimal(self):
        exp = LyricsExplanation(
            lyric_en="Never gonna give you up",
            lyric_zh="永远不会放弃你",
            explanation="This is a classic expression of commitment.",
        )
        assert exp.vocabulary == []
        assert exp.start_time is None

    def test_full(self):
        exp = LyricsExplanation(
            lyric_en="Never gonna give you up",
            lyric_zh="永远不会放弃你",
            explanation="This phrase uses 'give up' phrasal verb.",
            vocabulary=["give up", "never gonna"],
            start_time=10.0,
            end_time=14.0,
        )
        assert len(exp.vocabulary) == 2
        assert exp.end_time == 14.0


class TestCommentaryScript:
    def test_defaults(self):
        script = CommentaryScript()
        assert script.hook_text == ""
        assert script.lyrics_explanations == []

    def test_with_explanations(self):
        script = CommentaryScript(
            hook_text="今天我们来学习一首经典英文歌",
            background_text="这首歌由Rick Astley演唱",
            lyrics_explanations=[
                LyricsExplanation(
                    lyric_en="Never gonna give you up",
                    lyric_zh="永远不会放弃你",
                    explanation="give up = 放弃",
                ),
            ],
            deep_dive_text="Let's look at phrasal verbs",
            outro_text="Thanks for watching!",
        )
        assert len(script.lyrics_explanations) == 1


class TestMusicCommentarySession:
    def test_requires_song_config(self):
        with pytest.raises(ValidationError):
            MusicCommentarySession()

    def test_minimal(self):
        session = MusicCommentarySession(
            song_config=SongConfig(url="https://youtube.com/watch?v=abc"),
        )
        assert session.status == MusicCommentaryStatus.PENDING
        assert session.progress == 0.0
        assert len(session.id) == 12
        assert session.script_config.difficulty == DifficultyLevel.INTERMEDIATE

    def test_unique_ids(self):
        ids = set()
        for _ in range(100):
            session = MusicCommentarySession(
                song_config=SongConfig(url="https://youtube.com/watch?v=abc"),
            )
            ids.add(session.id)
        assert len(ids) == 100

    def test_progress_bounds(self):
        MusicCommentarySession(
            song_config=SongConfig(url="https://youtube.com/watch?v=abc"),
            progress=0.0,
        )
        MusicCommentarySession(
            song_config=SongConfig(url="https://youtube.com/watch?v=abc"),
            progress=100.0,
        )
        with pytest.raises(ValidationError):
            MusicCommentarySession(
                song_config=SongConfig(url="https://youtube.com/watch?v=abc"),
                progress=-1.0,
            )
        with pytest.raises(ValidationError):
            MusicCommentarySession(
                song_config=SongConfig(url="https://youtube.com/watch?v=abc"),
                progress=101.0,
            )

    def test_serialization_roundtrip(self):
        session = MusicCommentarySession(
            song_config=SongConfig(
                url="https://youtube.com/watch?v=abc",
                title="Test Song",
                genre=MusicGenre.ROCK,
            ),
            script_config=ScriptConfig(difficulty=DifficultyLevel.ADVANCED),
            metadata=YouTubeMetadata(title="Test", tags=["english"]),
        )
        data = session.model_dump(mode="json")
        restored = MusicCommentarySession(**data)
        assert restored.id == session.id
        assert restored.song_config.title == "Test Song"
        assert restored.song_config.genre == MusicGenre.ROCK
        assert restored.script_config.difficulty == DifficultyLevel.ADVANCED
        assert restored.metadata.tags == ["english"]

    def test_defaults_populated(self):
        session = MusicCommentarySession(
            song_config=SongConfig(url="https://youtube.com/watch?v=abc"),
        )
        assert session.tts_config.engine == "xtts_v2"
        assert session.audio_mix_config.song_volume_during_narration == 0.15
        assert session.metadata.category_id == "27"
        assert session.script is None
        assert session.youtube_video_id is None
        assert session.step_timings == {}
        assert session.triggered_by == "manual"


class TestMusicCommentarySessionCreate:
    def test_url_required(self):
        with pytest.raises(ValidationError):
            MusicCommentarySessionCreate()

    def test_minimal(self):
        req = MusicCommentarySessionCreate(url="https://youtube.com/watch?v=abc")
        assert req.genre == MusicGenre.POP
        assert req.difficulty == DifficultyLevel.INTERMEDIATE
        assert req.target_duration == 240.0

    def test_full(self):
        req = MusicCommentarySessionCreate(
            url="https://youtube.com/watch?v=abc",
            title="Test Song",
            artist="Test Artist",
            genre=MusicGenre.ROCK,
            difficulty=DifficultyLevel.BEGINNER,
            max_lyrics_lines=8,
            target_duration=180.0,
            highlight_start=30.0,
            highlight_end=90.0,
            triggered_by="n8n",
        )
        assert req.title == "Test Song"
        assert req.max_lyrics_lines == 8

    def test_duration_bounds(self):
        MusicCommentarySessionCreate(url="https://x.com/v", target_duration=120.0)
        MusicCommentarySessionCreate(url="https://x.com/v", target_duration=600.0)
        with pytest.raises(ValidationError):
            MusicCommentarySessionCreate(url="https://x.com/v", target_duration=60.0)
        with pytest.raises(ValidationError):
            MusicCommentarySessionCreate(url="https://x.com/v", target_duration=700.0)


class TestMusicCommentarySessionUpdate:
    def test_all_optional(self):
        update = MusicCommentarySessionUpdate()
        assert update.title is None
        assert update.description is None
        assert update.tags is None
        assert update.privacy_status is None

    def test_partial(self):
        update = MusicCommentarySessionUpdate(title="New Title")
        assert update.title == "New Title"
        assert update.description is None


class TestMusicGenreInfo:
    def test_creation(self):
        info = MusicGenreInfo(value="pop", label="Pop")
        assert info.value == "pop"
        assert info.label == "Pop"
