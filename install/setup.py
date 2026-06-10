r"""
GimmeTools setup — pure Python, no PowerShell required.

Creates tools/venv/, installs dependencies (with the right ONNX Runtime for
your GPU), creates directories, generates config.json, and installs the UI
library. Safe to run repeatedly.

Run with any Python 3.10+:
    py install\setup.py
    python install\setup.py

(GimmeTools.bat calls this for you.)
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = ROOT / "tools" / "venv"
REQ_FILE = ROOT / "install" / "requirements.txt"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def log(msg: str = "") -> None:
    print(msg, flush=True)


def step(msg: str) -> None:
    log(f"\n[*] {msg}")


def run(cmd: list[str], **kw) -> int:
    return subprocess.run([str(c) for c in cmd], **kw).returncode


# ── GPU detection (winreg first, then nvidia-smi — no wmic, no PowerShell) ──────

def detect_gpu_vendor() -> str:
    names: list[str] = []

    # Primary: read display adapters straight from the registry (always present).
    if os.name == "nt":
        try:
            import winreg
            key_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            base = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(base, i)
                    i += 1
                except OSError:
                    break
                if not sub.isdigit():
                    continue
                try:
                    k = winreg.OpenKey(base, sub)
                    desc, _ = winreg.QueryValueEx(k, "DriverDesc")
                    names.append(str(desc).lower())
                except OSError:
                    pass
        except Exception:
            pass

    # Secondary: nvidia-smi presence is a strong NVIDIA signal.
    if shutil.which("nvidia-smi"):
        names.append("nvidia")

    blob = " ".join(names)
    if any(w in blob for w in ("nvidia", "geforce", "rtx", "gtx", "quadro", "tesla")):
        return "nvidia"
    if any(w in blob for w in ("radeon", "amd ", "amd\t")) or blob.strip() == "amd":
        return "amd"
    if "intel" in blob and any(w in blob for w in ("arc", "iris", "uhd", "hd graphics")):
        return "intel"
    return "unknown"


def ort_package(vendor: str) -> str:
    return {
        "nvidia": "onnxruntime-gpu",
        "amd": "onnxruntime-directml",
        "intel": "onnxruntime-directml",
    }.get(vendor, "onnxruntime")


# ── Steps ──────────────────────────────────────────────────────────────────────

def main() -> int:
    log("=" * 50)
    log("  GimmeTools Setup")
    log("=" * 50)
    log(f"  Root: {ROOT}")

    # 1. Python version (this interpreter is the bootstrap)
    step("Checking Python...")
    if sys.version_info < (3, 10):
        log(f"    FAIL: Python 3.10+ required. You have {platform.python_version()}.")
        log("    Download from https://www.python.org/downloads/")
        return 1
    log(f"    OK: Python {platform.python_version()}")

    # 2. directories — create the whole tree FIRST, with this interpreter, so
    #    every parent (especially tools/) really exists on disk before venv runs.
    step("Creating directories...")
    for d in ("logs", "models", "outputs/tmp", "config",
              "tools", "tools/ffmpeg", "tools/realesrgan"):
        (ROOT / d).mkdir(parents=True, exist_ok=True)
    log("    OK")

    # 3. venv
    step("Setting up virtual environment...")
    vpy = venv_python()
    if not vpy.exists():
        # Ensure the parent exists (it does, from step 2) then build via the
        # canonical subprocess form — most reliable across Windows setups.
        VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
        rc = run([sys.executable, "-m", "venv", VENV_DIR])
        if rc != 0 or not vpy.exists():
            log("    FAIL: could not create the virtual environment.")
            log(f"    Tried: {sys.executable} -m venv {VENV_DIR}")
            log("    If this persists, your antivirus may be blocking venv —")
            log("    try moving GimmeTools to a simple path like C:\\GimmeTools.")
            return 1
        log(f"    OK: created {VENV_DIR}")
    else:
        log(f"    OK: venv exists at {VENV_DIR}")

    run([vpy, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])

    # 4. GPU
    step("Detecting GPU...")
    vendor = detect_gpu_vendor()
    ort = ort_package(vendor)
    log(f"    GPU vendor: {vendor}")
    log(f"    ONNX Runtime package: {ort}")

    # 5. base packages
    step("Installing base packages (rembg, Pillow, ...)")
    log("    This can take a few minutes the first time.")
    if run([vpy, "-m", "pip", "install", "-r", REQ_FILE]) != 0:
        log("    FAIL: pip install failed. Check your internet connection.")
        return 1
    log("    OK: base packages installed")

    # 6. correct ONNX Runtime
    step("Configuring ONNX Runtime for your hardware...")
    if ort != "onnxruntime":
        # rembg pulled the CPU build; swap it for the GPU build.
        run([vpy, "-m", "pip", "uninstall", "-y", "onnxruntime"])
        if run([vpy, "-m", "pip", "install", f"{ort}>=1.18.0"]) != 0:
            log(f"    WARN: {ort} failed to install — falling back to CPU onnxruntime.")
            run([vpy, "-m", "pip", "install", "onnxruntime>=1.18.0"])
        else:
            log(f"    OK: {ort} installed")
    else:
        run([vpy, "-m", "pip", "install", "onnxruntime>=1.18.0", "--quiet"])
        log("    OK: CPU onnxruntime ready")

    # 7. config.json (uses the backend's own loader so defaults stay in sync)
    step("Generating config...")
    bootstrap = (
        "import sys; sys.path.insert(0, r'%s'); "
        "from lib.config import Config; Config.load()" % (ROOT / "scripts")
    )
    run([vpy, "-c", bootstrap])
    log("    OK: config/config.json ready")

    # 8. UI library
    step("Installing UI library (customtkinter)...")
    run([vpy, "-m", "pip", "install", "customtkinter>=5.2.0", "--quiet"])
    log("    OK")

    # 9. external tools reminder
    step("External tools (download separately):")
    ffmpeg = ROOT / "tools" / "ffmpeg" / "ffmpeg.exe"
    esrgan = ROOT / "tools" / "realesrgan" / "realesrgan-ncnn-vulkan.exe"
    log(f"    ffmpeg       : {'FOUND' if ffmpeg.exists() else 'missing -> https://www.gyan.dev/ffmpeg/builds/'}")
    log(f"    Real-ESRGAN  : {'FOUND' if esrgan.exists() else 'missing -> https://github.com/xinntao/Real-ESRGAN/releases'}")
    log("    (HandBrakeCLI and Topaz are optional, auto-detected if installed.)")

    log("\n" + "=" * 50)
    log("  Setup complete.")
    log("=" * 50)
    log("\n  Launch the app:  double-click GimmeTools.bat")
    log(f"  Or diagnose:     \"{vpy}\" scripts\\diagnose.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
