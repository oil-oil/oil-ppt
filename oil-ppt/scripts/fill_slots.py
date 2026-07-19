#!/usr/bin/env python3
"""Fill template content slots from outline slide fields."""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

from background_presets import effective_background
from component_contracts import effective_media_fit, effective_media_surface
from component_registry import DATA_STORY_QUESTIONS
from editor_bindings import annotate_editable_fragment
from fill_templates import format_number, render_data_story
from icon_registry import CONNECTOR_ICON, icon_svg_markup
from media_assets import outline_media_bindings


MEDIA_FIT_DEFAULTS = {
    "artifact-focus": "contain",
    "cover": "cover",
    "end": "contain",
    "split-visual": "contain",
    "browser-showcase": "contain",
    "editorial-canvas": "contain",
    "step-hero": "contain",
}

AUTO_BACKDROP_TEMPLATES = {"cover", "section", "end"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--outline", type=Path, help="defaults to project/outline.json")
    return parser.parse_args()


def esc(value: str) -> str:
    return html.escape(str(value), quote=False)


def display_value(value: object) -> str:
    return "" if value is None else str(value)


def set_slot_text(fragment: str, slot: str, value: str | None) -> str:
    if value is None or str(value).strip() == "":
        return fragment
    pattern = re.compile(
        rf'(data-slot="{re.escape(slot)}"[^>]*>)(.*?)(</)',
        re.I | re.S,
    )
    return pattern.sub(lambda match: match.group(1) + esc(value) + match.group(3), fragment, count=1)


def set_slot_text_force(fragment: str, slot: str, value: str | None) -> str:
    pattern = re.compile(
        rf'(data-slot="{re.escape(slot)}"[^>]*>)(.*?)(</)',
        re.I | re.S,
    )
    return pattern.sub(lambda match: match.group(1) + esc(value or "") + match.group(3), fragment, count=1)


def set_slot_text_all(fragment: str, slot: str, value: str | None) -> str:
    """Fill every rendering of a semantic slot.

    Some variants keep the same semantic field in separate DOM branches so CSS
    can switch layouts without the model authoring duplicate content.
    """
    pattern = re.compile(
        rf'(data-slot="{re.escape(slot)}"[^>]*>)(.*?)(</)',
        re.I | re.S,
    )
    return pattern.sub(lambda match: match.group(1) + esc(value or "") + match.group(3), fragment)


def set_slot_html_force(fragment: str, slot: str, value: str | None) -> str:
    pattern = re.compile(
        rf'(data-slot="{re.escape(slot)}"[^>]*>)(.*?)(</)',
        re.I | re.S,
    )
    return pattern.sub(lambda match: match.group(1) + str(value or "") + match.group(3), fragment, count=1)


def mark_slot_fit(fragment: str, slot: str, minimum: int) -> str:
    pattern = re.compile(
        rf'<(?P<tag>[a-z][a-z0-9]*)\b(?P<attrs>[^>]*data-slot="{re.escape(slot)}"[^>]*)>',
        re.I,
    )

    def add(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        if not re.search(r"\bdata-fit\b", attrs, re.I):
            attrs += " data-fit"
        if not re.search(r"\bdata-min-size=", attrs, re.I):
            attrs += f' data-min-size="{minimum}"'
        return f'<{match.group("tag")}{attrs}>'

    return pattern.sub(add, fragment)


def fill_icon_slot(fragment: str, slot: str, name: object) -> str:
    pattern = re.compile(
        rf'<span\b(?=[^>]*data-slot="{re.escape(slot)}")[^>]*>.*?</span>',
        re.I | re.S,
    )
    icon = icon_svg_markup(str(name or "").strip()) if name else ""
    if not icon:
        return pattern.sub("", fragment, count=1)
    return pattern.sub(lambda match: re.sub(r">.*?</span>$", lambda _: f">{icon}</span>", match.group(0), flags=re.I | re.S), fragment, count=1)


def project_media_src(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return raw if raw.startswith(("../", "data:", "#")) else f"../{raw.lstrip('./')}"


def fill_common_slots(fragment: str, slide: dict) -> str:
    values = {
        "kicker": slide.get("kicker"),
        "content": slide.get("content") or slide.get("note"),
        "meta": slide.get("meta"),
        "page-note": slide.get("page_note"),
    }
    for slot, value in values.items():
        fragment = set_slot_text_force(fragment, slot, str(value or ""))
    return fragment


def replace_nth_h2(fragment: str, index: int, value: str) -> str:
    matches = list(re.finditer(r"(<h2\b[^>]*>)(.*?)(</h2>)", fragment, re.I | re.S))
    if index >= len(matches):
        return fragment
    m = matches[index]
    return fragment[: m.start()] + m.group(1) + esc(value) + m.group(3) + fragment[m.end() :]


def replace_nth(fragment: str, pattern: str, index: int, value: object) -> str:
    matches = list(re.finditer(pattern, fragment, re.I | re.S))
    if index >= len(matches):
        return fragment
    match = matches[index]
    return fragment[:match.start()] + match.group(1) + esc(str(value)) + match.group(3) + fragment[match.end():]


def replace_step_block(fragment: str, step_index: int, label: str | None, body: str | None) -> str:
    """three-steps / timeline style: article blocks with h2 + p."""
    articles = list(re.finditer(r"(<article\b[^>]*>)(.*?)(</article>)", fragment, re.I | re.S))
    if step_index >= len(articles):
        return fragment
    art = articles[step_index]
    inner = art.group(2)
    if label is not None and str(label).strip() != "":
        inner = re.sub(r"(<h2\b[^>]*>)(.*?)(</h2>)", lambda match: match.group(1) + esc(label) + match.group(3), inner, count=1, flags=re.I | re.S)
    if body is not None and str(body).strip() != "":
        inner = re.sub(r"(<p\b[^>]*>)(.*?)(</p>)", lambda match: match.group(1) + esc(body) + match.group(3), inner, count=1, flags=re.I | re.S)
    return fragment[: art.start()] + art.group(1) + inner + art.group(3) + fragment[art.end() :]


def set_visual_image(fragment: str, src: str, alt: str = "") -> str:
    if not src:
        return fragment
    project_relative = src if src.startswith(("../", "data:", "#")) else f"../{src.lstrip('./')}"
    img = f'<img class="oil-stock-visual" src="{html.escape(project_relative, quote=True)}" alt="{html.escape(alt or "", quote=True)}">'
    # cover media uses oil-stock-visual; end artifact plain img; generic main visual
    if re.search(r"<!-- OIL-VISUAL:main:START -->.*?<!-- OIL-VISUAL:main:END -->", fragment, re.I | re.S):
        return re.sub(
            r"<!-- OIL-VISUAL:main:START -->.*?<!-- OIL-VISUAL:main:END -->",
            lambda _: f"<!-- OIL-VISUAL:main:START -->{img}<!-- OIL-VISUAL:main:END -->",
            fragment,
            count=1,
            flags=re.I | re.S,
        )
    return fragment


def effective_backdrop_text(slide: dict) -> str:
    """Return content-owned background type without adding a model decision."""
    explicit = str(slide.get("backdrop_text") or "").strip()
    if explicit:
        return explicit
    if str(slide.get("template") or "") not in AUTO_BACKDROP_TEMPLATES:
        return ""
    highlight = str(slide.get("highlight") or "").strip()
    if not highlight or len(re.sub(r"\s+", "", highlight)) > 12:
        return ""
    return highlight


def inject_backdrop_text(fragment: str, slide: dict) -> str:
    value = effective_backdrop_text(slide)
    if not value:
        return fragment
    markup = f'<div class="oil-backdrop-text" aria-hidden="true">{esc(value)}</div>'
    return re.sub(r"(<section\b[^>]*>)", lambda match: match.group(1) + markup, fragment, count=1, flags=re.I)


def apply_media_attributes(fragment: str, slide: dict) -> str:
    if not outline_media_bindings(slide):
        return fragment
    fit = effective_media_fit(
        slide,
        fallback=MEDIA_FIT_DEFAULTS.get(str(slide.get("template") or ""), "cover"),
    )
    position = str(slide.get("media_position") or "center")
    treatment = str(slide.get("media_treatment") or "natural")
    surface = effective_media_surface(slide)
    template = str(slide.get("template") or "")
    variant = str(slide.get("variant") or "default")
    pattern = re.compile(r'<(?P<tag>[a-z][a-z0-9]*)\b(?P<attrs>[^>]*\bclass="[^"]*\boil-media\b[^"]*"[^>]*)>', re.I)
    if not pattern.search(fragment):
        raise SystemExit(f"Media template {slide.get('template')!r} has no standard oil-media container.")

    def add_attributes(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        for name, value in (("data-media-fit", fit), ("data-media-position", position), ("data-media-treatment", treatment), ("data-media-surface", surface)):
            if re.search(rf"\b{re.escape(name)}=", attrs, re.I):
                attrs = re.sub(
                    rf'({re.escape(name)}=["\'])[^"\']+(["\'])',
                    lambda item: item.group(1) + value + item.group(2), attrs, count=1, flags=re.I,
                )
            else:
                attrs += f' {name}="{html.escape(value, quote=True)}"'
        if template in {"bleed-split", "diagonal-split"}:
            side = "left" if variant == "media-left" else "right"
            if re.search(r"\bdata-side=", attrs, re.I):
                attrs = re.sub(
                    r'(data-side=["\'])[^"\']+(["\'])',
                    lambda item: item.group(1) + side + item.group(2), attrs, count=1, flags=re.I,
                )
            else:
                attrs += f' data-side="{side}"'
        return f'<{match.group("tag")}{attrs}>'

    return pattern.sub(add_attributes, fragment)


def fill_connectors(fragment: str) -> str:
    svg = icon_svg_markup(CONNECTOR_ICON)
    if not svg:
        return fragment
    return re.sub(
        r'(data-slot="connector"[^>]*>)(.*?)(</span>)',
        lambda match: match.group(1) + svg + match.group(3),
        fragment,
        flags=re.I | re.S,
    )


def _fill_flow_steps(fragment: str, slide: dict, limit: int, *, with_connectors: bool) -> str:
    steps = slide.get("steps")
    if not isinstance(steps, list):
        if with_connectors:
            fragment = fill_connectors(fragment)
        return fragment
    for i, item in enumerate(steps[:limit]):
        if isinstance(item, str):
            fragment = replace_step_block(fragment, i, item, None)
        elif isinstance(item, dict):
            label = item.get("label") or item.get("title") or item.get("h2")
            body = item.get("body") or item.get("text") or item.get("p")
            fragment = replace_step_block(fragment, i, label, body)
        else:
            continue
    if with_connectors:
        fragment = fill_connectors(fragment)
    return fragment


def fill_three_steps(fragment: str, slide: dict) -> str:
    return _fill_flow_steps(fragment, slide, 3, with_connectors=True)


def fill_timeline(fragment: str, slide: dict) -> str:
    return _fill_flow_steps(fragment, slide, 4, with_connectors=False)


def fill_process_rail(fragment: str, slide: dict) -> str:
    steps = slide.get("steps")
    if isinstance(steps, list):
        for i, item in enumerate(steps[:8]):
            label = item if isinstance(item, str) else (item.get("label") or item.get("title"))
            body = None if isinstance(item, str) else (item.get("body") or item.get("text") or item.get("p"))
            fragment = replace_step_block(fragment, i, label, body)
    fragment = fill_connectors(fragment)
    return fragment


def fill_quote(fragment: str, slide: dict) -> str:
    fragment = replace_nth(
        fragment,
        r'(<p\b[^>]*class="[^"]*\bquote-text\b[^"]*"[^>]*>)(.*?)(</p>)',
        0,
        slide.get("quote", ""),
    )
    return replace_nth(
        fragment,
        r'(<cite\b[^>]*class="[^"]*\bsource\b[^"]*"[^>]*>)(.*?)(</cite>)',
        0,
        slide.get("source", ""),
    )


def fill_card_trio(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    cards = slide.get("cards")
    if not isinstance(cards, list):
        return fragment
    for i, item in enumerate(cards[:3]):
        if isinstance(item, str):
            fragment = replace_step_block(fragment, i, item, None)
        elif isinstance(item, dict):
            fragment = replace_step_block(
                fragment,
                i,
                item.get("label") or item.get("title") or item.get("h2"),
                item.get("body") or item.get("text") or item.get("p"),
            )
            index = i + 1
            title = item.get("label") or item.get("title") or item.get("h2") or ""
            body = item.get("body") or item.get("text") or item.get("p") or ""
            fragment = set_slot_text_all(fragment, f"card-title-{index}", str(title))
            fragment = set_slot_text_all(fragment, f"card-body-{index}", str(body))
            if index == 3:
                backdrop = str(item.get("backdrop") or re.sub(r"\s+", "", str(title))[:4])
                fragment = re.sub(
                    r'data-backdrop="[^"]*"',
                    lambda _: f'data-backdrop="{html.escape(backdrop, quote=True)}"',
                    fragment,
                    count=1,
                )
            for image_index, evidence in enumerate((item.get("images") or [])[:2], start=1):
                if isinstance(evidence, dict):
                    value = evidence.get("image")
                    caption = evidence.get("caption") or evidence.get("label") or ""
                    alt = evidence.get("alt") or caption or title
                else:
                    value = evidence
                    caption = ""
                    alt = title
                src = project_media_src(value)
                markup = (
                    f'<img src="{html.escape(src, quote=True)}" '
                    f'alt="{html.escape(str(alt or ""), quote=True)}">'
                    if src else ""
                )
                fragment = set_slot_html_force(fragment, f"card-image-{index}-{image_index}", markup)
                fragment = set_slot_text_force(fragment, f"card-caption-{index}-{image_index}", str(caption))
    if slide.get("variant") == "media-evidence":
        for index in range(1, 4):
            fragment = mark_slot_fit(fragment, f"card-title-{index}", 32)
            fragment = mark_slot_fit(fragment, f"card-body-{index}", 20)
    return fragment


def fill_comparison(fragment: str, slide: dict) -> str:
    sides = slide.get("sides")
    if not isinstance(sides, list) or len(sides) < 2:
        return fragment
    fragment = fill_common_slots(fragment, slide)
    if slide.get("template") == "comparison":
        for side_index, side in enumerate(sides[:2], start=1):
            if not isinstance(side, dict):
                continue
            title = side.get("title") or side.get("label") or side.get("h2") or ""
            fragment = set_slot_text_all(fragment, f"side-title-{side_index}", str(title))
            fragment = set_slot_text_force(fragment, f"side-lead-{side_index}", str(side.get("lead") or ""))
            for point_index, point in enumerate((side.get("points") or [])[:2], start=1):
                if isinstance(point, dict):
                    point_title = point.get("title") or point.get("label") or ""
                    point_body = point.get("body") or point.get("text") or ""
                else:
                    point_title = ""
                    point_body = point
                fragment = set_slot_text_force(fragment, f"point-title-{side_index}-{point_index}", str(point_title))
                fragment = set_slot_text_all(fragment, f"point-body-{side_index}-{point_index}", str(point_body or ""))
            for evidence_index, evidence in enumerate((side.get("evidence") or [])[:2], start=1):
                if isinstance(evidence, dict):
                    value = evidence.get("image")
                    caption = evidence.get("caption") or evidence.get("label") or ""
                    alt = evidence.get("alt") or caption or title
                else:
                    value = evidence
                    caption = ""
                    alt = title
                src = project_media_src(value)
                markup = (
                    f'<img src="{html.escape(src, quote=True)}" '
                    f'alt="{html.escape(str(alt or ""), quote=True)}">'
                    if src else ""
                )
                fragment = set_slot_html_force(fragment, f"evidence-{side_index}-{evidence_index}", markup)
                fragment = set_slot_text_force(fragment, f"evidence-caption-{side_index}-{evidence_index}", str(caption))
        return fragment
    # comparison: two articles .side with h2 + p.point
    articles = list(re.finditer(r"(<article\b[^>]*>)(.*?)(</article>)", fragment, re.I | re.S))
    for i, side in enumerate(sides[:2]):
        if i >= len(articles):
            break
        art = articles[i]
        inner = art.group(2)
        if isinstance(side, dict):
            title = side.get("title") or side.get("label") or side.get("h2")
            points = side.get("points") or []
            if title:
                inner = re.sub(r"(<h2\b[^>]*>)(.*?)(</h2>)", lambda match: match.group(1) + esc(title) + match.group(3), inner, count=1, flags=re.I | re.S)
            if isinstance(points, list):
                point_matches = list(re.finditer(r"(<p\b[^>]*class=\"[^\"]*point[^\"]*\"[^>]*>)(.*?)(</p>)", inner, re.I | re.S))
                if not point_matches:
                    point_matches = list(re.finditer(r"(<p\b[^>]*>)(.*?)(</p>)", inner, re.I | re.S))
                for j, pt in enumerate(points):
                    if j >= len(point_matches):
                        break
                    text = pt if isinstance(pt, str) else (pt.get("text") or pt.get("body") or "")
                    if not text:
                        continue
                    m = point_matches[j]
                    inner = inner[: m.start()] + m.group(1) + esc(str(text)) + m.group(3) + inner[m.end() :]
                    point_matches = list(re.finditer(r"(<p\b[^>]*class=\"[^\"]*point[^\"]*\"[^>]*>)(.*?)(</p>)", inner, re.I | re.S))
                    if not point_matches:
                        point_matches = list(re.finditer(r"(<p\b[^>]*>)(.*?)(</p>)", inner, re.I | re.S))
        art_html = art.group(1) + inner + art.group(3)
        fragment = fragment[: art.start()] + art_html + fragment[art.end() :]
        # re-find articles after mutation
        articles = list(re.finditer(r"(<article\b[^>]*>)(.*?)(</article>)", fragment, re.I | re.S))
    return fragment


def fill_cover(fragment: str, slide: dict) -> str:
    kicker = slide.get("kicker")
    note = slide.get("note") or slide.get("content")
    fragment = set_slot_text_force(fragment, "kicker", str(kicker or ""))
    fragment = set_slot_text_force(fragment, "note", str(note or ""))
    image = slide.get("image") or slide.get("media")
    if image:
        fragment = set_visual_image(fragment, str(image), str(slide.get("image_alt") or slide.get("title") or ""))
    return fragment


def fill_end(fragment: str, slide: dict) -> str:
    note = slide.get("note") or slide.get("content")
    meta = slide.get("meta")
    aside = slide.get("aside") or (note if slide.get("variant") == "line-note" else None)
    aside_label = slide.get("aside_label")
    for slot in ("note", "meta", "aside", "aside-label", "artifact-title", "artifact-body"):
        fragment = set_slot_text_force(fragment, slot, "")
    if note:
        fragment = set_slot_text_force(fragment, "note", str(note))
        # also lead on line-artifact
        fragment = re.sub(
            r'(class="lead"[^>]*data-slot="note"[^>]*>)(.*?)(</p>)',
            lambda match: match.group(1) + esc(str(note)) + match.group(3),
            fragment,
            count=1,
            flags=re.I | re.S,
        )
    if meta:
        fragment = set_slot_text_force(fragment, "meta", str(meta))
    if aside:
        fragment = set_slot_text_force(fragment, "aside", str(aside))
    if aside_label:
        fragment = set_slot_text_force(fragment, "aside-label", str(aside_label))
    image = slide.get("image") or slide.get("artifact_image")
    if image:
        fragment = set_visual_image(fragment, str(image), str(slide.get("image_alt") or ""))
        # artifact may prefer non stock class
        fragment = fragment.replace('class="oil-stock-visual"', 'class=""', 1)
    title = slide.get("artifact_title")
    body = slide.get("artifact_body")
    if title:
        fragment = set_slot_text_force(fragment, "artifact-title", str(title))
    if body:
        fragment = set_slot_text_force(fragment, "artifact-body", str(body))
    return fragment


def fill_metric(fragment: str, slide: dict) -> str:
    fragment = fill_split_like(fragment, slide)
    metric = slide.get("metric") or {}
    for class_name, key in (("value", "value"), ("unit", "unit"), ("caption", "caption")):
        fragment = replace_nth(
            fragment,
            rf'(<[^>]+class="[^"]*\b{class_name}\b[^"]*"[^>]*>)(.*?)(</[^>]+>)',
            0,
            metric.get(key, ""),
        )
    fragment = set_slot_text_force(fragment, "metric-change", display_value(metric.get("change")))
    fragment = set_slot_text_force(fragment, "metric-change-label", str(metric.get("change_label") or ""))
    fragment = set_slot_text_force(fragment, "metric-target", display_value(metric.get("target")))
    if slide.get("variant") == "progress":
        value = float(metric["value"])
        target = float(metric["target"])
        percentage = value / target * 100
        fragment = set_slot_text_force(
            fragment,
            "metric-progress-label",
            f"{format_number(percentage, precision=1)}%",
        )
        clamped = max(0.0, min(100.0, percentage))
        fragment = re.sub(
            r'(<rect\b[^>]*\bdata-progress-fill\b[^>]*\bwidth=")[^"]*(")',
            lambda match: match.group(1) + f"{clamped:.2f}" + match.group(2),
            fragment,
            count=1,
            flags=re.I,
        )
    return fragment


def fill_recap(fragment: str, slide: dict) -> str:
    fragment = fill_split_like(fragment, slide)
    clone = dict(slide)
    clone["cards"] = slide.get("cards") or []
    return fill_card_trio(fragment, clone)


def fill_tabs(fragment: str, slide: dict) -> str:
    sides = slide.get("sides") or []
    for index, side in enumerate(sides[:2]):
        title = side.get("title") or side.get("label")
        body = side.get("body") or side.get("text")
        fragment = replace_nth(fragment, r'(<button\b[^>]*data-tab="[^"]+"[^>]*>)(.*?)(</button>)', index, title)
        fragment = replace_nth(fragment, r'(<h2\b[^>]*>)(.*?)(</h2>)', index, title)
        fragment = replace_nth(fragment, r'(<p\b[^>]*>)(.*?)(</p>)', index, body)
    return fragment


def fill_converge(fragment: str, slide: dict) -> str:
    groups = slide.get("groups") or []
    item_index = 0
    for group_index, group in enumerate(groups[:2]):
        title = group.get("title") or group.get("label")
        fragment = replace_nth(fragment, r'(<h2\b[^>]*>)(.*?)(</h2>)', group_index, title)
        for item in (group.get("items") or [])[:2]:
            fragment = replace_nth(fragment, r'(<div\b[^>]*class="[^"]*\bitem\b[^"]*"[^>]*>)(.*?)(</div>)', item_index, item)
            item_index += 1
    return replace_nth(fragment, r'(<div\b[^>]*class="[^"]*\boutcome\b[^"]*"[^>]*>)(.*?)(</div>)', 0, slide.get("outcome"))


def _fill_relationship_steps(fragment: str, slide: dict) -> str:
    for index, step in enumerate((slide.get("steps") or [])[:4], start=1):
        if not isinstance(step, dict):
            continue
        fragment = set_slot_text_force(fragment, f"step-title-{index}", str(step.get("title") or step.get("label") or ""))
        fragment = set_slot_text_force(fragment, f"step-body-{index}", str(step.get("body") or step.get("text") or ""))
    return fragment


def fill_cycle(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    fragment = set_slot_text_force(fragment, "statement", str(slide.get("statement") or ""))
    fragment = set_slot_text_force(fragment, "statement-body", str(slide.get("statement_body") or ""))
    return _fill_relationship_steps(fragment, slide)


def fill_quadrant(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    axes = slide.get("axes") or {}
    fragment = set_slot_text_force(fragment, "axis-x", str(axes.get("x") or ""))
    fragment = set_slot_text_force(fragment, "axis-y", str(axes.get("y") or ""))
    for group_index, group in enumerate((slide.get("groups") or [])[:4], start=1):
        if not isinstance(group, dict):
            continue
        fragment = set_slot_text_force(fragment, f"group-title-{group_index}", str(group.get("title") or group.get("label") or ""))
        fragment = set_slot_text_force(fragment, f"group-meta-{group_index}", str(group.get("meta") or ""))
        items = "".join(
            f'<span class="quadrant-item" data-slot="group-item-{group_index}-{item_index}" data-fit data-min-size="16">{esc(str(item))}</span>'
            for item_index, item in enumerate((group.get("items") or [])[:3], start=1)
        )
        fragment = set_slot_html_force(fragment, f"group-items-{group_index}", items)
        if group.get("emphasis") is True:
            fragment = fragment.replace(
                f'data-quadrant="{group_index}"',
                f'data-quadrant="{group_index}" data-emphasis="true"',
                1,
            )
    return fragment


def fill_tier_stack(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    return _fill_relationship_steps(fragment, slide)


def _relationship_positions(count: int) -> list[tuple[float, float]]:
    positions = {
        3: [(0.18, 0.19), (0.82, 0.19), (0.50, 0.82)],
        4: [(0.16, 0.18), (0.84, 0.18), (0.84, 0.80), (0.16, 0.80)],
        5: [(0.50, 0.11), (0.84, 0.31), (0.72, 0.82), (0.28, 0.82), (0.16, 0.31)],
    }
    return positions[count]


def _rect_edge(
    source: tuple[float, float], target: tuple[float, float], *, half_width: float, half_height: float,
) -> tuple[float, float]:
    dx = target[0] - source[0]
    dy = target[1] - source[1]
    scales = [
        half_width / abs(dx) if dx else float("inf"),
        half_height / abs(dy) if dy else float("inf"),
    ]
    scale = min(scales)
    return source[0] + dx * scale, source[1] + dy * scale


def _arrowhead_points(
    source: tuple[float, float], target: tuple[float, float], *, length: float = 22, half_width: float = 11,
) -> str:
    dx = target[0] - source[0]
    dy = target[1] - source[1]
    distance = (dx * dx + dy * dy) ** 0.5
    unit_x, unit_y = dx / distance, dy / distance
    base_x = target[0] - unit_x * length
    base_y = target[1] - unit_y * length
    perpendicular_x, perpendicular_y = -unit_y, unit_x
    left = (base_x + perpendicular_x * half_width, base_y + perpendicular_y * half_width)
    right = (base_x - perpendicular_x * half_width, base_y - perpendicular_y * half_width)
    return " ".join(
        f"{x:.1f},{y:.1f}"
        for x, y in (target, left, right)
    )


def fill_relationship_map(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    nodes = [node for node in (slide.get("nodes") or []) if isinstance(node, dict)]
    center = next(node for node in nodes if node.get("emphasis") is True)
    peripherals = [node for node in nodes if node is not center]
    ordered = [center, *peripherals]
    fragment = fragment.replace(
        'class="relationship-canvas" data-layout',
        f'class="relationship-canvas" data-peripheral-count="{len(peripherals)}" data-layout',
        1,
    )
    width, height = 1760.0, 718.0
    positions: dict[str, tuple[float, float]] = {str(center["id"]): (width / 2, height / 2)}
    for node, (x_ratio, y_ratio) in zip(peripherals, _relationship_positions(len(peripherals))):
        positions[str(node["id"])] = (width * x_ratio, height * y_ratio)

    node_markup: list[str] = []
    original_indexes = {str(node["id"]): index for index, node in enumerate(nodes, start=1)}
    for display_index, node in enumerate(ordered):
        node_id = str(node["id"])
        original_index = original_indexes[node_id]
        role = "center" if node is center else "peripheral"
        position = "center" if role == "center" else str(display_index)
        tone = "soft" if role == "center" else "neutral"
        index_label = "CORE" if role == "center" else f"{display_index:02d}"
        node_markup.append(
            f'<article class="relationship-node oil-surface" data-tone="{tone}" '
            f'data-node-role="{role}" data-node-id="{html.escape(node_id, quote=True)}" '
            f'data-node-position="{position}" data-visual-node data-bound>'
            f'<span class="node-index" data-small-ok>{index_label}</span>'
            f'<h2 data-slot="node-title-{original_index}" data-fit data-min-size="25">{esc(str(node["title"]))}</h2>'
            f'<p data-slot="node-body-{original_index}" data-sentence data-fit data-min-size="17">{esc(str(node["body"]))}</p>'
            f'</article>'
        )
    fragment = set_slot_html_force(fragment, "relationship-nodes", "".join(node_markup))

    link_markup: list[str] = []
    for link_index, link in enumerate(slide.get("links") or [], start=1):
        source_id = str(link["source"])
        target_id = str(link["target"])
        source_center = positions[source_id]
        target_center = positions[target_id]
        source_is_center = source_id == str(center["id"])
        target_is_center = target_id == str(center["id"])
        start = _rect_edge(
            source_center, target_center,
            half_width=213 if source_is_center else 184,
            half_height=114,
        )
        end_from_target = _rect_edge(
            target_center, source_center,
            half_width=213 if target_is_center else 184,
            half_height=114,
        )
        midpoint = ((start[0] + end_from_target[0]) / 2, (start[1] + end_from_target[1]) / 2)
        label = str(link["label"])
        label_width = min(196, max(76, len(re.sub(r"\s+", "", label)) * 20 + 32))
        link_markup.append(
            f'<line class="relationship-link" data-visual-edge x1="{start[0]:.1f}" y1="{start[1]:.1f}" '
            f'x2="{end_from_target[0]:.1f}" y2="{end_from_target[1]:.1f}"/>'
            f'<polygon class="relationship-arrow" data-relationship-arrow="{link_index}" '
            f'points="{_arrowhead_points(start, end_from_target)}"/>'
        )
        label_x = midpoint[0] - label_width / 2
        label_y = midpoint[1] - 20
        link_markup.append(
            f'<g class="relationship-label" aria-hidden="true">'
            f'<rect x="{label_x:.1f}" y="{label_y:.1f}" width="{label_width}" height="40" rx="20"/>'
            f'<text x="{midpoint[0]:.1f}" y="{midpoint[1] + 1:.1f}" data-slot="link-label-{link_index}" '
            f'data-overflow-ok data-small-ok>{esc(label)}</text></g>'
        )
    fragment = set_slot_html_force(fragment, "relationship-links", "".join(link_markup))
    return fragment


def fill_decision_matrix(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    fragment = set_slot_text_force(fragment, "source", str(slide.get("source") or ""))
    criteria = slide.get("criteria") or []
    head = ['<span data-small-ok>候选方案</span>']
    head.extend(
        f'<span data-slot="criterion-{index}" data-fit data-min-size="16">{esc(str(criterion))}</span>'
        for index, criterion in enumerate(criteria, start=1)
    )
    head.append('<span data-small-ok>总分 / 15</span>')
    fragment = set_slot_html_force(fragment, "decision-head", "".join(head))

    options = slide.get("options") or []
    totals = [sum(option["scores"]) for option in options]
    recommended = totals.index(max(totals))
    rows: list[str] = []
    for option_index, (option, total) in enumerate(zip(options, totals), start=1):
        is_recommended = option_index - 1 == recommended
        status = "推荐" if is_recommended else f"候选 {option_index:02d}"
        tone = "soft" if is_recommended else "neutral"
        scores = "".join(
            f'<span class="criterion-score" data-score="{score}" aria-label="{score} / 5">'
            f'<b>{score}</b><small>/5</small></span>'
            for score in option["scores"]
        )
        rows.append(
            f'<article class="decision-row oil-surface" data-tone="{tone}" data-visual-node data-bound '
            f'data-recommended="{str(is_recommended).lower()}"><div>'
            f'<h2 data-slot="option-title-{option_index}" data-fit data-min-size="23">{esc(str(option["title"]))}</h2>'
            f'<p data-small-ok>{status}</p></div>{scores}'
            f'<strong class="total-score">{total}<small>/15</small></strong></article>'
        )
    return set_slot_html_force(fragment, "decision-rows", "".join(rows))


def fill_evidence_matrix(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    claims = slide.get("claims") or []
    evidence = slide.get("evidence") or []
    fragment = fragment.replace(
        'class="evidence-matrix" data-layout',
        f'class="evidence-matrix" data-claim-count="{len(claims)}" data-evidence-count="{len(evidence)}" data-layout',
        1,
    )
    head = ['<span class="source-heading" data-small-ok>证据 / 来源</span>']
    head.extend(
        f'<span class="claim-heading" data-slot="claim-title-{claim_index}" data-fit data-min-size="16">'
        f'{esc(str(claim["title"]))}</span>'
        for claim_index, claim in enumerate(claims, start=1)
    )
    fragment = set_slot_html_force(fragment, "evidence-head", "".join(head))
    rows: list[str] = []
    claim_index_by_id = {str(claim["id"]): index for index, claim in enumerate(claims, start=1)}
    labels = {"supports": "支持", "challenges": "质疑", "context": "语境"}
    for evidence_index, item in enumerate(evidence, start=1):
        relation_by_claim = {str(link["claim"]): str(link["relation"]) for link in item["links"]}
        source = item["source"]
        note = item.get("note")
        note_markup = (
            f'<p class="evidence-note" data-slot="evidence-note-{evidence_index}" data-fit data-min-size="14">'
            f'{esc(str(note))}</p>' if note else ""
        )
        cells = []
        for claim in claims:
            relation = relation_by_claim.get(str(claim["id"]))
            if relation:
                cells.append(
                    f'<span class="relation relation-{relation}" aria-label="{labels[relation]}" '
                    f'data-claim-column="{claim_index_by_id[str(claim["id"])]}">'
                    f'<b aria-hidden="true"></b><small>{labels[relation]}</small></span>'
                )
            else:
                cells.append('<span class="relation relation-none" aria-label="无直接关系"><b aria-hidden="true"></b></span>')
        rows.append(
            f'<article class="evidence-row oil-surface" data-tone="neutral" data-visual-node data-bound>'
            f'<div class="evidence-copy"><h2 data-slot="evidence-title-{evidence_index}" data-fit data-min-size="18">'
            f'{esc(str(item["title"]))}</h2>{note_markup}'
            f'<a class="evidence-source" href="{html.escape(str(source["url"]), quote=True)}" '
            f'data-slot="evidence-source-{evidence_index}" data-fit data-min-size="13">{esc(str(source["label"]))}</a></div>'
            f'{"".join(cells)}</article>'
        )
    return set_slot_html_force(fragment, "evidence-rows", "".join(rows))


def fill_gantt_roadmap(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    periods = slide.get("periods") or []
    lanes = slide.get("lanes") or []
    period_index = {str(period["id"]): index for index, period in enumerate(periods)}
    fragment = fragment.replace(
        'class="gantt-roadmap" data-layout',
        f'class="gantt-roadmap" data-period-count="{len(periods)}" data-lane-count="{len(lanes)}" data-layout',
        1,
    )
    axis = '<span class="lane-axis-label" data-small-ok>工作泳道</span>' + "".join(
        f'<span data-slot="period-label-{index}" data-fit data-min-size="14">{esc(str(period["label"]))}</span>'
        for index, period in enumerate(periods, start=1)
    )
    fragment = set_slot_html_force(fragment, "roadmap-axis", axis)

    task_positions: dict[str, tuple[float, float, float]] = {}
    lane_markup: list[str] = []
    lane_height = 1000 / len(lanes)
    for lane_number, lane in enumerate(lanes, start=1):
        tasks = lane["items"]
        task_markup: list[str] = []
        for task_number, task in enumerate(tasks, start=1):
            start = period_index[str(task["start"])]
            end = period_index[str(task["end"])]
            span = end - start + 1
            note = task.get("note")
            note_markup = (
                f'<small data-slot="roadmap-note-{lane_number}-{task_number}" data-small-ok>'
                f'{esc(str(note))}</small>' if note else ""
            )
            task_markup.append(
                f'<article class="roadmap-task task-start-{start + 1} task-span-{span}" '
                f'data-task-id="{html.escape(str(task["id"]), quote=True)}" data-visual-node data-bound>'
                f'<b data-slot="roadmap-title-{lane_number}-{task_number}" data-small-ok>'
                f'{esc(str(task["title"]))}</b>{note_markup}</article>'
            )
            x_start = start / len(periods) * 1400
            x_end = (end + 1) / len(periods) * 1400
            y = (lane_number - 1) * lane_height + (task_number - 0.5) / len(tasks) * lane_height
            task_positions[str(task["id"])] = (x_start, x_end, y)
        lane_markup.append(
            f'<div class="roadmap-lane" data-task-count="{len(tasks)}">'
            f'<h2 data-slot="lane-title-{lane_number}" data-fit data-min-size="16">{esc(str(lane["title"]))}</h2>'
            f'<div class="lane-track">{"".join(task_markup)}</div></div>'
        )
    fragment = set_slot_html_force(fragment, "roadmap-lanes", "".join(lane_markup))

    connector_markup: list[str] = []
    for lane in lanes:
        for task in lane["items"]:
            target = task_positions[str(task["id"])]
            for dependency in task.get("depends_on") or []:
                source = task_positions[str(dependency)]
                start_x, start_y = source[1] - 8, source[2]
                end_x, end_y = target[0] + 8, target[2]
                bend = max(4.0, (end_x - start_x) * 0.35)
                connector_markup.append(
                    f'<path class="roadmap-connector" data-visual-edge '
                    f'd="M {start_x:.1f} {start_y:.1f} C {start_x + bend:.1f} {start_y:.1f}, '
                    f'{end_x - bend:.1f} {end_y:.1f}, {end_x:.1f} {end_y:.1f}"/>'
                    f'<circle class="roadmap-arrow" cx="{end_x:.1f}" cy="{end_y:.1f}" r="7"/>'
                )
    fragment = set_slot_html_force(fragment, "roadmap-connectors", "".join(connector_markup))
    return fragment


def fill_hierarchy_tree(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    nodes = slide.get("nodes") or []
    root_id = str(slide["root_id"])
    by_id = {str(node["id"]): node for node in nodes}
    depths = {root_id: 0}
    unresolved = set(by_id) - {root_id}
    while unresolved:
        resolved_this_round = []
        for node_id in unresolved:
            parent = str(by_id[node_id]["parent"])
            if parent in depths:
                depths[node_id] = depths[parent] + 1
                resolved_this_round.append(node_id)
        for node_id in resolved_this_round:
            unresolved.remove(node_id)
    levels = [[node for node in nodes if depths[str(node["id"])] == depth] for depth in range(max(depths.values()) + 1)]
    positions: dict[str, tuple[float, float]] = {}
    y_by_depth = {0: 82.0, 1: 330.0, 2: 590.0}
    level_markup: list[str] = []
    original_indexes = {str(node["id"]): index for index, node in enumerate(nodes, start=1)}
    for depth, level in enumerate(levels):
        nodes_markup: list[str] = []
        for position, node in enumerate(level, start=1):
            node_id = str(node["id"])
            x = (position - 0.5) / len(level) * 1760
            positions[node_id] = (x, y_by_depth[depth])
            original_index = original_indexes[node_id]
            body = node.get("body")
            body_markup = (
                f'<p data-slot="tree-body-{original_index}" data-fit data-min-size="15">{esc(str(body))}</p>'
                if body else ""
            )
            tone = "soft" if node_id == root_id else "neutral"
            nodes_markup.append(
                f'<article class="tree-node oil-surface" data-tone="{tone}" data-node-id="{html.escape(node_id, quote=True)}" '
                f'data-node-role="{"root" if node_id == root_id else "child"}" data-visual-node data-bound>'
                f'<span data-small-ok>{"ROOT" if node_id == root_id else f"L{depth}"}</span>'
                f'<h2 data-slot="tree-title-{original_index}" data-fit data-min-size="20">{esc(str(node["title"]))}</h2>'
                f'{body_markup}</article>'
            )
        level_markup.append(
            f'<div class="tree-level" data-tree-level="{depth}" data-node-count="{len(level)}">{"".join(nodes_markup)}</div>'
        )
    fragment = set_slot_html_force(fragment, "tree-levels", "".join(level_markup))
    connectors = []
    for node in nodes:
        if str(node["id"]) == root_id:
            continue
        parent = positions[str(node["parent"])]
        child = positions[str(node["id"])]
        midpoint = (parent[1] + child[1]) / 2
        connectors.append(
            f'<path class="tree-connector" data-visual-edge d="M {parent[0]:.1f} {parent[1] + 66:.1f} '
            f'C {parent[0]:.1f} {midpoint:.1f}, {child[0]:.1f} {midpoint:.1f}, {child[0]:.1f} {child[1] - 66:.1f}"/>'
        )
    fragment = set_slot_html_force(fragment, "tree-connectors", "".join(connectors))
    return fragment


def fill_editorial(fragment: str, slide: dict) -> str:
    fragment = fill_split_like(fragment, slide)
    image = slide.get("image") or slide.get("media")
    if image:
        fragment = set_visual_image(fragment, str(image), str(slide.get("image_alt") or slide.get("title") or ""))
    return fragment


def fill_editorial_feature(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    fragment = set_slot_text_force(fragment, "badge", str(slide.get("badge") or ""))
    fragment = set_slot_text_force(fragment, "media-note", str(slide.get("media_note") or ""))
    for index, item in enumerate((slide.get("cards") or [])[:3], start=1):
        if not isinstance(item, dict):
            continue
        fragment = set_slot_text_force(fragment, f"card-title-{index}", str(item.get("title") or item.get("label") or ""))
        fragment = set_slot_text_force(fragment, f"card-body-{index}", str(item.get("body") or item.get("text") or ""))
        fragment = fill_icon_slot(fragment, f"icon-{index}", item.get("icon"))
    image = slide.get("image") or slide.get("media")
    if image:
        fragment = set_visual_image(fragment, str(image), str(slide.get("image_alt") or slide.get("title") or ""))
    secondary = slide.get("secondary_image")
    if secondary:
        src = html.escape(project_media_src(secondary), quote=True)
        alt = html.escape(str(slide.get("secondary_image_alt") or slide.get("title") or ""), quote=True)
        fragment = set_slot_html_force(fragment, "secondary-visual", f'<img src="{src}" alt="{alt}">')
    return fragment


def fill_catalog_board(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    for index, metric in enumerate((slide.get("metrics") or [])[:3], start=1):
        if not isinstance(metric, dict):
            continue
        fragment = set_slot_text_force(fragment, f"metric-value-{index}", display_value(metric.get("value")))
        fragment = set_slot_text_force(fragment, f"metric-label-{index}", str(metric.get("label") or ""))
    for group_index, group in enumerate((slide.get("groups") or [])[:4], start=1):
        if not isinstance(group, dict):
            continue
        fragment = set_slot_text_force(fragment, f"group-title-{group_index}", str(group.get("title") or group.get("label") or ""))
        fragment = set_slot_text_force(fragment, f"group-meta-{group_index}", str(group.get("meta") or ""))
        items = []
        for item in (group.get("items") or [])[:3]:
            if not isinstance(item, dict):
                continue
            title = esc(str(item.get("title") or item.get("label") or ""))
            body = esc(str(item.get("body") or item.get("text") or ""))
            items.append(
                f'<article class="item" data-bound>'
                f'<h3 data-fit data-min-size="17">{title}</h3>'
                f'<p data-fit data-min-size="15">{body}</p></article>'
            )
        fragment = set_slot_html_force(fragment, f"group-items-{group_index}", "".join(items))
    return fragment


def fill_case_study_board(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    for index, metric in enumerate((slide.get("metrics") or [])[:2], start=1):
        if not isinstance(metric, dict):
            continue
        fragment = set_slot_text_force(fragment, f"metric-label-{index}", str(metric.get("label") or ""))
        fragment = set_slot_text_force(fragment, f"metric-value-{index}", display_value(metric.get("value")))
    insight = slide.get("insight") or {}
    fragment = set_slot_text_force(fragment, "insight-title", str(insight.get("title") or insight.get("label") or ""))
    fragment = set_slot_text_force(fragment, "insight-body", str(insight.get("body") or insight.get("text") or ""))
    fragment = fill_icon_slot(fragment, "insight-icon", insight.get("icon"))
    chart = slide.get("chart") or {}
    fragment = set_slot_text_force(fragment, "chart-label", str(chart.get("label") or ""))
    values = chart.get("values") if isinstance(chart, dict) else []
    if isinstance(values, list) and values:
        peak = max(float(value) for value in values) or 1
        bars = []
        for value in values:
            height = 22 + 78 * float(value) / peak
            level = max(2, min(10, round(height / 10)))
            focus = ' data-focus="true"' if float(value) == peak else ""
            label = html.escape(str(value), quote=True)
            bars.append(f'<i data-level="{level}" data-value="{label}" aria-label="{label}"{focus}></i>')
        fragment = set_slot_html_force(fragment, "chart-bars", "".join(bars))
    image = slide.get("image") or slide.get("media")
    if image:
        fragment = set_visual_image(fragment, str(image), str(slide.get("image_alt") or slide.get("title") or ""))
    return fragment


def fill_data_story(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    variant = str(slide.get("variant") or "")
    fragment = set_slot_text_force(fragment, "source", str(slide.get("source") or ""))
    fragment = set_slot_text_force(fragment, "data-question", DATA_STORY_QUESTIONS.get(variant, ""))
    return set_slot_html_force(fragment, "data-visual", render_data_story(slide))


def fill_annotated_showcase(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    for index, item in enumerate((slide.get("annotations") or [])[:3], start=1):
        if not isinstance(item, dict):
            continue
        fragment = set_slot_text_force(fragment, f"annotation-title-{index}", str(item.get("title") or item.get("label") or ""))
        fragment = set_slot_text_force(fragment, f"annotation-body-{index}", str(item.get("body") or item.get("text") or ""))
    image = slide.get("image") or slide.get("media")
    if image:
        fragment = set_visual_image(fragment, str(image), str(slide.get("image_alt") or slide.get("title") or ""))
    return fragment


def fill_narrative_bento(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    for slot in ("statement", "statement-body", "quote"):
        key = slot.replace("-", "_")
        fragment = set_slot_text_force(fragment, slot, str(slide.get(key) or ""))
    fragment = fill_icon_slot(fragment, "statement-icon", slide.get("statement_icon"))
    fragment = fill_icon_slot(fragment, "quote-icon", slide.get("quote_icon"))
    for index, item in enumerate((slide.get("cards") or [])[:2], start=1):
        if not isinstance(item, dict):
            continue
        fragment = set_slot_text_force(fragment, f"card-title-{index}", str(item.get("title") or item.get("label") or ""))
        fragment = set_slot_text_force(fragment, f"card-body-{index}", str(item.get("body") or item.get("text") or ""))
        fragment = fill_icon_slot(fragment, f"icon-{index}", item.get("icon"))
    return fragment


def fill_sequence_gallery(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    fragment = set_slot_text_force(fragment, "conclusion", str(slide.get("conclusion") or ""))
    for index, step in enumerate((slide.get("steps") or [])[:3], start=1):
        if not isinstance(step, dict):
            continue
        fragment = set_slot_text_force(fragment, f"step-title-{index}", str(step.get("title") or step.get("label") or ""))
        fragment = set_slot_text_force(fragment, f"step-body-{index}", str(step.get("body") or step.get("text") or ""))
        src = project_media_src(step.get("image"))
        alt = html.escape(str(step.get("image_alt") or step.get("title") or ""), quote=True)
        image = f'<img src="{html.escape(src, quote=True)}" alt="{alt}">' if src else ""
        fragment = set_slot_html_force(fragment, f"step-image-{index}", image)
    return fragment


def fill_process_cards(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    steps = (slide.get("steps") or [])[:4]
    icon_count = sum(bool(isinstance(step, dict) and str(step.get("icon") or "").strip()) for step in steps)
    icon_state = "all" if icon_count else "none"
    fragment = re.sub(
        r"(<section\b[^>]*)(>)",
        lambda match: match.group(1) + f' data-icons="{icon_state}"' + match.group(2),
        fragment,
        count=1,
        flags=re.I,
    )
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        fragment = set_slot_text_force(fragment, f"step-title-{index}", str(step.get("title") or step.get("label") or ""))
        fragment = set_slot_text_force(fragment, f"step-body-{index}", str(step.get("body") or step.get("text") or ""))
        fragment = fill_icon_slot(fragment, f"step-icon-{index}", step.get("icon"))
    for index, metric in enumerate((slide.get("measurements") or [])[:4], start=1):
        if not isinstance(metric, dict):
            continue
        fragment = set_slot_text_force(fragment, f"measurement-label-{index}", str(metric.get("label") or ""))
        fragment = set_slot_text_force(fragment, f"measurement-value-{index}", display_value(metric.get("value")))
    fragment = set_slot_text_force(fragment, "measurement-note", str(slide.get("measurement_note") or ""))
    fragment = set_slot_text_force(fragment, "measurement-meta", str(slide.get("measurement_meta") or ""))
    has_measurements = bool(slide.get("measurements"))
    measurement_state = "all" if has_measurements else "none"
    fragment = re.sub(
        r"(<section\b[^>]*)(>)",
        lambda match: match.group(1) + f' data-measurements="{measurement_state}"' + match.group(2),
        fragment,
        count=1,
        flags=re.I,
    )
    if not has_measurements:
        fragment = fragment.replace(
            'class="measurements" data-optional-region="measurements"',
            'class="measurements" data-optional-region="measurements" hidden aria-hidden="true"',
            1,
        )
    return fill_connectors(fragment)


def fill_split_like(fragment: str, slide: dict) -> str:
    note = slide.get("note") or slide.get("content")
    if note:
        # first body paragraph after h1
        def repl_first_p(m: re.Match[str], done=[False]) -> str:
            if done[0]:
                return m.group(0)
            done[0] = True
            return m.group(1) + esc(str(note)) + m.group(3)

        fragment = re.sub(r"(<p\b[^>]*>)(.*?)(</p>)", repl_first_p, fragment, count=1, flags=re.I | re.S)
    image = slide.get("image") or slide.get("media")
    if image:
        fragment = set_visual_image(fragment, str(image), str(slide.get("image_alt") or slide.get("title") or ""))
    return fragment


def fill_project_card_grid(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    for index, card in enumerate(slide.get("cards") or [], start=1):
        if not isinstance(card, dict):
            continue
        fragment = set_slot_text_force(fragment, f"card-title-{index}", display_value(card.get("title")))
        fragment = set_slot_text_force(fragment, f"card-meta-{index}", display_value(card.get("meta")))
        fragment = set_slot_text_force(fragment, f"card-body-{index}", display_value(card.get("body")))
    return fragment


def fill_artifact_focus(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    image = project_media_src(slide.get("image") or slide.get("media"))
    if image:
        alt = html.escape(display_value(slide.get("image_alt") or slide.get("title")), quote=True)
        markup = f'<img class="oil-stock-visual" src="{html.escape(image, quote=True)}" alt="{alt}">'
        fragment = re.sub(
            r'<div\b(?=[^>]*data-slot="media")[^>]*>.*?</div>',
            lambda _: markup, fragment, count=1, flags=re.I | re.S,
        )
    return fragment


def fill_brand_matrix(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    fragment = fragment.replace('class="brand-card is-empty', 'class="brand-card')
    groups = [group for group in (slide.get("groups") or []) if isinstance(group, dict)]
    for group_index in range(2):
        group = groups[group_index] if group_index < len(groups) else {}
        items = [item for item in (group.get("items") or []) if isinstance(item, dict)]
        fragment = set_slot_text_force(fragment, f"group-title-{group_index + 1}", display_value(group.get("title")))
        fragment = re.sub(
            rf'<div\b[^>]*data-brand-group="{group_index + 1}"[^>]*>',
            lambda match: re.sub(r'data-count="\d+"', f'data-count="{len(items)}"', match.group(0))
            if "data-count=" in match.group(0)
            else match.group(0)[:-1] + f' data-count="{len(items)}">',
            fragment, count=1, flags=re.I,
        )
        offset = group_index * 6
        for item_index, item in enumerate(items, start=1):
            slot_index = offset + item_index
            fragment = set_slot_text_force(fragment, f"cell-title-{slot_index}", display_value(item.get("title")))
            fragment = set_slot_text_force(fragment, f"cell-body-{slot_index}", display_value(item.get("meta")))
        for item_index in range(len(items) + 1, 7):
            slot_index = offset + item_index
            fragment = re.sub(
                rf'(<article\b(?=[^>]*class="[^"]*\bbrand-card\b)[^>]*>)(?=\s*<h2\b[^>]*data-slot="cell-title-{slot_index}")',
                lambda match: match.group(1) if "is-empty" in match.group(1) else match.group(1).replace('class="brand-card', 'class="brand-card is-empty', 1),
                fragment, count=1, flags=re.I | re.S,
            )
    return fragment


def fill_dialogue_vs_task(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    sides = slide.get("sides") or []
    for side_index, prefix in enumerate(("left", "right")):
        side = sides[side_index] if side_index < len(sides) and isinstance(sides[side_index], dict) else {}
        fragment = set_slot_text_force(fragment, f"{prefix}-label", "DIALOGUE" if side_index == 0 else "TASK")
        fragment = set_slot_text_force(fragment, f"{prefix}-title", display_value(side.get("title")))
        fragment = set_slot_text_force(fragment, f"{prefix}-body", display_value(side.get("lead")))
        for point_index, point in enumerate(side.get("points") or [], start=1):
            if f'data-slot="{prefix}-point-{point_index}"' not in fragment:
                fragment = re.sub(
                    rf'(<div\b[^>]*class="[^"]*\bpoints\b[^"]*"[^>]*>.*?data-slot="{prefix}-point-{point_index - 1}".*?)(</div>)',
                    lambda match: match.group(1) + f'<div class="point"><span data-slot="{prefix}-point-{point_index}"></span></div>' + match.group(2),
                    fragment, count=1, flags=re.I | re.S,
                )
            fragment = set_slot_text_force(fragment, f"{prefix}-point-{point_index}", display_value(point))
    if len(sides) >= 1 and isinstance(sides[0], dict):
        fragment = set_slot_text_force(fragment, "left-conclusion", display_value(sides[0].get("result")))
    if len(sides) >= 2 and isinstance(sides[1], dict):
        fragment = set_slot_text_force(fragment, "right-result", display_value(sides[1].get("result")))
    return set_slot_text_force(fragment, "versus", "VS")


def fill_dual_table_matrix(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    fragment = fragment.replace('class="row is-empty', 'class="row')
    fragment = re.sub(r'\sdata-highlight="true"', "", fragment)
    tables = slide.get("tables") or []
    for table_index, prefix in enumerate(("left", "right")):
        table = tables[table_index] if table_index < len(tables) and isinstance(tables[table_index], dict) else {}
        fragment = set_slot_text_force(fragment, f"{prefix}-title", display_value(table.get("title")))
        for row_index, row in enumerate(table.get("rows") or [], start=1):
            if not isinstance(row, list):
                continue
            fragment = set_slot_text_force(fragment, f"{prefix}-label-{row_index}", display_value(row[0] if row else ""))
            fragment = set_slot_text_force(fragment, f"{prefix}-value-{row_index}", display_value(row[1] if len(row) > 1 else ""))
        for row_index in range(len(table.get("rows") or []) + 1, 5):
            fragment = re.sub(
                rf'(<div\b(?=[^>]*class="[^"]*\brow\b)[^>]*>)(?=\s*<b\b[^>]*data-slot="{prefix}-label-{row_index}")',
                lambda match: match.group(1) if "is-empty" in match.group(1) else match.group(1).replace('class="row', 'class="row is-empty', 1),
                fragment, count=1, flags=re.I | re.S,
            )
        row_count = len(table.get("rows") or [])
        if row_count:
            fragment = re.sub(
                rf'(<div\b(?=[^>]*class="[^"]*\brow\b)[^>]*)(>)(?=\s*<b\b[^>]*data-slot="{prefix}-label-{row_count}")',
                lambda match: match.group(1) + ' data-highlight="true"' + match.group(2),
                fragment, count=1, flags=re.I | re.S,
            )
    return fragment


def fill_code_to_render(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    panels = slide.get("panels") or []
    for prefix, panel in zip(("left", "right"), panels):
        if not isinstance(panel, dict):
            continue
        fragment = set_slot_text_force(fragment, f"{prefix}-code-label", display_value(panel.get("title")))
        # Source is deliberately routed through the escaping text setter. Raw HTML
        # here would turn authored examples into active DOM and break closed structure.
        fragment = set_slot_text_force(fragment, f"{prefix}-source-code", display_value(panel.get("source")))
        fragment = set_slot_text_force(fragment, f"{prefix}-render-label", display_value(panel.get("render_title")))
        fragment = set_slot_text_force(fragment, f"{prefix}-render-body", display_value(panel.get("render_body")))
        fragment = set_slot_text_force(fragment, f"{prefix}-connector", "→")
    return fragment


def fill_step_hero(fragment: str, slide: dict) -> str:
    fragment = fill_common_slots(fragment, slide)
    fragment = fragment.replace('class="point is-empty', 'class="point')
    fragment = set_slot_text_force(fragment, "step-number", display_value(slide.get("step_number")))
    points = slide.get("points") or []
    for index in range(1, 5):
        value = points[index - 1] if index <= len(points) else ""
        fragment = set_slot_text_force(fragment, f"point-{index}", display_value(value))
        if not value:
            fragment = re.sub(
                rf'(<li\b(?=[^>]*class="[^"]*\bpoint\b)[^>]*data-slot="point-{index}"[^>]*>)',
                lambda match: match.group(1) if "is-empty" in match.group(1) else match.group(1).replace('class="point', 'class="point is-empty', 1),
                fragment, count=1, flags=re.I,
            )
    fragment = set_slot_text_force(fragment, "conclusion", display_value(slide.get("conclusion")))
    image = project_media_src(slide.get("image") or slide.get("media"))
    if image:
        alt = html.escape(display_value(slide.get("image_alt") or slide.get("title")), quote=True)
        markup = f'<img class="oil-stock-visual" src="{html.escape(image, quote=True)}" alt="{alt}">'
        fragment = re.sub(
            r'<div\b(?=[^>]*data-slot="media")[^>]*>.*?</div>',
            lambda _: markup, fragment, count=1, flags=re.I | re.S,
        )
    return fragment


FILLERS = {
    "artifact-focus": fill_artifact_focus,
    "project-card-grid": fill_project_card_grid,
    "brand-matrix": fill_brand_matrix,
    "dialogue-vs-task": fill_dialogue_vs_task,
    "dual-table-matrix": fill_dual_table_matrix,
    "code-to-render": fill_code_to_render,
    "step-hero": fill_step_hero,
    "three-steps": fill_three_steps,
    "timeline": fill_timeline,
    "process-rail": fill_process_rail,
    "process-cards": fill_process_cards,
    "quote": fill_quote,
    "card-trio": fill_card_trio,
    "comparison": fill_comparison,
    "comparison-list": fill_comparison,
    "cover": fill_cover,
    "end": fill_end,
    "split-visual": fill_split_like,
    "photo-split": fill_split_like,
    "photo-gradient": fill_split_like,
    "bleed-split": fill_split_like,
    "diagonal-split": fill_split_like,
    "browser-showcase": fill_split_like,
    "section": fill_split_like,
    "metric": fill_metric,
    "recap": fill_recap,
    "tabs": fill_tabs,
    "converge": fill_converge,
    "cycle": fill_cycle,
    "data-story": fill_data_story,
    "editorial-canvas": fill_editorial,
    "editorial-feature": fill_editorial_feature,
    "catalog-board": fill_catalog_board,
    "case-study-board": fill_case_study_board,
    "annotated-showcase": fill_annotated_showcase,
    "narrative-bento": fill_narrative_bento,
    "sequence-gallery": fill_sequence_gallery,
    "quadrant": fill_quadrant,
    "tier-stack": fill_tier_stack,
    "relationship-map": fill_relationship_map,
    "decision-matrix": fill_decision_matrix,
    "evidence-matrix": fill_evidence_matrix,
    "gantt-roadmap": fill_gantt_roadmap,
    "hierarchy-tree": fill_hierarchy_tree,
}


def fill_slide_file(path: Path, slide: dict, slide_index: int) -> bool:
    template = slide.get("template")
    if not template:
        raise SystemExit(f"Slide {slide.get('id')!r} is missing template.")
    text = path.read_text(encoding="utf-8")
    match = re.search(r"<!-- OIL-SLIDE:START -->(.*)<!-- OIL-SLIDE:END -->", text, re.S)
    if not match:
        raise SystemExit(f"Slide file is missing OIL-SLIDE markers: {path}")
    fragment = match.group(1)
    background = effective_background(slide)
    fragment, count = re.subn(
        r'(data-bg=["\'])[^"\']+(["\'])',
        rf'\g<1>{background}\g<2>',
        fragment,
        count=1,
    )
    if count != 1:
        raise SystemExit(f"Template {template} does not expose data-bg.")
    filler = FILLERS.get(template)
    if filler is None:
        raise SystemExit(f"No content filler registered for template: {template}")
    fragment = filler(fragment, slide)
    fragment = apply_media_attributes(fragment, slide)
    fragment = inject_backdrop_text(fragment, slide)
    fragment = annotate_editable_fragment(fragment, slide, slide_index)
    new_text = text[: match.start(1)] + fragment + text[match.end(1) :]
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def main() -> None:
    args = parse_args()
    project = args.project.expanduser().resolve()
    outline_path = (args.outline or (project / "outline.json")).expanduser().resolve()
    if not outline_path.is_file():
        raise SystemExit(f"Missing outline: {outline_path}")
    config_path = project / "deck.json"
    if not config_path.is_file():
        raise SystemExit(f"Not an oil-ppt project: {project}")
    outline = json.loads(outline_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    by_id = {
        slide["id"]: (index, slide)
        for index, slide in enumerate(outline.get("slides", []))
        if isinstance(slide, dict) and slide.get("id")
    }
    filled = 0
    for relative in config.get("slides", []):
        path = project / relative
        if not path.is_file():
            raise SystemExit(f"Configured slide file is missing: {path}")
        text = path.read_text(encoding="utf-8")
        id_match = re.search(r'data-slide-id=["\']([^"\']+)["\']', text)
        if not id_match:
            raise SystemExit(f"Slide file is missing data-slide-id: {path}")
        indexed_slide = by_id.get(id_match.group(1))
        if not indexed_slide:
            raise SystemExit(f"Slide {id_match.group(1)!r} is missing from outline.json")
        slide_index, slide = indexed_slide
        if fill_slide_file(path, slide, slide_index):
            filled += 1
    print(json.dumps({"project": str(project), "filled": filled}, ensure_ascii=False))


if __name__ == "__main__":
    main()
