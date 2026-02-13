"""Ambient sound library - manages real ambient sound files for mixing with AI music."""

import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

AMBIENT_SOUNDS: Dict[str, dict] = {
    "rain":      {"label": "Rain",      "label_zh": "雨声"},
    "thunder":   {"label": "Thunder",   "label_zh": "雷声"},
    "ocean":     {"label": "Ocean",     "label_zh": "海洋"},
    "stream":    {"label": "Stream",    "label_zh": "溪流"},
    "wind":      {"label": "Wind",      "label_zh": "风声"},
    "birds":     {"label": "Birds",     "label_zh": "鸟鸣"},
    "cicadas":   {"label": "Cicadas",   "label_zh": "蝉鸣"},
    "crickets":  {"label": "Crickets",  "label_zh": "蟋蟀"},
    "frogs":     {"label": "Frogs",     "label_zh": "蛙声"},
    "fireplace": {"label": "Fireplace", "label_zh": "壁炉"},
    "snow":      {"label": "Snow",      "label_zh": "雪"},
    "forest":    {"label": "Forest",    "label_zh": "森林"},
    "waterfall": {"label": "Waterfall", "label_zh": "瀑布"},
    "waves":     {"label": "Waves",     "label_zh": "浪花"},
    "whale":     {"label": "Whale",     "label_zh": "鲸鱼"},
}


def _get_audio_duration(path: Path) -> Optional[float]:
    """Get audio file duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


class AmbientLibrary:
    """Manages ambient sound files stored in data/ambient/."""

    def __init__(self, ambient_dir: Path):
        self._dir = ambient_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def list_sounds(self) -> List[dict]:
        """Return all ambient sounds with availability status."""
        results = []
        for name, meta in AMBIENT_SOUNDS.items():
            path = self._find_file(name)
            available = path is not None
            duration = _get_audio_duration(path) if path else None
            results.append({
                "name": name,
                "label": meta["label"],
                "label_zh": meta["label_zh"],
                "available": available,
                "duration_seconds": round(duration, 1) if duration else None,
            })
        return results

    def get_sound_path(self, name: str) -> Optional[Path]:
        """Get path to a sound file, or None if not available."""
        if name not in AMBIENT_SOUNDS:
            return None
        return self._find_file(name)

    def is_available(self, name: str) -> bool:
        """Check if a sound file exists."""
        return self._find_file(name) is not None

    def get_available_sounds(self, names: List[str]) -> List[Path]:
        """Filter a list of sound names to only those with available files."""
        paths = []
        for name in names:
            path = self.get_sound_path(name)
            if path:
                paths.append(path)
            else:
                logger.warning(f"Ambient sound '{name}' requested but file not found, skipping")
        return paths

    def _find_file(self, name: str) -> Optional[Path]:
        """Find a sound file by name, supporting .wav, .mp3, .flac."""
        for ext in (".wav", ".mp3", ".flac", ".ogg"):
            path = self._dir / f"{name}{ext}"
            if path.exists():
                return path
        return None
