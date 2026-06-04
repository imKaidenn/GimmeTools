"""
Configuration management for MediaTools.

Loads config/config.json relative to the toolkit root, applies defaults
for any missing keys, and exposes typed properties for common settings.

Path resolution priority (highest to lowest):
  1. MEDIATOOLS_ROOT env var
  2. Derived from this file's location: scripts/lib/config.py -> ../../.. = toolkit root
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional


def _resolve_toolkit_root() -> Path:
    env = os.environ.get("MEDIATOOLS_ROOT", "")
    if env:
        return Path(env).resolve()
    # scripts/lib/config.py -> lib -> scripts -> MediaTools
    return Path(__file__).resolve().parent.parent.parent


TOOLKIT_ROOT: Path = _resolve_toolkit_root()

DEFAULTS: dict = {
    "version": "1.0",
    "paths": {
        "output_dir": None,
        "models_dir": None,
        "logs_dir": None,
        "ffmpeg_exe": None,
        "ffprobe_exe": None,
        "handbrake_exe": None,
        "topaz_exe": None,
        "realesrgan_exe": None,
    },
    "background_removal": {
        "model": "birefnet-general",
        "gpu": "auto",
        "output_suffix": "_nobg",
        "output_format": "png",
    },
    "upscale": {
        "model": "realesrgan-x4plus",
        "scale": 4,
        "gpu_id": 0,
        "output_suffix": "_4x",
    },
    "video_pipeline": {
        "topaz_model": "iris-1",
        "topaz_scale": 2,
        "topaz_output_suffix": "_topaz",
        "handbrake_preset_file": "config/hb-preset.json",
        "handbrake_preset_name": "MediaTools H.265 1080p",
        "keep_intermediate": False,
    },
    "logging": {
        "max_log_files": 50,
        "level": "INFO",
    },
}


class Config:
    """Typed access to MediaTools settings."""

    def __init__(self, data: dict) -> None:
        self._data = data

    @staticmethod
    def load() -> "Config":
        """
        Load config/config.json, creating it with defaults if absent.
        Missing keys are filled from DEFAULTS — user settings are never
        overwritten.
        """
        config_path = TOOLKIT_ROOT / "config" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        if not config_path.exists():
            config_path.write_text(
                json.dumps(DEFAULTS, indent=2), encoding="utf-8"
            )
            return Config(_deep_merge(DEFAULTS, {}))

        with config_path.open(encoding="utf-8") as fh:
            user_data = json.load(fh)

        return Config(_deep_merge(DEFAULTS, user_data))

    def get(self, *keys: str, default: Any = None) -> Any:
        """Nested key accessor: config.get('video_pipeline', 'topaz_model')"""
        obj = self._data
        for key in keys:
            if not isinstance(obj, dict) or key not in obj:
                return default
            obj = obj[key]
        return obj

    # ── Resolved path properties ───────────────────────────────────────────

    @property
    def output_dir(self) -> Optional[Path]:
        """None means same folder as input (resolved per-call in entry scripts)."""
        v = self.get("paths", "output_dir")
        return Path(v) if v else None

    @property
    def models_dir(self) -> Path:
        v = self.get("paths", "models_dir")
        return Path(v) if v else TOOLKIT_ROOT / "models"

    @property
    def logs_dir(self) -> Path:
        v = self.get("paths", "logs_dir")
        return Path(v) if v else TOOLKIT_ROOT / "logs"

    @property
    def ffmpeg_exe(self) -> Optional[Path]:
        v = self.get("paths", "ffmpeg_exe")
        return Path(v) if v else None

    @property
    def ffprobe_exe(self) -> Optional[Path]:
        v = self.get("paths", "ffprobe_exe")
        return Path(v) if v else None

    @property
    def handbrake_exe(self) -> Optional[Path]:
        v = self.get("paths", "handbrake_exe")
        return Path(v) if v else None

    @property
    def topaz_exe(self) -> Optional[Path]:
        v = self.get("paths", "topaz_exe")
        return Path(v) if v else None

    @property
    def realesrgan_exe(self) -> Optional[Path]:
        v = self.get("paths", "realesrgan_exe")
        return Path(v) if v else None

    @property
    def log_level(self) -> str:
        return self.get("logging", "level", default="INFO")

    @property
    def max_log_files(self) -> int:
        return int(self.get("logging", "max_log_files", default=50))

    @property
    def handbrake_preset_file(self) -> Path:
        rel = self.get("video_pipeline", "handbrake_preset_file",
                       default="config/hb-preset.json")
        p = Path(rel)
        return p if p.is_absolute() else TOOLKIT_ROOT / p

    @property
    def tmp_dir(self) -> Path:
        return TOOLKIT_ROOT / "outputs" / "tmp"


# ── Internal ───────────────────────────────────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> dict:
    """
    Merge override into base recursively.
    Base keys absent from override are preserved unchanged.
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ── Self-test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cfg = Config.load()
    print(f"Toolkit root : {TOOLKIT_ROOT}")
    print(f"Models dir   : {cfg.models_dir}")
    print(f"Logs dir     : {cfg.logs_dir}")
    print(f"Log level    : {cfg.log_level}")
    print(f"BG model     : {cfg.get('background_removal', 'model')}")
    print(f"Upscale scale: {cfg.get('upscale', 'scale')}")
    print(f"Topaz model  : {cfg.get('video_pipeline', 'topaz_model')}")
    print("config.py OK")
