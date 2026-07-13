#!/usr/bin/env python3
"""Small verified Phosphor icon subset and deterministic search."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CONNECTOR_ICON = "arrow-right"
ICON_ROOT = Path(__file__).resolve().parent.parent / "assets" / "icons"
ICON_CATALOG = {
    "arrow-right": {"aliases": ["arrow", "next", "forward", "箭头", "下一步", "连接"]},
    "lightbulb": {"aliases": ["idea", "insight", "concept", "想法", "洞察", "灵感"]},
    "link": {"aliases": ["url", "connection", "chain", "链接", "连接", "引用"]},
    "file-text": {"aliases": ["document", "markdown", "notes", "文档", "文件", "大纲"]},
    "code": {"aliases": ["developer", "html", "program", "代码", "开发", "程序"]},
    "image": {"aliases": ["photo", "media", "visual", "图片", "照片", "素材"]},
    "magnifying-glass": {"aliases": ["search", "find", "query", "搜索", "查找", "查询"]},
    "download-simple": {"aliases": ["download", "save", "local", "下载", "保存", "本地"]},
    "quotes": {"aliases": ["quote", "citation", "speech", "引用", "原话", "引言"]},
    "chart-line": {"aliases": ["metric", "trend", "analytics", "数据", "趋势", "指标"]},
    "users-three": {"aliases": ["team", "audience", "people", "团队", "用户", "受众"]},
    "check-circle": {"aliases": ["done", "verified", "success", "完成", "验证", "通过"]},
}


def icon_path(name: str) -> Path:
    return ICON_ROOT / f"{name}.svg"


def verify_icon(name: str) -> dict:
    if name not in ICON_CATALOG:
        raise ValueError(f"unknown bundled icon: {name}")
    path = icon_path(name)
    if not path.is_file():
        raise ValueError(f"missing bundled icon: {path.name}")
    raw = path.read_text(encoding="utf-8").strip()
    if not re.search(r'<svg\b[^>]*viewBox=["\']0 0 256 256["\']', raw, re.I):
        raise ValueError(f"icon {name} must use the Phosphor 256 viewBox")
    if re.search(r"<\s*(?:script|foreignObject)\b|\son[a-z]+\s*=", raw, re.I):
        raise ValueError(f"icon {name} contains unsafe SVG content")
    if re.search(r"(?:href|src)\s*=\s*[\"'](?!#|data:)", raw, re.I):
        raise ValueError(f"icon {name} contains an external reference")
    return {
        "name": name,
        "file": path.name,
        "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "aliases": ICON_CATALOG[name]["aliases"],
    }


def verify_icons() -> list[dict]:
    return [verify_icon(name) for name in sorted(ICON_CATALOG)]


def search_icons(query: str) -> list[dict]:
    needle = query.strip().lower()
    ranked = []
    for name, metadata in ICON_CATALOG.items():
        terms = [name, *metadata["aliases"]]
        normalized = [term.lower() for term in terms]
        if not needle or not any(needle in term or term in needle for term in normalized):
            continue
        score = 0 if needle == name else 1 if name.startswith(needle) else 2
        ranked.append((score, name, verify_icon(name)))
    return [item[2] for item in sorted(ranked, key=lambda item: (item[0], item[1]))]


def print_icon_results(query: str | None = None) -> None:
    results = search_icons(query or "") if query is not None else verify_icons()
    print(json.dumps({
        "schema_version": "oil-ppt.icons/v1",
        "family": "Phosphor regular",
        "license": "MIT",
        "count": len(results),
        "icons": results,
    }, ensure_ascii=False, separators=(",", ":")))


def icon_svg_markup(name: str, *, class_name: str = "oil-icon") -> str:
    if name not in ICON_CATALOG:
        return ""
    try:
        verify_icon(name)
    except ValueError:
        return ""
    raw = icon_path(name).read_text(encoding="utf-8").strip()
    raw = re.sub(r"<svg\b([^>]*)>", rf'<svg class="{class_name}" aria-hidden="true" focusable="false"\1>', raw, count=1, flags=re.I)
    return re.sub(r'fill="(?!none)[^"]*"', 'fill="currentColor"', raw)
