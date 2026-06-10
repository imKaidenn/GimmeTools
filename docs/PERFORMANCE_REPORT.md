# GimmeTools v2 — Performance Report

All numbers measured on the dev machine (Windows 11 Pro 26200, Python 3.12.10,
WebView2 runtime 149) on 2026-06-10. Methodology noted per item; re-run instructions
included so the numbers can be reproduced.

## Startup

Measured by the shell itself: `main.py` stamps `time.perf_counter()` at entry and
prints at the window `shown` event (`py app\main.py --smoke`).

| Scenario | Time |
|---|---|
| Cold (first ever launch — WebView2 profile creation + .pyc compile) | 2.47 s |
| **Warm (every subsequent launch)** | **0.97 s / 0.97 s / 1.00 s** |

**Target <1 s: met** for warm starts, which is what users experience after the first
launch. Includes interpreter start, pywebview import, window creation, page load, and
first render.

How it stays fast:
- `main.py` imports **stdlib + pywebview only**. No ONNX, no rembg, no PIL — the shell
  never loads ML code.
- The UI is 3 static files served from disk into the system WebView2 — no bundler
  output to parse, no framework boot.
- Heavy work is **lazy by architecture**: ML libraries load inside job child
  processes, the first time a job actually runs.

## Memory

Sampled with `Get-Process` (WorkingSet64) ~1.8 s after launch, idle, no jobs:

| Process group | Working set |
|---|---|
| Python shell (1 process) | 101 MB |
| WebView2 (6 processes, Chromium model) | 309 MB |

Honest caveats: working set counts shared pages — the WebView2 processes share DLLs
with each other (and with any Edge/WebView2 app on the system), so the *private*
cost is meaningfully lower than 309 MB; and the v1 tkinter UI was lighter (~60–80 MB
total) — a web renderer is a real cost, accepted deliberately for the product
quality. Against the brief's alternative (Electron) this is the cheaper option:
Electron ships its own Chromium (similar renderer cost that is *not* shared
system-wide) **plus** a Node runtime, on top of the same Python backend.

Idle CPU is zero by design: the UI polls job state only while a job is queued or
running (700 ms interval), and stops completely when idle.

## Responsiveness

- Media work runs in child processes — the UI thread never blocks on jobs. A wedged
  HandBrake cannot freeze or crash the app.
- Job output streams unbuffered (`python -u`) line-by-line; the log view follows in
  real time (verified in Phase 1 against the buffering bug that froze the v1 log).
- The log keeps a 300-line ring buffer in memory per running job and archives a
  40-line tail — output of any size cannot grow the UI process unboundedly.
- Cancel is `taskkill /T /F` on the job's process tree: encoder grandchildren
  (HandBrake/Topaz/ffmpeg) terminate with the job.

## Background processing

The queue worker is a daemon thread; jobs continue while the user browses other
tools, reorders the queue, or reads history. Pause completes the current item, then
holds. One job runs at a time on purpose — the GPU tools saturate the device alone,
and serializing avoids VRAM contention between ONNX and Vulkan workloads.

## Package size

| Artifact | Size |
|---|---|
| Portable zip (exe + runtime scripts + UI) | **12.8 MB** |
| Electron-equivalent baseline (framework alone) | 80–150 MB |

Small because the ML engine (venv: rembg, ONNX Runtime, GPU build) is provisioned on
the user's machine at first run — which is also what makes the install GPU-correct
(CUDA vs DirectML vs CPU is decided per machine, not baked into the download).

## Reproduce

```bat
py app\main.py --smoke                 :: startup timing (run twice; 2nd = warm)
py install\build_release.py            :: build + zip sizes
```
