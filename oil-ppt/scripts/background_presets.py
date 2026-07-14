#!/usr/bin/env python3
"""Shared page-background contract and template-default resolution."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "assets" / "templates"

BACKGROUND_PRESETS = {
    "grid-fade": "通用内容页；中心阅读区清楚，网格向边缘淡出",
    "grid-wide": "流程、时间线和开放画布；保留更完整的结构网格",
    "soft-spotlight": "视觉主导或单一焦点页面；用低对比明暗集中注意力",
    "block-field": "章节、总结和关键判断页；用大块低透明色面形成节奏",
}

BACKGROUND_UI_LABELS = {
    "grid-fade": "渐隐网格",
    "grid-wide": "全幅网格",
    "soft-spotlight": "柔光聚焦",
    "block-field": "色块背景",
    "media-owned": "媒体铺底",
}

# Template-owned states are intentionally absent from the public contract.
# Models never choose these values; a template applies them when its media owns
# the whole canvas.
INTERNAL_BACKGROUNDS = {"media-owned"}
ALL_BACKGROUNDS = {*BACKGROUND_PRESETS, *INTERNAL_BACKGROUNDS}


@lru_cache(maxsize=None)
def template_background(template: str) -> str:
    path = TEMPLATES / f"{template}.html"
    if not path.is_file():
        raise SystemExit(f"Unknown template while resolving background: {template}")
    match = re.search(r'data-bg=["\']([^"\']+)["\']', path.read_text(encoding="utf-8"))
    value = match.group(1) if match else "grid-fade"
    if value not in ALL_BACKGROUNDS:
        raise SystemExit(f"Template {template!r} uses unknown background {value!r}.")
    return value


def effective_background(slide: dict) -> str:
    value = str(slide.get("background") or "").strip()
    return value or template_background(str(slide.get("template") or ""))


def background_ui_label(background: str) -> str:
    try:
        return BACKGROUND_UI_LABELS[background]
    except KeyError as error:
        raise ValueError(f"Missing Chinese UI label for background {background!r}.") from error
