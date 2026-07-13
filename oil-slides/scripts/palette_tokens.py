#!/usr/bin/env python3
"""Curated, bright restrained palette tokens for deterministic oil-ppt output."""
from __future__ import annotations

import re


HEX = re.compile(r"#[0-9a-fA-F]{6}")

PALETTES = {
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
    },
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
}

TOKEN_KEYS = (
    "canvas", "ink", "ink_2", "ink_3", "border", "surface", "surface_2",
    "accent", "accent_fill", "accent_soft", "accent_strong",
)


def canonical_name(name: str) -> str:
    value = name.strip().lower()
    return ALIASES.get(value, value)


def named_palette(name: str) -> dict[str, str]:
    canonical = canonical_name(name)
    if canonical not in PALETTES:
        raise ValueError(f"Unknown palette: {name}")
    return {"name": canonical, **PALETTES[canonical]}


def custom_palette(accent: str, accent_soft: str, accent_strong: str) -> dict[str, str]:
    for value in (accent, accent_soft, accent_strong):
        if not HEX.fullmatch(value):
            raise ValueError("Custom palette colors must be six-digit hex values.")
    neutral = PALETTES["oil-yellow"]
    def mix(left: str, right: str, ratio: float = .46) -> str:
        a = tuple(int(left[index:index + 2], 16) for index in (1, 3, 5))
        b = tuple(int(right[index:index + 2], 16) for index in (1, 3, 5))
        values = tuple(round(x * ratio + y * (1 - ratio)) for x, y in zip(a, b))
        return "#" + "".join(f"{value:02X}" for value in values)

    return {
        "name": "custom",
        **{key: neutral[key] for key in TOKEN_KEYS if not key.startswith("accent")},
        "accent": accent.upper(),
        "accent_fill": mix(accent, accent_soft),
        "accent_soft": accent_soft.upper(),
        "accent_strong": accent_strong.upper(),
    }


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
