"""Small deck-level theme catalog that only emits CSS custom properties."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

PALETTES = {
    "oil-yellow": {
        "slide-bg": "#FFFFFF", "stage-bg": "#F7F7F8", "ink": "#292929",
        "ink-2": "#666666", "ink-3": "#A3A3A3", "border": "#E8E8E8",
        "surface": "#F7F7F8", "surface-2": "#FAFAF9", "accent": "#FFD54A",
        "accent-fill": "#FFF0A8", "accent-soft": "#FFFCF2", "accent-strong": "#292929",
        "accent-alt": "#94CDB4", "accent-alt-soft": "#EDF7F2",
        "accent-warm": "#EFA06F", "accent-warm-soft": "#FFF1E8",
    },
    "ink-slate": {
        "slide-bg": "#FFFFFF", "stage-bg": "#F6F8FA", "ink": "#292929",
        "ink-2": "#666666", "ink-3": "#A3A3A3", "border": "#E8E8E8",
        "surface": "#F7F7F8", "surface-2": "#FAFAF9", "accent": "#9ED0FF",
        "accent-fill": "#DCEEFF", "accent-soft": "#F5FAFF", "accent-strong": "#292929",
        "accent-alt": "#91C9B1", "accent-alt-soft": "#EDF7F2",
        "accent-warm": "#E6B94E", "accent-warm-soft": "#FFF5DB",
    },
    "quiet-moss": {
        "slide-bg": "#FFFFFF", "stage-bg": "#F6F8F7", "ink": "#292929",
        "ink-2": "#666666", "ink-3": "#A3A3A3", "border": "#E8E8E8",
        "surface": "#F7F7F8", "surface-2": "#FAFAF9", "accent": "#A6E7CB",
        "accent-fill": "#DDF7EC", "accent-soft": "#F4FCF8", "accent-strong": "#292929",
        "accent-alt": "#8EB9E8", "accent-alt-soft": "#EEF4FC",
        "accent-warm": "#E9BC57", "accent-warm-soft": "#FFF5DD",
    },
    "warm-clay": {
        "slide-bg": "#FFFFFF", "stage-bg": "#FAF7F5", "ink": "#292929",
        "ink-2": "#666666", "ink-3": "#A3A3A3", "border": "#E8E8E8",
        "surface": "#F7F7F8", "surface-2": "#FAFAF9", "accent": "#FFB4A6",
        "accent-fill": "#FFE3DD", "accent-soft": "#FFF7F5", "accent-strong": "#292929",
        "accent-alt": "#8FB7D5", "accent-alt-soft": "#EFF5FA",
        "accent-warm": "#DDB45B", "accent-warm-soft": "#FFF4DE",
    },
    "dusty-plum": {
        "slide-bg": "#FFFFFF", "stage-bg": "#F8F7FB", "ink": "#292929",
        "ink-2": "#666666", "ink-3": "#A3A3A3", "border": "#E8E8E8",
        "surface": "#F7F7F8", "surface-2": "#FAFAF9", "accent": "#C8B8FF",
        "accent-fill": "#E9E3FF", "accent-soft": "#F9F7FF", "accent-strong": "#292929",
        "accent-alt": "#91C7B5", "accent-alt-soft": "#EEF7F4",
        "accent-warm": "#D9A27D", "accent-warm-soft": "#FFF2EA",
    },
}

TYPOGRAPHY = {
    "clean": {
        "font-zh": '"Noto Sans SC","PingFang SC","Microsoft YaHei",Inter,sans-serif',
        "font-ui": 'Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
    },
    "editorial": {
        "font-zh": '"Songti SC",STSong,"Noto Serif SC",SimSun,serif',
        "font-ui": 'Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
    },
    "technical": {
        "font-zh": '"IBM Plex Sans","Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif',
        "font-ui": '"SF Mono","Cascadia Code",Menlo,monospace',
    },
}

SHAPES = {
    "crisp": {"surface-radius": "12px", "surface-radius-sm": "10px", "surface-radius-lg": "18px", "media-radius": "12px", "icon-radius": "10px"},
    "soft": {"surface-radius": "26px", "surface-radius-sm": "18px", "surface-radius-lg": "34px", "media-radius": "22px", "icon-radius": "18px"},
    "round": {"surface-radius": "36px", "surface-radius-sm": "26px", "surface-radius-lg": "46px", "media-radius": "28px", "icon-radius": "22px"},
}

# A direction is a semantic creative brief and a convenient starting preset.
# It deliberately emits no extra CSS: palette/type/shape remain the complete
# runtime theme contract.
DIRECTIONS = {
    "fresh-default": {
        "label": "清新默认",
        "description": "轻快、明亮的通用叙事起点，优先让结论和证据呼吸。",
        "principles": ["留白先于装饰", "浅色建立层级", "一个页面一个主判断"],
        "recommended": {"palette": "oil-yellow", "typography": "clean", "shape": "soft"},
    },
    "editorial-story": {
        "label": "编辑叙事",
        "description": "用节奏、标题和少量重点色推进观点，而不是堆叠信息框。",
        "principles": ["标题有主次", "证据服务叙事", "局部色块制造停顿"],
        "recommended": {"palette": "dusty-plum", "typography": "editorial", "shape": "soft"},
    },
    "technical-system": {
        "label": "技术系统",
        "description": "清楚呈现结构、接口和因果关系，保持理性而不工业化。",
        "principles": ["关系优先于容器", "用线索而非重框", "深色面只承担关键层"],
        "recommended": {"palette": "ink-slate", "typography": "technical", "shape": "crisp"},
    },
    "warm-friendly": {
        "label": "温暖友好",
        "description": "以柔和色彩和亲近节奏解释复杂内容，仍保持干净可读。",
        "principles": ["颜色柔和但对比清楚", "用圆角表达亲和", "让行动步骤可亲近"],
        "recommended": {"palette": "warm-clay", "typography": "clean", "shape": "round"},
    },
    "calm-research": {
        "label": "沉静研究",
        "description": "让观察、证据与结论稳定展开，适合研究、复盘和解释型内容。",
        "principles": ["证据先行", "低饱和建立秩序", "结论留出讨论空间"],
        "recommended": {"palette": "quiet-moss", "typography": "clean", "shape": "crisp"},
    },
}


def catalog() -> dict[str, object]:
    return {
        "palettes": sorted(PALETTES),
        "typography": sorted(TYPOGRAPHY),
        "shapes": sorted(SHAPES),
        "directions": {name: DIRECTIONS[name] for name in sorted(DIRECTIONS)},
    }


def validate_theme(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise SystemExit("deck.theme must be an object.")
    allowed = {"palette", "typography", "shape", "direction"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise SystemExit("deck.theme contains unsupported keys: " + ", ".join(unknown))
    result = {
        "palette": str(value.get("palette") or "oil-yellow"),
        "typography": str(value.get("typography") or "clean"),
        "shape": str(value.get("shape") or "soft"),
        "direction": str(value.get("direction") or "fresh-default"),
    }
    registries = {"palette": PALETTES, "typography": TYPOGRAPHY, "shape": SHAPES, "direction": DIRECTIONS}
    for key, registry in registries.items():
        if result[key] not in registry:
            raise SystemExit(f"Unknown {key}: {result[key]}")
    return result


def theme_css(deck: dict) -> str:
    theme = validate_theme(deck.get("theme"))
    tokens = {
        **PALETTES[theme["palette"]],
        **TYPOGRAPHY[theme["typography"]],
        **SHAPES[theme["shape"]],
    }
    tokens["accent-mark"] = tokens["accent"]
    tokens["accent-wash"] = tokens["accent-soft"]
    tokens["accent-ink"] = tokens["accent-strong"]
    return ":root{" + "".join(f"--{name}:{value};" for name, value in tokens.items()) + "}"


def project_theme_css(project: Path, deck: dict) -> str:
    path = project / "runtime" / "theme.css"
    expected = theme_css(deck)
    if not path.is_file():
        raise SystemExit(f"Project theme file is missing: {path}")
    actual = path.read_text(encoding="utf-8").strip()
    if actual != expected:
        raise SystemExit("runtime/theme.css does not match deck.theme; use the theme set command.")
    return actual


def write_project_theme(project: Path, deck: dict) -> Path:
    path = project / "runtime" / "theme.css"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".theme.", suffix=".css", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(theme_css(deck) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path
