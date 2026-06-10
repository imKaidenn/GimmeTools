"""
GimmeTools — Image Upscaling

Upscale images using Real-ESRGAN (portable ncnn-vulkan binary).
GPU accelerated via Vulkan — works on NVIDIA, AMD, and Intel GPUs.

The realesrgan-ncnn-vulkan binary must be placed in tools/realesrgan/.
Download from: https://github.com/xinntao/Real-ESRGAN/releases

Usage:
    python upscale_image.py photo.jpg
    python upscale_image.py photo.jpg --output big.png
    python upscale_image.py photo.jpg --scale 2
    python upscale_image.py photos/ --batch
    python upscale_image.py photo.jpg --model realesrgan-x4plus-anime
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import Config
from lib.logger import setup_logger, log_header
from lib.tool_discovery import find_realesrgan

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}

# Fixed-factor models reject any other -s value; only realesr-animevideov3
# is multi-scale. Validated up front so users get one clear line instead of
# a raw ncnn crash dump.
MODEL_SCALES = {
    "realesrgan-x4plus": {4},
    "realesrgan-x4plus-anime": {4},
    "realesrnet-x4plus": {4},
    "realesr-animevideov3": {2, 3, 4},
}


# ── Upscale ────────────────────────────────────────────────────────────────────

def upscale_image(
    exe: Path,
    input_path: Path,
    output_path: Path,
    model: str,
    scale: int,
    gpu_id: int,
    logger,
) -> bool:
    """Upscale a single image with realesrgan-ncnn-vulkan. Returns True on success."""
    logger.info("Input      : %s", input_path)
    logger.info("Output     : %s", output_path)
    logger.info("Model      : %s", model)
    logger.info("Scale      : %dx", scale)
    logger.info("GPU ID     : %d", gpu_id)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(exe),
        "-i", str(input_path),
        "-o", str(output_path),
        "-n", model,
        "-s", str(scale),
        "-g", str(gpu_id),
    ]

    logger.info("Command    : %s", " ".join(cmd))
    start = time.perf_counter()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min per image is generous
            cwd=str(exe.parent),  # models are resolved relative to cwd
        )
        elapsed = time.perf_counter() - start

        if result.returncode != 0:
            logger.error("Failed (exit %d) after %.2fs", result.returncode, elapsed)
            if result.stderr:
                for line in result.stderr.strip().splitlines()[-10:]:
                    logger.error("  stderr: %s", line)
            logger.error("Exit code  : 1")
            return False

        if not output_path.exists():
            logger.error("Binary exited 0 but output file not found")
            logger.error("Exit code  : 1")
            return False

        logger.info("Completed in %.2fs", elapsed)
        logger.info("Output size: %.1f KB", output_path.stat().st_size / 1024)
        logger.info("Exit code  : 0")
        return True

    except subprocess.TimeoutExpired:
        logger.error("Timed out after 10 minutes")
        logger.error("Exit code  : 1")
        return False
    except Exception as e:
        logger.error("Error: %s", e)
        logger.error("Exit code  : 1")
        return False


# ── CLI helpers ────────────────────────────────────────────────────────────────

def resolve_output(
    input_path: Path,
    output_arg: Optional[str],
    suffix: str,
    output_dir: Optional[Path],
) -> Path:
    if output_arg:
        return Path(output_arg)
    stem = input_path.stem + suffix
    parent = output_dir if output_dir else input_path.parent
    return parent / (stem + ".png")


def collect_images(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in IMAGE_EXTENSIONS else []
    if path.is_dir():
        return sorted(
            p for p in path.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        )
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upscale images with Real-ESRGAN (GPU-accelerated via Vulkan)."
    )
    parser.add_argument("input", help="Image file or directory (with --batch)")
    parser.add_argument("-o", "--output", help="Output file path (single image mode)")
    parser.add_argument("--batch", action="store_true", help="Process all images in a directory")
    parser.add_argument("--model", help="Model name (default: from config)")
    parser.add_argument("--scale", type=int, help="Upscale factor 2/3/4 (default: from config)")
    parser.add_argument("--gpu-id", type=int, help="GPU device ID (default: from config)")
    parser.add_argument("--output-dir", help="Output directory (default: same as input)")

    args = parser.parse_args()
    cfg = Config.load()

    logger = setup_logger("upscale", cfg.logs_dir, cfg.log_level, cfg.max_log_files)
    log_header(logger, "image-upscale")

    # Resolve settings
    model = args.model or cfg.get("upscale", "model", default="realesrgan-x4plus")
    scale = args.scale or int(cfg.get("upscale", "scale", default=4))
    gpu_id = args.gpu_id if args.gpu_id is not None else int(cfg.get("upscale", "gpu_id", default=0))
    suffix = cfg.get("upscale", "output_suffix", default="_4x")
    output_dir = Path(args.output_dir) if args.output_dir else cfg.output_dir

    # Validate model/scale combination before any work
    allowed = MODEL_SCALES.get(model)
    if allowed and scale not in allowed:
        msg = (
            f"Model '{model}' only supports scale "
            f"{'/'.join(str(s) for s in sorted(allowed))}x — you asked for {scale}x.\n"
            "Use realesr-animevideov3 for 2x/3x, or scale 4 with this model."
        )
        logger.error(msg)
        print(f"Error: {msg}", file=sys.stderr)
        return 1

    # Find the binary
    result = find_realesrgan(cfg.realesrgan_exe)
    if not result.found:
        logger.error(result.detail)
        print(f"Error: {result.detail}", file=sys.stderr)
        return 1
    exe = result.path

    logger.info("Binary     : %s", exe)

    input_path = Path(args.input)
    images = collect_images(input_path)

    if not images:
        logger.error("No images found at: %s", input_path)
        print(f"Error: No images found at {input_path}", file=sys.stderr)
        return 1

    if not args.batch and len(images) > 1:
        logger.error("Multiple images found — use --batch for directories")
        print("Error: Use --batch to process a directory.", file=sys.stderr)
        return 1

    total = len(images)
    failed = 0

    for i, img in enumerate(images, 1):
        if total > 1:
            logger.info("── [%d/%d] ─────────────────────────────────", i, total)
            print(f"[{i}/{total}] {img.name}")

        out = resolve_output(img, args.output if total == 1 else None, suffix, output_dir)

        if not upscale_image(exe, img, out, model, scale, gpu_id, logger):
            failed += 1

    if total > 1:
        logger.info("── Batch complete: %d/%d succeeded ──", total - failed, total)
        print(f"\nDone: {total - failed}/{total} succeeded.")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
