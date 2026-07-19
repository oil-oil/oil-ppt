#!/usr/bin/env python3
"""Bind rendered slide text to stable JSON pointers for the authoring editor."""
from __future__ import annotations

import re
from collections.abc import Callable, Iterator


def pointer(*parts: object) -> str:
    encoded = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(encoded)


def pointer_parts(value: str) -> list[str]:
    if not value.startswith("/"):
        raise ValueError("JSON pointer must start with '/'.")
    return [part.replace("~1", "/").replace("~0", "~") for part in value[1:].split("/")]


def get_pointer(data: object, value: str) -> object:
    current = data
    for part in pointer_parts(value):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(value)
    return current


def set_pointer(data: object, value: str, replacement: str) -> None:
    parts = pointer_parts(value)
    if not parts:
        raise KeyError(value)
    current = data
    for part in parts[:-1]:
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(value)
    final = parts[-1]
    if isinstance(current, list):
        current[int(final)] = replacement
    elif isinstance(current, dict):
        current[final] = replacement
    else:
        raise KeyError(value)


def _existing_key(item: object, candidates: tuple[str, ...], default: str | None = None) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in candidates:
        if key in item:
            return key
    return default


def _slide_pointer(slide_index: int, *parts: object) -> str:
    return pointer("slides", slide_index, *parts)


def _body_field(slide: dict, *, content_first: bool) -> str | None:
    fields = ("content", "note") if content_first else ("note", "content")
    return _existing_key(slide, fields)


def slot_pointer(slide: dict, slide_index: int, slot: str) -> str | None:
    direct = {
        "kicker": "kicker", "meta": "meta", "page-note": "page_note",
        "badge": "badge", "media-note": "media_note", "quote": "quote",
        "source": "source", "outcome": "outcome", "conclusion": "conclusion",
        "statement": "statement", "statement-body": "statement_body",
        "measurement-note": "measurement_note", "measurement-meta": "measurement_meta",
        "artifact-title": "artifact_title", "artifact-body": "artifact_body",
        "aside-label": "aside_label", "chart-label": "chart.label",
        "insight-title": "insight.title", "insight-body": "insight.body",
        "step-number": "step_number",
    }
    if slot == "content":
        field = _body_field(slide, content_first=True)
        return _slide_pointer(slide_index, field) if field else None
    if slot == "note":
        field = _body_field(slide, content_first=False)
        return _slide_pointer(slide_index, field) if field else None
    if slot == "aside":
        if "aside" in slide:
            return _slide_pointer(slide_index, "aside")
        if slide.get("variant") == "line-note":
            field = _body_field(slide, content_first=False)
            return _slide_pointer(slide_index, field) if field else None
        return None
    if slot in direct:
        parts = direct[slot].split(".")
        try:
            get_pointer({"slides": [slide]}, pointer("slides", 0, *parts))
        except (KeyError, IndexError, ValueError):
            return None
        return _slide_pointer(slide_index, *parts)

    metric_slot = {
        "metric-change": "change",
        "metric-change-label": "change_label",
    }.get(slot)
    if metric_slot:
        metric = slide.get("metric")
        if isinstance(metric, dict) and metric_slot in metric:
            return _slide_pointer(slide_index, "metric", metric_slot)
        return None

    match = re.fullmatch(r"node-(title|body)-(\d+)", slot)
    if match:
        index = int(match.group(2)) - 1
        nodes = slide.get("nodes") or []
        key = match.group(1)
        if index >= len(nodes) or not isinstance(nodes[index], dict) or key not in nodes[index]:
            return None
        return _slide_pointer(slide_index, "nodes", index, key)

    match = re.fullmatch(r"link-label-(\d+)", slot)
    if match:
        index = int(match.group(1)) - 1
        links = slide.get("links") or []
        if index >= len(links) or not isinstance(links[index], dict) or "label" not in links[index]:
            return None
        return _slide_pointer(slide_index, "links", index, "label")

    match = re.fullmatch(r"claim-title-(\d+)", slot)
    if match:
        index = int(match.group(1)) - 1
        claims = slide.get("claims") or []
        return (
            _slide_pointer(slide_index, "claims", index, "title")
            if index < len(claims) and isinstance(claims[index], dict) and "title" in claims[index] else None
        )

    match = re.fullmatch(r"evidence-(title|note|source)-(\d+)", slot)
    if match:
        field, raw_index = match.groups()
        index = int(raw_index) - 1
        evidence = slide.get("evidence") or []
        if index >= len(evidence) or not isinstance(evidence[index], dict):
            return None
        if field == "source":
            source = evidence[index].get("source")
            return _slide_pointer(slide_index, "evidence", index, "source", "label") if isinstance(source, dict) and "label" in source else None
        return _slide_pointer(slide_index, "evidence", index, field) if field in evidence[index] else None

    match = re.fullmatch(r"period-label-(\d+)", slot)
    if match:
        index = int(match.group(1)) - 1
        periods = slide.get("periods") or []
        return _slide_pointer(slide_index, "periods", index, "label") if index < len(periods) else None

    match = re.fullmatch(r"lane-title-(\d+)", slot)
    if match:
        index = int(match.group(1)) - 1
        lanes = slide.get("lanes") or []
        return _slide_pointer(slide_index, "lanes", index, "title") if index < len(lanes) else None

    match = re.fullmatch(r"roadmap-(title|note)-(\d+)-(\d+)", slot)
    if match:
        field, lane_raw, task_raw = match.groups()
        lane_index, task_index = int(lane_raw) - 1, int(task_raw) - 1
        lanes = slide.get("lanes") or []
        if lane_index >= len(lanes) or not isinstance(lanes[lane_index], dict):
            return None
        tasks = lanes[lane_index].get("items") or []
        if task_index >= len(tasks) or not isinstance(tasks[task_index], dict) or field not in tasks[task_index]:
            return None
        return _slide_pointer(slide_index, "lanes", lane_index, "items", task_index, field)

    match = re.fullmatch(r"tree-(title|body)-(\d+)", slot)
    if match:
        field, raw_index = match.groups()
        index = int(raw_index) - 1
        nodes = slide.get("nodes") or []
        if index >= len(nodes) or not isinstance(nodes[index], dict) or field not in nodes[index]:
            return None
        return _slide_pointer(slide_index, "nodes", index, field)

    match = re.fullmatch(r"criterion-(\d+)", slot)
    if match:
        index = int(match.group(1)) - 1
        criteria = slide.get("criteria") or []
        if index >= len(criteria) or not isinstance(criteria[index], str):
            return None
        return _slide_pointer(slide_index, "criteria", index)

    match = re.fullmatch(r"option-title-(\d+)", slot)
    if match:
        index = int(match.group(1)) - 1
        options = slide.get("options") or []
        if index >= len(options) or not isinstance(options[index], dict) or "title" not in options[index]:
            return None
        return _slide_pointer(slide_index, "options", index, "title")

    match = re.fullmatch(r"card-(title|meta|body)-(\d+)", slot)
    if match:
        index = int(match.group(2)) - 1
        cards = slide.get("cards") or []
        if index >= len(cards) or not isinstance(cards[index], dict):
            return None
        candidates = ("title", "label", "h2") if match.group(1) == "title" else (("meta",) if match.group(1) == "meta" else ("body", "text", "p"))
        key = _existing_key(cards[index], candidates)
        return _slide_pointer(slide_index, "cards", index, key) if key else None

    match = re.fullmatch(r"card-caption-(\d+)-(\d+)", slot)
    if match:
        card_index, evidence_index = int(match.group(1)) - 1, int(match.group(2)) - 1
        cards = slide.get("cards") or []
        if card_index >= len(cards) or not isinstance(cards[card_index], dict):
            return None
        evidence = cards[card_index].get("images") or []
        if evidence_index >= len(evidence) or not isinstance(evidence[evidence_index], dict):
            return None
        key = _existing_key(evidence[evidence_index], ("caption", "label"))
        return _slide_pointer(slide_index, "cards", card_index, "images", evidence_index, key) if key else None

    match = re.fullmatch(r"side-(title|lead)-(\d+)", slot)
    if match:
        index = int(match.group(2)) - 1
        sides = slide.get("sides") or []
        if index >= len(sides) or not isinstance(sides[index], dict):
            return None
        candidates = ("title", "label", "h2") if match.group(1) == "title" else ("lead",)
        key = _existing_key(sides[index], candidates)
        return _slide_pointer(slide_index, "sides", index, key) if key else None

    match = re.fullmatch(r"point-(title|body)-(\d+)-(\d+)", slot)
    if match:
        side_index, point_index = int(match.group(2)) - 1, int(match.group(3)) - 1
        sides = slide.get("sides") or []
        if side_index >= len(sides) or not isinstance(sides[side_index], dict):
            return None
        points = sides[side_index].get("points") or []
        if point_index >= len(points):
            return None
        point_item = points[point_index]
        if isinstance(point_item, str):
            return _slide_pointer(slide_index, "sides", side_index, "points", point_index) if match.group(1) == "body" else None
        candidates = ("title", "label") if match.group(1) == "title" else ("body", "text")
        key = _existing_key(point_item, candidates)
        return _slide_pointer(slide_index, "sides", side_index, "points", point_index, key) if key else None

    match = re.fullmatch(r"evidence-caption-(\d+)-(\d+)", slot)
    if match:
        side_index, evidence_index = int(match.group(1)) - 1, int(match.group(2)) - 1
        sides = slide.get("sides") or []
        if side_index >= len(sides) or not isinstance(sides[side_index], dict):
            return None
        evidence = sides[side_index].get("evidence") or []
        if evidence_index >= len(evidence) or not isinstance(evidence[evidence_index], dict):
            return None
        key = _existing_key(evidence[evidence_index], ("caption", "label"))
        return _slide_pointer(slide_index, "sides", side_index, "evidence", evidence_index, key) if key else None

    match = re.fullmatch(r"step-(title|body)-(\d+)", slot)
    if match:
        index = int(match.group(2)) - 1
        steps = slide.get("steps") or []
        if index >= len(steps):
            return None
        item = steps[index]
        if isinstance(item, str):
            return _slide_pointer(slide_index, "steps", index) if match.group(1) == "title" else None
        candidates = ("title", "label", "h2") if match.group(1) == "title" else ("body", "text", "p")
        key = _existing_key(item, candidates)
        return _slide_pointer(slide_index, "steps", index, key) if key else None

    match = re.fullmatch(r"metric-(value|label)-(\d+)", slot)
    if match:
        index = int(match.group(2)) - 1
        metrics = slide.get("metrics") or []
        if index >= len(metrics) or not isinstance(metrics[index], dict) or match.group(1) not in metrics[index]:
            return None
        return _slide_pointer(slide_index, "metrics", index, match.group(1))

    match = re.fullmatch(r"measurement-(value|label)-(\d+)", slot)
    if match:
        index = int(match.group(2)) - 1
        measurements = slide.get("measurements") or []
        if index >= len(measurements) or not isinstance(measurements[index], dict) or match.group(1) not in measurements[index]:
            return None
        return _slide_pointer(slide_index, "measurements", index, match.group(1))

    match = re.fullmatch(r"group-(title|meta)-(\d+)", slot)
    if match:
        index = int(match.group(2)) - 1
        groups = slide.get("groups") or []
        if index >= len(groups) or not isinstance(groups[index], dict):
            return None
        candidates = ("title", "label") if match.group(1) == "title" else ("meta",)
        key = _existing_key(groups[index], candidates)
        return _slide_pointer(slide_index, "groups", index, key) if key else None

    match = re.fullmatch(r"group-item-(\d+)-(\d+)", slot)
    if match:
        group_index, item_index = int(match.group(1)) - 1, int(match.group(2)) - 1
        groups = slide.get("groups") or []
        if group_index >= len(groups) or not isinstance(groups[group_index], dict):
            return None
        items = groups[group_index].get("items") or []
        if item_index >= len(items) or not isinstance(items[item_index], str):
            return None
        return _slide_pointer(slide_index, "groups", group_index, "items", item_index)

    match = re.fullmatch(r"axis-(x|y)", slot)
    if match:
        axes = slide.get("axes") or {}
        key = match.group(1)
        return _slide_pointer(slide_index, "axes", key) if isinstance(axes, dict) and key in axes else None

    match = re.fullmatch(r"annotation-(title|body)-(\d+)", slot)
    if match:
        index = int(match.group(2)) - 1
        annotations = slide.get("annotations") or []
        if index >= len(annotations) or not isinstance(annotations[index], dict) or match.group(1) not in annotations[index]:
            return None
        return _slide_pointer(slide_index, "annotations", index, match.group(1))

    match = re.fullmatch(r"bullet-(\d+)", slot)
    if match:
        index = int(match.group(1)) - 1
        points = slide.get("points") or []
        return _slide_pointer(slide_index, "points", index) if index < len(points) and isinstance(points[index], str) else None

    match = re.fullmatch(r"point-(\d+)", slot)
    if match:
        index = int(match.group(1)) - 1
        points = slide.get("points") or []
        return _slide_pointer(slide_index, "points", index) if index < len(points) and isinstance(points[index], str) else None

    if slot in {"axis-x", "axis-y"}:
        group_index = 1 if slot == "axis-x" else 0
        groups = slide.get("groups") or []
        if group_index < len(groups) and isinstance(groups[group_index], dict) and "title" in groups[group_index]:
            return _slide_pointer(slide_index, "groups", group_index, "title")
        return None

    match = re.fullmatch(r"cell-(title|body)-(\d+)", slot)
    if match:
        flat_index = int(match.group(2)) - 1
        groups = slide.get("groups") or []
        if slide.get("template") == "brand-matrix":
            group_index, item_index = divmod(flat_index, 6)
            if group_index < len(groups) and isinstance(groups[group_index], dict):
                items = groups[group_index].get("items") or []
                field = "title" if match.group(1) == "title" else "meta"
                if item_index < len(items) and isinstance(items[item_index], dict) and field in items[item_index]:
                    return _slide_pointer(slide_index, "groups", group_index, "items", item_index, field)
            return None
        remaining = flat_index
        for group_index, group in enumerate(groups):
            items = group.get("items") if isinstance(group, dict) else []
            if remaining < len(items):
                item = items[remaining]
                field = "title" if match.group(1) == "title" else "meta"
                return _slide_pointer(slide_index, "groups", group_index, "items", remaining, field) if isinstance(item, dict) and field in item else None
            remaining -= len(items)
        return None

    match = re.fullmatch(r"(left|right)-(title|body)", slot)
    if match:
        if slide.get("template") == "dual-table-matrix" and match.group(2) == "title":
            table_index = 0 if match.group(1) == "left" else 1
            tables = slide.get("tables") or []
            return _slide_pointer(slide_index, "tables", table_index, "title") if table_index < len(tables) else None
        side_index = 0 if match.group(1) == "left" else 1
        sides = slide.get("sides") or []
        if side_index >= len(sides) or not isinstance(sides[side_index], dict):
            return None
        if match.group(2) == "title":
            return _slide_pointer(slide_index, "sides", side_index, "title")
        return _slide_pointer(slide_index, "sides", side_index, "lead")

    match = re.fullmatch(r"(left|right)-point-(\d+)", slot)
    if match:
        side_index = 0 if match.group(1) == "left" else 1
        sides = slide.get("sides") or []
        if side_index >= len(sides) or not isinstance(sides[side_index], dict):
            return None
        point_index = int(match.group(2)) - 1
        points = sides[side_index].get("points") or []
        return _slide_pointer(slide_index, "sides", side_index, "points", point_index) if 0 <= point_index < len(points) else None

    if slot in {"left-conclusion", "right-result"}:
        side_index = 0 if slot == "left-conclusion" else 1
        sides = slide.get("sides") or []
        return _slide_pointer(slide_index, "sides", side_index, "result") if side_index < len(sides) and isinstance(sides[side_index], dict) and "result" in sides[side_index] else None

    match = re.fullmatch(r"(left|right)-(label|value)-(\d+)", slot)
    if match:
        table_index = 0 if match.group(1) == "left" else 1
        row_index = int(match.group(3)) - 1
        column_index = 0 if match.group(2) == "label" else 1
        tables = slide.get("tables") or []
        if table_index < len(tables) and isinstance(tables[table_index], dict):
            rows = tables[table_index].get("rows") or []
            if row_index < len(rows) and isinstance(rows[row_index], list) and column_index < len(rows[row_index]):
                return _slide_pointer(slide_index, "tables", table_index, "rows", row_index, column_index)
        return None

    code_fields = {"code-label": "title", "source-code": "source", "render-label": "render_title", "render-body": "render_body"}
    if slot in code_fields:
        panels = slide.get("panels") or []
        field = code_fields[slot]
        return _slide_pointer(slide_index, "panels", 0, field) if panels and isinstance(panels[0], dict) and field in panels[0] else None
    match = re.fullmatch(r"panel-(\d+)-(source-label|source|render-label|render-body)", slot)
    if match:
        panel_index = int(match.group(1)) - 1
        field = {"source-label": "title", "source": "source", "render-label": "render_title", "render-body": "render_body"}[match.group(2)]
        panels = slide.get("panels") or []
        return _slide_pointer(slide_index, "panels", panel_index, field) if panel_index < len(panels) and isinstance(panels[panel_index], dict) and field in panels[panel_index] else None
    match = re.fullmatch(r"(left|right)-(code-label|source-code|render-label|render-body)", slot)
    if match:
        panel_index = 0 if match.group(1) == "left" else 1
        field = {"code-label": "title", "source-code": "source", "render-label": "render_title", "render-body": "render_body"}[match.group(2)]
        panels = slide.get("panels") or []
        return _slide_pointer(slide_index, "panels", panel_index, field) if panel_index < len(panels) and isinstance(panels[panel_index], dict) and field in panels[panel_index] else None
    return None


def _add_edit_path(open_tag: str, value: str | None) -> str:
    if not value or "data-edit-path=" in open_tag:
        return open_tag
    return open_tag[:-1] + f' data-edit-path="{value}">'


def _annotate_open_tags(fragment: str, pattern: str, paths: list[str | None]) -> str:
    matches = list(re.finditer(pattern, fragment, re.I | re.S))
    for match, value in reversed(list(zip(matches, paths))):
        replacement = _add_edit_path(match.group(0), value)
        fragment = fragment[:match.start()] + replacement + fragment[match.end():]
    return fragment


def _annotate_first(fragment: str, pattern: str, value: str | None) -> str:
    match = re.search(pattern, fragment, re.I | re.S)
    if not match or not value:
        return fragment
    replacement = _add_edit_path(match.group(0), value)
    return fragment[:match.start()] + replacement + fragment[match.end():]


def _annotate_article_blocks(
    fragment: str,
    selector: str,
    paths_for: Callable[[str, int], tuple[str | None, list[str | None]]],
) -> str:
    pattern = re.compile(rf'(<article\b(?=[^>]*{selector})[^>]*>)(.*?)(</article>)', re.I | re.S)
    matches = list(pattern.finditer(fragment))
    for ordinal, match in reversed(list(enumerate(matches))):
        title_path, body_paths = paths_for(match.group(1), ordinal)
        inner = _annotate_first(match.group(2), r"<h[23]\b[^>]*>", title_path)
        inner = _annotate_open_tags(inner, r"<p\b[^>]*>", body_paths)
        replacement = match.group(1) + inner + match.group(3)
        fragment = fragment[:match.start()] + replacement + fragment[match.end():]
    return fragment


def annotate_editable_fragment(fragment: str, slide: dict, slide_index: int) -> str:
    title_path = _slide_pointer(slide_index, "title")
    fragment = re.sub(
        r"<h1\b[^>]*>",
        lambda match: _add_edit_path(match.group(0), title_path),
        fragment,
        flags=re.I,
    )

    def bind_slot(match: re.Match[str]) -> str:
        return _add_edit_path(match.group(0), slot_pointer(slide, slide_index, match.group("slot")))

    fragment = re.sub(
        r'<[a-z][a-z0-9]*\b(?=[^>]*data-slot="(?P<slot>[^"]+)")[^>]*>',
        bind_slot,
        fragment,
        flags=re.I,
    )

    template = str(slide.get("template") or "")
    primary_body_templates = {
        "bleed-split", "browser-showcase", "diagonal-split", "editorial-canvas",
        "metric", "photo-gradient", "photo-split", "recap", "section", "split-visual",
    }
    if template in primary_body_templates:
        field = _body_field(slide, content_first=False)
        fragment = _annotate_first(fragment, r"<p\b[^>]*>", _slide_pointer(slide_index, field) if field else None)

    if template in {"three-steps", "timeline", "process-rail"}:
        steps = slide.get("steps") or []

        def step_paths(open_tag: str, ordinal: int) -> tuple[str | None, list[str | None]]:
            step_match = re.search(r'data-step="(\d+)"', open_tag, re.I)
            index = int(step_match.group(1)) - 1 if step_match else ordinal
            if index >= len(steps):
                return None, []
            item = steps[index]
            if isinstance(item, str):
                return _slide_pointer(slide_index, "steps", index), []
            title_key = _existing_key(item, ("title", "label", "h2"))
            body_key = _existing_key(item, ("body", "text", "p"))
            return (
                _slide_pointer(slide_index, "steps", index, title_key) if title_key else None,
                [_slide_pointer(slide_index, "steps", index, body_key)] if body_key else [],
            )

        fragment = _annotate_article_blocks(fragment, r"data-step=", step_paths)

    if template in {"card-trio", "recap"}:
        cards = slide.get("cards") or []

        def card_paths(_open_tag: str, ordinal: int) -> tuple[str | None, list[str | None]]:
            if ordinal >= len(cards) or not isinstance(cards[ordinal], dict):
                return None, []
            title_key = _existing_key(cards[ordinal], ("title", "label", "h2"))
            body_key = _existing_key(cards[ordinal], ("body", "text", "p"))
            return (
                _slide_pointer(slide_index, "cards", ordinal, title_key) if title_key else None,
                [_slide_pointer(slide_index, "cards", ordinal, body_key)] if body_key else [],
            )

        fragment = _annotate_article_blocks(fragment, r"data-visual-item", card_paths)

    if template == "comparison-list":
        sides = slide.get("sides") or []

        def side_paths(_open_tag: str, ordinal: int) -> tuple[str | None, list[str | None]]:
            if ordinal >= len(sides) or not isinstance(sides[ordinal], dict):
                return None, []
            side = sides[ordinal]
            title_key = _existing_key(side, ("title", "label", "h2"))
            body_paths: list[str | None] = []
            for point_index, item in enumerate(side.get("points") or []):
                if isinstance(item, str):
                    body_paths.append(_slide_pointer(slide_index, "sides", ordinal, "points", point_index))
                else:
                    key = _existing_key(item, ("body", "text"))
                    body_paths.append(_slide_pointer(slide_index, "sides", ordinal, "points", point_index, key) if key else None)
            return _slide_pointer(slide_index, "sides", ordinal, title_key) if title_key else None, body_paths

        fragment = _annotate_article_blocks(fragment, r'class="[^"]*\bside\b', side_paths)

    if template == "tabs":
        sides = slide.get("sides") or []
        title_paths: list[str | None] = []
        body_paths: list[str | None] = []
        for side_index, side in enumerate(sides[:2]):
            title_key = _existing_key(side, ("title", "label"))
            body_key = _existing_key(side, ("body", "text"))
            title_paths.append(_slide_pointer(slide_index, "sides", side_index, title_key) if title_key else None)
            body_paths.append(_slide_pointer(slide_index, "sides", side_index, body_key) if body_key else None)
        fragment = _annotate_open_tags(fragment, r"<button\b(?=[^>]*data-tab=)[^>]*>", title_paths)
        fragment = _annotate_open_tags(fragment, r"<h2\b[^>]*>", title_paths)
        fragment = _annotate_open_tags(fragment, r"<p\b[^>]*>", body_paths)

    if template == "converge":
        groups = slide.get("groups") or []
        title_paths: list[str | None] = []
        item_paths: list[str | None] = []
        for group_index, group in enumerate(groups[:2]):
            title_key = _existing_key(group, ("title", "label"))
            title_paths.append(_slide_pointer(slide_index, "groups", group_index, title_key) if title_key else None)
            for item_index, item in enumerate((group.get("items") or [])[:2]):
                if isinstance(item, str):
                    item_paths.append(_slide_pointer(slide_index, "groups", group_index, "items", item_index))
        fragment = _annotate_open_tags(fragment, r"<h2\b[^>]*>", title_paths)
        fragment = _annotate_open_tags(fragment, r'<div\b(?=[^>]*class="[^"]*\bitem\b)[^>]*>', item_paths)
        fragment = _annotate_first(fragment, r'<div\b(?=[^>]*class="[^"]*\boutcome\b)[^>]*>', slot_pointer(slide, slide_index, "outcome"))

    if template == "quote":
        fragment = _annotate_first(fragment, r'<p\b(?=[^>]*class="[^"]*\bquote-text\b)[^>]*>', _slide_pointer(slide_index, "quote") if "quote" in slide else None)
        fragment = _annotate_first(fragment, r'<cite\b(?=[^>]*class="[^"]*\bsource\b)[^>]*>', _slide_pointer(slide_index, "source") if "source" in slide else None)

    if template == "metric" and isinstance(slide.get("metric"), dict):
        metric = slide["metric"]
        for class_name, key in (("value", "value"), ("unit", "unit"), ("caption", "caption")):
            editable = key != "value" or slide.get("variant") != "progress"
            fragment = _annotate_first(
                fragment,
                rf'<[a-z][a-z0-9]*\b(?=[^>]*class="[^"]*\b{class_name}\b)[^>]*>',
                _slide_pointer(slide_index, "metric", key) if editable and key in metric else None,
            )

    if template == "catalog-board":
        item_paths: list[tuple[str | None, str | None]] = []
        for group_index, group in enumerate(slide.get("groups") or []):
            if not isinstance(group, dict):
                continue
            for item_index, item in enumerate(group.get("items") or []):
                if not isinstance(item, dict):
                    continue
                title_key = _existing_key(item, ("title", "label"))
                body_key = _existing_key(item, ("body", "text"))
                item_paths.append((
                    _slide_pointer(slide_index, "groups", group_index, "items", item_index, title_key) if title_key else None,
                    _slide_pointer(slide_index, "groups", group_index, "items", item_index, body_key) if body_key else None,
                ))

        def catalog_paths(_open_tag: str, ordinal: int) -> tuple[str | None, list[str | None]]:
            if ordinal >= len(item_paths):
                return None, []
            return item_paths[ordinal][0], [item_paths[ordinal][1]]

        fragment = _annotate_article_blocks(fragment, r'class="[^"]*\bitem\b', catalog_paths)
    return fragment


def iter_editable_values(data: dict) -> Iterator[tuple[str, str]]:
    slides = data.get("slides") or []
    for slide_index, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        candidates: set[str] = {_slide_pointer(slide_index, "title")}
        top_level = (
            "kicker", "content", "note", "meta", "page_note", "badge", "media_note",
            "quote", "source", "outcome", "conclusion", "statement", "statement_body",
            "measurement_note", "measurement_meta", "artifact_title", "artifact_body",
            "aside", "aside_label", "step_number",
        )
        candidates.update(_slide_pointer(slide_index, key) for key in top_level if key in slide)
        for collection, title_keys, body_keys in (
            ("cards", ("title", "label", "h2"), ("body", "text", "p")),
            ("steps", ("title", "label", "h2"), ("body", "text", "p")),
            ("annotations", ("title", "label"), ("body", "text")),
        ):
            for item_index, item in enumerate(slide.get(collection) or []):
                if isinstance(item, str):
                    candidates.add(_slide_pointer(slide_index, collection, item_index))
                    continue
                for key in (*title_keys, *body_keys, "meta"):
                    if key in item:
                        candidates.add(_slide_pointer(slide_index, collection, item_index, key))
                if collection == "cards":
                    for image_index, evidence in enumerate(item.get("images") or []):
                        if isinstance(evidence, dict):
                            key = _existing_key(evidence, ("caption", "label"))
                            if key:
                                candidates.add(_slide_pointer(slide_index, collection, item_index, "images", image_index, key))
        for side_index, side in enumerate(slide.get("sides") or []):
            if not isinstance(side, dict):
                continue
            for key in ("title", "label", "body", "text", "lead", "result"):
                if key in side:
                    candidates.add(_slide_pointer(slide_index, "sides", side_index, key))
            for point_index, item in enumerate(side.get("points") or []):
                if isinstance(item, str):
                    candidates.add(_slide_pointer(slide_index, "sides", side_index, "points", point_index))
                elif isinstance(item, dict):
                    for key in ("title", "label", "body", "text", "meta"):
                        if key in item:
                            candidates.add(_slide_pointer(slide_index, "sides", side_index, "points", point_index, key))
            for evidence_index, evidence in enumerate(side.get("evidence") or []):
                if isinstance(evidence, dict):
                    key = _existing_key(evidence, ("caption", "label"))
                    if key:
                        candidates.add(_slide_pointer(slide_index, "sides", side_index, "evidence", evidence_index, key))
        for group_index, group in enumerate(slide.get("groups") or []):
            if not isinstance(group, dict):
                continue
            for key in ("title", "label", "meta"):
                if key in group:
                    candidates.add(_slide_pointer(slide_index, "groups", group_index, key))
            for item_index, item in enumerate(group.get("items") or []):
                if isinstance(item, str):
                    candidates.add(_slide_pointer(slide_index, "groups", group_index, "items", item_index))
                elif isinstance(item, dict):
                    for key in ("title", "label", "body", "text"):
                        if key in item:
                            candidates.add(_slide_pointer(slide_index, "groups", group_index, "items", item_index, key))
        for collection in ("metrics", "measurements"):
            for item_index, item in enumerate(slide.get(collection) or []):
                if isinstance(item, dict):
                    for key in ("label", "value"):
                        if key in item:
                            candidates.add(_slide_pointer(slide_index, collection, item_index, key))
        for point_index, point in enumerate(slide.get("points") or []):
            if isinstance(point, str):
                candidates.add(_slide_pointer(slide_index, "points", point_index))
        for table_index, table in enumerate(slide.get("tables") or []):
            if not isinstance(table, dict):
                continue
            if "title" in table:
                candidates.add(_slide_pointer(slide_index, "tables", table_index, "title"))
            for row_index, row in enumerate(table.get("rows") or []):
                if isinstance(row, list):
                    for column_index, cell in enumerate(row):
                        if isinstance(cell, str):
                            candidates.add(_slide_pointer(slide_index, "tables", table_index, "rows", row_index, column_index))
        for panel_index, panel in enumerate(slide.get("panels") or []):
            if isinstance(panel, dict):
                for key in ("title", "source", "render_title", "render_body"):
                    if key in panel:
                        candidates.add(_slide_pointer(slide_index, "panels", panel_index, key))
        for collection in ("metric", "insight", "chart"):
            item = slide.get(collection)
            if not isinstance(item, dict):
                continue
            if collection == "metric":
                allowed = ["unit", "caption"]
                if slide.get("variant") != "progress":
                    allowed.insert(0, "value")
                if slide.get("variant") == "delta":
                    allowed.extend(("change", "change_label"))
            else:
                allowed = ["title", "body"] if collection == "insight" else ["label"]
            for key in allowed:
                if key in item:
                    candidates.add(_slide_pointer(slide_index, collection, key))
        for node_index, node in enumerate(slide.get("nodes") or []):
            if isinstance(node, dict):
                for key in ("title", "body"):
                    if key in node:
                        candidates.add(_slide_pointer(slide_index, "nodes", node_index, key))
        for link_index, link in enumerate(slide.get("links") or []):
            if isinstance(link, dict) and "label" in link:
                candidates.add(_slide_pointer(slide_index, "links", link_index, "label"))
        for criterion_index, criterion in enumerate(slide.get("criteria") or []):
            if isinstance(criterion, str):
                candidates.add(_slide_pointer(slide_index, "criteria", criterion_index))
        for option_index, option in enumerate(slide.get("options") or []):
            if isinstance(option, dict) and "title" in option:
                candidates.add(_slide_pointer(slide_index, "options", option_index, "title"))
        axes = slide.get("axes")
        if isinstance(axes, dict):
            for key in ("x", "y"):
                if key in axes:
                    candidates.add(_slide_pointer(slide_index, "axes", key))
        for value in sorted(candidates):
            try:
                raw = get_pointer(data, value)
            except (KeyError, IndexError, ValueError):
                continue
            if isinstance(raw, (str, int, float)) and not isinstance(raw, bool):
                yield value, str(raw)


def editable_values(data: dict) -> dict[str, str]:
    return dict(iter_editable_values(data))
