# GimmeTools v2 — Architecture

## The shell decision: why not Tauri or Electron

The Phase 2 brief preferred Tauri, falling back to Electron. The decision matrix on the
actual constraints:

| | Tauri | Electron | **pywebview + WebView2 (chosen)** |
|---|---|---|---|
| Window + renderer | native + system WebView2 | bundled Chromium | native + system WebView2 |
| Extra runtime needed | Rust **and** Node toolchains | Node + ~100 MB Chromium per install | none — Python is already required by the backend |
| Backend (rembg/ONNX) | still needs a bundled **Python sidecar** | still needs a bundled **Python sidecar** | first-class |
| Cold start | <1s | 2–4s (misses the stated <1s target) | **0.97s measured** |
| Build on dev machine | ✗ no Rust toolchain installed | possible | ✓ verified end-to-end |
| Download size | small | 80–150 MB | **12.8 MB measured** |

pywebview + WebView2 **is** the Tauri architecture — a native window hosting the OS
webview, with a thin language bridge — minus a second language runtime. Because the
entire UI is plain HTML/CSS/JS with a 20-method JSON bridge, migrating the shell to real
Tauri later is a lift-and-shift: keep `app/ui/` byte-for-byte, reimplement `app/api.py`'s
method surface as Tauri commands.

## Layered structure

```
app/                          ← desktop application (v2)
│   main.py                   shell: window, crash reporting, --smoke
│   api.py                    JS bridge: thin, JSON-in/JSON-out
│   paths.py                  source/frozen path + interpreter resolution
│   services/                 feature services (no UI imports anywhere)
│       tools_registry.py     single source of truth for every tool
│       jobs.py               queue: worker thread + child processes
│       presets.py            named option sets, import/export
│       settings.py           ui-state + whitelisted config.json editor
│       updates.py            GitHub release check (stdlib only)
│   ui/                       plain web front-end (no build step)
│       index.html · app.css · app.js
scripts/                      ← processing CLIs + shared lib (unchanged v1 contract)
│   remove_bg.py · upscale_image.py · process_video.py · diagnose.py
│   lib/                      config, logger, gpu_detect, tool_discovery
ui/gimmetools.py              ← classic customtkinter UI, kept as fallback
install/                      setup.py (env bootstrap) · build_release.py (packaging)
```

### Rules that keep it maintainable

1. **The UI process never does media work.** Every job is a child process running the
   same CLI a terminal user runs, in the toolkit venv. The shell stays responsive, a
   crashed job can't take the app down, and cancel is process-tree kill — no cooperative
   cancellation code in the tools.
2. **`tools_registry.py` is the only place a tool is defined.** Sidebar, command
   palette, option forms, constraint rules (e.g. fixed-4× upscale models), and CLI
   argument building all derive from it. Adding a tool = one registry entry.
3. **Services have no UI knowledge.** Each is independently unit-tested via a
   `__main__` self-test (all passing on Windows); `api.py` is the only composition
   point.
4. **Configuration is centralized and shared.** The app edits the same
   `config/config.json` the CLIs read, through a whitelist (`AppSettings`) so hand
   edits and unknown keys survive round-trips. UI-only state (favorites, recents,
   last-used options) lives in `config/ui-state.json` and is safe to delete.
5. **Typing**: dataclasses + type hints across all new Python; the JS side gets typed
   shapes documented by the bridge methods' return dicts.

## Process model

```
GimmeTools.exe / pythonw app\main.py        (shell, ~stdlib imports only)
 └─ WebView2 (system)                        renders app/ui
 └─ JobQueue worker thread
     └─ tools\venv\Scripts\python.exe -u scripts\<tool>.py …   (one at a time)
         └─ ffmpeg / HandBrakeCLI / Topaz ffmpeg / realesrgan  (grandchildren)
```

- UI ↔ Python: `window.pywebview.api.*` promises; the UI polls `get_state()` at 700 ms
  only while jobs are active (zero idle polling).
- Python → UI push: only for the startup update check (`evaluate_js`).
- Job output: child stdout streamed line-by-line into a ring buffer (300 lines live,
  40 archived per history entry); `[i/n]` lines parsed into progress.

## Logging & crash reporting

- Every job child writes its own timestamped file under `logs/` (v1 contract, rotated).
- Shell crashes write `logs/ui-crash.log` and show a native (ctypes) error dialog —
  no tkinter import, works under `pythonw` and frozen.
- Job history (status, timing, exit code, log tail) persists to
  `data/job-history.json` (cap 200) and powers the History tab.

## Auto-update architecture

Implemented now (detection): `services/updates.py` queries the GitHub releases API at
startup (opt-out in Settings) and on demand; a toast deep-links to the release page.
Designed next step (delivery), documented in RELEASE_V2.md: the installer build enables
download-and-swap — the shell downloads the new portable zip to `data/update/`,
verifies size/hash from the release manifest, and a tiny `update.bat` swaps folders on
next launch. No code signing is assumed; SmartScreen implications are documented.
