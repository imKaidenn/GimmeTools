"""
GimmeTools — app settings and UI state.

Two stores, both plain JSON under config/:
  config.json    — backend settings (shared with the CLI, via scripts/lib).
                   The app edits a small whitelisted subset.
  ui-state.json  — favorites, recents, last-used options, window prefs.
                   Purely cosmetic; safe to delete at any time.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_RECENTS_LIMIT = 8


class UiState:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict = self._load()

    def _load(self) -> dict:
        try:
            # utf-8-sig: tolerate a BOM from hand-edits/external writers
            data = json.loads(self._path.read_text(encoding="utf-8-sig"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except OSError:
            pass

    # ── Favorites ──────────────────────────────────────────────────────────

    @property
    def favorites(self) -> list[str]:
        return list(self._data.get("favorites", []))

    def toggle_favorite(self, tool_id: str) -> list[str]:
        favs = self._data.setdefault("favorites", [])
        if tool_id in favs:
            favs.remove(tool_id)
        else:
            favs.append(tool_id)
        self._save()
        return list(favs)

    # ── Recents ────────────────────────────────────────────────────────────

    @property
    def recents(self) -> list[str]:
        pairs = sorted(
            self._data.get("recents", {}).items(),
            key=lambda kv: kv[1], reverse=True,
        )
        return [tool_id for tool_id, _ in pairs[:_RECENTS_LIMIT]]

    def touch_recent(self, tool_id: str) -> None:
        self._data.setdefault("recents", {})[tool_id] = time.time()
        self._save()

    # ── Last-used options per tool ─────────────────────────────────────────

    def get_last_options(self, tool_id: str) -> dict:
        return dict(self._data.get("last_options", {}).get(tool_id, {}))

    def set_last_options(self, tool_id: str, options: dict) -> None:
        self._data.setdefault("last_options", {})[tool_id] = options
        self._save()


class AppSettings:
    """Whitelisted, app-editable subset of config/config.json.

    Reads/writes the same file scripts/lib/config.py loads, touching only
    known keys so hand-edits and CLI behavior survive round-trips.
    """

    _EDITABLE = {
        "output_dir": ("paths", "output_dir"),
        "keep_intermediate": ("video_pipeline", "keep_intermediate"),
        "check_updates": ("app", "check_updates"),
    }

    def __init__(self, config_path: Path) -> None:
        self._path = config_path

    def _read(self) -> dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}

    def get(self) -> dict:
        data = self._read()
        out: dict[str, Any] = {}
        for key, (section, name) in self._EDITABLE.items():
            out[key] = data.get(section, {}).get(name)
        if out.get("check_updates") is None:
            out["check_updates"] = True
        return out

    def update(self, values: dict) -> dict:
        data = self._read()
        for key, value in values.items():
            if key not in self._EDITABLE:
                continue
            section, name = self._EDITABLE[key]
            data.setdefault(section, {})[name] = value
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return self.get()


# ── Self-test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        st = UiState(Path(tmp) / "ui-state.json")
        assert st.favorites == []
        st.toggle_favorite("upscale")
        st.toggle_favorite("remove-bg")
        assert UiState(Path(tmp) / "ui-state.json").favorites == ["upscale", "remove-bg"]
        st.toggle_favorite("upscale")
        assert st.favorites == ["remove-bg"]

        st.touch_recent("upscale")
        time.sleep(0.01)
        st.touch_recent("remove-bg")
        assert st.recents[0] == "remove-bg"

        st.set_last_options("upscale", {"scale": "2"})
        assert st.get_last_options("upscale") == {"scale": "2"}

        cfg = Path(tmp) / "config.json"
        cfg.write_text('{"paths": {"output_dir": null}, "logging": {"level": "INFO"}}')
        s = AppSettings(cfg)
        assert s.get()["output_dir"] is None
        assert s.get()["check_updates"] is True
        s.update({"output_dir": "D:/out", "check_updates": False, "bogus": 1})
        data = json.loads(cfg.read_text())
        assert data["paths"]["output_dir"] == "D:/out"
        assert data["logging"]["level"] == "INFO"        # untouched
        assert "bogus" not in str(data)
        assert s.get()["check_updates"] is False
    print("settings.py OK")
