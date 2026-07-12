#!/usr/bin/env python3
"""Curated component choices owned by oil-slides templates."""
from __future__ import annotations


# Compose track: pick a closed component, explicitly choose variant/decor,
# then fill slots. Templates own geometry; models compete on content and media.
#
# Contracts must match template reality. Do not list counts, variants, or
# decorations that the HTML/CSS cannot actually render.
COMPONENT_CONTRACTS = {
    "bleed-split": {"use_when": "文字与一张可出血的主视觉共同表达判断。", "variants": ("default",), "decorations": ("none",)},
    "browser-showcase": {"use_when": "真实界面截图或明确标注的 UI 演示是主要证据。", "variants": ("default",), "decorations": ("none",)},
    "card-trio": {"use_when": "三个可独立拿走的信息单元共同支撑一个判断，并且有一主两辅。", "variants": ("feature-left", "feature-right"), "decorations": ("none",)},
    "comparison": {"use_when": "两个对象需要以相同维度直接对照。", "variants": ("default",), "decorations": ("dots", "halo", "corner-grid")},
    "comparison-list": {
        "use_when": "两个责任域或方案需要逐项对齐比较。",
        "variants": ("focus-right", "focus-left", "balanced"),
        "decorations": ("dots", "halo", "corner-grid"),
    },
    "converge": {"use_when": "多个输入汇聚为一个结果或判断。", "variants": ("default",), "decorations": ("none",)},
    "cover": {
        "use_when": "演示开场。statement=大字焦点；media=标题+真实主视觉。",
        "variants": ("statement", "media"),
        "decorations": ("none",),
    },
    "diagonal-split": {"use_when": "章节转折或冲突需要更强的方向感，并有一张主视觉。", "variants": ("default",), "decorations": ("none",)},
    "editorial-canvas": {"use_when": "一段说明与素材、局部或批注共同组成展陈式页面。", "variants": ("default",), "decorations": ("none",)},
    "end": {
        "use_when": "演示结束。line=一句刀；line-note=一句+余韵；line-artifact=一句+二维码/物件。",
        "variants": ("line", "line-note", "line-artifact"),
        "decorations": ("none",),
    },
    "metric": {"use_when": "一个真实数字及其意义是页面焦点。", "variants": ("default",), "decorations": ("orbit", "halo", "dots")},
    "photo-gradient": {"use_when": "照片需要与少量文字自然融合。", "variants": ("default",), "decorations": ("none",)},
    "photo-split": {"use_when": "照片与解释文字权重接近。", "variants": ("default",), "decorations": ("none",)},
    "process-rail": {
        "use_when": "六或八个短动作组成一条完整流程总览。",
        "variants": ("steps-8", "steps-6"),
        # Open canvas: no wrapping surface, so no surface decorations.
        "decorations": ("none",),
    },
    "recap": {
        "use_when": "一句收束判断由三条原则支撑。",
        "variants": ("thesis-left", "thesis-right"),
        "decorations": ("halo", "dots", "corner-grid"),
    },
    "section": {"use_when": "内容确实进入一个新的章节。", "variants": ("default",), "decorations": ("none",)},
    "split-visual": {"use_when": "一张真实图片、插画或材料组合与正文并置；按信息权重选择均衡、视觉主导或文字主导。", "variants": ("media-dominant", "balanced", "copy-dominant", "default"), "decorations": ("none",)},
    "tabs": {"use_when": "同一对象的多个状态或视图需要切换式对照。", "variants": ("default",), "decorations": ("corner-grid", "dots", "halo")},
    "three-steps": {
        "use_when": "三个连续动作构成可读完的短流程。",
        "variants": ("linear", "focus-middle"),
        "decorations": ("corner-grid", "dots", "halo"),
    },
    "timeline": {"use_when": "四个阶段沿时间推进，且每个阶段都需要一句解释。", "variants": ("default",), "decorations": ("none",)},
}

# Deck-level quality metadata. Semantic family explains what a component means;
# silhouette and surface density explain how it reads from a distance. Frame
# ownership prevents a media asset and its template from drawing the same shell.
COMPONENT_QUALITY = {
    "bleed-split": {"silhouette": "bleed", "surface_density": "none", "frame_owner": "media"},
    "browser-showcase": {"silhouette": "browser", "surface_density": "light", "frame_owner": "template"},
    "card-trio": {"silhouette": "card-grid", "surface_density": "heavy", "frame_owner": "none"},
    "comparison": {"silhouette": "two-panel", "surface_density": "heavy", "frame_owner": "none"},
    "comparison-list": {"silhouette": "two-panel", "surface_density": "heavy", "frame_owner": "none"},
    "converge": {"silhouette": "diagram", "surface_density": "light", "frame_owner": "none"},
    "cover": {"silhouette": "focal", "surface_density": "none", "frame_owner": "template"},
    "diagonal-split": {"silhouette": "bleed", "surface_density": "none", "frame_owner": "media"},
    "editorial-canvas": {"silhouette": "canvas", "surface_density": "light", "frame_owner": "template"},
    "end": {"silhouette": "focal", "surface_density": "none", "frame_owner": "template"},
    "metric": {"silhouette": "metric", "surface_density": "light", "frame_owner": "none"},
    "photo-gradient": {"silhouette": "bleed", "surface_density": "none", "frame_owner": "media"},
    "photo-split": {"silhouette": "split", "surface_density": "none", "frame_owner": "media"},
    "process-rail": {"silhouette": "rail", "surface_density": "none", "frame_owner": "none"},
    "recap": {"silhouette": "editorial-list", "surface_density": "heavy", "frame_owner": "none"},
    "section": {"silhouette": "focal", "surface_density": "none", "frame_owner": "none"},
    "split-visual": {"silhouette": "split", "surface_density": "light", "frame_owner": "none"},
    "tabs": {"silhouette": "two-panel", "surface_density": "heavy", "frame_owner": "none"},
    "three-steps": {"silhouette": "step-grid", "surface_density": "heavy", "frame_owner": "none"},
    "timeline": {"silhouette": "timeline", "surface_density": "none", "frame_owner": "none"},
}

# Programmatic diagrams/sequences must use these closed structure templates.
CLOSED_STRUCTURE_TEMPLATES = frozenset({
    "process-rail",
    "three-steps",
    "timeline",
    "converge",
    "card-trio",
})


def choices_for(template: str) -> dict:
    try:
        return COMPONENT_CONTRACTS[template]
    except KeyError as error:
        raise SystemExit(f"Template {template!r} has no component contract.") from error


def quality_for(template: str) -> dict:
    try:
        return COMPONENT_QUALITY[template]
    except KeyError as error:
        raise SystemExit(f"Template {template!r} has no deck-quality metadata.") from error


def normalize_component_choices(slide: dict, index: int) -> None:
    contract = choices_for(slide["template"])
    variant = slide.get("variant")
    decor = slide.get("decor")
    if not isinstance(variant, str) or not variant.strip():
        allowed = ", ".join(contract["variants"])
        raise SystemExit(f"Outline slide {index} must explicitly choose variant for {slide['template']!r}; allowed: {allowed}.")
    if not isinstance(decor, str) or not decor.strip():
        allowed = ", ".join(contract["decorations"])
        raise SystemExit(f"Outline slide {index} must explicitly choose decor for {slide['template']!r}; allowed: {allowed}.")
    if decor not in contract["decorations"]:
        allowed = ", ".join(contract["decorations"])
        raise SystemExit(
            f"Outline slide {index} decor {decor!r} is invalid for {slide['template']!r}; allowed: {allowed}."
        )
    if variant not in contract["variants"]:
        allowed = ", ".join(contract["variants"])
        raise SystemExit(
            f"Outline slide {index} variant {variant!r} is invalid for {slide['template']!r}; allowed: {allowed}."
        )
