#!/usr/bin/env python3
"""Small explicit outline contract shared by preview, scaffold, and build."""
from __future__ import annotations

import re
from pathlib import Path

from background_presets import BACKGROUND_PRESETS
from component_contracts import COMPONENT_CONTRACTS, normalize_component_choices
from icon_registry import ICON_CATALOG
from palette_tokens import PALETTES, canonical_name
from profile_tokens import SHAPE_PROFILES, TYPE_PROFILES


TEMPLATE_FAMILIES = {
    "bleed-split": "bleed", "browser-showcase": "split", "card-trio": "cards",
    "comparison": "comparison", "comparison-list": "comparison", "converge": "canvas",
    "cover": "focal", "diagonal-split": "bleed", "editorial-canvas": "canvas",
    "end": "focal", "metric": "focal", "photo-gradient": "bleed",
    "photo-split": "split", "process-rail": "sequence", "quote": "focal", "recap": "cards",
    "section": "focal", "split-visual": "split", "tabs": "comparison",
    "three-steps": "sequence", "timeline": "sequence",
    "editorial-feature": "compound", "catalog-board": "compound",
    "case-study-board": "compound", "annotated-showcase": "compound",
    "narrative-bento": "compound", "sequence-gallery": "compound",
}

TEMPLATE_CONTENT_HELP = {
    "cover": "content optional; media variant also requires image",
    "end": "line needs title; line-note needs aside/content; line-artifact needs image + artifact_title + artifact_body",
    "section": "content",
    "three-steps": "steps[3] with label + body",
    "timeline": "steps[4] with label + body",
    "process-rail": "steps[6] or steps[8] with label",
    "quote": "quote + source",
    "card-trio": "cards[3] with title + body",
    "comparison": "sides[2], each with title + points[2]",
    "comparison-list": "sides[2], each with title + points[3]",
    "tabs": "sides[2], each with title + body",
    "metric": "content + metric.value + metric.unit + metric.caption",
    "recap": "content + cards[3] with title + body",
    "converge": "groups[2], each with title + items[2], plus outcome",
    "editorial-canvas": "content + image",
    "bleed-split": "content + image",
    "browser-showcase": "content + image",
    "diagonal-split": "content + image",
    "photo-gradient": "content + image",
    "photo-split": "content + image",
    "split-visual": "content + image",
    "editorial-feature": "content + image + cards[3] with title + body; optional card.icon",
    "catalog-board": "metrics[3] + groups[4], each with title/meta + items[3] title/body",
    "case-study-board": "content + metrics[2] + insight; evidence variant uses image, chart variant uses chart.label + chart.values",
    "annotated-showcase": "content + image + annotations[3] with title + body",
    "narrative-bento": "content + statement + statement_body + cards[2] + quote; optional icons",
    "sequence-gallery": "content + conclusion + steps[3], each with title + body + image",
}

MEDIA_TEMPLATES = {
    "bleed-split", "browser-showcase", "diagonal-split", "photo-gradient",
    "photo-split", "split-visual", "editorial-canvas",
    "editorial-feature", "annotated-showcase",
}


DECK_FIELDS = {
    "title": {"type": "string", "required": True},
    "palette": {"type": "named palette or custom object", "required": True},
    "palette_source": {"type": "string", "required": "for custom palette", "allowed": ["user", "brand"]},
    "typography": {"type": "string", "required": True, "allowed": list(TYPE_PROFILES)},
    "shape": {"type": "string", "required": True, "allowed": list(SHAPE_PROFILES)},
    "media_policy": {
        "type": "string", "required": False, "default": "required", "allowed": ["required", "text-only"],
        "rule": "required 让长演示维持真实素材覆盖；确实没有外部证据且以程序化结构为主时选 text-only",
    },
    "click_navigation": {"type": "boolean", "required": True, "default": False},
    "next_preview": {"type": "boolean", "required": False, "default": True},
    "show_progress": {"type": "boolean", "required": False, "default": True},
    "show_counter": {"type": "boolean", "required": False, "default": True},
}

SHARED_SLIDE_FIELDS = {
    "highlight": {
        "type": "string",
        "required": False,
        "use_when": "标题中有一个需要观众记住的短语",
        "rule": "复制 title 中的一个精确短语；每页最多一个；不写 HTML",
    },
    "background": {
        "type": "string",
        "required": False,
        "allowed": list(BACKGROUND_PRESETS),
        "use_when": "根据页面关系和整套节奏选择背景；省略时使用模板默认值",
        "rule": "只填写 allowed 中的名称；不写 CSS 或 data-bg",
    },
    "backdrop_text": {
        "type": "string",
        "required": False,
        "use_when": "页面确有一个适合放大为背景的短关键词",
        "rule": "填写 1–12 个非空字符；只表达当前页面内容，不写页码或默认装饰词",
    },
    "media_frame": {
        "type": "string",
        "required": "when the slide declares image/media/artifact_image",
        "allowed": ["content", "self-framed"],
        "use_when": "媒体页声明素材是否只是内容，或素材外框本身就是证据",
        "rule": "通常使用 content；只有素材自带设备壳、文档边框等且该外框必须保留时使用 self-framed",
    },
    "image_alt": {
        "type": "string",
        "required": False,
        "use_when": "素材需要比页面标题更准确的无障碍描述",
        "rule": "省略时程序使用页面标题；装饰图才允许显式空字符串",
    },
    "media_fit": {
        "type": "string",
        "required": False,
        "allowed": ["cover", "contain"],
        "use_when": "素材不可裁切时选 contain；照片铺满时选 cover",
        "rule": "省略时由模板按素材角色决定",
    },
    "media_position": {
        "type": "string",
        "required": False,
        "allowed": ["center", "left", "right", "top", "bottom", "top-left", "top-right", "bottom-left", "bottom-right"],
        "use_when": "cover 裁切需要保留偏离中心的主体",
        "rule": "省略时为 center；只选择 allowed 中的主体方位",
    },
    "media_treatment": {
        "type": "string",
        "required": False,
        "allowed": ["natural", "muted", "mono"],
        "use_when": "整套照片需要统一为自然、低饱和或黑白处理",
        "rule": "真实截图、品牌色和数据证据使用 natural；默认 natural",
    },
    "media_role": {
        "type": "string",
        "required": False,
        "use_when": "素材需要声明它在页面中的证据角色",
        "rule": "如 product-screenshot、evidence、photo、illustration；省略时 media plan 按模板推断",
    },
    "media_fidelity": {
        "type": "string",
        "required": False,
        "allowed": ["strict", "contextual", "illustrative"],
        "use_when": "严格保留截图/数据，或只保持语境与风格",
        "rule": "真实 UI、数据和文档使用 strict；照片用 contextual；概念图用 illustrative",
    },
    "media_question": {
        "type": "string",
        "required": False,
        "use_when": "明确这张素材回答的页面问题",
        "rule": "一句短句；省略时 media plan 从标题生成",
    },
    "media_source": {
        "type": "object",
        "required": False,
        "use_when": "记录用户素材、开放素材或生成素材的来源与权利依据",
        "rule": "可包含 kind、url、author、license、rights 与修改说明",
    },
}


def _text(value: object) -> str:
    return str(value or "").strip()


def _items(slide: dict, key: str) -> list:
    value = slide.get(key)
    return value if isinstance(value, list) else []


def _label(item: object) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return _text(item.get("label") or item.get("title") or item.get("h2"))
    return ""


def _body(item: object) -> str:
    if isinstance(item, dict):
        return _text(item.get("body") or item.get("text") or item.get("p"))
    return ""


def _require_cards(slide: dict, index: int, key: str, count: int, *, bodies: bool = True) -> list:
    items = _items(slide, key)
    if len(items) != count:
        raise SystemExit(f"Outline slide {index} template {slide['template']!r} requires exactly {count} {key} items.")
    for item_index, item in enumerate(items, start=1):
        if not _label(item):
            raise SystemExit(f"Outline slide {index} {key}[{item_index}] requires a label/title.")
        if bodies and not _body(item):
            raise SystemExit(f"Outline slide {index} {key}[{item_index}] requires body text.")
    return items


def _require_sides(slide: dict, index: int, points: int) -> None:
    sides = _items(slide, "sides")
    if len(sides) != 2:
        raise SystemExit(f"Outline slide {index} template {slide['template']!r} requires exactly 2 sides.")
    for side_index, side in enumerate(sides, start=1):
        if not _label(side):
            raise SystemExit(f"Outline slide {index} sides[{side_index}] requires a title.")
        values = side.get("points") if isinstance(side, dict) else None
        if not isinstance(values, list) or len(values) != points or any(not _text(v.get("text") or v.get("body") if isinstance(v, dict) else v) for v in values):
            raise SystemExit(f"Outline slide {index} sides[{side_index}] requires exactly {points} non-empty points.")


def _require_content(slide: dict, index: int) -> None:
    if not _text(slide.get("content") or slide.get("note") or slide.get("aside")):
        raise SystemExit(f"Outline slide {index} template {slide['template']!r} requires content/note text.")


def _require_metrics(slide: dict, index: int, count: int) -> list:
    metrics = _items(slide, "metrics")
    if len(metrics) != count:
        raise SystemExit(f"Outline slide {index} template {slide['template']!r} requires exactly {count} metrics.")
    for metric_index, metric in enumerate(metrics, start=1):
        if not isinstance(metric, dict) or not _text(metric.get("label")) or not _text(metric.get("value")):
            raise SystemExit(f"Outline slide {index} metrics[{metric_index}] requires label and value.")
    return metrics


def _require_icon(value: object, index: int, field: str) -> None:
    if value is None or not str(value).strip():
        return
    if str(value) not in ICON_CATALOG:
        raise SystemExit(f"Outline slide {index} {field} must be a bundled icon: {', '.join(sorted(ICON_CATALOG))}.")


def validate_slide_content(slide: dict, index: int) -> None:
    template = slide["template"]
    variant = slide["variant"]
    image = _text(slide.get("image") or slide.get("media") or slide.get("artifact_image"))

    if template == "editorial-feature":
        _require_content(slide, index)
        if not image:
            raise SystemExit(f"Outline slide {index} template 'editorial-feature' requires an image path.")
        cards = _require_cards(slide, index, "cards", 3)
        for item_index, item in enumerate(cards, start=1):
            if isinstance(item, dict):
                _require_icon(item.get("icon"), index, f"cards[{item_index}].icon")
    elif template == "catalog-board":
        _require_metrics(slide, index, 3)
        groups = _items(slide, "groups")
        if len(groups) != 4:
            raise SystemExit(f"Outline slide {index} template 'catalog-board' requires exactly 4 groups.")
        for group_index, group in enumerate(groups, start=1):
            items = group.get("items") if isinstance(group, dict) else None
            if not _label(group) or not isinstance(items, list) or len(items) != 3:
                raise SystemExit(f"Outline slide {index} groups[{group_index}] requires title and exactly 3 items.")
            for item_index, item in enumerate(items, start=1):
                if not isinstance(item, dict) or not _label(item) or not _body(item):
                    raise SystemExit(f"Outline slide {index} groups[{group_index}].items[{item_index}] requires title and body.")
    elif template == "case-study-board":
        _require_content(slide, index)
        _require_metrics(slide, index, 2)
        insight = slide.get("insight")
        if not isinstance(insight, dict) or not _label(insight) or not _body(insight):
            raise SystemExit(f"Outline slide {index} template 'case-study-board' requires insight.title and insight.body.")
        _require_icon(insight.get("icon"), index, "insight.icon")
        if variant == "evidence" and not image:
            raise SystemExit(f"Outline slide {index} case-study-board evidence variant requires an image path.")
        if variant == "chart":
            chart = slide.get("chart")
            values = chart.get("values") if isinstance(chart, dict) else None
            if not isinstance(chart, dict) or not _text(chart.get("label")) or not isinstance(values, list) or not 3 <= len(values) <= 7:
                raise SystemExit(f"Outline slide {index} case-study-board chart variant requires chart.label and 3–7 values.")
            if any(not isinstance(value, (int, float)) or value < 0 for value in values):
                raise SystemExit(f"Outline slide {index} chart.values must contain non-negative numbers.")
    elif template == "annotated-showcase":
        _require_content(slide, index)
        if not image:
            raise SystemExit(f"Outline slide {index} template 'annotated-showcase' requires an image path.")
        _require_cards(slide, index, "annotations", 3)
    elif template == "narrative-bento":
        _require_content(slide, index)
        for field in ("statement", "statement_body", "quote"):
            if not _text(slide.get(field)):
                raise SystemExit(f"Outline slide {index} template 'narrative-bento' requires {field}.")
        cards = _require_cards(slide, index, "cards", 2)
        for item_index, item in enumerate(cards, start=1):
            if isinstance(item, dict):
                _require_icon(item.get("icon"), index, f"cards[{item_index}].icon")
        for field in ("statement_icon", "quote_icon"):
            _require_icon(slide.get(field), index, field)
    elif template == "sequence-gallery":
        _require_content(slide, index)
        if not _text(slide.get("conclusion")):
            raise SystemExit(f"Outline slide {index} template 'sequence-gallery' requires conclusion.")
        steps = _require_cards(slide, index, "steps", 3)
        for step_index, step in enumerate(steps, start=1):
            if not isinstance(step, dict) or not _text(step.get("image")):
                raise SystemExit(f"Outline slide {index} steps[{step_index}] requires a project-relative image.")
    elif template in MEDIA_TEMPLATES:
        _require_content(slide, index)
        if not image:
            raise SystemExit(f"Outline slide {index} template {template!r} requires an image path.")
    elif template == "cover":
        if variant == "media" and not image:
            raise SystemExit(f"Outline slide {index} cover variant 'media' requires an image path.")
    elif template == "section":
        _require_content(slide, index)
    elif template == "end":
        if variant == "line-note" and not _text(slide.get("aside") or slide.get("content")):
            raise SystemExit(f"Outline slide {index} end variant 'line-note' requires aside/content text.")
        if variant == "line-artifact":
            if not image:
                raise SystemExit(f"Outline slide {index} end variant 'line-artifact' requires an image path.")
            for field in ("artifact_title", "artifact_body"):
                if not _text(slide.get(field)):
                    raise SystemExit(f"Outline slide {index} end variant 'line-artifact' requires {field}.")
    elif template == "three-steps":
        _require_cards(slide, index, "steps", 3)
    elif template == "timeline":
        _require_cards(slide, index, "steps", 4)
    elif template == "process-rail":
        count = 6 if variant == "steps-6" else 8
        _require_cards(slide, index, "steps", count, bodies=False)
    elif template == "quote":
        if not _text(slide.get("quote")) or not _text(slide.get("source")):
            raise SystemExit(f"Outline slide {index} template 'quote' requires quote and source.")
    elif template == "card-trio":
        _require_cards(slide, index, "cards", 3)
    elif template == "recap":
        _require_content(slide, index)
        _require_cards(slide, index, "cards", 3)
    elif template == "comparison":
        _require_sides(slide, index, 2)
    elif template == "comparison-list":
        _require_sides(slide, index, 3)
    elif template == "tabs":
        sides = _items(slide, "sides")
        if len(sides) != 2 or any(not _label(side) or not _body(side) for side in sides):
            raise SystemExit(f"Outline slide {index} template 'tabs' requires 2 sides with title and body.")
    elif template == "metric":
        _require_content(slide, index)
        metric = slide.get("metric")
        if not isinstance(metric, dict) or any(not _text(metric.get(key)) for key in ("value", "unit", "caption")):
            raise SystemExit(f"Outline slide {index} template 'metric' requires metric.value, metric.unit and metric.caption.")
    elif template == "converge":
        groups = _items(slide, "groups")
        if len(groups) != 2 or not _text(slide.get("outcome")):
            raise SystemExit(f"Outline slide {index} template 'converge' requires 2 groups and outcome.")
        for group_index, group in enumerate(groups, start=1):
            values = group.get("items") if isinstance(group, dict) else None
            if not _label(group) or not isinstance(values, list) or len(values) != 2 or any(not _text(v) for v in values):
                raise SystemExit(f"Outline slide {index} groups[{group_index}] requires title and exactly 2 items.")
def validate_outline(data: dict, templates_dir: Path) -> list[dict]:
    if not _text(data.get("title")):
        raise SystemExit("Outline requires a title.")
    palette = data.get("palette")
    if isinstance(palette, str):
        if canonical_name(palette) not in PALETTES:
            raise SystemExit(f"Outline palette must be one of: {', '.join(sorted(PALETTES))}.")
    elif isinstance(palette, dict):
        if data.get("palette_source") not in {"user", "brand"}:
            raise SystemExit("A custom palette requires palette_source 'user' or 'brand'.")
        for key in ("accent", "accent_soft", "accent_strong"):
            if not isinstance(palette.get(key), str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", palette[key]):
                raise SystemExit(f"Custom palette requires six-digit {key}.")
    else:
        raise SystemExit("Outline requires an explicit palette name or custom palette object.")
    if data.get("typography") not in TYPE_PROFILES:
        raise SystemExit(f"Outline typography must be one of: {', '.join(TYPE_PROFILES)}.")
    if data.get("shape") not in SHAPE_PROFILES:
        raise SystemExit(f"Outline shape must be one of: {', '.join(SHAPE_PROFILES)}.")
    if data.get("media_policy", "required") not in {"required", "text-only"}:
        raise SystemExit("Outline media_policy must be 'required' or 'text-only'.")
    if "click_navigation" not in data or not isinstance(data["click_navigation"], bool):
        raise SystemExit("Outline requires boolean click_navigation.")
    for field in ("next_preview", "show_progress", "show_counter"):
        if field in data and not isinstance(data[field], bool):
            raise SystemExit(f"Outline {field} must be boolean when provided.")

    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        raise SystemExit("Outline requires a non-empty slides array.")
    available = {path.stem for path in templates_dir.glob("*.html")}
    ids: set[str] = set()
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            raise SystemExit(f"Outline slide {index} must be an object.")
        slide_id = slide.get("id")
        title = slide.get("title")
        template = slide.get("template")
        if not isinstance(slide_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slide_id):
            raise SystemExit(f"Outline slide {index} has invalid id.")
        if slide_id in ids:
            raise SystemExit(f"Outline has duplicate id: {slide_id}")
        if not _text(title):
            raise SystemExit(f"Outline slide {index} requires a title.")
        if template not in available or template not in COMPONENT_CONTRACTS:
            raise SystemExit(f"Outline slide {index} uses unknown template {template!r}.")
        highlight = slide.get("highlight")
        if highlight is not None and (not isinstance(highlight, str) or not highlight or highlight not in title):
            raise SystemExit(f"Outline slide {index} highlight must be an exact phrase inside its title.")
        background = slide.get("background")
        if background is not None and background not in BACKGROUND_PRESETS:
            raise SystemExit(f"Outline slide {index} background must be one of: {', '.join(BACKGROUND_PRESETS)}.")
        backdrop_text = slide.get("backdrop_text")
        if backdrop_text is not None:
            if not isinstance(backdrop_text, str) or not backdrop_text.strip() or len(re.sub(r"\s+", "", backdrop_text)) > 12:
                raise SystemExit(f"Outline slide {index} backdrop_text must contain 1–12 non-space characters.")
        image = _text(slide.get("image") or slide.get("media") or slide.get("artifact_image"))
        nested_media = template == "sequence-gallery" and any(_text(item.get("image")) for item in _items(slide, "steps") if isinstance(item, dict))
        if (image or nested_media) and slide.get("media_frame") not in {"content", "self-framed"}:
            raise SystemExit(f"Outline slide {index} with media requires media_frame 'content' or 'self-framed'.")
        for field, allowed in (
            ("media_fit", {"cover", "contain"}),
            ("media_position", {"center", "left", "right", "top", "bottom", "top-left", "top-right", "bottom-left", "bottom-right"}),
            ("media_treatment", {"natural", "muted", "mono"}),
        ):
            if slide.get(field) is not None and slide[field] not in allowed:
                raise SystemExit(f"Outline slide {index} {field} must be one of: {', '.join(sorted(allowed))}.")
        if slide.get("media_fidelity") is not None and slide["media_fidelity"] not in {"strict", "contextual", "illustrative"}:
            raise SystemExit(f"Outline slide {index} media_fidelity must be strict, contextual or illustrative.")
        for field in ("media_role", "media_question"):
            if slide.get(field) is not None and not _text(slide[field]):
                raise SystemExit(f"Outline slide {index} {field} must be a non-empty string when provided.")
        if slide.get("media_source") is not None and not isinstance(slide["media_source"], dict):
            raise SystemExit(f"Outline slide {index} media_source must be an object when provided.")
        normalize_component_choices(slide, index)
        validate_slide_content(slide, index)
        ids.add(slide_id)
    return slides
