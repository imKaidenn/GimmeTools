"""
GimmeTools — Background Removal

Remove backgrounds from images using rembg + BiRefNet (ONNX).
Outputs transparent PNGs.

Usage:
    python remove_bg.py photo.jpg
    python remove_bg.py photo.jpg --output clean.png
    python remove_bg.py photos/ --batch
    python remove_bg.py photo.jpg --model u2net
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Allow running from scripts/ or from GimmeTools root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import Config
from lib.logger import setup_logger, log_header
from lib.gpu_detect import detect as detect_gpu

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}


def remove_background(
    input_path: Path,
    output_path: Path,
    model_name: str,
    gpu_setting: str,
    logger,
) -> bool:
    """Remove background from a single image. Returns True on success."""
    try:
        from rembg import remove, new_session
        from PIL import Image
    except ImportError as e:
        logger.error("Missing dependency: %s — run GimmeTools.bat (or: py install\\setup.py) first", e)
        return False

    logger.info("Input      : %s", input_path)
    logger.info("Output     : %s", output_path)
    logger.info("Model      : %s", model_name)

    gpu = detect_gpu(gpu_setting)
    logger.info("GPU        : %s", gpu.detail)

    start = time.perf_counter()

    try:
        session = new_session(model_name)
        img = Image.open(input_path).convert("RGBA")
        result = remove(img, session=session)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path, format="PNG")

        elapsed = time.perf_counter() - start
        logger.info("Completed in %.2fs", elapsed)
        logger.info("Output size: %.1f KB", output_path.stat().st_size / 1024)
        logger.info("Exit code  : 0")
        return True

    except FileNotFoundError:
        logger.error("Input file not found: %s", input_path)
        logger.error("Exit code  : 1")
        return False
    except Exception as e:
        elapsed = time.perf_counter() - start
        logger.error("Failed after %.2fs: %s", elapsed, e)
        logger.error("Exit code  : 1")
        return False


def resolve_output(input_path: Path, output_arg: str | None, suffix: str, output_dir: Path | None) -> Path:
    """Determine output path from input path, user args, and config."""
    if output_arg:
        return Path(output_arg)
    stem = input_path.stem + suffix
    parent = output_dir if output_dir else input_path.parent
    return parent / (stem + ".png")


def collect_images(path: Path) -> list[Path]:
    """Return all image files under path (non-recursive)."""
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
        description="Remove background from images (transparent PNG output)."
    )
    parser.add_argument("input", help="Image file or directory (with --batch)")
    parser.add_argument("-o", "--output", help="Output file path (single image mode)")
    parser.add_argument("--batch", action="store_true", help="Process all images in a directory")
    parser.add_argument("--model", help="rembg model name (default: from config)")
    parser.add_argument("--gpu", choices=["auto", "cpu", "cuda", "directml"],
                        help="GPU mode (default: from config)")
    parser.add_argument("--output-dir", help="Output directory (default: same as input)")

    args = parser.parse_args()
    cfg = Config.load()

    # rembg reads U2NET_HOME for model storage — pin it to the toolkit's
    # models/ dir so models stay inside the portable folder, not ~/.u2net.
    os.environ.setdefault("U2NET_HOME", str(cfg.models_dir))
    cfg.models_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logger("remove-bg", cfg.logs_dir, cfg.log_level, cfg.max_log_files)
    log_header(logger, "background-removal")

    model_name = args.model or cfg.get("background_removal", "model", default="birefnet-general")
    gpu_setting = args.gpu or cfg.get("background_removal", "gpu", default="auto")
    suffix = cfg.get("background_removal", "output_suffix", default="_nobg")
    output_dir = Path(args.output_dir) if args.output_dir else cfg.output_dir

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

    for i, img_path in enumerate(images, 1):
        if total > 1:
            logger.info("── [%d/%d] ─────────────────────────────────", i, total)
            print(f"[{i}/{total}] {img_path.name}")

        out = resolve_output(img_path, args.output if total == 1 else None, suffix, output_dir)

        if not remove_background(img_path, out, model_name, gpu_setting, logger):
            failed += 1

    if total > 1:
        logger.info("── Batch complete: %d/%d succeeded ──", total - failed, total)
        print(f"\nDone: {total - failed}/{total} succeeded.")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
