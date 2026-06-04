"""
External tool discovery for MediaTools.

Finds: ffmpeg, ffprobe, HandBrakeCLI, Topaz Video AI.

Discovery order for each tool:
  1. Explicit path in config.json (paths.<tool>_exe)
  2. MEDIATOOLS_<TOOL>_EXE environment variable
  3. Bundled copy inside tools/ffmpeg/ (ffmpeg/ffprobe only)
  4. Common Windows install locations
  5. PATH (shutil.which)

All searches are non-fatal. Missing optional tools return found=False
so callers can decide whether to skip or abort.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Recompute root here to avoid circular import with config.py at module level.
# Callers that already have a Config should pass config paths explicitly.
def _toolkit_root() -> Path:
    env = os.environ.get("MEDIATOOLS_ROOT", "")
    if env:
        return Path(env).resolve()
    # scripts/lib/tool_discovery.py -> lib -> scripts -> MediaTools
    return Path(__file__).resolve().parent.parent.parent


_ROOT = _toolkit_root()


@dataclass
class ToolResult:
    name: str
    path: Optional[Path]
    version: Optional[str]
    found: bool
    detail: str

    def require(self) -> Path:
        """Return path or raise RuntimeError with a helpful message."""
        if not self.found or self.path is None:
            raise RuntimeError(self.detail)
        return self.path


# ── Public finders ─────────────────────────────────────────────────────────────

def find_ffmpeg(config_path: Optional[Path] = None) -> ToolResult:
    candidates = _build_candidates(
        env_var="MEDIATOOLS_FFMPEG_EXE",
        config_path=config_path,
        bundled=[
            _ROOT / "tools" / "ffmpeg" / "ffmpeg.exe",
            _ROOT / "tools" / "ffmpeg" / "ffmpeg",
        ],
        install_paths=[],
        which_name="ffmpeg",
    )
    return _probe("ffmpeg", candidates, ["-version"], _first_line)


def find_ffprobe(config_path: Optional[Path] = None) -> ToolResult:
    candidates = _build_candidates(
        env_var="MEDIATOOLS_FFPROBE_EXE",
        config_path=config_path,
        bundled=[
            _ROOT / "tools" / "ffmpeg" / "ffprobe.exe",
            _ROOT / "tools" / "ffmpeg" / "ffprobe",
        ],
        install_paths=[],
        which_name="ffprobe",
    )
    return _probe("ffprobe", candidates, ["-version"], _first_line)


def find_handbrake(config_path: Optional[Path] = None) -> ToolResult:
    pf   = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    la   = os.environ.get("LOCALAPPDATA", "")

    install_paths = [
        Path(pf)   / "HandBrake" / "HandBrakeCLI.exe",
        Path(pf86) / "HandBrake" / "HandBrakeCLI.exe",
    ]
    if la:
        install_paths.append(Path(la) / "HandBrake" / "HandBrakeCLI.exe")

    candidates = _build_candidates(
        env_var="MEDIATOOLS_HANDBRAKE_EXE",
        config_path=config_path,
        bundled=[],
        install_paths=install_paths,
        which_name="HandBrakeCLI",
    )
    result = _probe("HandBrakeCLI", candidates, ["--version"], _first_line)
    if not result.found:
        result.detail = (
            "HandBrakeCLI not found. "
            "Download from https://handbrake.fr/downloads2.php "
            "or set MEDIATOOLS_HANDBRAKE_EXE."
        )
    return result


def find_topaz(config_path: Optional[Path] = None) -> ToolResult:
    """
    Locate the Topaz Video AI CLI binary.

    Topaz Video AI 3.x ships a custom ffmpeg.exe at:
      <install dir>/ffmpeg.exe
    It is distinct from the system ffmpeg and must be called with
    TVAI-specific -vf filter arguments.

    Version 2.x uses veai.exe with a different argument schema.
    We prefer tvai/ffmpeg (v3) over veai (v2).
    """
    pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    la = os.environ.get("LOCALAPPDATA", "")

    topaz_dirs = [
        Path(pf) / "Topaz Labs LLC" / "Topaz Video AI",
        Path(pf) / "Topaz Video AI",
    ]
    if la:
        topaz_dirs += [
            Path(la) / "Topaz Labs LLC" / "Topaz Video AI",
        ]

    # v3: custom ffmpeg.exe in install dir (identified by checking for tvai models nearby)
    # v2: veai.exe
    install_paths = []
    for d in topaz_dirs:
        install_paths.append(d / "ffmpeg.exe")   # v3 CLI
        install_paths.append(d / "veai.exe")      # v2 CLI

    candidates = _build_candidates(
        env_var="MEDIATOOLS_TOPAZ_EXE",
        config_path=config_path,
        bundled=[],
        install_paths=install_paths,
        which_name=None,   # don't check PATH — avoid grabbing system ffmpeg
    )

    # Filter: if a candidate is named ffmpeg.exe, confirm it's the Topaz one
    # by checking that a models directory or TopazVideoAI.exe lives beside it.
    verified: list[Path] = []
    for c in candidates:
        if not c.exists():
            continue
        if c.name.lower() == "ffmpeg.exe":
            parent = c.parent
            is_topaz = (
                (parent / "TopazVideoAI.exe").exists()
                or (parent / "models").is_dir()
                or "topaz" in str(parent).lower()
            )
            if not is_topaz:
                continue
        verified.append(c)

    result = _probe("Topaz Video AI", verified, ["--version"], _first_line)
    if not result.found:
        result.detail = (
            "Topaz Video AI not found — AI video enhancement will be skipped. "
            "Install from https://www.topazlabs.com/topaz-video-ai "
            "or set MEDIATOOLS_TOPAZ_EXE."
        )
    return result


# ── Internal ───────────────────────────────────────────────────────────────────

def _build_candidates(
    env_var: str,
    config_path: Optional[Path],
    bundled: list[Path],
    install_paths: list[Path],
    which_name: Optional[str],
) -> list[Path]:
    candidates: list[Path] = []

    if config_path:
        candidates.append(config_path)

    env_val = os.environ.get(env_var, "")
    if env_val:
        candidates.append(Path(env_val))

    candidates.extend(bundled)
    candidates.extend(install_paths)

    if which_name:
        found = shutil.which(which_name)
        if found:
            candidates.append(Path(found))

    return candidates


def _probe(
    name: str,
    candidates: list[Path],
    version_flags: list[str],
    version_parse,
) -> ToolResult:
    for candidate in candidates:
        if not candidate.exists():
            continue
        version = _get_version(candidate, version_flags, version_parse)
        return ToolResult(
            name=name,
            path=candidate,
            version=version,
            found=True,
            detail=f"{name}: {candidate}" + (f" ({version})" if version else ""),
        )
    return ToolResult(
        name=name,
        path=None,
        version=None,
        found=False,
        detail=f"{name} not found.",
    )


def _get_version(exe: Path, flags: list[str], parse) -> Optional[str]:
    try:
        result = subprocess.run(
            [str(exe)] + flags,
            capture_output=True, text=True, timeout=10,
        )
        raw = (result.stdout or result.stderr or "").strip()
        return parse(raw) if raw else None
    except Exception:
        return None


def _first_line(output: str) -> Optional[str]:
    lines = output.splitlines()
    return lines[0].strip() if lines else None


# ── Self-test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    for label, result in [
        ("ffmpeg",      find_ffmpeg()),
        ("ffprobe",     find_ffprobe()),
        ("HandBrakeCLI", find_handbrake()),
        ("Topaz",       find_topaz()),
    ]:
        status = "FOUND" if result.found else "NOT FOUND"
        print(f"  [{status:9}] {result.detail}")
    print("tool_discovery.py OK")
