#!/usr/bin/env python3
"""Curated component choices owned by oil-ppt templates."""
from __future__ import annotations


# Compose track: pick a closed component, explicitly choose variant/decor,
# then fill slots. Templates own geometry; models compete on content and media.
#
# Contracts must match template reality. Do not list counts, variants, or
# decorations that the HTML/CSS cannot actually render.
COMPONENT_CONTRACTS = {
    "bleed-split": {"use_when": "文字与一张可出血的主视觉共同表达判断；按主体位置选择左右出血。", "variants": ("media-right", "media-left"), "decorations": ("none",)},
    "browser-showcase": {"use_when": "真实界面截图或明确标注的 UI 演示是主要证据；按讲述顺序选择界面在左或右。", "variants": ("media-right", "media-left"), "decorations": ("none",)},
    "card-trio": {"use_when": "三个可独立拿走的信息单元共同支撑一个判断，并且有一主两辅；左右型强调纵向主卡，feature-top 先给总领再读两项支撑，media-evidence 用两组图片证据与一个文字决策块完成路由。", "variants": ("feature-left", "feature-right", "feature-top", "media-evidence"), "decorations": ("none",)},
    "comparison": {"use_when": "两个对象需要以相同维度直接对照；有成组真实图片证据时使用 visual-evidence。", "variants": ("default", "visual-evidence"), "decorations": ("none", "dots", "corner-grid")},
    "comparison-list": {
        "use_when": "两个责任域或方案需要逐项对齐比较。",
        "variants": ("focus-right", "focus-left", "balanced"),
        "decorations": ("none", "dots", "corner-grid"),
    },
    "converge": {"use_when": "多个输入汇聚为一个结果或判断。", "variants": ("default",), "decorations": ("none",)},
    "cover": {
        "use_when": "演示开场。statement=大字焦点；media=标题+真实主视觉。",
        "variants": ("statement", "media"),
        "decorations": ("none",),
    },
    "diagonal-split": {"use_when": "章节转折或冲突需要更强的方向感，并有一张主视觉；斜切方向应跟随内容动势。", "variants": ("media-right", "media-left"), "decorations": ("none",)},
    "editorial-canvas": {"use_when": "一段说明与素材、局部或批注共同组成展陈式页面。", "variants": ("default",), "decorations": ("none",)},
    "end": {
        "use_when": "演示结束。line=一句刀；line-note=一句+余韵；line-artifact=一句+二维码/物件。",
        "variants": ("line", "line-note", "line-artifact"),
        "decorations": ("none",),
    },
    "metric": {"use_when": "一个真实数字及其意义是页面焦点。", "variants": ("default",), "decorations": ("none", "dots", "corner-grid")},
    "photo-gradient": {"use_when": "照片铺满页面并与少量文字自然融合；按主体空白选择文字落在左或右。", "variants": ("copy-left", "copy-right"), "decorations": ("none",)},
    "photo-split": {"use_when": "照片与解释文字权重接近；按阅读顺序选择媒体在左或右。", "variants": ("media-right", "media-left"), "decorations": ("none",)},
    "process-rail": {
        "use_when": "六个带简短解释的步骤，或八个只需短标签的动作，组成一条完整流程总览。",
        "variants": ("steps-8", "steps-6"),
        # Open canvas: no wrapping surface, so no surface decorations.
        "decorations": ("none",),
    },
    "quote": {
        "use_when": "一段真实引用或一句需要独立停留的原话是页面焦点。",
        "variants": ("default",),
        "decorations": ("none",),
    },
    "recap": {
        "use_when": "一句收束判断由三条原则支撑。",
        "variants": ("thesis-left", "thesis-right"),
        "decorations": ("none", "dots", "corner-grid"),
    },
    "section": {"use_when": "内容确实进入一个新的章节。", "variants": ("default",), "decorations": ("none",)},
    "split-visual": {"use_when": "一张真实图片、插画或材料组合与正文并置；按信息权重选择均衡、视觉主导或文字主导。", "variants": ("media-dominant", "balanced", "copy-dominant"), "decorations": ("none",)},
    "tabs": {"use_when": "同一对象的多个状态或视图需要切换式对照。", "variants": ("default",), "decorations": ("none", "corner-grid", "dots")},
    "three-steps": {
        "use_when": "三个连续动作构成可读完的短流程。",
        "variants": ("linear", "focus-middle"),
        "decorations": ("none", "corner-grid", "dots"),
    },
    "timeline": {"use_when": "四个阶段沿时间推进，且每个阶段都需要一句解释。", "variants": ("default",), "decorations": ("none",)},
    "editorial-feature": {"use_when": "一张主视觉与三个支撑信息共同解释一个核心判断；有第二张辅助图且需要更强编辑感时使用 hero-collage。", "variants": ("default", "hero-collage"), "decorations": ("none",)},
    "catalog-board": {"use_when": "四个分类下各有三个同构条目，需要在一页形成可浏览的结构化目录。", "variants": ("default",), "decorations": ("none",)},
    "case-study-board": {"use_when": "真实案例需要同时展示证据、两个指标与一个核心洞察；没有截图但有真实数据时使用 chart。", "variants": ("evidence", "chart"), "decorations": ("none",)},
    "annotated-showcase": {"use_when": "一张真实界面、作品或材料需要用三个局部标注明确阅读重点。", "variants": ("default",), "decorations": ("none",)},
    "narrative-bento": {"use_when": "一个主判断、两项补充和一句收束需要形成明显主次，而不是平均卡片。", "variants": ("default",), "decorations": ("none",)},
    "sequence-gallery": {"use_when": "三个连续画面共同呈现输入、变化与输出，每一步都有真实图片。", "variants": ("default",), "decorations": ("none",)},
    "process-cards": {"use_when": "四个带解释的连续步骤需要横向读完；terminal-focus 用深色结果块明确收束。", "variants": ("linear", "terminal-focus"), "decorations": ("none",)},
}

# Deck-level quality metadata. Semantic family explains what a component means;
# silhouette and surface density explain how it reads from a distance. Frame
# ownership prevents a media asset and its template from drawing the same shell.
COMPONENT_QUALITY = {
    "bleed-split": {"silhouette": "bleed", "surface_density": "none", "frame_owner": "media"},
    "browser-showcase": {"silhouette": "browser", "surface_density": "light", "frame_owner": "template"},
    "card-trio": {"silhouette": "card-grid", "surface_density": "heavy", "frame_owner": "none"},
    "comparison": {"silhouette": "two-panel", "surface_density": "heavy", "frame_owner": "none"},
    "comparison-list": {"silhouette": "matrix", "surface_density": "light", "frame_owner": "none"},
    "converge": {"silhouette": "diagram", "surface_density": "light", "frame_owner": "none"},
    "cover": {"silhouette": "focal", "surface_density": "none", "frame_owner": "template"},
    "diagonal-split": {"silhouette": "bleed", "surface_density": "none", "frame_owner": "media"},
    "editorial-canvas": {"silhouette": "canvas", "surface_density": "light", "frame_owner": "template"},
    "end": {"silhouette": "focal", "surface_density": "none", "frame_owner": "template"},
    "metric": {"silhouette": "metric", "surface_density": "light", "frame_owner": "none"},
    "photo-gradient": {"silhouette": "bleed", "surface_density": "none", "frame_owner": "media"},
    "photo-split": {"silhouette": "split", "surface_density": "none", "frame_owner": "media"},
    "process-rail": {"silhouette": "rail", "surface_density": "none", "frame_owner": "none"},
    "quote": {"silhouette": "focal", "surface_density": "none", "frame_owner": "none"},
    "recap": {"silhouette": "editorial-list", "surface_density": "heavy", "frame_owner": "none"},
    "section": {"silhouette": "focal", "surface_density": "none", "frame_owner": "none"},
    "split-visual": {"silhouette": "split", "surface_density": "light", "frame_owner": "none"},
    "tabs": {"silhouette": "state-panel", "surface_density": "heavy", "frame_owner": "none"},
    "three-steps": {"silhouette": "step-grid", "surface_density": "light", "frame_owner": "none"},
    "timeline": {"silhouette": "timeline", "surface_density": "none", "frame_owner": "none"},
    "editorial-feature": {"silhouette": "editorial-feature", "surface_density": "light", "frame_owner": "template"},
    "catalog-board": {"silhouette": "catalog", "surface_density": "heavy", "frame_owner": "none"},
    "case-study-board": {"silhouette": "case-board", "surface_density": "light", "frame_owner": "template"},
    "annotated-showcase": {"silhouette": "annotated", "surface_density": "light", "frame_owner": "template"},
    "narrative-bento": {"silhouette": "bento", "surface_density": "heavy", "frame_owner": "none"},
    "sequence-gallery": {"silhouette": "gallery", "surface_density": "heavy", "frame_owner": "template"},
    "process-cards": {"silhouette": "step-cards", "surface_density": "heavy", "frame_owner": "none"},
}


# Variant-level signatures describe changes visible from a distance. Mirroring
# a composition keeps the same signature; a genuinely different reading path
# gets a new one. Audit uses these values instead of trusting variant names.
VARIANT_QUALITY = {
    "bleed-split": {
        "media-right": {"layout_signature": "edge-bleed", "visual_energy": "anchor"},
        "media-left": {"layout_signature": "edge-bleed", "visual_energy": "anchor"},
    },
    "browser-showcase": {
        "media-right": {"layout_signature": "browser-split", "visual_energy": "anchor"},
        "media-left": {"layout_signature": "browser-split", "visual_energy": "anchor"},
    },
    "cover": {
        "statement": {"layout_signature": "focal-statement", "visual_energy": "anchor"},
        "media": {"layout_signature": "cover-media-split", "visual_energy": "anchor"},
    },
    "end": {
        "line": {"layout_signature": "focal-closing", "visual_energy": "anchor"},
        "line-note": {"layout_signature": "closing-aside", "visual_energy": "quiet"},
        "line-artifact": {"layout_signature": "closing-artifact", "visual_energy": "anchor"},
    },
    "diagonal-split": {
        "media-right": {"layout_signature": "diagonal-bleed", "visual_energy": "anchor"},
        "media-left": {"layout_signature": "diagonal-bleed", "visual_energy": "anchor"},
    },
    "card-trio": {
        "feature-left": {"layout_signature": "feature-support-vertical", "visual_energy": "structured"},
        "feature-right": {"layout_signature": "feature-support-vertical", "visual_energy": "structured"},
        "feature-top": {"layout_signature": "feature-support-band", "visual_energy": "structured"},
        "media-evidence": {"layout_signature": "evidence-routing", "visual_energy": "anchor"},
    },
    "comparison-list": {
        "focus-right": {"layout_signature": "comparison-matrix", "visual_energy": "structured"},
        "focus-left": {"layout_signature": "comparison-matrix", "visual_energy": "structured"},
        "balanced": {"layout_signature": "comparison-matrix", "visual_energy": "structured"},
    },
    "process-rail": {
        "steps-6": {"layout_signature": "serpentine-rail", "visual_energy": "anchor"},
        "steps-8": {"layout_signature": "serpentine-rail", "visual_energy": "anchor"},
    },
    "photo-gradient": {
        "copy-left": {"layout_signature": "full-photo-overlay", "visual_energy": "anchor"},
        "copy-right": {"layout_signature": "full-photo-overlay", "visual_energy": "anchor"},
    },
    "photo-split": {
        "media-right": {"layout_signature": "balanced-photo-split", "visual_energy": "anchor"},
        "media-left": {"layout_signature": "balanced-photo-split", "visual_energy": "anchor"},
    },
    "recap": {
        "thesis-left": {"layout_signature": "thesis-principles", "visual_energy": "structured"},
        "thesis-right": {"layout_signature": "thesis-principles", "visual_energy": "structured"},
    },
    "split-visual": {
        "media-dominant": {"layout_signature": "inset-split", "visual_energy": "anchor"},
        "balanced": {"layout_signature": "inset-split", "visual_energy": "structured"},
        "copy-dominant": {"layout_signature": "inset-split", "visual_energy": "structured"},
    },
    "three-steps": {
        "linear": {"layout_signature": "three-stage-spine", "visual_energy": "structured"},
        "focus-middle": {"layout_signature": "three-stage-spine", "visual_energy": "structured"},
    },
    "case-study-board": {
        "evidence": {"layout_signature": "case-evidence", "visual_energy": "anchor"},
        "chart": {"layout_signature": "case-chart", "visual_energy": "structured"},
    },
    "comparison": {
        "default": {"layout_signature": "two-panel", "visual_energy": "structured"},
        "visual-evidence": {"layout_signature": "evidence-comparison", "visual_energy": "anchor"},
    },
    "editorial-feature": {
        "default": {"layout_signature": "editorial-feature", "visual_energy": "anchor"},
        "hero-collage": {"layout_signature": "editorial-hero-collage", "visual_energy": "anchor"},
    },
    "process-cards": {
        "linear": {"layout_signature": "four-step-cards", "visual_energy": "structured"},
        "terminal-focus": {"layout_signature": "four-step-terminal", "visual_energy": "anchor"},
    },
}

# Programmatic diagrams/sequences must use these closed structure templates.
CLOSED_STRUCTURE_TEMPLATES = frozenset({
    "process-rail",
    "three-steps",
    "timeline",
    "converge",
    "card-trio",
    "editorial-feature",
    "catalog-board",
    "case-study-board",
    "annotated-showcase",
    "narrative-bento",
    "sequence-gallery",
    "process-cards",
})


def choices_for(template: str) -> dict:
    try:
        return COMPONENT_CONTRACTS[template]
    except KeyError as error:
        raise SystemExit(f"Template {template!r} has no component contract.") from error


def quality_for(template: str, variant: str | None = None) -> dict:
    try:
        base = dict(COMPONENT_QUALITY[template])
    except KeyError as error:
        raise SystemExit(f"Template {template!r} has no deck-quality metadata.") from error
    override = VARIANT_QUALITY.get(template, {}).get(str(variant or ""), {})
    base.update(override)
    base.setdefault("layout_signature", base["silhouette"])
    base.setdefault("visual_energy", "anchor" if base["silhouette"] in {"bleed", "browser", "canvas", "diagram", "metric", "rail", "timeline"} else "structured")
    return base


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
