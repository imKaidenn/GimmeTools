# GimmeTools — Repository Audit Report

**Date:** 2026-06-10 · **Scope:** full repository (v1.0, commit `64882c6`) · **Auditor:** automated deep review of every source file

---

## 0. Scope correction — what this repo actually is

The audit request assumed GimmeTools is an AI-prompt platform (prompt templates, LLM chains,
agents, token costs). **It is not.** A full-text scan of the repository found zero prompts,
zero LLM API calls, zero agents, and zero AI-orchestration code. GimmeTools is a local media
toolkit that wraps three external engines:

| Feature | Engine | Integration |
|---|---|---|
| Background removal | rembg + BiRefNet (ONNX) | in-process Python |
| Image upscaling | realesrgan-ncnn-vulkan | subprocess |
| Video pipeline | Topaz Video AI (optional) → HandBrakeCLI | subprocess |

Consequently the requested deliverables `PROMPT_AUDIT.md`, `TOKEN_OPTIMIZATION_REPORT.md`,
and `AI_ARCHITECTURE.md` have no subject matter and are intentionally **not produced** —
generating them would be fabrication. The phases that *do* apply (deep code audit, UI/UX
review, code quality, implementation) are covered below and implemented in the accompanying
commits.

---

## 1. Critical issues

### C1 — `tools\handbrake\` is never searched (README contract broken)
- **Where:** `scripts/lib/tool_discovery.py` (`find_handbrake`, `bundled=[]`)
- **What:** README line 52 instructs users to "put HandBrakeCLI.exe on PATH or in
  `tools\handbrake\`", and `.gitignore` even reserves `tools/handbrake/`. The finder checks
  config → env var → Program Files → PATH, but **never** `tools\handbrake\`. A user who
  follows the README gets "HandBrakeCLI not found" and the entire video feature fails.
- **Fix:** add `tools/handbrake/HandBrakeCLI.exe` to the bundled candidates.

### C2 — rembg models ignore `models/` (README contract broken)
- **Where:** `scripts/remove_bg.py`
- **What:** README line 56: "Models for rembg download on first use into `models/`." In
  reality rembg downloads to `%USERPROFILE%\.u2net` because nothing ever sets the
  `U2NET_HOME` environment variable. The `models/` folder and the `paths.models_dir` config
  key are decorative. ~0.4–1.7 GB of model data lands silently in the user's home directory,
  and the "portable folder" promise is broken (moving the toolkit re-downloads nothing, but
  uninstalling leaves orphaned gigabytes).
- **Fix:** set `U2NET_HOME` to `cfg.models_dir` before creating the rembg session.

### C3 — Topaz v3 step cannot work as written
- **Where:** `scripts/process_video.py` (`run_topaz`)
- **What:** Topaz Video AI 3.x's `ffmpeg.exe` requires `TVAI_MODEL_DIR` and
  `TVAI_MODEL_DATA_DIR` environment variables (the GUI sets them in its own session). The
  pipeline spawns it with a clean environment, so the `tvai_up` filter aborts with a
  model-directory error on virtually every install. The flagship "Topaz enhance" path has
  most likely never produced output.
- **Fix:** resolve the standard model locations (`%ProgramData%\Topaz Labs LLC\Topaz Video
  AI\models`, sibling `models/` dir) and pass them in the child environment; also specify an
  explicit high-quality intermediate encoder instead of relying on ffmpeg defaults.

---

## 2. High-priority issues

### H1 — UI log panel freezes during runs (buffered child stdout)
- **Where:** `ui/gimmetools.py` (`Runner.run`)
- **What:** Backend scripts write progress with `print()`. When stdout is a pipe, CPython
  block-buffers (~8 KB), so the "live" log panel shows nothing until the process exits —
  for a 20-minute encode the app looks hung. The UI's core promise (streamed output) only
  works by accident for chatty processes.
- **Fix:** invoke the child as `python -u script.py …` (unbuffered).

### H2 — Cancel orphans HandBrake/Topaz encoders
- **Where:** `ui/gimmetools.py` (`Runner.cancel`)
- **What:** `proc.terminate()` kills only the Python wrapper. The actual `HandBrakeCLI.exe`
  / Topaz `ffmpeg.exe` child keeps encoding at 100 % GPU/CPU with no window and no way to
  stop it short of Task Manager.
- **Fix:** kill the process tree (`taskkill /PID <pid> /T /F` on Windows).

### H3 — UI failures are invisible (pythonw + no excepthook)
- **Where:** `GimmeTools.bat` + `ui/gimmetools.py`
- **What:** The launcher starts the UI with `pythonw.exe` (no console). Any startup crash —
  bad venv, broken customtkinter, a syntax error — exits silently: the user double-clicks
  and nothing happens, with zero feedback anywhere.
- **Fix:** top-level exception hook that writes `logs/ui-crash.log` and shows a Tk error
  box before exiting.

### H4 — Partial batch failures report success (exit 0)
- **Where:** `remove_bg.py`, `upscale_image.py`, `process_video.py` (`return 1 if failed == total else 0`)
- **What:** A batch of 10 with 9 failures exits `0`. Scripting/automation on top of the CLI
  (the project's own context-menu integration included) cannot detect partial failure.
- **Fix:** non-zero exit if *any* item failed.

### H5 — Upscale scale/model mismatch fails cryptically
- **Where:** `scripts/upscale_image.py`, mirrored in the UI's Scale dropdown
- **What:** `realesrgan-x4plus`, `realesrgan-x4plus-anime`, and `realesrnet-x4plus` are
  fixed 4× models; only `realesr-animevideov3` supports 2/3/4×. The config default pairs
  `realesrgan-x4plus` with a free-choice scale, and the UI offers 2/3/4 for every model. A
  user picking "2" gets a raw ncnn crash dump.
- **Fix:** validate the combination up front and fail with a one-line explanation.

---

## 3. Medium-priority issues

| # | Where | Issue | Fix |
|---|---|---|---|
| M1 | `lib/gpu_detect.py` | `_wmi_gpu_name()` shells out to `wmic`, which is removed on Windows 11 24H2+; GPU names silently disappear on new installs. `install/setup.py` already has the correct registry-based approach. | Read `DriverDesc` from the display-class registry key (same as setup.py). |
| M2 | `lib/gpu_detect.py` | Docstring promises forced `cuda`/`directml` "errors if unavailable", but the code silently falls back to CPU through a dead `pass` branch. Users forcing CUDA can't tell it didn't engage. | Honest fallback detail string; docstring matches behavior. |
| M3 | `scripts/process_video.py:213` | GPU detect reads `background_removal.gpu` — wrong config section — and the result is irrelevant to the video pipeline anyway (Topaz/HandBrake manage their own acceleration); it just imports onnxruntime for a log line. | Remove the call. |
| M4 | `scripts/diagnose.py` | Reimplements Real-ESRGAN discovery by hand, ignoring the config/env overrides that `upscale_image.py` honors — diagnostics can contradict actual behavior. | Single `find_realesrgan` in `lib/tool_discovery.py`, used everywhere. |
| M5 | `install/requirements.txt` | `tqdm` and `requests` are installed but never imported anywhere. | Remove. |
| M6 | `scripts/process_video.py` | If `handbrake_preset_name` (config) doesn't match the name inside the preset JSON, HandBrake exits with a cryptic error. The two are user-editable independently. | Read the preset file; if the configured name isn't present, use the file's first preset and log it. |
| M7 | `scripts/upscale_image.py:88-90` | `models_dir` computed and never used (dead code). | Remove. |
| M8 | `README.md` CLI examples | `python scripts\remove_bg.py …` uses the *system* interpreter, which has none of the venv's packages — every example fails as written. | Document the venv interpreter path. |

---

## 4. Low-priority issues

| # | Where | Issue |
|---|---|---|
| L1 | everywhere | Branding split: docstrings, log headers, setup banner, context-menu labels, env vars, and the HandBrake preset all say "MediaTools" in a project shipped as "GimmeTools". User-visible strings fixed; the preset is renamed with a graceful fallback (M6) covering old configs; `MEDIATOOLS_*` env vars are kept as-is for backward compatibility; the uninstaller cleans both old and new context-menu key prefixes. |
| L2 | `remove_bg.py:43`, `diagnose.py:87,96`, `ui/gimmetools.py:150,377`, `register_context_menu.ps1:32` | Stale guidance "run install\setup.ps1 first" — the canonical entry point is `GimmeTools.bat` (setup.ps1 is a thin wrapper kept for habit). |
| L3 | `install/setup.py` | Step comments numbered 1,2,3,3,4,5,7,8,9. Cosmetic. |
| L4 | `lib/logger.py` (`log_header`) | Version hardcoded `"1.0"` separately from `ui/gimmetools.py`'s `VERSION`. Single-source in `lib/__init__.py`. |
| L5 | `register_context_menu.ps1` | Context-menu commands run the console `python.exe`: a console window flashes and vanishes, taking any error message with it. Documented; full fix (a small `pyw` shim with completion toast) deferred to Phase 2 of integration work. |
| L6 | `scripts/process_video.py` docstring | Usage example `--batch videos/` is wrong (the directory is the positional arg). |
| L7 | `scripts/diagnose.py` | Exits 1 when optional tools are missing, so the UI labels a successful diagnostic run "✗ Exited with code 1". Diagnose now always exits 0 — its job is reporting, and the report itself shows the failures. |

---

## 5. Architecture assessment (what's already good)

- **Thin-UI principle is real:** the UI shells out to the same CLIs a terminal user runs;
  deleting `ui/` leaves the backend intact. This is the right shape — keep it.
- **Tool discovery layering** (config → env → bundled → install dirs → PATH) is consistent
  and sensible; the bugs above are gaps in the candidate lists, not in the design.
- **Path discipline:** everything derives from `TOOLKIT_ROOT`; no hardcoded usernames or
  drive letters anywhere. The portability brief was honored.
- **Setup is idempotent** and pure-Python (no PowerShell dependency) — the right call for
  the "PowerShell not on PATH" machines that prompted it.
- **Logging contract** (timestamped per-run files, rotation, mandatory header) is
  implemented and used uniformly by all three pipelines.

## 6. Estimated impact of the fixes

| Fix | Impact |
|---|---|
| C1 + C2 + C3 | The video pipeline and the two README install paths go from *broken on a fresh machine* to working. These three alone justify a 1.1 release. |
| H1 + H2 + H3 | The UI stops looking hung, stops leaking runaway encoders, and stops failing silently — the three biggest "feels broken" reports a real user base would file. |
| H4 + H5 + M6 | Automation on top of the CLI (context menu, scripts) becomes trustworthy. |
| M1 | GPU naming keeps working on current Windows 11 builds. |

## 7. Recommended follow-ups (not in this pass)

1. **Context-menu UX** — replace the console-flash invocation with a tiny `pythonw` shim
   that shows a completion/error toast (L5).
2. **A `--dry-run` flag** on `process_video.py` printing the exact Topaz/HandBrake commands.
3. **CI smoke test** — `python -m compileall` + lib self-tests on a Windows GitHub runner.
4. **Real-ESRGAN auto-download** in setup.py (it's a permissively-licensed portable zip).
