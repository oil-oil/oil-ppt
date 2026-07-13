#!/usr/bin/env python3
"""Shared typography and shape profiles for oil-ppt."""
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
    "crisp": {"radius": "12px", "radius_sm": "10px", "radius_lg": "18px", "media_radius": "12px", "icon_radius": "10px", "shadow": "none"},
    "soft": {"radius": "26px", "radius_sm": "18px", "radius_lg": "34px", "media_radius": "22px", "icon_radius": "18px", "shadow": "none"},
    "round": {"radius": "36px", "radius_sm": "26px", "radius_lg": "46px", "media_radius": "28px", "icon_radius": "22px", "shadow": "none"},
}

SHAPE_META = {
    "crisp": {"label": "利落", "description": "边角更克制。"},
    "soft": {"label": "柔和", "description": "默认的轻圆角。"},
    "round": {"label": "圆润", "description": "更明显的圆角。"},
}
