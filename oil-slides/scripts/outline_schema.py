#!/usr/bin/env python3
"""Small explicit outline contract shared by preview, scaffold, and build."""
from __future__ import annotations

import re
from pathlib import Path

from component_contracts import COMPONENT_CONTRACTS, normalize_component_choices
from palette_tokens import PALETTES, canonical_name
from profile_tokens import SHAPE_PROFILES, TYPE_PROFILES


TEMPLATE_FAMILIES = {
    "bleed-split": "bleed", "browser-showcase": "split", "card-trio": "cards",
    "comparison": "comparison", "comparison-list": "comparison", "converge": "canvas",
    "cover": "focal", "diagonal-split": "bleed", "editorial-canvas": "canvas",
    "end": "focal", "metric": "focal", "photo-gradient": "bleed",
    "photo-split": "split", "process-rail": "sequence", "recap": "cards",
    "section": "focal", "split-visual": "split", "tabs": "comparison",
    "three-steps": "sequence", "timeline": "sequence",
}

TEMPLATE_CONTENT_HELP = {
    "cover": "content optional; media variant also requires image",
    "end": "line needs title; line-note needs aside/content; line-artifact needs image + artifact_title + artifact_body",
    "section": "content",
    "three-steps": "steps[3] with label + body",
    "timeline": "steps[4] with label + body",
    "process-rail": "steps[6] or steps[8] with label",
    "card-trio": "cards[3] with title + body",
    "comparison": "sides[2], each with title + points[2]",
    "comparison-list": "sides[2], each with title + points[3]",
    "tabs": "sides[2], each with title + body",
    "metric": "content + metric.value + metric.unit + metric.caption",
    "recap": "content + cards[3] with title + body",
    "converge": "groups[2], each with title + items[2], plus outcome",
    "editorial-canvas": "content; image optional",
    "bleed-split": "content + image",
    "browser-showcase": "content + image",
    "diagonal-split": "content + image",
    "photo-gradient": "content + image",
    "photo-split": "content + image",
    "split-visual": "content + image",
}

MEDIA_TEMPLATES = {
    "bleed-split", "browser-showcase", "diagonal-split", "photo-gradient",
    "photo-split", "split-visual",
}


def _text(value: object) -> str:
    return str(value or "").strip()


def _items(slide: dict, key: str) -> list:
    value = slide.get(key)
    return value if isinstance(value, list) else []


def _label(item: object) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return _text(item.get("label") or item.get("title") or item.get("h2"))
    return ""


def _body(item: object) -> str:
    if isinstance(item, dict):
        return _text(item.get("body") or item.get("text") or item.get("p"))
    return ""


def _require_cards(slide: dict, index: int, key: str, count: int, *, bodies: bool = True) -> list:
    items = _items(slide, key)
    if len(items) != count:
        raise SystemExit(f"Outline slide {index} template {slide['template']!r} requires exactly {count} {key} items.")
    for item_index, item in enumerate(items, start=1):
        if not _label(item):
            raise SystemExit(f"Outline slide {index} {key}[{item_index}] requires a label/title.")
        if bodies and not _body(item):
            raise SystemExit(f"Outline slide {index} {key}[{item_index}] requires body text.")
    return items


def _require_sides(slide: dict, index: int, points: int) -> None:
    sides = _items(slide, "sides")
    if len(sides) != 2:
        raise SystemExit(f"Outline slide {index} template {slide['template']!r} requires exactly 2 sides.")
    for side_index, side in enumerate(sides, start=1):
        if not _label(side):
            raise SystemExit(f"Outline slide {index} sides[{side_index}] requires a title.")
        values = side.get("points") if isinstance(side, dict) else None
        if not isinstance(values, list) or len(values) != points or any(not _text(v.get("text") or v.get("body") if isinstance(v, dict) else v) for v in values):
            raise SystemExit(f"Outline slide {index} sides[{side_index}] requires exactly {points} non-empty points.")


def _require_content(slide: dict, index: int) -> None:
    if not _text(slide.get("content") or slide.get("note") or slide.get("aside")):
        raise SystemExit(f"Outline slide {index} template {slide['template']!r} requires content/note text.")


def validate_slide_content(slide: dict, index: int) -> None:
    template = slide["template"]
    variant = slide["variant"]
    image = _text(slide.get("image") or slide.get("media") or slide.get("artifact_image"))

    if template in MEDIA_TEMPLATES:
        _require_content(slide, index)
        if not image:
            raise SystemExit(f"Outline slide {index} template {template!r} requires an image path.")
    elif template == "cover":
        if variant == "media" and not image:
            raise SystemExit(f"Outline slide {index} cover variant 'media' requires an image path.")
    elif template == "section":
        _require_content(slide, index)
    elif template == "end":
        if variant == "line-note" and not _text(slide.get("aside") or slide.get("content")):
            raise SystemExit(f"Outline slide {index} end variant 'line-note' requires aside/content text.")
        if variant == "line-artifact":
            if not image:
                raise SystemExit(f"Outline slide {index} end variant 'line-artifact' requires an image path.")
            for field in ("artifact_title", "artifact_body"):
                if not _text(slide.get(field)):
                    raise SystemExit(f"Outline slide {index} end variant 'line-artifact' requires {field}.")
    elif template == "three-steps":
        _require_cards(slide, index, "steps", 3)
    elif template == "timeline":
        _require_cards(slide, index, "steps", 4)
    elif template == "process-rail":
        count = 6 if variant == "steps-6" else 8
        _require_cards(slide, index, "steps", count, bodies=False)
    elif template == "card-trio":
        _require_cards(slide, index, "cards", 3)
    elif template == "recap":
        _require_content(slide, index)
        _require_cards(slide, index, "cards", 3)
    elif template == "comparison":
        _require_sides(slide, index, 2)
    elif template == "comparison-list":
        _require_sides(slide, index, 3)
    elif template == "tabs":
        sides = _items(slide, "sides")
        if len(sides) != 2 or any(not _label(side) or not _body(side) for side in sides):
            raise SystemExit(f"Outline slide {index} template 'tabs' requires 2 sides with title and body.")
    elif template == "metric":
        _require_content(slide, index)
        metric = slide.get("metric")
        if not isinstance(metric, dict) or any(not _text(metric.get(key)) for key in ("value", "unit", "caption")):
            raise SystemExit(f"Outline slide {index} template 'metric' requires metric.value, metric.unit and metric.caption.")
    elif template == "converge":
        groups = _items(slide, "groups")
        if len(groups) != 2 or not _text(slide.get("outcome")):
            raise SystemExit(f"Outline slide {index} template 'converge' requires 2 groups and outcome.")
        for group_index, group in enumerate(groups, start=1):
            values = group.get("items") if isinstance(group, dict) else None
            if not _label(group) or not isinstance(values, list) or len(values) != 2 or any(not _text(v) for v in values):
                raise SystemExit(f"Outline slide {index} groups[{group_index}] requires title and exactly 2 items.")
    elif template == "editorial-canvas":
        _require_content(slide, index)


def validate_outline(data: dict, templates_dir: Path) -> list[dict]:
    if not _text(data.get("title")):
        raise SystemExit("Outline requires a title.")
    palette = data.get("palette")
    if isinstance(palette, str):
        if canonical_name(palette) not in PALETTES:
            raise SystemExit(f"Outline palette must be one of: {', '.join(sorted(PALETTES))}.")
    elif isinstance(palette, dict):
        if data.get("palette_source") not in {"user", "brand"}:
            raise SystemExit("A custom palette requires palette_source 'user' or 'brand'.")
        for key in ("accent", "accent_soft", "accent_strong"):
            if not isinstance(palette.get(key), str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", palette[key]):
                raise SystemExit(f"Custom palette requires six-digit {key}.")
    else:
        raise SystemExit("Outline requires an explicit palette name or custom palette object.")
    if data.get("typography") not in TYPE_PROFILES:
        raise SystemExit(f"Outline typography must be one of: {', '.join(TYPE_PROFILES)}.")
    if data.get("shape") not in SHAPE_PROFILES:
        raise SystemExit(f"Outline shape must be one of: {', '.join(SHAPE_PROFILES)}.")
    if data.get("media_policy", "required") not in {"required", "text-only"}:
        raise SystemExit("Outline media_policy must be 'required' or 'text-only'.")

    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        raise SystemExit("Outline requires a non-empty slides array.")
    available = {path.stem for path in templates_dir.glob("*.html")}
    ids: set[str] = set()
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            raise SystemExit(f"Outline slide {index} must be an object.")
        slide_id = slide.get("id")
        title = slide.get("title")
        template = slide.get("template")
        if not isinstance(slide_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slide_id):
            raise SystemExit(f"Outline slide {index} has invalid id.")
        if slide_id in ids:
            raise SystemExit(f"Outline has duplicate id: {slide_id}")
        if not _text(title):
            raise SystemExit(f"Outline slide {index} requires a title.")
        if template not in available or template not in COMPONENT_CONTRACTS:
            raise SystemExit(f"Outline slide {index} uses unknown template {template!r}.")
        highlight = slide.get("highlight")
        if highlight is not None and (not isinstance(highlight, str) or not highlight or highlight not in title):
            raise SystemExit(f"Outline slide {index} highlight must be an exact phrase inside its title.")
        normalize_component_choices(slide, index)
        validate_slide_content(slide, index)
        ids.add(slide_id)
    return slides
