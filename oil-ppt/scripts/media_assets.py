#!/usr/bin/env python3
"""Stdlib-only media inspection and source policy for oil-ppt."""
from __future__ import annotations

import hashlib
import json
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path


MEDIA_SOURCES = {
    "user-material": {
        "best_for": "用户自有文件、真实产品截图、网页、文档和案例证据",
        "access": "local-or-browser",
        "rights": "记录自有、获准或内部引用依据；不能自动宣称自由授权",
        "priority": 1,
    },
    "wikimedia-commons": {
        "best_for": "历史、文化、人物、地点、档案照片和公共图表",
        "access": "official-api",
        "documentation": "https://www.mediawiki.org/wiki/API:Imageinfo/en",
        "rights": "读取 extmetadata；只接受明确许可，保留作者、来源、许可与修改记录",
        "priority": 2,
    },
    "pexels": {
        "best_for": "当代商业照片与生活方式照片",
        "access": "api-key",
        "documentation": "https://www.pexels.com/api/documentation/",
        "rights": "保留摄影师与 Pexels 来源；遵守 Pexels License，不做素材再分发",
        "priority": 3,
    },
    "openverse": {
        "best_for": "跨站发现开放授权候选",
        "access": "discovery-only",
        "documentation": "https://docs.openverse.org/",
        "rights": "必须回原始 landing page 二次核验，未核验不得进入正式预览",
        "priority": 4,
    },
    "generated-illustration": {
        "best_for": "无事实指向的概念隐喻与氛围插画",
        "access": "environment-image-generator",
        "rights": "不得替代产品、数据、案例、真人或其他事实证据；图内不生成文字",
        "priority": 5,
    },
    "unsplash-api": {
        "best_for": "仅在交付方式允许 API hotlink、下载事件与署名时",
        "access": "not-compatible-with-offline-inline-delivery",
        "documentation": "https://unsplash.com/documentation",
        "rights": "默认不接入本地内联交付管线",
        "priority": 99,
    },
}


RASTER_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _jpeg_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        if handle.read(2) != b"\xff\xd8":
            raise ValueError("invalid JPEG signature")
        while True:
            byte = handle.read(1)
            if not byte:
                break
            if byte != b"\xff":
                continue
            marker = handle.read(1)
            while marker == b"\xff":
                marker = handle.read(1)
            if not marker or marker in {b"\xd8", b"\xd9"}:
                continue
            size_raw = handle.read(2)
            if len(size_raw) != 2:
                break
            size = struct.unpack(">H", size_raw)[0]
            if size < 2:
                raise ValueError("invalid JPEG segment length")
            if marker[0] in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                payload = handle.read(size - 2)
                if len(payload) < 5:
                    break
                return struct.unpack(">HH", payload[1:5])[1], struct.unpack(">HH", payload[1:5])[0]
            handle.seek(size - 2, 1)
    raise ValueError("JPEG dimensions not found")


def _webp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("invalid WebP signature")
    chunk = data[12:16]
    if chunk == b"VP8X":
        return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
    if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], "little")
        return 1 + (bits & 0x3FFF), 1 + ((bits >> 14) & 0x3FFF)
    if chunk == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
        return int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF
    raise ValueError("unsupported or corrupt WebP header")


def _svg_number(value: str | None) -> float | None:
    if not value:
        return None
    match = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)", value)
    return float(match.group(1)) if match else None


def _svg_dimensions(path: Path) -> tuple[int, int]:
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("SVG exceeds the 8 MB inspection limit")
    raw = path.read_text(encoding="utf-8")
    if re.search(r"<\s*(?:script|foreignObject)\b", raw, re.I):
        raise ValueError("SVG scripts and foreignObject are forbidden")
    if re.search(r"(?:href|src)\s*=\s*[\"'](?!#|data:)[^\"']+", raw, re.I):
        raise ValueError("SVG external references are forbidden")
    if re.search(r"url\(\s*[\"']?(?!#|data:)[^)]+", raw, re.I):
        raise ValueError("SVG external CSS URLs are forbidden")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise ValueError(f"invalid SVG XML: {error}") from error
    if root.tag.rsplit("}", 1)[-1].lower() != "svg":
        raise ValueError("SVG root element is missing")
    width = _svg_number(root.get("width"))
    height = _svg_number(root.get("height"))
    view_box = root.get("viewBox") or root.get("viewbox")
    if (not width or not height) and view_box:
        values = [float(value) for value in re.split(r"[\s,]+", view_box.strip()) if value]
        if len(values) == 4:
            width, height = values[2], values[3]
    if not width or not height or width <= 0 or height <= 0:
        raise ValueError("SVG requires positive width/height or viewBox dimensions")
    return round(width), round(height)


def inspect_image(path: Path) -> dict:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"media file is missing: {path}")
    suffix = path.suffix.lower()
    data = path.read_bytes() if suffix in {".png", ".gif", ".webp"} else b""
    if suffix == ".svg":
        mime = "image/svg+xml"
        width, height = _svg_dimensions(path)
    elif suffix == ".png":
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise ValueError("invalid PNG signature or IHDR")
        mime = RASTER_MIME[suffix]
        width, height = struct.unpack(">II", data[16:24])
    elif suffix in {".jpg", ".jpeg"}:
        mime = RASTER_MIME[suffix]
        width, height = _jpeg_dimensions(path)
    elif suffix == ".gif":
        if len(data) < 10 or data[:6] not in {b"GIF87a", b"GIF89a"}:
            raise ValueError("invalid GIF signature")
        mime = RASTER_MIME[suffix]
        width, height = struct.unpack("<HH", data[6:10])
    elif suffix == ".webp":
        mime = RASTER_MIME[suffix]
        width, height = _webp_dimensions(data[:64])
    else:
        raise ValueError(f"unsupported image type: {suffix or '(no extension)'}")
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")
    return {
        "path": str(path),
        "mime": mime,
        "width": width,
        "height": height,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "aspect_ratio": round(width / height, 5),
    }


def outline_media_bindings(slide: dict) -> list[tuple[str, object]]:
    """Return every local image field consumed by a template.

    Keeping this traversal in one place makes nested media as strict as the
    traditional single-image slides without asking the authoring model to
    remember extra verification commands.
    """
    bindings: list[tuple[str, object]] = []
    value = slide.get("image") or slide.get("media") or slide.get("artifact_image")
    if value:
        bindings.append(("image", value))
    if slide.get("secondary_image"):
        bindings.append(("secondary_image", slide["secondary_image"]))
    if slide.get("template") == "sequence-gallery":
        for step_index, step in enumerate(slide.get("steps") or [], start=1):
            if isinstance(step, dict) and step.get("image"):
                bindings.append((f"steps[{step_index}].image", step["image"]))
    if slide.get("template") == "comparison":
        for side_index, side in enumerate(slide.get("sides") or [], start=1):
            if not isinstance(side, dict):
                continue
            for item_index, item in enumerate(side.get("evidence") or [], start=1):
                image = item.get("image") if isinstance(item, dict) else item
                if image:
                    bindings.append((f"sides[{side_index}].evidence[{item_index}].image", image))
    if slide.get("template") == "card-trio":
        for card_index, card in enumerate(slide.get("cards") or [], start=1):
            if not isinstance(card, dict):
                continue
            for item_index, item in enumerate(card.get("images") or [], start=1):
                image = item.get("image") if isinstance(item, dict) else item
                if image:
                    bindings.append((f"cards[{card_index}].images[{item_index}].image", image))
    return bindings


def verify_outline_media(data: dict, base: Path) -> list[dict]:
    root = base.expanduser().resolve()
    verified: list[dict] = []
    for index, slide in enumerate(data.get("slides") or [], start=1):
        for field, bound_value in outline_media_bindings(slide):
            if re.match(r"(?:https?:|data:|file:)", str(bound_value), re.I):
                raise SystemExit(f"Outline slide {index} {field} must be a project-relative local file: {bound_value}")
            path = (root / str(bound_value)).resolve()
            if root not in path.parents:
                raise SystemExit(f"Outline slide {index} {field} must stay inside the project: {bound_value}")
            try:
                details = inspect_image(path)
            except ValueError as error:
                raise SystemExit(f"Outline slide {index} media verification failed for {field}={bound_value}: {error}") from error
            details["slide_id"] = slide.get("id")
            details["field"] = field
            details["relative_path"] = str(bound_value)
            verified.append(details)
    return verified


def print_sources() -> None:
    print(json.dumps({"schema_version": "oil-ppt.media-sources/v1", "sources": MEDIA_SOURCES}, ensure_ascii=False, separators=(",", ":")))
