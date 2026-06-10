"""
GimmeTools — path resolution that works both from source and frozen.

Source layout:   <root>/app/paths.py   → root is the repo folder.
Frozen (PyInstaller onedir): GimmeTools.exe sits in the root; bundled
modules/data live in <root>/_internal. Runtime folders (scripts/, tools/,
config/, logs/, outputs/, data/) are real directories beside the exe.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))


def toolkit_root() -> Path:
    if FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def ui_dir() -> Path:
    if FROZEN:
        # --add-data places app/ui under the PyInstaller bundle dir
        return Path(getattr(sys, "_MEIPASS", toolkit_root())) / "app" / "ui"
    return Path(__file__).resolve().parent / "ui"


def assets_dir() -> Path:
    if FROZEN:
        return Path(getattr(sys, "_MEIPASS", toolkit_root())) / "assets"
    return toolkit_root() / "assets"


def bootstrap_python() -> Path | None:
    """An interpreter able to run install/setup.py.

    From source that's sys.executable; frozen, the exe is not a Python, so
    find one on the machine (same contract as v1's launcher: Python 3.10+
    is a documented requirement for the processing backend).
    """
    if not FROZEN:
        return Path(sys.executable)
    for name in ("py", "python", "python3"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None
