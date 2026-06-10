"""
GimmeTools — Video Processing Pipeline

Video → (optional) Topaz Video AI enhance → HandBrakeCLI encode → final output.

Usage:
    python process_video.py input.mp4
    python process_video.py input.mp4 --output final.mp4
    python process_video.py input.mp4 --skip-topaz
    python process_video.py videos/ --batch
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import Config
from lib.logger import setup_logger, log_header
from lib.tool_discovery import find_ffmpeg, find_ffprobe, find_handbrake, find_topaz

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".mts"}


# ── Probe ──────────────────────────────────────────────────────────────────────

def probe_video(ffprobe_path: Path, input_path: Path, logger) -> Optional[dict]:
    """Return ffprobe JSON output for the input file."""
    cmd = [
        str(ffprobe_path),
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(input_path),
    ]
    logger.info("Probing    : %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error("ffprobe failed (exit %d): %s", result.returncode, result.stderr.strip())
            return None
        return json.loads(result.stdout)
    except Exception as e:
        logger.error("ffprobe error: %s", e)
        return None


def log_probe(probe_data: dict, logger) -> None:
    """Log key video metadata from probe output."""
    fmt = probe_data.get("format", {})
    logger.info("  Duration : %s s", fmt.get("duration", "?"))
    logger.info("  Size     : %.1f MB", int(fmt.get("size", 0)) / (1024 * 1024))
    logger.info("  Format   : %s", fmt.get("format_long_name", "?"))

    for s in probe_data.get("streams", []):
        codec_type = s.get("codec_type", "")
        if codec_type == "video":
            logger.info("  Video    : %s %sx%s @ %s fps",
                        s.get("codec_name", "?"),
                        s.get("width", "?"), s.get("height", "?"),
                        s.get("r_frame_rate", "?"))
        elif codec_type == "audio":
            logger.info("  Audio    : %s %s ch @ %s Hz",
                        s.get("codec_name", "?"),
                        s.get("channels", "?"),
                        s.get("sample_rate", "?"))


# ── Topaz Step ─────────────────────────────────────────────────────────────────

def run_topaz(
    topaz_exe: Path,
    input_path: Path,
    output_path: Path,
    model: str,
    scale: int,
    logger,
) -> bool:
    """
    Run Topaz Video AI CLI.

    Topaz v3 uses a custom ffmpeg with -vf flags like:
      tvai_up=model=<model>:scale=<n>:...

    Topaz v2 uses veai.exe with different syntax.
    We detect based on the binary name.
    """
    is_v3 = topaz_exe.name.lower() == "ffmpeg.exe"

    env = os.environ.copy()
    if is_v3:
        _set_tvai_env(env, topaz_exe, logger)
        vf = f"tvai_up=model={model}:scale={scale}:device=0"
        cmd = [
            str(topaz_exe),
            "-i", str(input_path),
            "-vf", vf,
            # High-quality intermediate; HandBrake does the final compression.
            "-c:v", "libx264", "-crf", "14", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            "-y",
            str(output_path),
        ]
    else:
        # v2 veai.exe syntax
        cmd = [
            str(topaz_exe),
            "-i", str(input_path),
            "-o", str(output_path),
            "-m", model,
            "-s", str(scale),
        ]

    logger.info("Topaz cmd  : %s", " ".join(cmd))
    start = time.perf_counter()

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=7200,  # 2hr max
            env=env,
        )
        elapsed = time.perf_counter() - start
        if result.returncode != 0:
            logger.error("Topaz failed (exit %d) after %.1fs", result.returncode, elapsed)
            if result.stderr:
                for line in result.stderr.strip().splitlines()[-10:]:
                    logger.error("  stderr: %s", line)
            return False

        logger.info("Topaz done in %.1fs", elapsed)
        return True

    except subprocess.TimeoutExpired:
        logger.error("Topaz timed out after 2 hours")
        return False
    except Exception as e:
        logger.error("Topaz error: %s", e)
        return False


def _set_tvai_env(env: dict, topaz_exe: Path, logger) -> None:
    """
    Topaz's ffmpeg needs TVAI_MODEL_DIR / TVAI_MODEL_DATA_DIR to locate its
    models (the GUI sets these in its own session; a bare subprocess has
    neither). Respect values the user already exported.
    """
    program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    candidates = [
        program_data / "Topaz Labs LLC" / "Topaz Video AI" / "models",
        topaz_exe.parent / "models",
    ]
    model_dir = next((c for c in candidates if c.is_dir()), None)

    if "TVAI_MODEL_DIR" not in env:
        if model_dir:
            env["TVAI_MODEL_DIR"] = str(model_dir)
        else:
            logger.warning("Topaz models dir not found — set TVAI_MODEL_DIR if the Topaz step fails")
    if "TVAI_MODEL_DATA_DIR" not in env and model_dir:
        env["TVAI_MODEL_DATA_DIR"] = str(model_dir)


# ── HandBrake Step ─────────────────────────────────────────────────────────────

def run_handbrake(
    hb_exe: Path,
    input_path: Path,
    output_path: Path,
    preset_file: Optional[Path],
    preset_name: str,
    logger,
) -> bool:
    """Encode with HandBrakeCLI using a JSON preset."""
    cmd = [
        str(hb_exe),
        "-i", str(input_path),
        "-o", str(output_path),
    ]

    if preset_file and preset_file.exists():
        preset_name = _validate_preset_name(preset_file, preset_name, logger)
        cmd += ["--preset-import-file", str(preset_file), "-Z", preset_name]
    else:
        # Fallback to built-in preset
        cmd += ["-Z", "Fast 1080p30"]
        logger.warning("Preset file not found (%s) — using built-in 'Fast 1080p30'",
                        preset_file)

    logger.info("HandBrake  : %s", " ".join(cmd))
    start = time.perf_counter()

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=7200
        )
        elapsed = time.perf_counter() - start
        if result.returncode != 0:
            logger.error("HandBrake failed (exit %d) after %.1fs", result.returncode, elapsed)
            if result.stderr:
                for line in result.stderr.strip().splitlines()[-10:]:
                    logger.error("  stderr: %s", line)
            return False

        logger.info("HandBrake done in %.1fs", elapsed)
        return True

    except subprocess.TimeoutExpired:
        logger.error("HandBrake timed out after 2 hours")
        return False
    except Exception as e:
        logger.error("HandBrake error: %s", e)
        return False


def _validate_preset_name(preset_file: Path, preset_name: str, logger) -> str:
    """
    The configured preset name and the preset file are user-editable
    independently. If the name isn't in the file, fall back to the file's
    first preset instead of letting HandBrake die with a cryptic error.
    """
    try:
        data = json.loads(preset_file.read_text(encoding="utf-8"))
        names = [p.get("PresetName", "") for p in data.get("PresetList", [])]
        if preset_name in names:
            return preset_name
        if names and names[0]:
            logger.warning("Preset '%s' not in %s — using '%s'",
                           preset_name, preset_file.name, names[0])
            return names[0]
    except Exception as e:
        logger.warning("Could not parse preset file %s: %s", preset_file, e)
    return preset_name


# ── Pipeline ───────────────────────────────────────────────────────────────────

def process_one(
    input_path: Path,
    output_path: Path,
    cfg: Config,
    logger,
    skip_topaz: bool = False,
) -> bool:
    """
    Full pipeline for a single video file.
    Returns True if the final output is valid.
    """
    logger.info("Input      : %s", input_path)
    logger.info("Output     : %s", output_path)

    # ── Step 1: Probe ──
    ffprobe_result = find_ffprobe(cfg.ffprobe_exe)
    if not ffprobe_result.found:
        logger.error("ffprobe: %s", ffprobe_result.detail)
        return False

    probe_data = probe_video(ffprobe_result.path, input_path, logger)
    if not probe_data:
        return False
    log_probe(probe_data, logger)

    # ── Step 2: Topaz (optional) ──
    topaz_input = input_path
    topaz_temp = None

    if not skip_topaz:
        topaz_result = find_topaz(cfg.topaz_exe)
        if topaz_result.found:
            logger.info("Topaz      : %s", topaz_result.detail)

            cfg.tmp_dir.mkdir(parents=True, exist_ok=True)
            topaz_temp = cfg.tmp_dir / f"{uuid.uuid4().hex}{input_path.suffix}"

            model = cfg.get("video_pipeline", "topaz_model", default="iris-1")
            scale = int(cfg.get("video_pipeline", "topaz_scale", default=2))

            if run_topaz(topaz_result.path, input_path, topaz_temp, model, scale, logger):
                topaz_input = topaz_temp
            else:
                logger.warning("Topaz step failed — continuing with original input")
                _cleanup(topaz_temp)
                topaz_temp = None
        else:
            logger.info("Topaz      : %s", topaz_result.detail)
    else:
        logger.info("Topaz      : skipped (--skip-topaz)")

    # ── Step 3: HandBrake encode ──
    hb_result = find_handbrake(cfg.handbrake_exe)
    if not hb_result.found:
        logger.error("HandBrake  : %s", hb_result.detail)
        # If Topaz produced output, at least keep it
        if topaz_temp and topaz_temp.exists():
            logger.info("Topaz intermediate preserved: %s", topaz_temp)
        return False

    logger.info("HandBrake  : %s", hb_result.detail)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    preset_name = cfg.get("video_pipeline", "handbrake_preset_name",
                          default="GimmeTools H.265 1080p")

    success = run_handbrake(
        hb_result.path, topaz_input, output_path,
        cfg.handbrake_preset_file, preset_name, logger,
    )

    # ── Step 4: Validate & cleanup ──
    if success and output_path.exists():
        out_probe = probe_video(ffprobe_result.path, output_path, logger)
        if out_probe:
            logger.info("── Output validated ──")
            log_probe(out_probe, logger)

        keep = cfg.get("video_pipeline", "keep_intermediate", default=False)
        if topaz_temp and not keep:
            _cleanup(topaz_temp)
    else:
        if topaz_temp and topaz_temp.exists():
            logger.info("Topaz intermediate preserved for diagnosis: %s", topaz_temp)

    logger.info("Exit code  : %d", 0 if success else 1)
    return success


def _cleanup(path: Optional[Path]) -> None:
    if path and path.exists():
        try:
            path.unlink()
        except OSError:
            pass


# ── CLI ────────────────────────────────────────────────────────────────────────

def resolve_output(input_path: Path, output_arg: Optional[str], output_dir: Optional[Path]) -> Path:
    if output_arg:
        return Path(output_arg)
    stem = input_path.stem + "_processed"
    parent = output_dir if output_dir else input_path.parent
    return parent / (stem + ".mp4")


def collect_videos(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in VIDEO_EXTENSIONS else []
    if path.is_dir():
        return sorted(
            p for p in path.iterdir()
            if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
        )
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process videos: (optional) Topaz enhance → HandBrake encode."
    )
    parser.add_argument("input", help="Video file or directory (with --batch)")
    parser.add_argument("-o", "--output", help="Output file path (single video mode)")
    parser.add_argument("--batch", action="store_true", help="Process all videos in a directory")
    parser.add_argument("--skip-topaz", action="store_true",
                        help="Skip Topaz AI step (HandBrake encode only)")
    parser.add_argument("--output-dir", help="Output directory (default: same as input)")

    args = parser.parse_args()
    cfg = Config.load()

    logger = setup_logger("process-video", cfg.logs_dir, cfg.log_level, cfg.max_log_files)
    log_header(logger, "video-pipeline")

    # Verify ffmpeg is available (needed for probe at minimum)
    ffmpeg_result = find_ffmpeg(cfg.ffmpeg_exe)
    logger.info("ffmpeg     : %s", ffmpeg_result.detail)

    input_path = Path(args.input)
    videos = collect_videos(input_path)

    if not videos:
        logger.error("No video files found at: %s", input_path)
        print(f"Error: No video files found at {input_path}", file=sys.stderr)
        return 1

    if not args.batch and len(videos) > 1:
        logger.error("Multiple videos found — use --batch for directories")
        print("Error: Use --batch to process a directory.", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else cfg.output_dir
    total = len(videos)
    failed = 0

    for i, vid in enumerate(videos, 1):
        if total > 1:
            logger.info("══ [%d/%d] ══════════════════════════════════", i, total)
            print(f"[{i}/{total}] {vid.name}")

        out = resolve_output(vid, args.output if total == 1 else None, output_dir)

        if not process_one(vid, out, cfg, logger, skip_topaz=args.skip_topaz):
            failed += 1

    if total > 1:
        logger.info("══ Batch complete: %d/%d succeeded ══", total - failed, total)
        print(f"\nDone: {total - failed}/{total} succeeded.")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
