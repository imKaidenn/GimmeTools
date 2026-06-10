# GimmeTools v1.1 — Release Notes

Full background in [`AUDIT_REPORT.md`](AUDIT_REPORT.md). Finding IDs below (C1, H1, …) refer to it.

## Fixed — things that were broken on a fresh machine

- **`tools\handbrake\` now works** (C1). The README told you to drop `HandBrakeCLI.exe`
  there; the code never looked. Now it does.
- **rembg models now live in `models/`** (C2). They used to land silently in
  `%USERPROFILE%\.u2net` — the toolkit folder is now actually portable, and uninstalling
  doesn't leave gigabytes behind. (`U2NET_HOME` is pinned per-run; an existing `~/.u2net`
  cache keeps working for anything already downloaded there.)
- **The Topaz step can actually run** (C3). Topaz's ffmpeg needs `TVAI_MODEL_DIR` /
  `TVAI_MODEL_DATA_DIR`; GimmeTools now sets them from the standard install locations and
  writes a high-quality H.264 intermediate instead of whatever ffmpeg defaulted to.
- **Diagnostics no longer crashes on Windows** (found live during verification). The report
  used box-drawing characters that don't exist in the default Windows console encoding —
  every `diagnose.py` run on a stock console died with `UnicodeEncodeError`. Output is now
  console-safe, and unicode filenames degrade gracefully instead of crashing any script.

## Fixed — UI

- **Live log actually streams** (H1). Child output was block-buffered, so the log panel sat
  empty until the job finished. Long encodes no longer look hung.
- **Cancel really cancels** (H2). It used to kill only the Python wrapper, leaving
  HandBrake/Topaz encoding at full tilt in the background. It now kills the whole tree.
- **Crashes are visible** (H3). If the UI fails to start you now get an error dialog and
  `logs/ui-crash.log` instead of a double-click that silently does nothing.
- **Scale picker can't produce invalid jobs** (H5). Fixed-4× models lock the scale to 4;
  2×/3× are only offered for the multi-scale model — and the CLI validates the same rule
  with a clear message.

## Fixed — CLI behavior

- Batch runs exit non-zero if **any** item failed (was: only if *all* failed) (H4).
- If the configured HandBrake preset name doesn't match the preset file, the file's first
  preset is used with a logged warning instead of a cryptic HandBrake error (M6).
- `diagnose.py` always exits 0 — it's a report, and the report carries the failures (L7).
- GPU names are read from the registry instead of `wmic`, which no longer exists on
  current Windows 11 builds (M1).
- Forcing `--gpu cuda`/`directml` when unavailable now *says* it fell back to CPU (M2).

## Cleaned up

- Real-ESRGAN discovery unified in `lib/tool_discovery.py` — the upscaler and diagnostics
  can no longer disagree about which binary would run (M4).
- Removed unused dependencies (`tqdm`, `requests`) and dead code (M5, M7, M3).
- All user-facing text says **GimmeTools** (was a mix of GimmeTools/MediaTools). The
  `MEDIATOOLS_*` environment variable overrides are unchanged for compatibility; the
  context-menu uninstaller removes both old- and new-style entries (L1).
- README command-line examples now use the venv interpreter, so they work as written (M8).

## Verification

- `python -m compileall` clean on every source file (Python 3.12).
- All four `scripts/lib/*` self-tests pass on Windows 11.
- `diagnose.py` runs end-to-end on a stock cp1252 console.
- Not exercised in this pass: a real Topaz/HandBrake encode and a rembg inference (no
  tool binaries on the dev machine) — C3's env-var fix follows Topaz's documented CLI
  requirements but should be confirmed on a machine with Topaz installed.
