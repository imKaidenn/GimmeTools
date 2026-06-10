"""
GimmeTools — JS bridge.

One class, exposed to the web UI via pywebview's js_api. Every method takes
and returns JSON-able values only. The UI polls get_state() while jobs are
active; everything else is request/response.
"""

from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.config import Config, VERSION  # noqa: E402

from app.services import tools_registry  # noqa: E402
from app.services.jobs import JobQueue  # noqa: E402
from app.services.presets import PresetStore  # noqa: E402
from app.services.settings import AppSettings, UiState  # noqa: E402
from app.services import updates  # noqa: E402


def venv_python() -> Path:
    win = ROOT / "tools" / "venv" / "Scripts" / "python.exe"
    nix = ROOT / "tools" / "venv" / "bin" / "python"
    if win.exists():
        return win
    if nix.exists():
        return nix
    return Path(sys.executable)


class Api:
    def __init__(self) -> None:
        self._window = None   # set by main.py after window creation
        self.cfg = Config.load()
        self.ui_state = UiState(ROOT / "config" / "ui-state.json")
        self.app_settings = AppSettings(ROOT / "config" / "config.json")
        self.presets = PresetStore(ROOT / "config" / "presets.json")
        self.queue = JobQueue(
            python_exe=venv_python(),
            scripts_dir=SCRIPTS_DIR,
            history_path=ROOT / "data" / "job-history.json",
        )

    def attach_window(self, window) -> None:
        self._window = window

    # ── Bootstrap ──────────────────────────────────────────────────────────

    def boot(self) -> dict:
        """Everything the UI needs to render its first frame."""
        return {
            "version": VERSION,
            "root": str(ROOT),
            "venv_ok": "venv" in str(venv_python()),
            "tools": tools_registry.tools_as_dicts(),
            "favorites": self.ui_state.favorites,
            "recents": self.ui_state.recents,
            "settings": self.app_settings.get(),
            "presets": self.presets.list_all(),
            "state": self.queue.snapshot(),
        }

    # ── Jobs ───────────────────────────────────────────────────────────────

    def enqueue(self, tool_id: str, inputs: list, options: dict) -> dict:
        tool = tools_registry.get_tool(tool_id)
        inputs = [str(p) for p in (inputs or [])]

        try:
            output_dir = self.app_settings.get().get("output_dir")
            args = tools_registry.build_args(tool, inputs, options or {}, output_dir)
        except ValueError as e:
            return {"ok": False, "error": str(e)}

        label = self._job_label(tool, inputs)
        job_id = self.queue.enqueue(tool.id, tool.name, label, tool.script, args)
        self.ui_state.touch_recent(tool.id)
        self.ui_state.set_last_options(tool.id, options or {})
        return {"ok": True, "job_id": job_id, "recents": self.ui_state.recents}

    @staticmethod
    def _job_label(tool, inputs: list[str]) -> str:
        if tool.accepts == "none":
            return tool.name
        p = Path(inputs[0])
        if p.is_dir():
            exts = tools_registry.accepted_extensions(tool)
            n = sum(1 for f in p.iterdir()
                    if f.is_file() and f.suffix.lower() in exts)
            return f"{p.name} ({n} files)"
        return p.name

    def get_state(self) -> dict:
        return self.queue.snapshot()

    def cancel_job(self, job_id: str) -> bool:
        return self.queue.cancel(job_id)

    def move_job(self, job_id: str, direction: int) -> bool:
        return self.queue.move(job_id, int(direction))

    def pause_queue(self) -> None:
        self.queue.pause()

    def resume_queue(self) -> None:
        self.queue.resume()

    def clear_history(self) -> None:
        self.queue.clear_history()

    def get_job_log(self, job_id: str) -> list:
        return self.queue.get_log(job_id)

    # ── Favorites / recents ────────────────────────────────────────────────

    def toggle_favorite(self, tool_id: str) -> list:
        return self.ui_state.toggle_favorite(tool_id)

    def get_last_options(self, tool_id: str) -> dict:
        return self.ui_state.get_last_options(tool_id)

    # ── Presets ────────────────────────────────────────────────────────────

    def save_preset(self, tool_id: str, name: str, options: dict) -> dict:
        try:
            self.presets.save(tool_id, name, options or {})
            return {"ok": True, "presets": self.presets.list_all()}
        except ValueError as e:
            return {"ok": False, "error": str(e)}

    def delete_preset(self, preset_id: str) -> dict:
        self.presets.delete(preset_id)
        return {"ok": True, "presets": self.presets.list_all()}

    def export_presets(self, tool_id: Optional[str] = None) -> dict:
        path = self._save_dialog("gimmetools-presets.json")
        if not path:
            return {"ok": False, "error": "cancelled"}
        try:
            n = self.presets.export_to(Path(path), tool_id)
            return {"ok": True, "count": n, "path": path}
        except OSError as e:
            return {"ok": False, "error": str(e)}

    def import_presets(self) -> dict:
        paths = self._open_dialog(file_types=("Preset files (*.json)",))
        if not paths:
            return {"ok": False, "error": "cancelled"}
        try:
            n = self.presets.import_from(Path(paths[0]))
            return {"ok": True, "count": n, "presets": self.presets.list_all()}
        except (ValueError, OSError) as e:
            return {"ok": False, "error": str(e)}

    # ── Settings ───────────────────────────────────────────────────────────

    def get_settings(self) -> dict:
        return self.app_settings.get()

    def save_settings(self, values: dict) -> dict:
        return self.app_settings.update(values or {})

    # ── File pickers / shell ───────────────────────────────────────────────

    def pick_files(self, kind: str) -> list:
        if kind == "image":
            types = ("Images (*.jpg;*.jpeg;*.png;*.bmp;*.tiff;*.tif;*.webp)",)
        elif kind == "video":
            types = ("Videos (*.mp4;*.mkv;*.avi;*.mov;*.wmv;*.flv;*.webm;*.m4v)",)
        else:
            types = ("All files (*.*)",)
        return list(self._open_dialog(file_types=types, multiple=True) or [])

    def pick_folder(self) -> list:
        import webview
        if not self._window:
            return []
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        return list(result or [])

    def open_path(self, path: str) -> bool:
        p = Path(path)
        if not p.exists():
            return False
        os.startfile(str(p))  # noqa: S606 — opening user's own files/folders
        return True

    def open_external(self, url: str) -> bool:
        if not url.startswith(("https://", "http://")):
            return False
        webbrowser.open(url)
        return True

    def _open_dialog(self, file_types: tuple = (), multiple: bool = False):
        import webview
        if not self._window:
            return []
        return self._window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=multiple, file_types=list(file_types),
        )

    def _save_dialog(self, default_name: str):
        import webview
        if not self._window:
            return None
        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename=default_name,
        )
        if isinstance(result, (list, tuple)):
            return result[0] if result else None
        return result

    # ── Updates ────────────────────────────────────────────────────────────

    def check_updates(self) -> dict:
        return updates.check(VERSION).to_dict()

    def check_updates_async(self) -> None:
        """Fire-and-forget on startup; pushes a UI event when newer exists."""
        if not self.app_settings.get().get("check_updates", True):
            return

        def _worker() -> None:
            info = updates.check(VERSION)
            if info.available and self._window:
                import json as _json
                self._window.evaluate_js(
                    f"window.onUpdateAvailable({_json.dumps(info.to_dict())})"
                )

        threading.Thread(target=_worker, daemon=True).start()

    # ── Setup (first run without a venv) ───────────────────────────────────

    def run_setup(self) -> dict:
        """Run install/setup.py as a queue job using the bootstrap python
        (the venv interpreter doesn't exist until setup finishes)."""
        job_id = self.queue.enqueue_cmd(
            "setup", "First-time Setup", "build environment",
            [sys.executable, "-u", str(ROOT / "install" / "setup.py")],
        )
        return {"ok": True, "job_id": job_id}

    def shutdown(self) -> None:
        self.queue.shutdown()
