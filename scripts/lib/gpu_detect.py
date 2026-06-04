"""
GPU detection for MediaTools.

Determines the best available ONNX Runtime execution provider:
  CUDA (NVIDIA)  → requires onnxruntime-gpu
  DirectML (AMD/Intel) → requires onnxruntime-directml
  CPU            → requires onnxruntime (base package)

Never raises. Falls back to CPU on any error so the pipeline always continues.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GPUInfo:
    provider: str           # "cuda" | "directml" | "cpu"
    name: Optional[str]     # Human-readable GPU name, if detectable
    ort_version: Optional[str]
    detail: str             # Single log-ready line


def detect(gpu_setting: str = "auto") -> GPUInfo:
    """
    Detect the best available inference provider.

    Args:
        gpu_setting: "auto" tries GPU then falls back to CPU.
                     "cpu"  forces CPU regardless of hardware.
                     "cuda" forces CUDA (errors if unavailable).
                     "directml" forces DirectML (errors if unavailable).

    Returns:
        GPUInfo — never raises.
    """
    if gpu_setting == "cpu":
        return GPUInfo(
            provider="cpu",
            name=None,
            ort_version=_ort_version(),
            detail="CPU forced by config",
        )

    try:
        import onnxruntime as ort

        available = ort.get_available_providers()
        ort_ver = ort.__version__

        if gpu_setting in ("auto", "cuda") and "CUDAExecutionProvider" in available:
            name = _nvidia_name()
            return GPUInfo(
                provider="cuda",
                name=name,
                ort_version=ort_ver,
                detail=f"NVIDIA {name or 'GPU'} — CUDAExecutionProvider — onnxruntime {ort_ver}",
            )

        if gpu_setting in ("auto", "directml") and "DmlExecutionProvider" in available:
            name = _wmi_gpu_name()
            return GPUInfo(
                provider="directml",
                name=name,
                ort_version=ort_ver,
                detail=f"{name or 'AMD/Intel GPU'} — DmlExecutionProvider — onnxruntime {ort_ver}",
            )

        if gpu_setting not in ("auto", "cpu"):
            # Forced provider not available — log but do not raise
            pass

    except ImportError:
        pass
    except Exception:
        pass

    return GPUInfo(
        provider="cpu",
        name=None,
        ort_version=_ort_version(),
        detail="CPU only — no GPU provider available",
    )


def ort_package_for(provider: str) -> str:
    """Return the pip package name that provides this provider."""
    return {
        "cuda": "onnxruntime-gpu",
        "directml": "onnxruntime-directml",
        "cpu": "onnxruntime",
    }.get(provider, "onnxruntime")


# ── Private helpers ────────────────────────────────────────────────────────────

def _ort_version() -> Optional[str]:
    try:
        import onnxruntime as ort
        return ort.__version__
    except Exception:
        return None


def _nvidia_name() -> Optional[str]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return None


def _wmi_gpu_name() -> Optional[str]:
    """Best-effort WMI query for the primary GPU name on Windows."""
    try:
        result = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "name"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            lines = [
                ln.strip() for ln in result.stdout.splitlines()
                if ln.strip() and ln.strip().lower() != "name"
            ]
            if lines:
                return lines[0]
    except Exception:
        pass
    return None


# ── Self-test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    info = detect()
    print("GPU Detection Result")
    print(f"  Provider    : {info.provider}")
    print(f"  Name        : {info.name or 'N/A'}")
    print(f"  ORT version : {info.ort_version or 'not installed'}")
    print(f"  Detail      : {info.detail}")
    print(f"  pip package : {ort_package_for(info.provider)}")
    print("gpu_detect.py OK")
