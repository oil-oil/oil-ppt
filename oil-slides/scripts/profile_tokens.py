#!/usr/bin/env python3
"""Shared typography and shape profiles for oil-slides."""
from __future__ import annotations


# Keep CJK and Latin on the same geometric sans family. Do not use SF Pro Rounded /
# Arial Rounded MT Bold / ui-rounded: they only round Latin glyphs and leave Chinese
# on PingFang, so mixed text looks like two different typefaces.
_SANS_ZH = '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", Inter, sans-serif'
_SANS_UI = 'Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'

TYPE_PROFILES = {
    "clean": {
        "zh": _SANS_ZH,
        "ui": _SANS_UI,
    },
    # Same letterforms as clean. Friendlier teaching tone should come from shape/radius
    # and copy, not from a separate rounded Latin face.
    "rounded": {
        "zh": _SANS_ZH,
        "ui": _SANS_UI,
    },
    "editorial": {
        "zh": '"Songti SC", STSong, "Noto Serif SC", SimSun, serif',
        "ui": _SANS_UI,
    },
    "technical": {
        "zh": '"IBM Plex Sans", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif',
        "ui": '"SF Mono", "Cascadia Code", Menlo, monospace',
    },
}

TYPE_META = {
    "clean": {"label": "清爽无衬线", "description": "中英文同一套无衬线，现代、克制，适合大多数演示。"},
    "rounded": {
        "label": "亲近无衬线",
        "description": "与 clean 同一套无衬线；亲和感请靠圆角与文案，不改字形。",
    },
    "editorial": {"label": "编辑感衬线", "description": "更像书刊，适合叙事与文化内容。"},
    "technical": {"label": "技术感无衬线", "description": "理性、紧凑，适合系统与工程主题。"},
}

SHAPE_PROFILES = {
    "crisp": {"radius": "10px", "shadow": "0 4px 14px rgba(0,0,0,.035)"},
    "soft": {"radius": "22px", "shadow": "0 10px 28px rgba(0,0,0,.045)"},
    "round": {"radius": "36px", "shadow": "0 14px 34px rgba(0,0,0,.055)"},
}

SHAPE_META = {
    "crisp": {"label": "利落", "description": "边角更克制。"},
    "soft": {"label": "柔和", "description": "默认的轻圆角。"},
    "round": {"label": "圆润", "description": "更明显的圆角。"},
}
