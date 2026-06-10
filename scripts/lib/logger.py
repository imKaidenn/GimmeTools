"""
Logging for GimmeTools.

Each run gets its own timestamped file: YYYY-MM-DD_HH-MM-SS_<operation>.log
Old files are rotated when the count exceeds max_log_files.

Console output is WARNING and above only — INFO stays in the file.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path


_FMT = "[%(asctime)s.%(msecs)03d] %(levelname)-5s %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    operation: str,
    logs_dir: Path,
    level: str = "INFO",
    max_log_files: int = 50,
) -> logging.Logger:
    """
    Create a logger for one run of <operation>.

    Args:
        operation:     Short name used in the filename, e.g. 'remove-bg'.
        logs_dir:      Directory to write log files into (created if absent).
        level:         Logging level string, e.g. 'INFO', 'DEBUG'.
        max_log_files: Keep at most this many .log files; delete oldest first.

    Returns:
        A configured Logger instance. The same name can be retrieved later
        with logging.getLogger('mediatools.<operation>').
    """
    # Unencodable characters (unicode filenames on a cp1252 console) must
    # degrade, not crash the run.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass

    logs_dir.mkdir(parents=True, exist_ok=True)
    _rotate(logs_dir, max_log_files)

    log_path = _make_path(operation, logs_dir)
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    logger = logging.getLogger(f"mediatools.{operation}")
    logger.setLevel(numeric_level)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter(_FMT, datefmt=_DATEFMT)

    # File — all levels
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(numeric_level)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Stderr — WARNING and above only (visible in a terminal without noise)
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


def log_header(logger: logging.Logger, operation: str, version: str | None = None) -> None:
    """Write the mandatory run header to the log."""
    import platform
    if version is None:
        try:
            from .config import VERSION
        except ImportError:  # running as a standalone script, not a package
            from config import VERSION
        version = VERSION
    logger.info("── GimmeTools v%s ──────────────────────────", version)
    logger.info("Operation  : %s", operation)
    logger.info("Platform   : %s %s", platform.system(), platform.version())
    logger.info("Python     : %s", platform.python_version())


# ── Internal ───────────────────────────────────────────────────────────────────

def _make_path(operation: str, logs_dir: Path) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_op = operation.replace(" ", "-").replace("/", "-").replace("\\", "-")
    return logs_dir / f"{ts}_{safe_op}.log"


def _rotate(logs_dir: Path, max_log_files: int) -> None:
    """Delete oldest .log files when count would exceed max_log_files."""
    logs = sorted(logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
    # -1 because we're about to add one more
    excess = len(logs) - (max_log_files - 1)
    for old in logs[:max(excess, 0)]:
        try:
            old.unlink()
        except OSError:
            pass


# ── Self-test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile
    import time

    def _close(lg: logging.Logger) -> None:
        # Windows won't delete (rotate) a log whose handler is still open.
        # Real runs are one process per logger so this only matters here.
        for h in lg.handlers:
            h.close()
        lg.handlers.clear()

    with tempfile.TemporaryDirectory() as tmp:
        log_dir = Path(tmp) / "logs"
        logger = setup_logger("test-op", log_dir, level="DEBUG", max_log_files=5)
        log_header(logger, "test-op")

        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")

        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) == 1, f"Expected 1 log file, got {len(log_files)}"

        log_text = log_files[0].read_text(encoding="utf-8")
        assert "Operation  : test-op" in log_text
        assert "debug message" in log_text
        assert "info message" in log_text
        _close(logger)

        # Test rotation
        for i in range(6):
            _close(setup_logger(f"op-{i}", log_dir, max_log_files=5))
            time.sleep(0.01)

        remaining = list(log_dir.glob("*.log"))
        assert len(remaining) <= 5, f"Rotation failed: {len(remaining)} files remain"

    print("logger.py OK")
