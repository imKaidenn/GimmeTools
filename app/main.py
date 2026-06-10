"""
GimmeTools — desktop app shell (v2).

Native window + system WebView2 + thin Python bridge: the Tauri
architecture, with the Python runtime the backend already requires instead
of a Rust sidecar. The UI is plain HTML/CSS/JS in app/ui/ — no Node, no
bundler, no build step.

Startup is kept under a second by importing only stdlib + pywebview here;
heavy work (ONNX, rembg) happens in job child processes, never in the shell.

Usage:
    python app/main.py             normal launch
    python app/main.py --smoke     hidden window, auto-close, exit 0 if alive
"""

from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.paths import toolkit_root, ui_dir, assets_dir  # noqa: E402

ROOT = toolkit_root()

WINDOW_TITLE = "GimmeTools"
MIN_SIZE = (860, 600)
START_SIZE = (1180, 760)


def _set_window_icon() -> None:
    """Set the titlebar/taskbar icon.

    pywebview only supports the icon kwarg on GTK/QT, so on Windows we send
    WM_SETICON to our window directly. Best-effort: a missing icon must never
    affect startup.
    """
    try:
        import ctypes
        ico = assets_dir() / "icon.ico"
        if not ico.exists():
            return
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = user32.FindWindowW(None, WINDOW_TITLE)
        if not hwnd:
            return
        IMAGE_ICON, LR_LOADFROMFILE = 1, 0x10
        WM_SETICON, ICON_SMALL, ICON_BIG = 0x0080, 0, 1
        for cx, which in ((16, ICON_SMALL), (32, ICON_BIG)):
            hicon = user32.LoadImageW(None, str(ico), IMAGE_ICON, cx, cx, LR_LOADFROMFILE)
            if hicon:
                user32.SendMessageW(hwnd, WM_SETICON, which, hicon)
    except Exception:
        pass


def _crash_dialog(text: str) -> None:
    """Native error box — no tkinter import, works under pythonw."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            None, text, "GimmeTools failed to start", 0x10,
        )
    except Exception:
        pass


def main() -> int:
    smoke = "--smoke" in sys.argv
    t0 = time.perf_counter()

    try:
        import webview

        from app.api import Api

        api = Api()
        window = webview.create_window(
            WINDOW_TITLE,
            url=str(ui_dir() / "index.html"),
            js_api=api,
            width=START_SIZE[0],
            height=START_SIZE[1],
            min_size=MIN_SIZE,
            background_color="#0a0911",
            hidden=smoke,
        )
        api.attach_window(window)

        def on_shown() -> None:
            print(f"[gimmetools] window shown in {time.perf_counter() - t0:.2f}s",
                  flush=True)
            _set_window_icon()
            api.check_updates_async()
            if smoke:
                # Give the page a moment to load, prove the bridge answers,
                # then close from a thread (destroy() must not block 'shown').
                import threading

                def _close() -> None:
                    time.sleep(2.5)
                    try:
                        boot = api.boot()
                        assert boot["tools"], "registry empty"
                        print("[gimmetools] smoke: bridge OK, "
                              f"{len(boot['tools'])} tools", flush=True)
                    finally:
                        window.destroy()

                threading.Thread(target=_close, daemon=True).start()

        window.events.shown += on_shown
        window.events.closed += api.shutdown

        webview.start(gui="edgechromium", debug=False)
        return 0

    except Exception:
        crash = traceback.format_exc()
        try:
            log_path = ROOT / "logs" / "ui-crash.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(crash, encoding="utf-8")
            hint = f"\n\nDetails: {log_path}"
        except OSError:
            hint = ""
        if not smoke:
            last = crash.strip().splitlines()[-1]
            _crash_dialog(f"{last}{hint}")
        print(crash, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
