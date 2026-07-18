#!/usr/bin/env python3
"""Curated, bright restrained palette tokens for deterministic oil-ppt output."""
from __future__ import annotations

import colorsys
import re


HEX = re.compile(r"#[0-9a-fA-F]{6}")

PALETTES = {
    "soft-editorial": {
        "canvas": "#FBFBF8",
        "ink": "#353633",
        "ink_2": "#73756F",
        "ink_3": "#999B95",
        "border": "#DEDFD9",
        "surface": "#F1F2EE",
        "surface_2": "#FFFFFF",
        "accent": "#79AEE8",
        "accent_fill": "#C9DFF5",
        "accent_soft": "#EAF3FC",
        "accent_strong": "#353633",
        "accent_alt": "#86C8AA",
        "accent_alt_soft": "#EAF7F0",
        "accent_warm": "#F0BF4D",
        "accent_warm_soft": "#FFF4D5",
    },
    "oil-yellow": {
        "canvas": "#FFFFFF",
        "ink": "#292929",
        "ink_2": "#666666",
        "ink_3": "#A3A3A3",
        "border": "#E8E8E8",
        "surface": "#F7F7F8",
        "surface_2": "#FAFAF9",
        "accent": "#FFD54A",
        "accent_fill": "#FFF0A8",
        "accent_soft": "#FFFCF2",
        "accent_strong": "#292929",
        "accent_alt": "#94CDB4",
        "accent_alt_soft": "#EDF7F2",
        "accent_warm": "#EFA06F",
        "accent_warm_soft": "#FFF1E8",
    },
    "ink-slate": {
        "canvas": "#FFFFFF",
        "ink": "#292929",
        "ink_2": "#666666",
        "ink_3": "#A3A3A3",
        "border": "#E8E8E8",
        "surface": "#F7F7F8",
        "surface_2": "#FAFAF9",
        "accent": "#9ED0FF",
        "accent_fill": "#DCEEFF",
        "accent_soft": "#F5FAFF",
        "accent_strong": "#292929",
        "accent_alt": "#91C9B1",
        "accent_alt_soft": "#EDF7F2",
        "accent_warm": "#E6B94E",
        "accent_warm_soft": "#FFF5DB",
    },
    "quiet-moss": {
        "canvas": "#FFFFFF",
        "ink": "#292929",
        "ink_2": "#666666",
        "ink_3": "#A3A3A3",
        "border": "#E8E8E8",
        "surface": "#F7F7F8",
        "surface_2": "#FAFAF9",
        "accent": "#A6E7CB",
        "accent_fill": "#DDF7EC",
        "accent_soft": "#F4FCF8",
        "accent_strong": "#292929",
        "accent_alt": "#8EB9E8",
        "accent_alt_soft": "#EEF4FC",
        "accent_warm": "#E9BC57",
        "accent_warm_soft": "#FFF5DD",
    },
    "warm-clay": {
        "canvas": "#FFFFFF",
        "ink": "#292929",
        "ink_2": "#666666",
        "ink_3": "#A3A3A3",
        "border": "#E8E8E8",
        "surface": "#F7F7F8",
        "surface_2": "#FAFAF9",
        "accent": "#FFB4A6",
        "accent_fill": "#FFE3DD",
        "accent_soft": "#FFF7F5",
        "accent_strong": "#292929",
        "accent_alt": "#8FB7D5",
        "accent_alt_soft": "#EFF5FA",
        "accent_warm": "#DDB45B",
        "accent_warm_soft": "#FFF4DE",
    },
    "dusty-plum": {
        "canvas": "#FFFFFF",
        "ink": "#292929",
        "ink_2": "#666666",
        "ink_3": "#A3A3A3",
        "border": "#E8E8E8",
        "surface": "#F7F7F8",
        "surface_2": "#FAFAF9",
        "accent": "#C8B8FF",
        "accent_fill": "#E9E3FF",
        "accent_soft": "#F9F7FF",
        "accent_strong": "#292929",
        "accent_alt": "#91C7B5",
        "accent_alt_soft": "#EEF7F4",
        "accent_warm": "#D9A27D",
        "accent_warm_soft": "#FFF2EA",
    },
    "ocean-cobalt": {
        "canvas": "#FCFDFF",
        "ink": "#27313A",
        "ink_2": "#5F6972",
        "ink_3": "#98A2AA",
        "border": "#DFE6EC",
        "surface": "#F1F5F9",
        "surface_2": "#F7FAFC",
        "accent": "#5E82F6",
        "accent_fill": "#CFDAFF",
        "accent_soft": "#F0F4FF",
        "accent_strong": "#243A72",
        "accent_alt": "#67B8A6",
        "accent_alt_soft": "#EDF8F5",
        "accent_warm": "#D8A54C",
        "accent_warm_soft": "#FFF3DC",
    },
    "sand-copper": {
        "canvas": "#FFFDFC",
        "ink": "#302D2A",
        "ink_2": "#6B625B",
        "ink_3": "#A79B91",
        "border": "#ECE3DB",
        "surface": "#F8F2ED",
        "surface_2": "#FCF8F5",
        "accent": "#E7A06F",
        "accent_fill": "#F6D9C6",
        "accent_soft": "#FFF5EE",
        "accent_strong": "#66402D",
        "accent_alt": "#80A9C9",
        "accent_alt_soft": "#EFF4F8",
        "accent_warm": "#D8AE54",
        "accent_warm_soft": "#FFF5DE",
    },
    "glacier-teal": {
        "canvas": "#FCFEFE",
        "ink": "#263333",
        "ink_2": "#5D6D6C",
        "ink_3": "#97A7A5",
        "border": "#DDE9E7",
        "surface": "#EFF7F5",
        "surface_2": "#F6FBFA",
        "accent": "#63C9BE",
        "accent_fill": "#CDEFEA",
        "accent_soft": "#EFFAF8",
        "accent_strong": "#245B57",
        "accent_alt": "#8D9DDD",
        "accent_alt_soft": "#F0F2FC",
        "accent_warm": "#D8AF61",
        "accent_warm_soft": "#FFF4DF",
    },
}

PALETTE_META = {
    "soft-editorial": {"label": "纸刊蓝", "description": "偏纸张质感的浅蓝与柔和中性色。"},
    "oil-yellow": {"label": "明亮黄", "description": "明亮白底与克制黄强调，适合大多数演示。"},
    "ink-slate": {"label": "雾蓝", "description": "清爽浅蓝，信息感明确但不过度冷峻。"},
    "quiet-moss": {"label": "苔绿", "description": "安静自然的浅绿，适合长期主义与组织主题。"},
    "warm-clay": {"label": "暖陶", "description": "温暖珊瑚色，亲和但仍保持清楚对比。"},
    "dusty-plum": {"label": "灰紫", "description": "低饱和紫色，适合抽象概念与叙事内容。"},
    "ocean-cobalt": {"label": "深海蓝", "description": "更深的冷蓝层级，适合系统与技术内容。"},
    "sand-copper": {"label": "沙铜", "description": "纸张暖白与铜色强调，稳重且有人文感。"},
    "glacier-teal": {"label": "冰川青", "description": "冷静青色与低对比表面，适合研究与分析。"},
}

ALIASES = {
    "warm": "oil-yellow",
    "yellow": "oil-yellow",
    "warm-yellow": "oil-yellow",
    "paper-gold": "oil-yellow",
    "mist-blue": "ink-slate",
    "sky-blue": "ink-slate",
    "blue": "ink-slate",
    "sage": "quiet-moss",
    "sage-green": "quiet-moss",
    "mint": "quiet-moss",
    "mint-green": "quiet-moss",
    "coral": "warm-clay",
    "soft-violet": "dusty-plum",
    "lavender": "dusty-plum",
    "violet": "dusty-plum",
    "purple": "dusty-plum",
    "cobalt": "ocean-cobalt",
    "deep-blue": "ocean-cobalt",
    "copper": "sand-copper",
    "sand": "sand-copper",
    "teal": "glacier-teal",
    "editorial": "soft-editorial",
    "soft-editorial-modern": "soft-editorial",
}

TOKEN_KEYS = (
    "canvas", "ink", "ink_2", "ink_3", "border", "surface", "surface_2",
    "accent", "accent_fill", "accent_soft", "accent_strong",
    "accent_alt", "accent_alt_soft", "accent_warm", "accent_warm_soft",
)


def _mix(left: str, right: str, ratio: float) -> str:
    a = tuple(int(left[index:index + 2], 16) for index in (1, 3, 5))
    b = tuple(int(right[index:index + 2], 16) for index in (1, 3, 5))
    values = tuple(round(x * ratio + y * (1 - ratio)) for x, y in zip(a, b))
    return "#" + "".join(f"{value:02X}" for value in values)


def _shift_hue(value: str, degrees: float) -> str:
    rgb = tuple(int(value[index:index + 2], 16) / 255 for index in (1, 3, 5))
    hue, lightness, saturation = colorsys.rgb_to_hls(*rgb)
    hue = (hue + degrees / 360) % 1
    lightness = min(.76, max(.58, lightness))
    saturation = min(.62, max(.34, saturation * .82))
    shifted = colorsys.hls_to_rgb(hue, lightness, saturation)
    return "#" + "".join(f"{round(channel * 255):02X}" for channel in shifted)


def _with_companions(data: dict[str, str]) -> dict[str, str]:
    result = dict(data)
    accent = result["accent"]
    canvas = result["canvas"]
    result.setdefault("accent_alt", _shift_hue(accent, 105))
    result.setdefault("accent_warm", _shift_hue(accent, -78))
    result.setdefault("accent_alt_soft", _mix(result["accent_alt"], canvas, .15))
    result.setdefault("accent_warm_soft", _mix(result["accent_warm"], canvas, .17))
    return result


def canonical_name(name: str) -> str:
    value = name.strip().lower()
    return ALIASES.get(value, value)


def named_palette(name: str) -> dict[str, str]:
    canonical = canonical_name(name)
    if canonical not in PALETTES:
        raise ValueError(f"Unknown palette: {name}")
    return {"name": canonical, **_with_companions(PALETTES[canonical])}


def custom_palette(accent: str, accent_soft: str, accent_strong: str) -> dict[str, str]:
    for value in (accent, accent_soft, accent_strong):
        if not HEX.fullmatch(value):
            raise ValueError("Custom palette colors must be six-digit hex values.")
    neutral = PALETTES["oil-yellow"]
    result = {
        "name": "custom",
        **{key: neutral[key] for key in TOKEN_KEYS if not key.startswith("accent")},
        "accent": accent.upper(),
        "accent_fill": _mix(accent, accent_soft, .46),
        "accent_soft": accent_soft.upper(),
        "accent_strong": accent_strong.upper(),
    }
    return {"name": result.pop("name"), **_with_companions(result)}


def normalize_palette(data: dict) -> dict[str, str]:
    name = canonical_name(str(data.get("name") or "custom"))
    if name in PALETTES:
        # Named palettes are fixed recipes; do not merge ad-hoc token overrides.
        return named_palette(name)
    base = custom_palette(
        str(data.get("accent") or ""),
        str(data.get("accent_soft") or ""),
        str(data.get("accent_strong") or ""),
    )
    for key in TOKEN_KEYS:
        value = data.get(key)
        if value is not None:
            if not isinstance(value, str) or not HEX.fullmatch(value):
                raise ValueError(f"palette.{key} must be a six-digit hex color.")
            base[key] = value.upper()
    return base
