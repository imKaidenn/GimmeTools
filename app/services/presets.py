"""
GimmeTools — saved presets.

A preset is a named snapshot of one tool's options. Stored in
config/presets.json; export/import is the same shape wrapped with a
format marker so files are self-describing and future-proof.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

_FORMAT = "gimmetools-presets"
_FORMAT_VERSION = 1


class PresetStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._presets: list[dict] = self._load()

    def _load(self) -> list[dict]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._presets, indent=2), encoding="utf-8")

    # ── CRUD ───────────────────────────────────────────────────────────────

    def list_for(self, tool_id: str) -> list[dict]:
        return [p for p in self._presets if p["tool_id"] == tool_id]

    def list_all(self) -> list[dict]:
        return list(self._presets)

    def save(self, tool_id: str, name: str, options: dict) -> dict:
        name = name.strip()
        if not name:
            raise ValueError("preset name is empty")
        # Same name on the same tool replaces (intuitive "overwrite")
        existing = next(
            (p for p in self._presets
             if p["tool_id"] == tool_id and p["name"].lower() == name.lower()),
            None,
        )
        if existing:
            existing["options"] = dict(options)
            existing["updated"] = time.time()
            self._save()
            return existing
        preset = {
            "id": uuid.uuid4().hex[:10],
            "tool_id": tool_id,
            "name": name,
            "options": dict(options),
            "updated": time.time(),
        }
        self._presets.append(preset)
        self._save()
        return preset

    def delete(self, preset_id: str) -> bool:
        before = len(self._presets)
        self._presets = [p for p in self._presets if p["id"] != preset_id]
        if len(self._presets) != before:
            self._save()
            return True
        return False

    # ── Export / import ────────────────────────────────────────────────────

    def export_to(self, file_path: Path, tool_id: str | None = None) -> int:
        presets = self.list_for(tool_id) if tool_id else self.list_all()
        payload = {
            "format": _FORMAT,
            "version": _FORMAT_VERSION,
            "exported": time.time(),
            "presets": presets,
        }
        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return len(presets)

    def import_from(self, file_path: Path) -> int:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        if payload.get("format") != _FORMAT:
            raise ValueError("not a GimmeTools preset file")
        count = 0
        for p in payload.get("presets", []):
            if not isinstance(p, dict) or "tool_id" not in p or "name" not in p:
                continue
            self.save(p["tool_id"], p["name"], p.get("options", {}))
            count += 1
        return count


# ── Self-test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = PresetStore(Path(tmp) / "presets.json")
        p = store.save("upscale", "Anime 2x", {"model": "realesr-animevideov3", "scale": "2"})
        store.save("upscale", "Photo 4x", {"model": "realesrgan-x4plus", "scale": "4"})
        store.save("remove-bg", "Portraits", {"model": "birefnet-portrait"})
        assert len(store.list_for("upscale")) == 2
        assert len(store.list_all()) == 3

        # Same name overwrites
        store.save("upscale", "anime 2x", {"model": "realesr-animevideov3", "scale": "3"})
        assert len(store.list_for("upscale")) == 2
        assert store.list_for("upscale")[0]["options"]["scale"] == "3"

        out = Path(tmp) / "export.json"
        assert store.export_to(out, "upscale") == 2

        store2 = PresetStore(Path(tmp) / "presets2.json")
        assert store2.import_from(out) == 2
        assert len(store2.list_for("upscale")) == 2

        assert store.delete(p["id"])
        assert not store.delete("nope")

        try:
            store2.import_from(Path(tmp) / "presets.json")  # raw list, no marker
            raise AssertionError("should reject non-preset file")
        except (ValueError, Exception):
            pass
    print("presets.py OK")
