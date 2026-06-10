"""
GimmeTools — tool registry.

Single source of truth for every tool the app exposes. The UI renders its
sidebar, command palette, and option forms from this data; the job queue
builds CLI commands from it. Adding a tool here is the only step needed to
surface it everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp")
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".mts")


@dataclass(frozen=True)
class ToolOption:
    key: str                      # stable id, also used in presets
    label: str
    kind: str                     # "select" | "toggle"
    flag: str                     # CLI flag, "" for toggles that emit flag only when on
    choices: tuple[str, ...] = ()
    default: object = None
    help: str = ""


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    category: str                 # sidebar group
    description: str
    icon: str                     # inline SVG path data (24x24 viewBox)
    script: str                   # under scripts/
    accepts: str                  # "image" | "video" | "none"
    options: tuple[ToolOption, ...] = ()
    keywords: tuple[str, ...] = ()
    # {option_key: {controlling_value: allowed_values}} — UI-side constraints
    constraints: dict = field(default_factory=dict)


_ICON_WAND = ("M9.5 2.7l1 2.3 2.3 1-2.3 1-1 2.3-1-2.3L6.2 6l2.3-1 1-2.3zM19 3l.7 1.6L21.3 5.3l-1.6.7L19 7.6 18.3 6l-1.6-.7 1.6-.7L19 3zM20.5 12.5L4.9 21.1a1 1 0 0 1-1.4-1.4l8.6-15.6a1 1 0 0 1 1.7 0l6.7 6.7a1 1 0 0 1 0 1.7z")
_ICON_EXPAND = ("M3 9V5a2 2 0 0 1 2-2h4M21 9V5a2 2 0 0 0-2-2h-4M3 15v4a2 2 0 0 0 2 2h4M21 15v4a2 2 0 0 1-2 2h-4")
_ICON_FILM = ("M4 3h16a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM3 8h18M3 16h18M8 3v18M16 3v18")
_ICON_PULSE = ("M3 12h4l2-7 4 14 2-7h6")


TOOLS: tuple[Tool, ...] = (
    Tool(
        id="remove-bg",
        name="Remove Background",
        category="Image",
        description="Cut the background out of any image — transparent PNG out. BiRefNet ONNX, fully local.",
        icon=_ICON_WAND,
        script="remove_bg.py",
        accepts="image",
        options=(
            ToolOption(
                key="model", label="Model", kind="select", flag="--model",
                choices=("birefnet-general", "birefnet-portrait", "isnet-general-use",
                         "u2net", "u2netp", "u2net_human_seg"),
                default="birefnet-general",
                help="birefnet-general is the best all-rounder; -portrait for people.",
            ),
            ToolOption(
                key="gpu", label="GPU", kind="select", flag="--gpu",
                choices=("auto", "cpu", "cuda", "directml"),
                default="auto",
                help="auto picks the best available provider.",
            ),
        ),
        keywords=("background", "transparent", "png", "cutout", "rembg", "alpha"),
    ),
    Tool(
        id="upscale",
        name="Upscale Image",
        category="Image",
        description="Enlarge images 2-4x with Real-ESRGAN. Vulkan-accelerated on NVIDIA, AMD, and Intel.",
        icon=_ICON_EXPAND,
        script="upscale_image.py",
        accepts="image",
        options=(
            ToolOption(
                key="model", label="Model", kind="select", flag="--model",
                choices=("realesrgan-x4plus", "realesrgan-x4plus-anime",
                         "realesrnet-x4plus", "realesr-animevideov3"),
                default="realesrgan-x4plus",
                help="x4plus for photos, -anime for line art, animevideov3 for 2x/3x.",
            ),
            ToolOption(
                key="scale", label="Scale", kind="select", flag="--scale",
                choices=("2", "3", "4"),
                default="4",
                help="2x/3x require the animevideov3 model.",
            ),
        ),
        keywords=("upscale", "enlarge", "esrgan", "4x", "2x", "resolution", "zoom"),
        constraints={
            "scale": {
                "realesrgan-x4plus": ["4"],
                "realesrgan-x4plus-anime": ["4"],
                "realesrnet-x4plus": ["4"],
                "realesr-animevideov3": ["2", "3", "4"],
            },
        },
    ),
    Tool(
        id="process-video",
        name="Process Video",
        category="Video",
        description="Optional Topaz AI enhance, then a clean H.265 encode via HandBrake. One command, whole pipeline.",
        icon=_ICON_FILM,
        script="process_video.py",
        accepts="video",
        options=(
            ToolOption(
                key="skip_topaz", label="Skip Topaz (encode only)", kind="toggle",
                flag="--skip-topaz", default=False,
                help="Topaz runs only if installed; this skips it even then.",
            ),
        ),
        keywords=("video", "encode", "h265", "handbrake", "topaz", "compress", "enhance"),
    ),
    Tool(
        id="diagnose",
        name="Diagnostics",
        category="System",
        description="Check every dependency, GPU, model, and folder. Share the output when reporting issues.",
        icon=_ICON_PULSE,
        script="diagnose.py",
        accepts="none",
        keywords=("diagnose", "doctor", "check", "health", "debug", "gpu"),
    ),
)


def get_tool(tool_id: str) -> Tool:
    for t in TOOLS:
        if t.id == tool_id:
            return t
    raise KeyError(f"unknown tool: {tool_id}")


def tools_as_dicts() -> list[dict]:
    return [asdict(t) for t in TOOLS]


def build_args(tool: Tool, inputs: list[str], options: dict, output_dir: str | None) -> list[str]:
    """Translate UI state into the CLI argument list for the tool's script."""
    args: list[str] = []
    if tool.accepts != "none":
        if not inputs:
            raise ValueError("no input files")
        args.append(inputs[0])
        if len(inputs) == 1 and Path(inputs[0]).is_dir():
            args.append("--batch")

    for opt in tool.options:
        value = options.get(opt.key, opt.default)
        if opt.kind == "toggle":
            if value:
                args.append(opt.flag)
        elif value is not None and str(value) != "":
            args += [opt.flag, str(value)]

    if output_dir and tool.accepts != "none":
        args += ["--output-dir", output_dir]
    return args


def accepted_extensions(tool: Tool) -> tuple[str, ...]:
    if tool.accepts == "image":
        return IMAGE_EXTENSIONS
    if tool.accepts == "video":
        return VIDEO_EXTENSIONS
    return ()


# ── Self-test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    assert len(TOOLS) == 4
    t = get_tool("upscale")
    args = build_args(t, ["C:/x/photo.jpg"], {"model": "realesr-animevideov3", "scale": "2"}, None)
    assert args == ["C:/x/photo.jpg", "--model", "realesr-animevideov3", "--scale", "2"], args
    v = get_tool("process-video")
    args = build_args(v, ["C:/x/in.mp4"], {"skip_topaz": True}, "C:/out")
    assert args == ["C:/x/in.mp4", "--skip-topaz", "--output-dir", "C:/out"], args
    d = get_tool("diagnose")
    assert build_args(d, [], {}, None) == []
    assert all(isinstance(x, dict) for x in tools_as_dicts())
    print("tools_registry.py OK")
