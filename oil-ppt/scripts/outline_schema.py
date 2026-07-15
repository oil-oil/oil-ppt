#!/usr/bin/env python3
"""Small explicit outline contract shared by preview, scaffold, and build."""
from __future__ import annotations

import re
from pathlib import Path

from background_presets import BACKGROUND_PRESETS
from component_contracts import COMPONENT_CONTRACTS, PAGE_BLEND_TEMPLATES, normalize_component_choices
from icon_registry import ICON_CATALOG
from media_assets import outline_media_bindings
from palette_tokens import PALETTES, TOKEN_KEYS, canonical_name, normalize_palette
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
    "process-cards": "sequence",
}

TEMPLATE_CONTENT_HELP = {
    "cover": "content optional; media variant also requires image",
    "end": "line needs title; line-note needs exactly one of aside/content/note; line-artifact needs image + artifact_title + artifact_body",
    "section": "content",
    "three-steps": "steps[3] with label + body",
    "timeline": "steps[4] with label + body",
    "process-rail": "steps-6 uses steps[6] with title + body; steps-8 uses steps[8] with title only",
    "quote": "quote + source",
    "card-trio": "feature variants use cards[3] with title + body; media-evidence additionally requires cards[1..2].images[2] with image + optional caption",
    "comparison": "default uses sides[2] with title + points[2]; visual-evidence additionally requires evidence[2] per side",
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
    "editorial-feature": "content + image + cards[3] with title + body; hero-collage also requires secondary_image",
    "catalog-board": "metrics[3] + groups[4], each with title/meta + items[3] title/body",
    "case-study-board": "content + metrics[2] + insight; evidence variant uses image, chart variant uses chart.label + chart.values",
    "annotated-showcase": "content + image + annotations[3] with title + body",
    "narrative-bento": "content + statement + statement_body + cards[2] + quote; optional icons",
    "sequence-gallery": "content + conclusion + steps[3], each with title + body + image",
    "process-cards": "steps[4] with title + body; icons are all-or-none; optional measurements[4] require measurement_note + measurement_meta",
}


# Only complex variants need an extra map. This is emitted by `contract --id`
# so a weaker model sees the shortest valid input before optional polish.
VARIANT_INPUT_GUIDANCE = {
    "process-rail": {
        "steps-6": {
            "minimum": ["steps[6]: title + body"],
            "optional": [],
        },
        "steps-8": {
            "minimum": ["steps[8]: title only"],
            "optional": [],
        },
    },
    "editorial-feature": {
        "default": {
            "minimum": ["content", "image", "cards[3]: title + body"],
            "optional": ["cards[].icon", "meta", "page_note"],
        },
        "hero-collage": {
            "minimum": ["content", "image", "secondary_image", "cards[3]: title + body"],
            "optional": ["badge", "media_note", "meta", "page_note"],
        },
    },
    "comparison": {
        "default": {
            "minimum": ["sides[2]: title + points[2]"],
            "optional": [],
        },
        "visual-evidence": {
            "minimum": ["content", "sides[2]: title + evidence[2] + points[2]"],
            "optional": ["sides[].lead", "evidence[].caption", "evidence[].alt"],
        },
    },
    "card-trio": {
        "feature-left": {"minimum": ["cards[3]: title + body"], "optional": []},
        "feature-right": {"minimum": ["cards[3]: title + body"], "optional": []},
        "feature-top": {"minimum": ["cards[3]: title + body"], "optional": []},
        "media-evidence": {
            "minimum": ["content", "cards[3]: title + body", "cards[1..2].images[2]"],
            "optional": ["cards[1..2].images[].caption", "cards[1..2].images[].alt", "cards[3].backdrop"],
        },
    },
    "process-cards": {
        "linear": {"minimum": ["content", "steps[4]: title + body"], "optional": ["icons on all 4 steps", "measurements[4] + measurement_note + measurement_meta"]},
        "terminal-focus": {"minimum": ["content", "steps[4]: title + body"], "optional": ["icons on all 4 steps", "measurements[4] + measurement_note + measurement_meta"]},
    },
    "catalog-board": {
        "default": {
            "minimum": ["metrics[3]: value + label", "groups[4]: title + meta + items[3](title + body)"],
            "optional": ["kicker", "page_note", "meta"],
            "budgets": {"group.title": 12, "group.meta": 18, "item.title": 14, "item.body": 24},
        },
    },
    "case-study-board": {
        "evidence": {
            "minimum": ["content", "image", "media_frame", "metrics[2]: value + label", "insight: title + body"],
            "optional": ["insight.icon", "image_alt"],
        },
        "chart": {
            "minimum": ["content", "metrics[2]: value + label", "insight: title + body", "chart.label + chart.values[3..7]"],
            "optional": ["insight.icon"],
        },
    },
    "annotated-showcase": {
        "default": {
            "minimum": ["content", "image", "media_frame", "annotations[3]: title + body"],
            "optional": ["kicker", "image_alt"],
            "budgets": {"annotation.title": 16, "annotation.body": 48},
        },
    },
    "narrative-bento": {
        "default": {
            "minimum": ["content", "statement", "statement_body", "cards[2]: title + body", "quote"],
            "optional": ["kicker", "statement_icon", "quote_icon", "cards[].icon"],
        },
    },
    "sequence-gallery": {
        "default": {
            "minimum": ["content", "conclusion", "media_frame", "steps[3]: title + body + image"],
            "optional": ["kicker", "page_note", "steps[].image_alt", "steps[].media_question", "steps[].media_source"],
        },
    },
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
        "rule": "默认 required；只有用户明确要求整套不使用图片时才选 text-only，并在 plan 阶段记录用户确认",
    },
    "click_navigation": {"type": "boolean", "required": True, "default": False},
    "next_preview": {"type": "boolean", "required": False, "default": True},
    "show_progress": {"type": "boolean", "required": False, "default": True},
    "show_counter": {"type": "boolean", "required": False, "default": True},
}

DECK_ALLOWED_FIELDS = frozenset({*DECK_FIELDS, "slides"})

SLIDE_ALLOWED_FIELDS = frozenset({
    "id", "title", "template", "variant", "decor",
    "highlight", "background", "backdrop_text",
    "kicker", "content", "note", "meta", "page_note",
    "image", "media", "artifact_image", "image_alt",
    "secondary_image", "secondary_image_alt", "badge", "media_note",
    "media_frame", "media_fit", "media_position", "media_treatment", "media_surface",
    "media_role", "media_fidelity", "media_question", "media_source",
    "cards", "steps", "sides", "groups", "outcome",
    "quote", "source", "metric", "metrics", "insight", "chart", "annotations",
    "statement", "statement_body", "statement_icon", "quote_icon", "conclusion",
    "measurements", "measurement_note", "measurement_meta",
    "aside", "aside_label", "artifact_title", "artifact_body",
    # Planning hints consumed by the recommender; intentionally not rendered.
    "visual_task", "media_intent",
})

BASE_VISIBLE_FIELDS = frozenset({
    "id", "title", "template", "variant", "decor",
    "highlight", "background", "backdrop_text", "visual_task", "media_intent",
})
MEDIA_METADATA_FIELDS = frozenset({
    "media_frame", "media_fit", "media_position", "media_treatment",
    "media_role", "media_fidelity", "media_question", "media_source",
})
STANDARD_MEDIA_FIELDS = frozenset({"content", "note", "image", "media", "image_alt", *MEDIA_METADATA_FIELDS})

# Top-level fields that can affect each template's rendered result. Variant-only
# fields are narrowed further by validate_slide_content.
TEMPLATE_VISIBLE_FIELDS = {
    "cover": {"kicker", "content", "note", "image", "media", "image_alt", *MEDIA_METADATA_FIELDS},
    "end": {"content", "note", "meta", "aside", "aside_label", "image", "artifact_image", "image_alt", "artifact_title", "artifact_body", *MEDIA_METADATA_FIELDS},
    "section": {"content", "note"},
    "three-steps": {"steps"},
    "timeline": {"steps"},
    "process-rail": {"steps"},
    "quote": {"quote", "source"},
    "card-trio": {"content", "note", "kicker", "cards", *MEDIA_METADATA_FIELDS},
    "comparison": {"content", "note", "kicker", "sides", *MEDIA_METADATA_FIELDS},
    "comparison-list": {"sides"},
    "tabs": {"sides"},
    "metric": {"content", "note", "metric"},
    "recap": {"content", "note", "cards"},
    "converge": {"groups", "outcome"},
    "bleed-split": set(STANDARD_MEDIA_FIELDS),
    "browser-showcase": set(STANDARD_MEDIA_FIELDS),
    "diagonal-split": set(STANDARD_MEDIA_FIELDS),
    "editorial-canvas": set(STANDARD_MEDIA_FIELDS),
    "photo-gradient": set(STANDARD_MEDIA_FIELDS),
    "photo-split": set(STANDARD_MEDIA_FIELDS),
    "split-visual": {*STANDARD_MEDIA_FIELDS, "media_surface"},
    "editorial-feature": {"content", "note", "kicker", "meta", "page_note", "image", "media", "image_alt", "secondary_image", "secondary_image_alt", "badge", "media_note", "cards", "media_surface", *MEDIA_METADATA_FIELDS},
    "catalog-board": {"kicker", "meta", "page_note", "metrics", "groups"},
    "case-study-board": {"content", "note", "kicker", "image", "media", "image_alt", "metrics", "insight", "chart", *MEDIA_METADATA_FIELDS},
    "annotated-showcase": {"content", "note", "kicker", "image", "media", "image_alt", "annotations", *MEDIA_METADATA_FIELDS},
    "narrative-bento": {"content", "note", "kicker", "statement", "statement_body", "statement_icon", "quote", "quote_icon", "cards"},
    "sequence-gallery": {"content", "note", "kicker", "page_note", "conclusion", "steps", *MEDIA_METADATA_FIELDS},
    "process-cards": {"content", "note", "kicker", "steps", "measurements", "measurement_note", "measurement_meta"},
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
    "media_surface": {
        "type": "string",
        "required": False,
        "allowed": ["component", "page-blend"],
        "use_when": "split-visual 或 editorial-feature 中，概念插画或自带完整边界的素材需要直接融入页面",
        "rule": "概念插画使用 page-blend；普通截图、界面和文档使用 component；声明 media_frame=self-framed 时自动使用 page-blend，避免双重外框",
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
    return "" if value is None or isinstance(value, bool) else str(value).strip()


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


def _reject_alias_conflicts(value: object, index: int, path: str) -> None:
    """Reject ambiguous aliases before rendering or editor binding can diverge."""
    if isinstance(value, dict):
        for aliases in (("label", "title", "h2"), ("body", "text", "p")):
            present = [key for key in aliases if key in value]
            if len(present) > 1:
                raise SystemExit(
                    f"Outline slide {index} {path} provides conflicting aliases: {', '.join(present)}. Keep exactly one."
                )
        if "image" in value:
            present = [key for key in ("caption", "label") if key in value]
            if len(present) > 1:
                raise SystemExit(
                    f"Outline slide {index} {path} provides both caption and label for one image. Keep exactly one."
                )
        for key, item in value.items():
            _reject_alias_conflicts(item, index, f"{path}.{key}")
    elif isinstance(value, list):
        for item_index, item in enumerate(value, start=1):
            _reject_alias_conflicts(item, index, f"{path}[{item_index}]")


def _max_chars(value: object, index: int, field: str, maximum: int) -> None:
    length = len(re.sub(r"\s+", "", _text(value)))
    if length > maximum:
        raise SystemExit(
            f"Outline slide {index} {field} is too long for its fixed component "
            f"({length}/{maximum} non-space characters). Shorten the copy or choose a roomier component."
        )


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


def _reject_point_fields(sides: list, index: int, allowed: set[str], reason: str) -> None:
    for side_index, side in enumerate(sides, start=1):
        values = side.get("points") if isinstance(side, dict) else None
        if isinstance(values, list):
            _reject_nested_fields(values, index, f"sides[{side_index}].points", allowed, reason)


def _require_content(slide: dict, index: int) -> None:
    if not _text(slide.get("content") or slide.get("note")):
        raise SystemExit(f"Outline slide {index} template {slide['template']!r} requires content/note text.")


def _reject_fields(slide: dict, index: int, fields: tuple[str, ...], reason: str) -> None:
    hidden = [field for field in fields if slide.get(field) is not None]
    if hidden:
        raise SystemExit(
            f"Outline slide {index} fields {', '.join(hidden)} are not rendered by "
            f"{slide['template']}/{slide['variant']} ({reason}). Remove them or choose the matching variant."
        )


def _reject_object_fields(item: object, index: int, path: str, allowed: set[str], reason: str) -> None:
    if not isinstance(item, dict):
        return
    hidden = sorted(set(item) - allowed)
    if hidden:
        raise SystemExit(
            f"Outline slide {index} {path} field(s) {', '.join(hidden)} are not rendered "
            f"({reason}). Remove them or choose the matching component/variant."
        )


def _reject_nested_fields(items: list, index: int, key: str, allowed: set[str], reason: str) -> None:
    """Reject nested keys that the selected component cannot visibly consume."""
    for item_index, item in enumerate(items, start=1):
        _reject_object_fields(item, index, f"{key}[{item_index}]", allowed, reason)


def _require_metrics(slide: dict, index: int, count: int) -> list:
    metrics = _items(slide, "metrics")
    if len(metrics) != count:
        raise SystemExit(f"Outline slide {index} template {slide['template']!r} requires exactly {count} metrics.")
    for metric_index, metric in enumerate(metrics, start=1):
        if not isinstance(metric, dict) or not _text(metric.get("label")) or not _text(metric.get("value")):
            raise SystemExit(f"Outline slide {index} metrics[{metric_index}] requires label and value.")
        hidden = sorted(set(metric) - {"label", "value"})
        if hidden:
            raise SystemExit(f"Outline slide {index} metrics[{metric_index}] field(s) {', '.join(hidden)} are not rendered.")
    return metrics


def _require_icon(value: object, index: int, field: str) -> None:
    if value is None or not str(value).strip():
        return
    if str(value) not in ICON_CATALOG:
        raise SystemExit(f"Outline slide {index} {field} must be a bundled icon: {', '.join(sorted(ICON_CATALOG))}.")


def _media_item_path(value: object) -> str:
    if isinstance(value, dict):
        return _text(value.get("image"))
    return _text(value)


def _require_project_media_path(value: object, index: int, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"Outline slide {index} {field} requires a non-empty project-relative image path.")
    path = value.strip()
    if (
        path.startswith(("/", "\\"))
        or re.match(r"^[A-Za-z]:[\\/]", path)
        or re.match(r"^(?:https?|data|file):", path, re.I)
        or ".." in Path(path).parts
    ):
        raise SystemExit(f"Outline slide {index} {field} must stay project-relative: {path}")
    return path


def _require_media_items(values: object, index: int, field: str, count: int) -> list:
    if not isinstance(values, list) or len(values) != count:
        raise SystemExit(f"Outline slide {index} {field} requires exactly {count} media items.")
    for item_index, item in enumerate(values, start=1):
        path = _require_project_media_path(_media_item_path(item), index, f"{field}[{item_index}]")
        if isinstance(item, dict):
            hidden = sorted(set(item) - {"image", "caption", "label", "alt"})
            if hidden:
                raise SystemExit(f"Outline slide {index} {field}[{item_index}] field(s) {', '.join(hidden)} are not rendered.")
            for copy_field in ("caption", "label", "alt"):
                if item.get(copy_field) is not None and not _text(item.get(copy_field)):
                    raise SystemExit(f"Outline slide {index} {field}[{item_index}].{copy_field} must be non-empty when provided.")
    return values


def _validate_media_contract(slide: dict, index: int) -> list[tuple[str, object]]:
    """Reject media fields that the selected component would silently ignore."""
    template = str(slide.get("template") or "")
    variant = str(slide.get("variant") or "")
    bindings = outline_media_bindings(slide)
    declared_top_fields = [field for field in ("image", "media", "artifact_image") if slide.get(field)]
    if len(declared_top_fields) > 1:
        raise SystemExit(
            f"Outline slide {index} declares multiple aliases for the same top-level media: "
            f"{', '.join(declared_top_fields)}. Keep exactly one."
        )
    top_level = _text(slide.get("image") or slide.get("media") or slide.get("artifact_image"))

    allows_top_level = (
        template in MEDIA_TEMPLATES
        or (template == "cover" and variant == "media")
        or (template == "end" and variant == "line-artifact")
        or (template == "case-study-board" and variant == "evidence")
    )
    if top_level and not allows_top_level:
        raise SystemExit(
            f"Outline slide {index} {template}/{variant} does not render image/media/artifact_image. "
            "Remove the hidden field or choose a media-capable component."
        )
    for field, value in bindings:
        _require_project_media_path(value, index, field)
    if slide.get("secondary_image") and not (template == "editorial-feature" and variant == "hero-collage"):
        raise SystemExit(f"Outline slide {index} secondary_image is only rendered by editorial-feature/hero-collage.")

    if template != "comparison" or variant != "visual-evidence":
        if any(isinstance(side, dict) and side.get("evidence") is not None for side in _items(slide, "sides")):
            raise SystemExit(f"Outline slide {index} {template}/{variant} does not render sides[].evidence.")
    if template != "card-trio" or variant != "media-evidence":
        if any(isinstance(card, dict) and card.get("images") is not None for card in _items(slide, "cards")):
            raise SystemExit(f"Outline slide {index} {template}/{variant} does not render cards[].images.")
    if template != "sequence-gallery":
        nested_media_fields = {"image", "image_alt", "media_question", "media_source"}
        for step_index, step in enumerate(_items(slide, "steps"), start=1):
            if isinstance(step, dict) and nested_media_fields.intersection(step):
                fields = ", ".join(sorted(nested_media_fields.intersection(step)))
                raise SystemExit(f"Outline slide {index} {template}/{variant} does not render steps[{step_index}] field(s) {fields}.")

    frame = slide.get("media_frame")
    if bindings and frame not in {"content", "self-framed"}:
        raise SystemExit(f"Outline slide {index} with media requires media_frame 'content' or 'self-framed'.")
    if not bindings and frame is not None:
        raise SystemExit(f"Outline slide {index} declares media_frame but the selected component has no rendered media.")
    media_only_fields = (
        "media_fit", "media_position", "media_treatment", "media_surface", "media_role",
        "media_fidelity", "media_question", "media_source",
    )
    if not bindings:
        _reject_fields(slide, index, media_only_fields, "media metadata requires rendered media")
    if slide.get("media_surface") is not None and template not in PAGE_BLEND_TEMPLATES:
        allowed = ", ".join(sorted(PAGE_BLEND_TEMPLATES))
        raise SystemExit(f"Outline slide {index} media_surface is only supported by: {allowed}.")
    if not top_level and slide.get("image_alt") is not None:
        raise SystemExit(f"Outline slide {index} image_alt requires a rendered top-level image/media/artifact_image.")
    if not slide.get("secondary_image") and slide.get("secondary_image_alt") is not None:
        raise SystemExit(f"Outline slide {index} secondary_image_alt requires secondary_image.")
    return bindings


def validate_slide_content(slide: dict, index: int) -> None:
    template = slide["template"]
    variant = slide["variant"]
    _reject_alias_conflicts(slide, index, "slide")
    image = _text(slide.get("image") or slide.get("media") or slide.get("artifact_image"))
    if _text(slide.get("content")) and _text(slide.get("note")):
        raise SystemExit(f"Outline slide {index} accepts content or note as aliases, not both.")

    if template == "editorial-feature":
        _require_content(slide, index)
        if not image:
            raise SystemExit(f"Outline slide {index} template 'editorial-feature' requires an image path.")
        cards = _require_cards(slide, index, "cards", 3)
        card_fields = {"label", "title", "body"}
        if variant == "default":
            card_fields.add("icon")
        _reject_nested_fields(cards, index, "cards", card_fields, f"editorial-feature/{variant}")
        for item_index, item in enumerate(cards, start=1):
            if isinstance(item, dict):
                _require_icon(item.get("icon"), index, f"cards[{item_index}].icon")
        if variant == "hero-collage":
            secondary = _text(slide.get("secondary_image"))
            if not secondary or secondary.startswith(("/", "http://", "https://")):
                raise SystemExit(f"Outline slide {index} editorial-feature hero-collage requires project-relative secondary_image.")
        else:
            _reject_fields(slide, index, ("badge", "media_note", "secondary_image", "secondary_image_alt"), "collage-only fields")
    elif template == "catalog-board":
        _reject_fields(slide, index, ("content", "note"), "the catalog header is composed from metrics")
        metrics = _require_metrics(slide, index, 3)
        for metric_index, metric in enumerate(metrics, start=1):
            _max_chars(metric.get("value"), index, f"metrics[{metric_index}].value", 10)
            _max_chars(metric.get("label"), index, f"metrics[{metric_index}].label", 14)
        groups = _items(slide, "groups")
        if len(groups) != 4:
            raise SystemExit(f"Outline slide {index} template 'catalog-board' requires exactly 4 groups.")
        for group_index, group in enumerate(groups, start=1):
            items = group.get("items") if isinstance(group, dict) else None
            if not _label(group) or not isinstance(group, dict) or not _text(group.get("meta")) or not isinstance(items, list) or len(items) != 3:
                raise SystemExit(f"Outline slide {index} groups[{group_index}] requires title, meta, and exactly 3 items.")
            _max_chars(_label(group), index, f"groups[{group_index}].title", 12)
            _max_chars(group.get("meta") if isinstance(group, dict) else "", index, f"groups[{group_index}].meta", 18)
            for item_index, item in enumerate(items, start=1):
                if not isinstance(item, dict) or not _label(item) or not _body(item):
                    raise SystemExit(f"Outline slide {index} groups[{group_index}].items[{item_index}] requires title and body.")
                hidden = sorted(set(item) - {"label", "title", "body"})
                if hidden:
                    raise SystemExit(f"Outline slide {index} groups[{group_index}].items[{item_index}] field(s) {', '.join(hidden)} are not rendered.")
                _max_chars(_label(item), index, f"groups[{group_index}].items[{item_index}].title", 14)
                _max_chars(_body(item), index, f"groups[{group_index}].items[{item_index}].body", 24)
        _reject_nested_fields(groups, index, "groups", {"label", "title", "meta", "items"}, "catalog-board")
    elif template == "case-study-board":
        _reject_fields(slide, index, ("meta", "page_note"), "this component has no footer metadata slots")
        _require_content(slide, index)
        _require_metrics(slide, index, 2)
        insight = slide.get("insight")
        if not isinstance(insight, dict) or not _label(insight) or not _body(insight):
            raise SystemExit(f"Outline slide {index} template 'case-study-board' requires insight.title and insight.body.")
        _reject_object_fields(insight, index, "insight", {"label", "title", "body", "icon"}, "case-study-board")
        _require_icon(insight.get("icon"), index, "insight.icon")
        if variant == "evidence" and not image:
            raise SystemExit(f"Outline slide {index} case-study-board evidence variant requires an image path.")
        if variant == "evidence":
            _reject_fields(slide, index, ("chart",), "the evidence variant shows an image instead of the native chart")
        if variant == "chart":
            chart = slide.get("chart")
            values = chart.get("values") if isinstance(chart, dict) else None
            if not isinstance(chart, dict) or not _text(chart.get("label")) or not isinstance(values, list) or not 3 <= len(values) <= 7:
                raise SystemExit(f"Outline slide {index} case-study-board chart variant requires chart.label and 3–7 values.")
            hidden = sorted(set(chart) - {"label", "values"})
            if hidden:
                raise SystemExit(f"Outline slide {index} chart field(s) {', '.join(hidden)} are not rendered.")
            if any(not isinstance(value, (int, float)) or value < 0 for value in values):
                raise SystemExit(f"Outline slide {index} chart.values must contain non-negative numbers.")
    elif template == "annotated-showcase":
        _reject_fields(slide, index, ("meta", "page_note"), "this component has no footer metadata slots")
        _require_content(slide, index)
        if not image:
            raise SystemExit(f"Outline slide {index} template 'annotated-showcase' requires an image path.")
        annotations = _require_cards(slide, index, "annotations", 3)
        _reject_nested_fields(annotations, index, "annotations", {"label", "title", "body"}, "annotated-showcase")
        for annotation_index, annotation in enumerate(annotations, start=1):
            _max_chars(_label(annotation), index, f"annotations[{annotation_index}].title", 16)
            _max_chars(_body(annotation), index, f"annotations[{annotation_index}].body", 48)
    elif template == "narrative-bento":
        _reject_fields(slide, index, ("meta", "page_note"), "this component has no footer metadata slots")
        _require_content(slide, index)
        for field in ("statement", "statement_body", "quote"):
            if not _text(slide.get(field)):
                raise SystemExit(f"Outline slide {index} template 'narrative-bento' requires {field}.")
        cards = _require_cards(slide, index, "cards", 2)
        _reject_nested_fields(cards, index, "cards", {"label", "title", "body", "icon"}, "narrative-bento")
        for item_index, item in enumerate(cards, start=1):
            if isinstance(item, dict):
                _require_icon(item.get("icon"), index, f"cards[{item_index}].icon")
        for field in ("statement_icon", "quote_icon"):
            _require_icon(slide.get(field), index, field)
    elif template == "sequence-gallery":
        _reject_fields(slide, index, ("meta",), "this component exposes page_note but not meta")
        _require_content(slide, index)
        if not _text(slide.get("conclusion")):
            raise SystemExit(f"Outline slide {index} template 'sequence-gallery' requires conclusion.")
        steps = _require_cards(slide, index, "steps", 3)
        _reject_nested_fields(
            steps, index, "steps",
            {"label", "title", "body", "image", "image_alt", "media_question", "media_source"},
            "sequence-gallery",
        )
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
        if variant == "line":
            _reject_fields(
                slide, index,
                ("content", "note", "meta", "aside", "aside_label", "artifact_title", "artifact_body"),
                "line renders only the closing title",
            )
        if variant == "line-note":
            copy_fields = [field for field in ("aside", "content", "note") if _text(slide.get(field))]
            if len(copy_fields) != 1:
                raise SystemExit(
                    f"Outline slide {index} end variant 'line-note' requires exactly one of aside, content, or note."
                )
            _reject_fields(slide, index, ("meta", "artifact_title", "artifact_body"), "line-note has no artifact or meta slots")
        if variant == "line-artifact":
            _reject_fields(slide, index, ("meta", "aside", "aside_label"), "line-artifact has no aside or meta slots")
            if _text(slide.get("content")) and _text(slide.get("note")):
                raise SystemExit(f"Outline slide {index} end variant 'line-artifact' accepts content or note, not both aliases.")
            if not image:
                raise SystemExit(f"Outline slide {index} end variant 'line-artifact' requires an image path.")
            for field in ("artifact_title", "artifact_body"):
                if not _text(slide.get(field)):
                    raise SystemExit(f"Outline slide {index} end variant 'line-artifact' requires {field}.")
    elif template == "three-steps":
        steps = _require_cards(slide, index, "steps", 3)
        _reject_nested_fields(steps, index, "steps", {"label", "title", "body"}, "three-steps")
    elif template == "timeline":
        steps = _require_cards(slide, index, "steps", 4)
        _reject_nested_fields(steps, index, "steps", {"label", "title", "body"}, "timeline")
    elif template == "process-rail":
        count = 6 if variant == "steps-6" else 8
        steps = _require_cards(slide, index, "steps", count, bodies=variant == "steps-6")
        allowed = {"label", "title", "body"} if variant == "steps-6" else {"label", "title"}
        _reject_nested_fields(steps, index, "steps", allowed, f"process-rail/{variant}")
    elif template == "process-cards":
        _reject_fields(slide, index, ("meta", "page_note"), "this component has no footer metadata slots")
        _require_content(slide, index)
        steps = _require_cards(slide, index, "steps", 4)
        _reject_nested_fields(
            steps, index, "steps", {"label", "title", "body", "icon"},
            f"process-cards/{variant}",
        )
        icon_count = sum(bool(isinstance(step, dict) and _text(step.get("icon"))) for step in steps)
        if icon_count not in {0, 4}:
            raise SystemExit(f"Outline slide {index} process-cards icons are all-or-none; found {icon_count}/4.")
        for step_index, step in enumerate(steps, start=1):
            if isinstance(step, dict):
                _require_icon(step.get("icon"), index, f"steps[{step_index}].icon")
        measurements = slide.get("measurements")
        if measurements is None and (slide.get("measurement_note") is not None or slide.get("measurement_meta") is not None):
            raise SystemExit(
                f"Outline slide {index} measurement_note/measurement_meta require measurements[4]."
            )
        if measurements is not None:
            _require_metrics({**slide, "metrics": measurements}, index, 4)
            if not _text(slide.get("measurement_note")) or not _text(slide.get("measurement_meta")):
                raise SystemExit(
                    f"Outline slide {index} measurements[4] require non-empty measurement_note and measurement_meta."
                )
    elif template == "quote":
        if not _text(slide.get("quote")) or not _text(slide.get("source")):
            raise SystemExit(f"Outline slide {index} template 'quote' requires quote and source.")
    elif template == "card-trio":
        cards = _require_cards(slide, index, "cards", 3)
        if variant == "media-evidence":
            _reject_fields(slide, index, ("meta", "page_note"), "this component has no footer metadata slots")
            _require_content(slide, index)
            for card_index, card in enumerate(cards[:2], start=1):
                if not isinstance(card, dict):
                    raise SystemExit(f"Outline slide {index} cards[{card_index}] must be an object for media-evidence.")
                _reject_object_fields(
                    card, index, f"cards[{card_index}]", {"label", "title", "body", "images"},
                    "card-trio/media-evidence evidence card",
                )
                _require_media_items(card.get("images"), index, f"cards[{card_index}].images", 2)
            _reject_object_fields(
                cards[2], index, "cards[3]", {"label", "title", "body", "backdrop"},
                "card-trio/media-evidence decision card",
            )
        else:
            _reject_nested_fields(
                cards, index, "cards", {"label", "title", "body"},
                f"card-trio/{variant}",
            )
            _reject_fields(slide, index, ("content", "note", "kicker", "meta", "page_note"), "feature variants show only the title and three cards")
    elif template == "recap":
        _require_content(slide, index)
        cards = _require_cards(slide, index, "cards", 3)
        _reject_nested_fields(cards, index, "cards", {"label", "title", "body"}, "recap")
    elif template == "comparison":
        _require_sides(slide, index, 2)
        sides = _items(slide, "sides")
        if variant == "visual-evidence":
            _reject_nested_fields(sides, index, "sides", {"label", "title", "lead", "points", "evidence"}, "comparison/visual-evidence")
            _reject_point_fields(sides, index, {"label", "title", "body"}, "comparison/visual-evidence")
            _reject_fields(slide, index, ("meta", "page_note"), "this component has no footer metadata slots")
            _require_content(slide, index)
            for side_index, side in enumerate(_items(slide, "sides"), start=1):
                if not isinstance(side, dict):
                    raise SystemExit(f"Outline slide {index} sides[{side_index}] must be an object for comparison visual-evidence.")
                _require_media_items(side.get("evidence"), index, f"sides[{side_index}].evidence", 2)
        else:
            _reject_nested_fields(sides, index, "sides", {"label", "title", "points"}, "comparison/default")
            _reject_point_fields(sides, index, {"body"}, "comparison/default")
            _reject_fields(slide, index, ("content", "note", "kicker", "meta", "page_note"), "the default comparison hides its intro block")
    elif template == "comparison-list":
        _require_sides(slide, index, 3)
        sides = _items(slide, "sides")
        _reject_nested_fields(sides, index, "sides", {"label", "title", "points"}, "comparison-list")
        _reject_point_fields(sides, index, {"body"}, "comparison-list")
    elif template == "tabs":
        sides = _items(slide, "sides")
        if len(sides) != 2 or any(not _label(side) or not _body(side) for side in sides):
            raise SystemExit(f"Outline slide {index} template 'tabs' requires 2 sides with title and body.")
        _reject_nested_fields(sides, index, "sides", {"label", "title", "body"}, "tabs")
    elif template == "metric":
        _require_content(slide, index)
        metric = slide.get("metric")
        if not isinstance(metric, dict) or any(not _text(metric.get(key)) for key in ("value", "unit", "caption")):
            raise SystemExit(f"Outline slide {index} template 'metric' requires metric.value, metric.unit and metric.caption.")
        hidden = sorted(set(metric) - {"value", "unit", "caption"})
        if hidden:
            raise SystemExit(f"Outline slide {index} metric field(s) {', '.join(hidden)} are not rendered.")
        _max_chars(metric.get("value"), index, "metric.value", 12)
        _max_chars(metric.get("unit"), index, "metric.unit", 8)
        _max_chars(metric.get("caption"), index, "metric.caption", 36)
    elif template == "converge":
        groups = _items(slide, "groups")
        if len(groups) != 2 or not _text(slide.get("outcome")):
            raise SystemExit(f"Outline slide {index} template 'converge' requires 2 groups and outcome.")
        _reject_nested_fields(groups, index, "groups", {"label", "title", "items"}, "converge")
        for group_index, group in enumerate(groups, start=1):
            values = group.get("items") if isinstance(group, dict) else None
            if not _label(group) or not isinstance(values, list) or len(values) != 2 or any(not isinstance(v, str) or not v.strip() for v in values):
                raise SystemExit(f"Outline slide {index} groups[{group_index}] requires title and exactly 2 items.")


def validate_outline(data: dict, templates_dir: Path) -> list[dict]:
    if not isinstance(data, dict):
        raise SystemExit("Outline JSON must contain an object at the top level.")
    unknown_deck = sorted(set(data) - DECK_ALLOWED_FIELDS)
    if unknown_deck:
        raise SystemExit(f"Outline has unknown deck field(s): {', '.join(unknown_deck)}.")
    if not _text(data.get("title")):
        raise SystemExit("Outline requires a title.")
    palette = data.get("palette")
    if isinstance(palette, str):
        if canonical_name(palette) not in PALETTES:
            raise SystemExit(f"Outline palette must be one of: {', '.join(sorted(PALETTES))}.")
    elif isinstance(palette, dict):
        if data.get("palette_source") not in {"user", "brand"}:
            raise SystemExit("A custom palette requires palette_source 'user' or 'brand'.")
        unknown_tokens = sorted(set(palette) - {*TOKEN_KEYS, "name"})
        if unknown_tokens:
            raise SystemExit(f"Custom palette has unknown token(s): {', '.join(unknown_tokens)}.")
        if palette.get("name") not in {None, "custom"}:
            raise SystemExit("Custom palette name, when provided, must be 'custom'.")
        try:
            normalize_palette(palette)
        except ValueError as error:
            raise SystemExit(f"Invalid custom palette: {error}") from error
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
        unknown_slide = sorted(set(slide) - SLIDE_ALLOWED_FIELDS)
        if unknown_slide:
            raise SystemExit(f"Outline slide {index} has unknown field(s): {', '.join(unknown_slide)}.")
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
        visible_fields = BASE_VISIBLE_FIELDS | set(TEMPLATE_VISIBLE_FIELDS[template])
        hidden_fields = sorted(set(slide) - visible_fields)
        if hidden_fields:
            raise SystemExit(
                f"Outline slide {index} field(s) {', '.join(hidden_fields)} are not consumed by template {template!r}. "
                "Remove them or choose a component whose contract exposes those fields."
            )
        normalize_component_choices(slide, index)
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
        bindings = _validate_media_contract(slide, index)
        if data.get("media_policy", "required") == "text-only" and bindings:
            fields = ", ".join(field for field, _ in bindings)
            raise SystemExit(
                f"Outline slide {index} declares media ({fields}) while deck media_policy is 'text-only'. "
                "Remove the media or change the confirmed deck policy."
            )
        for field, allowed in (
            ("media_fit", {"cover", "contain"}),
            ("media_position", {"center", "left", "right", "top", "bottom", "top-left", "top-right", "bottom-left", "bottom-right"}),
            ("media_treatment", {"natural", "muted", "mono"}),
            ("media_surface", {"component", "page-blend"}),
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
        for field in ("image_alt", "secondary_image_alt"):
            if slide.get(field) is not None and not isinstance(slide[field], str):
                raise SystemExit(f"Outline slide {index} {field} must be a string when provided.")
        validate_slide_content(slide, index)
        ids.add(slide_id)
    return slides
