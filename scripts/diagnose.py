"""
MediaTools — Diagnostics

Checks all dependencies, GPU, models, config — produces a summary
the user can share for troubleshooting.

Usage:
    python diagnose.py
"""

from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import Config, TOOLKIT_ROOT
from lib.gpu_detect import detect as detect_gpu, ort_package_for
from lib.tool_discovery import find_ffmpeg, find_ffprobe, find_handbrake, find_topaz


def section(title: str) -> None:
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")


def ok(msg: str) -> None:
    print(f"  [  OK  ]  {msg}")


def warn(msg: str) -> None:
    print(f"  [ WARN ]  {msg}")


def fail(msg: str) -> None:
    print(f"  [ FAIL ]  {msg}")


def info(msg: str) -> None:
    print(f"  [ INFO ]  {msg}")


def main() -> int:
    issues = 0

    section("System")
    info(f"OS           : {platform.system()} {platform.version()}")
    info(f"Architecture : {platform.machine()}")
    info(f"Python       : {sys.version}")
    info(f"Toolkit root : {TOOLKIT_ROOT}")

    # ── Config ──
    section("Configuration")
    try:
        cfg = Config.load()
        config_file = TOOLKIT_ROOT / "config" / "config.json"
        ok(f"config.json loaded from {config_file}")
        info(f"  Log level    : {cfg.log_level}")
        info(f"  BG model     : {cfg.get('background_removal', 'model')}")
        info(f"  Upscale model: {cfg.get('upscale', 'model')}")
        info(f"  Upscale scale: {cfg.get('upscale', 'scale')}x")
    except Exception as e:
        fail(f"config.json: {e}")
        issues += 1
        cfg = None

    # ── GPU ──
    section("GPU Detection")
    gpu = detect_gpu()
    if gpu.provider != "cpu":
        ok(gpu.detail)
    else:
        warn(gpu.detail)
        info(f"Install {ort_package_for('cuda')} (NVIDIA) or {ort_package_for('directml')} (AMD) for GPU acceleration")

    # ── ONNX Runtime ──
    section("ONNX Runtime")
    try:
        import onnxruntime as ort
        ok(f"onnxruntime {ort.__version__}")
        info(f"Providers: {', '.join(ort.get_available_providers())}")
    except ImportError:
        fail("onnxruntime not installed — run install/setup.ps1")
        issues += 1

    # ── rembg ──
    section("rembg (Background Removal)")
    try:
        import rembg
        ok(f"rembg {rembg.__version__}")
    except ImportError:
        fail("rembg not installed — run install/setup.ps1")
        issues += 1
    except AttributeError:
        ok("rembg installed (version not exposed)")

    # ── Pillow ──
    try:
        from PIL import Image
        ok(f"Pillow {Image.__version__}")
    except ImportError:
        fail("Pillow not installed")
        issues += 1

    # ── Real-ESRGAN ──
    section("Real-ESRGAN (Image Upscaling)")
    esrgan_dir = TOOLKIT_ROOT / "tools" / "realesrgan"
    esrgan_exe = esrgan_dir / "realesrgan-ncnn-vulkan.exe"
    if esrgan_exe.exists():
        ok(f"Binary found: {esrgan_exe}")
        models_dir = esrgan_dir / "models"
        if models_dir.is_dir():
            model_files = list(models_dir.glob("*.bin")) + list(models_dir.glob("*.param"))
            ok(f"Models dir: {len(model_files)} files in {models_dir}")
        else:
            # models might be beside the exe
            model_files = list(esrgan_dir.glob("*.bin")) + list(esrgan_dir.glob("*.param"))
            if model_files:
                ok(f"Models: {len(model_files)} files beside binary")
            else:
                warn("No model files found — upscaling will fail")
                issues += 1
    else:
        env_exe = shutil.which("realesrgan-ncnn-vulkan")
        if env_exe:
            ok(f"Binary found in PATH: {env_exe}")
        else:
            warn("realesrgan-ncnn-vulkan not found")
            info("Download from: https://github.com/xinntao/Real-ESRGAN/releases")
            info(f"Extract to: {esrgan_dir}")

    # ── ffmpeg / ffprobe ──
    section("ffmpeg / ffprobe")
    for label, finder, cfg_path in [
        ("ffmpeg",  find_ffmpeg,  cfg.ffmpeg_exe if cfg else None),
        ("ffprobe", find_ffprobe, cfg.ffprobe_exe if cfg else None),
    ]:
        result = finder(cfg_path)
        if result.found:
            ok(result.detail)
        else:
            fail(result.detail)
            info(f"Place in {TOOLKIT_ROOT / 'tools' / 'ffmpeg' / (label + '.exe')}")
            issues += 1

    # ── HandBrakeCLI ──
    section("HandBrakeCLI")
    hb = find_handbrake(cfg.handbrake_exe if cfg else None)
    if hb.found:
        ok(hb.detail)
    else:
        warn(hb.detail)

    # ── Topaz ──
    section("Topaz Video AI (Optional)")
    topaz = find_topaz(cfg.topaz_exe if cfg else None)
    if topaz.found:
        ok(topaz.detail)
    else:
        info(topaz.detail)

    # ── Directories ──
    section("Directories")
    for label, path in [
        ("Logs",    TOOLKIT_ROOT / "logs"),
        ("Models",  TOOLKIT_ROOT / "models"),
        ("Outputs", TOOLKIT_ROOT / "outputs"),
        ("Tmp",     TOOLKIT_ROOT / "outputs" / "tmp"),
    ]:
        if path.is_dir():
            ok(f"{label}: {path}")
        else:
            warn(f"{label}: {path} (does not exist — will be created on first run)")

    # ── Disk space ──
    section("Disk Space")
    try:
        usage = shutil.disk_usage(TOOLKIT_ROOT)
        free_gb = usage.free / (1024 ** 3)
        if free_gb < 5:
            warn(f"{free_gb:.1f} GB free on {TOOLKIT_ROOT.drive or TOOLKIT_ROOT.anchor} — video processing needs 10+ GB")
            issues += 1
        else:
            ok(f"{free_gb:.1f} GB free on {TOOLKIT_ROOT.drive or TOOLKIT_ROOT.anchor}")
    except Exception:
        info("Could not check disk space")

    # ── Summary ──
    section("Summary")
    if issues == 0:
        print("\n  All checks passed. MediaTools is ready.\n")
    else:
        print(f"\n  {issues} issue(s) found. See details above.\n")

    return 0 if issues == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
