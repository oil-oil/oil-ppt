#!/usr/bin/env python3
"""One system-owned connector icon for flow templates."""
from __future__ import annotations

import re
from pathlib import Path


CONNECTOR_ICON = "arrow-right"
ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "icons" / "arrow-right.svg"


def icon_svg_markup(name: str, *, class_name: str = "oil-icon") -> str:
    if name != CONNECTOR_ICON or not ICON_PATH.is_file():
        return ""
    raw = ICON_PATH.read_text(encoding="utf-8").strip()
    raw = re.sub(r"<svg\b([^>]*)>", rf'<svg class="{class_name}" aria-hidden="true" focusable="false"\1>', raw, count=1, flags=re.I)
    return re.sub(r'fill="(?!none)[^"]*"', 'fill="currentColor"', raw)
