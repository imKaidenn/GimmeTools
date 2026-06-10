# GimmeTools 2.0 — Release Guide & Notes

## What v2 is

GimmeTools is now a desktop application: a native window hosting a redesigned web UI
(Raycast/Linear-inspired) over the same local processing engine — background removal,
Real-ESRGAN upscaling, and the Topaz→HandBrake video pipeline. The v1 CLIs are
unchanged and remain first-class; the classic customtkinter UI ships as an automatic
fallback. Details: [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md),
[UI_REDESIGN.md](UI_REDESIGN.md), [PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md).

Highlights:
- Command palette (Ctrl+K), sidebar with favorites/categories/recents, keyboard
  shortcuts, toasts, settings panel
- Drag-and-drop importing; batch queue with reorder, pause/resume, cancel
  (process-tree kill); persistent job history with logs
- Saved presets per tool with export/import
- Update check against GitHub releases (opt-out in Settings)
- Warm startup ~1 s; 12.8 MB portable download

## Building a release

On any Windows machine with Python 3.10+:

```bat
py install\build_release.py
```

Produces in `dist\`:

| Artifact | What it is |
|---|---|
| `GimmeTools\` | onedir app — `GimmeTools.exe` + `_internal\` + runtime folders |
| `GimmeTools-2.0-portable-win64.zip` | the portable build (unzip anywhere, run the exe) |
| `GimmeTools-Setup.iss` | Inno Setup 6 script |
| `GimmeTools-Setup-2.0.exe` | installer — built automatically **if `iscc` is on PATH** |

To build the installer, install [Inno Setup 6](https://jrsoftware.org/isinfo.php) and
either re-run the builder or `iscc dist\GimmeTools-Setup.iss`. The installer is
per-user (`%LOCALAPPDATA%\GimmeTools`, no admin), creates Start-menu/desktop entries,
and offers launch-on-finish.

`py install\build_release.py --skip-exe` stages a source-based portable build
(entry point `GimmeTools.bat`) without PyInstaller.

### Publishing

1. `git tag v2.0 && git push --tags`
2. Create a GitHub release for the tag; upload the portable zip and the installer.
3. The in-app update check compares the latest release tag against the running
   version and toasts users on older builds.

## End-user requirements

- Windows 10/11 with the WebView2 runtime (preinstalled on Win 11 and most Win 10).
- Python 3.10+ for the processing engine. First launch shows a one-click **Run
  setup** banner that builds `tools\venv\` and installs the GPU-correct ONNX Runtime.
  The app itself (exe build) runs without Python; only the engine needs it.
- ffmpeg / HandBrakeCLI / Real-ESRGAN binaries as in v1 (`tools\` folders or PATH);
  Topaz Video AI optional, auto-discovered.

## Auto-update: current state and the designed next step

**Shipping now (detection):** startup + on-demand checks of the GitHub releases API;
a toast deep-links to the release page. Offline-safe, opt-out in Settings.

**Designed (delivery), not yet shipped:**
1. Shell downloads the new portable zip to `data\update\` in the background.
2. Integrity check against the release's published size/digest.
3. On next launch, a generated `update.bat` swaps the app folder and relaunches
   (`_internal` swap is atomic-enough for a single-user app; rollback keeps the
   previous folder until one successful boot).
4. Settings gains an "install updates automatically" toggle.

Not implemented yet because unsigned binaries make silent self-replacement a
SmartScreen/AV flag-magnet; revisit with a code-signing cert (or distribute via
winget, which sidesteps self-update entirely).

## Known limitations

- The exe shell is unsigned — first download/run will show SmartScreen's "unknown
  publisher" prompt.
- End-to-end media verification (real rembg inference, Topaz pass, HandBrake encode)
  still needs a machine with the tool binaries installed; the pipeline logic is
  covered by service self-tests and the v1.1 fixes, but a release should be
  preceded by one real run of each tool (`scripts\diagnose.py` first).
- Single-job concurrency by design (GPU saturation); a concurrency setting for
  CPU-only image batches is a reasonable v2.1 candidate.
