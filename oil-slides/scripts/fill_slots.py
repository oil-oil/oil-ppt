#!/usr/bin/env python3
"""Fill template content slots from outline slide fields."""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

from icon_registry import CONNECTOR_ICON, icon_svg_markup


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--outline", type=Path, help="defaults to project/outline.json")
    return parser.parse_args()


def esc(value: str) -> str:
    return html.escape(str(value), quote=False)


def set_slot_text(fragment: str, slot: str, value: str | None) -> str:
    if value is None or str(value).strip() == "":
        return fragment
    pattern = re.compile(
        rf'(data-slot="{re.escape(slot)}"[^>]*>)(.*?)(</)',
        re.I | re.S,
    )
    return pattern.sub(rf"\g<1>{esc(value)}\3", fragment, count=1)


def set_slot_text_force(fragment: str, slot: str, value: str | None) -> str:
    pattern = re.compile(
        rf'(data-slot="{re.escape(slot)}"[^>]*>)(.*?)(</)',
        re.I | re.S,
    )
    return pattern.sub(rf"\g<1>{esc(value or '')}\3", fragment, count=1)


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
        inner = re.sub(r"(<h2\b[^>]*>)(.*?)(</h2>)", rf"\g<1>{esc(label)}\g<3>", inner, count=1, flags=re.I | re.S)
    if body is not None and str(body).strip() != "":
        inner = re.sub(r"(<p\b[^>]*>)(.*?)(</p>)", rf"\g<1>{esc(body)}\g<3>", inner, count=1, flags=re.I | re.S)
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
            f"<!-- OIL-VISUAL:main:START -->{img}<!-- OIL-VISUAL:main:END -->",
            fragment,
            count=1,
            flags=re.I | re.S,
        )
    return fragment


def fill_connectors(fragment: str) -> str:
    svg = icon_svg_markup(CONNECTOR_ICON)
    if not svg:
        return fragment
    return re.sub(
        r'(data-slot="connector"[^>]*>)(.*?)(</span>)',
        rf"\g<1>{svg}\g<3>",
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
            if label:
                fragment = replace_nth_h2(fragment, i, str(label))
    fragment = fill_connectors(fragment)
    return fragment


def fill_card_trio(fragment: str, slide: dict) -> str:
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
    return fragment


def fill_comparison(fragment: str, slide: dict) -> str:
    sides = slide.get("sides")
    if not isinstance(sides, list) or len(sides) < 2:
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
                inner = re.sub(r"(<h2\b[^>]*>)(.*?)(</h2>)", rf"\g<1>{esc(title)}\g<3>", inner, count=1, flags=re.I | re.S)
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
    aside = slide.get("aside")
    aside_label = slide.get("aside_label")
    for slot in ("note", "meta", "aside", "aside-label", "artifact-title", "artifact-body"):
        fragment = set_slot_text_force(fragment, slot, "")
    if note:
        fragment = set_slot_text_force(fragment, "note", str(note))
        # also lead on line-artifact
        fragment = re.sub(
            r'(class="lead"[^>]*data-slot="note"[^>]*>)(.*?)(</p>)',
            rf"\g<1>{esc(str(note))}\g<3>",
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
        fragment = replace_nth(fragment, r'(<div\b[^>]*class="[^"]*\bsymbol\b[^"]*"[^>]*>)(.*?)(</div>)', index, str(title)[:1])
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


def fill_editorial(fragment: str, slide: dict) -> str:
    fragment = fill_split_like(fragment, slide)
    image = slide.get("image") or slide.get("media")
    if image:
        fragment = set_visual_image(fragment, str(image), str(slide.get("image_alt") or slide.get("title") or ""))
    return fragment


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


FILLERS = {
    "three-steps": fill_three_steps,
    "timeline": fill_timeline,
    "process-rail": fill_process_rail,
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
    "editorial-canvas": fill_editorial,
}


def fill_slide_file(path: Path, slide: dict) -> bool:
    template = slide.get("template")
    if not template:
        raise SystemExit(f"Slide {slide.get('id')!r} is missing template.")
    text = path.read_text(encoding="utf-8")
    match = re.search(r"<!-- OIL-SLIDE:START -->(.*)<!-- OIL-SLIDE:END -->", text, re.S)
    if not match:
        raise SystemExit(f"Slide file is missing OIL-SLIDE markers: {path}")
    fragment = match.group(1)
    filler = FILLERS.get(template)
    if filler is None:
        raise SystemExit(f"No content filler registered for template: {template}")
    fragment = filler(fragment, slide)
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
        raise SystemExit(f"Not an oil-slides project: {project}")
    outline = json.loads(outline_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in outline.get("slides", []) if isinstance(s, dict) and s.get("id")}
    filled = 0
    for relative in config.get("slides", []):
        path = project / relative
        if not path.is_file():
            raise SystemExit(f"Configured slide file is missing: {path}")
        text = path.read_text(encoding="utf-8")
        id_match = re.search(r'data-slide-id=["\']([^"\']+)["\']', text)
        if not id_match:
            raise SystemExit(f"Slide file is missing data-slide-id: {path}")
        slide = by_id.get(id_match.group(1))
        if not slide:
            raise SystemExit(f"Slide {id_match.group(1)!r} is missing from outline.json")
        if fill_slide_file(path, slide):
            filled += 1
    print(json.dumps({"project": str(project), "filled": filled}, ensure_ascii=False))


if __name__ == "__main__":
    main()
