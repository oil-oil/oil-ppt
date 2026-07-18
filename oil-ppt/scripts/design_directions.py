#!/usr/bin/env python3
"""Program-owned visual directions composed from legal oil-ppt settings."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from palette_tokens import PALETTES, canonical_name
from profile_tokens import SHAPE_PROFILES, TYPE_PROFILES


@dataclass(frozen=True)
class DesignDirection:
    id: str
    label: str
    palette: str
    typography: str
    shape: str
    use_when: str
    visual: str


DESIGN_DIRECTIONS = (
    DesignDirection(
        id="fresh-default",
        label="清爽默认",
        palette="oil-yellow",
        typography="clean",
        shape="soft",
        use_when="大多数产品、汇报与通用演示。",
        visual="明亮白底、克制黄强调与轻圆角。",
    ),
    DesignDirection(
        id="editorial-story",
        label="编辑叙事",
        palette="soft-editorial",
        typography="editorial",
        shape="crisp",
        use_when="人物、文化、品牌故事与长叙事。",
        visual="纸刊浅蓝、衬线标题与利落边角。",
    ),
    DesignDirection(
        id="technical-system",
        label="技术系统",
        palette="ocean-cobalt",
        typography="technical",
        shape="crisp",
        use_when="工程方案、系统架构与技术说明。",
        visual="深海蓝层级、紧凑字形与克制直角感。",
    ),
    DesignDirection(
        id="warm-friendly",
        label="温暖亲和",
        palette="warm-clay",
        typography="rounded",
        shape="round",
        use_when="教学、社区、服务体验与轻松沟通。",
        visual="暖陶强调、亲近无衬线与明显圆角。",
    ),
    DesignDirection(
        id="calm-research",
        label="冷静研究",
        palette="glacier-teal",
        typography="clean",
        shape="crisp",
        use_when="研究洞察、分析报告与审慎决策。",
        visual="冰川青、低对比表面与清晰边界。",
    ),
)

DESIGN_DIRECTION_BY_ID = {direction.id: direction for direction in DESIGN_DIRECTIONS}


def registry_issues() -> list[str]:
    issues: list[str] = []
    ids = [direction.id for direction in DESIGN_DIRECTIONS]
    combinations = [
        (direction.palette, direction.typography, direction.shape)
        for direction in DESIGN_DIRECTIONS
    ]
    if len(ids) != len(set(ids)):
        issues.append("design direction ids must be unique")
    if len(combinations) != len(set(combinations)):
        issues.append("design direction setting combinations must be unique")
    for direction in DESIGN_DIRECTIONS:
        if direction.palette not in PALETTES:
            issues.append(f"{direction.id} uses unknown palette {direction.palette}")
        if direction.typography not in TYPE_PROFILES:
            issues.append(f"{direction.id} uses unknown typography {direction.typography}")
        if direction.shape not in SHAPE_PROFILES:
            issues.append(f"{direction.id} uses unknown shape {direction.shape}")
        if not all((direction.label, direction.use_when, direction.visual)):
            issues.append(f"{direction.id} requires a label, use_when, and visual description")
    return issues


def public_registry() -> list[dict[str, str]]:
    return [asdict(direction) for direction in DESIGN_DIRECTIONS]


def matching_direction(data: dict) -> str | None:
    palette = data.get("palette")
    if not isinstance(palette, str):
        return None
    settings = (canonical_name(palette), data.get("typography"), data.get("shape"))
    for direction in DESIGN_DIRECTIONS:
        if settings == (direction.palette, direction.typography, direction.shape):
            return direction.id
    return None


_REGISTRY_ISSUES = registry_issues()
if _REGISTRY_ISSUES:
    raise RuntimeError("Invalid design direction registry: " + "; ".join(_REGISTRY_ISSUES))
