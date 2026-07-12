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
    "clean-halo": "章节、总结和收束页；减少网格并保留轻微空间层次",
    "paper-wash": "卡片、对比和编辑感页面；加入极轻纸张质感",
    "soft-spotlight": "视觉主导或单一焦点页面；用柔和聚光集中注意力",
    "mist-grid": "关系图、机制图和较开放的信息画布；网格更柔和",
    "section-glow": "章节转折和关键判断页；只在局部形成克制的强调",
    "none": "照片全幅或背景本身已经承担视觉时",
}


@lru_cache(maxsize=None)
def template_background(template: str) -> str:
    path = TEMPLATES / f"{template}.html"
    if not path.is_file():
        raise SystemExit(f"Unknown template while resolving background: {template}")
    match = re.search(r'data-bg=["\']([^"\']+)["\']', path.read_text(encoding="utf-8"))
    value = match.group(1) if match else "grid-fade"
    if value not in BACKGROUND_PRESETS:
        raise SystemExit(f"Template {template!r} uses unknown background {value!r}.")
    return value


def effective_background(slide: dict) -> str:
    value = str(slide.get("background") or "").strip()
    return value or template_background(str(slide.get("template") or ""))

