#!/usr/bin/env python3
"""Stdlib-only media inspection and source policy for oil-ppt."""
from __future__ import annotations

import hashlib
import io
import re
import struct
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

from html_urls import css_urls


RASTER_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    with io.BytesIO(data) as handle:
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


def _svg_dimensions(data: bytes) -> tuple[int, int]:
    try:
        raw = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("SVG must be UTF-8 encoded") from error
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


def inspect_image_bytes(data: bytes, suffix: str) -> dict:
    """Inspect image bytes according to their declared filename extension."""
    suffix = suffix.lower()
    size = len(data)
    if suffix == ".svg" and size > 8 * 1024 * 1024:
        raise ValueError("SVG exceeds the 8 MB inspection limit")
    if suffix == ".svg":
        mime = "image/svg+xml"
        width, height = _svg_dimensions(data)
    elif suffix == ".png":
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise ValueError("invalid PNG signature or IHDR")
        mime = RASTER_MIME[suffix]
        width, height = struct.unpack(">II", data[16:24])
    elif suffix in {".jpg", ".jpeg"}:
        mime = RASTER_MIME[suffix]
        width, height = _jpeg_dimensions(data)
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
        "mime": mime,
        "width": width,
        "height": height,
        "bytes": size,
        "sha256": hashlib.sha256(data).hexdigest(),
        "aspect_ratio": round(width / height, 5),
    }


def inspect_image(path: Path) -> dict:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"media file is missing: {path}")
    details = inspect_image_bytes(path.read_bytes(), path.suffix)
    return {"path": str(path), **details}


class _MediaReferenceParser(HTMLParser):
    """Collect real media attributes while retaining a useful CSS-like locator."""

    _ATTRIBUTES = {
        "img": ("src", "srcset"),
        "source": ("src", "srcset"),
        "image": ("href", "xlink:href"),  # SVG <image>
        "use": ("href", "xlink:href"),    # external SVG symbols
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._seen: dict[str, int] = {}
        self.references: list[dict] = []
        self.errors: list[dict] = []
        self.css_sources: list[tuple[str, str]] = []
        self._style_selector: str | None = None
        self._style_chunks: list[str] = []

    @staticmethod
    def _srcset(value: str) -> list[str]:
        # Width/density descriptors cannot contain unescaped spaces. This is
        # intentionally conservative: invalid candidates are still reported.
        return [candidate.strip().split()[0] for candidate in value.split(",") if candidate.strip()]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = {name.lower(): value for name, value in attrs if value is not None}
        index = self._seen.get(tag, 0) + 1
        self._seen[tag] = index
        selector = f"{tag}:nth-of-type({index})"
        if style := values.get("style"):
            self.css_sources.append((f"{selector}[style]", style))
        if tag == "style":
            self._style_selector = selector
            self._style_chunks = []
        allowed = self._ATTRIBUTES.get(tag)
        if not allowed:
            return
        if tag == "img" and "alt" not in values:
            self.errors.append({
                "selector": selector,
                "attribute": "alt",
                "candidate": 1,
                "path": "",
                "reason": "img requires an alt attribute (use alt=\"\" only for decoration)",
            })
        for attribute in allowed:
            raw = values.get(attribute)
            if raw is None:
                continue
            candidates = self._srcset(raw) if attribute == "srcset" else [raw.strip()]
            for candidate_index, value in enumerate(candidates, start=1):
                if not value or value.startswith("#"):
                    continue
                self.references.append({
                    "selector": selector,
                    "attribute": attribute,
                    "candidate": candidate_index,
                    "path": value,
                })

    def handle_data(self, data: str) -> None:
        if self._style_selector is not None:
            self._style_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "style" and self._style_selector is not None:
            self.css_sources.append((self._style_selector, "".join(self._style_chunks)))
            self._style_selector = None
            self._style_chunks = []


def _project_relative_path(project: Path, slide_file: Path, value: str) -> tuple[Path | None, str | None]:
    """Resolve one HTML media URL without permitting a project boundary escape."""
    if value.startswith("data:"):
        return None, "embedded data URLs are not accepted in slide sources"
    if value.startswith(("/", "\\", "//")) or re.match(r"^[A-Za-z]:[\\/]", value):
        return None, "media must use a project-relative local path"
    if re.match(r"^[a-z][a-z0-9+.-]*:", value, re.I):
        return None, "remote or scheme-qualified media is forbidden"
    resolved = (slide_file.parent / value).resolve()
    if resolved == project or not resolved.is_relative_to(project):
        return None, "media must stay inside the project"
    return resolved, None


def scan_slide_media(project: Path, slide_path: Path, *, slide_id: str | None = None) -> dict:
    """Inspect every ``img``, ``source``, and external SVG reference in one slide.

    Results retain the slide file plus a CSS-like selector so failures are
    actionable at the page source.
    """
    root = project.expanduser().resolve()
    source = slide_path.expanduser().resolve()
    try:
        relative_file = source.relative_to(root).as_posix()
    except ValueError:
        raise ValueError(f"slide HTML must stay inside the project: {source}") from None
    if not source.is_file():
        raise ValueError(f"slide HTML is missing: {relative_file}")
    text = source.read_text(encoding="utf-8")
    parser = _MediaReferenceParser()
    parser.feed(text)
    parser.close()
    css_index = 0
    for selector, css in parser.css_sources:
        for raw_value in css_urls(css):
            value = raw_value.strip()
            if value and not value.startswith("#"):
                css_index += 1
                parser.references.append({
                    "selector": f"{selector} url({css_index})",
                    "attribute": "css-url",
                    "candidate": 1,
                    "path": value,
                })
    items: list[dict] = []
    errors: list[dict] = [
        {"slide": slide_id, "file": relative_file, **item}
        for item in parser.errors
    ]
    cache: dict[Path, dict | ValueError] = {}
    for reference in parser.references:
        value = reference["path"]
        path, reason = _project_relative_path(root, source, value)
        location = {"slide": slide_id, "file": relative_file, **reference}
        if reason:
            errors.append({**location, "reason": reason})
            continue
        assert path is not None
        if path not in cache:
            try:
                cache[path] = inspect_image(path)
            except ValueError as error:
                cache[path] = error
        inspected = cache[path]
        if isinstance(inspected, ValueError):
            errors.append({**location, "reason": str(inspected)})
            continue
        items.append({
            **location,
            "relative_path": path.relative_to(root).as_posix(),
            "inspection": dict(inspected),
        })
    return {"count": len(items), "items": items, "errors": errors}


def scan_deck_media(project: Path, deck: dict) -> dict:
    """Scan the slide HTML paths listed by the minimal deck manifest."""
    root = project.expanduser().resolve()
    paths = deck.get("slides") if isinstance(deck, dict) else None
    if not isinstance(paths, list):
        raise ValueError("deck manifest must contain a slides array")
    items: list[dict] = []
    errors: list[dict] = []
    for page, relative in enumerate(paths, start=1):
        if not isinstance(relative, str) or not relative:
            errors.append({"page": page, "file": str(relative), "reason": "slide path must be a non-empty string"})
            continue
        slide_file = (root / relative).resolve()
        try:
            result = scan_slide_media(root, slide_file, slide_id=slide_file.stem)
        except ValueError as error:
            errors.append({"page": page, "file": relative, "reason": str(error)})
            continue
        for item in result["items"]:
            items.append({"page": page, **item})
        for error in result["errors"]:
            errors.append({"page": page, **error})
    return {"count": len(items), "items": items, "errors": errors}


def verify_deck_media(project: Path, deck: dict) -> list[dict]:
    """Raise one aggregated, locator-rich error for invalid slide media."""
    report = scan_deck_media(project, deck)
    if report["errors"]:
        lines = [
            f"{item.get('file', 'unknown')} {item.get('selector', '')} {item.get('attribute', '')}="
            f"{item.get('path', '')}: {item['reason']}"
            for item in report["errors"]
        ]
        raise SystemExit("Media verification failed:\n- " + "\n- ".join(lines))
    return report["items"]
