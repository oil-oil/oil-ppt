#!/usr/bin/env python3
"""Preserve a screenshot while adapting it to a slide-owned media slot."""
from __future__ import annotations

from pathlib import Path

from media_assets import inspect_image


RATIO_SIZES = {
    "16:9": (1600, 900),
    "16:10": (1600, 1000),
    "4:3": (1440, 1080),
    "1:1": (1200, 1200),
    "21:9": (1890, 810),
}
PADDING = {"compact": 0.045, "standard": 0.075, "spacious": 0.11}
ALIGNMENTS = {
    "center", "left", "right", "top", "bottom",
    "top-left", "top-right", "bottom-left", "bottom-right",
}


def _rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    from PIL import ImageColor
    red, green, blue = ImageColor.getrgb(value)
    return red, green, blue, alpha


def _position(available: tuple[int, int, int, int], size: tuple[int, int], alignment: str) -> tuple[int, int]:
    left, top, right, bottom = available
    width, height = size
    horizontal = "left" if "left" in alignment else "right" if "right" in alignment else "center"
    vertical = "top" if "top" in alignment else "bottom" if "bottom" in alignment else "center"
    x = left if horizontal == "left" else right - width if horizontal == "right" else left + (right - left - width) // 2
    y = top if vertical == "top" else bottom - height if vertical == "bottom" else top + (bottom - top - height) // 2
    return x, y


def frame_media(
    source: Path,
    output: Path,
    *,
    ratio: str = "16:10",
    padding: str = "standard",
    align: str = "center",
    fit: str = "contain",
    palette: dict | None = None,
) -> dict:
    try:
        from PIL import Image, ImageChops, ImageDraw
    except ImportError as error:
        raise ValueError("Pillow is required only for `media frame`; install the `Pillow` Python package") from error
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    if ratio not in RATIO_SIZES:
        raise ValueError(f"ratio must be one of: {', '.join(RATIO_SIZES)}")
    if padding not in PADDING:
        raise ValueError(f"padding must be one of: {', '.join(PADDING)}")
    if align not in ALIGNMENTS:
        raise ValueError(f"align must be one of: {', '.join(sorted(ALIGNMENTS))}")
    if fit not in {"contain", "cover"}:
        raise ValueError("fit must be contain or cover")
    if source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("media frame accepts PNG, JPEG, or WebP screenshots")
    inspect_image(source)
    colors = {
        "canvas": "#FFFFFF",
        "surface": "#F3F5F6",
        "accent_soft": "#F5FAFF",
        **(palette or {}),
    }
    width, height = RATIO_SIZES[ratio]
    canvas = Image.new("RGBA", (width, height), _rgba(colors["canvas"]))
    draw = ImageDraw.Draw(canvas, "RGBA")
    # Two quiet rectangular fields create depth without circles, dense lines,
    # or a second frame around the source.
    draw.rounded_rectangle(
        (round(width * .58), round(height * .04), round(width * 1.04), round(height * .42)),
        radius=round(min(width, height) * .035), fill=_rgba(colors["surface"], 210),
    )
    draw.rounded_rectangle(
        (round(width * -.04), round(height * .68), round(width * .42), round(height * 1.04)),
        radius=round(min(width, height) * .035), fill=_rgba(colors["accent_soft"], 230),
    )
    inset = round(min(width, height) * PADDING[padding])
    available = (inset, inset, width - inset, height - inset)
    available_size = (available[2] - available[0], available[3] - available[1])
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
    scale = min(available_size[0] / image.width, available_size[1] / image.height)
    if fit == "cover":
        scale = max(available_size[0] / image.width, available_size[1] / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    image = image.resize(size, Image.Resampling.LANCZOS)
    if fit == "cover":
        left = max(0, (image.width - available_size[0]) // 2)
        top = max(0, (image.height - available_size[1]) // 2)
        image = image.crop((left, top, left + available_size[0], top + available_size[1]))
        size = image.size
    x, y = _position(available, size, align)
    radius = max(8, round(min(width, height) * .016))
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    mask = ImageChops.multiply(mask, image.getchannel("A"))
    canvas.paste(image, (x, y), mask)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, format="PNG", optimize=True)
    return {
        "source": inspect_image(source),
        "output": inspect_image(output),
        "ratio": ratio,
        "padding": padding,
        "align": align,
        "fit": fit,
    }
