#!/usr/bin/env python3
"""Deterministic capability candidates for an already structured outline."""
from __future__ import annotations

import re

from background_presets import template_background
from component_contracts import COMPONENT_CONTRACTS
from outline_schema import MEDIA_TEMPLATES, TEMPLATE_FAMILIES


MEDIA_MENU = {
    "inset": ["split-visual", "photo-split"],
    "interface": ["browser-showcase"],
    "canvas": ["editorial-canvas"],
    "edge_bleed": ["bleed-split"],
    "diagonal_bleed": ["diagonal-split"],
    "full_photo": ["photo-gradient"],
    "compound": ["editorial-feature", "catalog-board", "case-study-board", "annotated-showcase", "narrative-bento", "sequence-gallery"],
}


def _text(slide: dict) -> str:
    values = (
        slide.get("title"), slide.get("content"), slide.get("note"),
        slide.get("visual_task"), slide.get("media_intent"),
    )
    return " ".join(str(value or "") for value in values)


def _candidate(template: str, reason_code: str) -> dict:
    contract = COMPONENT_CONTRACTS[template]
    skeleton = {
        "template": template,
        "variant": contract["variants"][0],
        "decor": contract["decorations"][0],
        "background": template_background(template),
    }
    if template in MEDIA_TEMPLATES or template in {"case-study-board", "sequence-gallery"}:
        skeleton["media_frame"] = "content"
    return {"template": template, "reason_code": reason_code, "valid_skeleton": skeleton}


def slide_recommendation(slide: dict) -> dict | None:
    selected = slide["template"]
    candidates: list[dict] = []
    high_confidence = False

    steps = slide.get("steps") if isinstance(slide.get("steps"), list) else []
    cards = slide.get("cards") if isinstance(slide.get("cards"), list) else []
    groups = slide.get("groups") if isinstance(slide.get("groups"), list) else []
    metrics = slide.get("metrics") if isinstance(slide.get("metrics"), list) else []
    annotations = slide.get("annotations") if isinstance(slide.get("annotations"), list) else []
    image = slide.get("image") or slide.get("media") or slide.get("artifact_image")

    if image and len(annotations) == 3:
        candidates.append(_candidate("annotated-showcase", "IMAGE_WITH_THREE_ANNOTATIONS"))
        high_confidence = True
    elif len(groups) == 4 and len(metrics) == 3 and all(isinstance(group, dict) and len(group.get("items") or []) == 3 for group in groups):
        candidates.append(_candidate("catalog-board", "FOUR_GROUPS_THREE_ITEMS"))
        high_confidence = True
    elif len(metrics) == 2 and isinstance(slide.get("insight"), dict) and (image or isinstance(slide.get("chart"), dict)):
        candidates.append(_candidate("case-study-board", "CASE_EVIDENCE_METRICS_INSIGHT"))
        high_confidence = True
    elif slide.get("statement") and slide.get("quote") and len(cards) == 2:
        candidates.append(_candidate("narrative-bento", "THESIS_TWO_SUPPORTS_QUOTE"))
        high_confidence = True
    elif len(steps) == 3 and all(isinstance(step, dict) and step.get("image") for step in steps):
        candidates.append(_candidate("sequence-gallery", "THREE_VISUAL_STAGES"))
        high_confidence = True
    elif image and len(cards) == 3:
        candidates.append(_candidate("editorial-feature", "MAIN_VISUAL_THREE_SUPPORTS"))
        high_confidence = True
    elif slide.get("quote") and slide.get("source"):
        candidates.append(_candidate("quote", "EXPLICIT_QUOTE_SOURCE"))
        high_confidence = True
    elif isinstance(slide.get("metric"), dict):
        candidates.append(_candidate("metric", "EXPLICIT_SINGLE_METRIC"))
        high_confidence = True
    elif isinstance(slide.get("groups"), list) and slide.get("outcome"):
        candidates.append(_candidate("converge", "TWO_GROUPS_TO_OUTCOME"))
        high_confidence = True
    elif steps:
        count = len(steps)
        if count == 3:
            candidates.append(_candidate("three-steps", "THREE_EXPLAINED_STEPS"))
            high_confidence = True
        elif count == 4:
            candidates.append(_candidate("timeline", "FOUR_TEMPORAL_STAGES"))
        elif count in {6, 8}:
            candidates.append(_candidate("process-rail", f"{count}_SHORT_ACTIONS"))
            high_confidence = True
    elif len(cards) == 3:
        template = "recap" if slide.get("content") or slide.get("note") else "card-trio"
        candidates.append(_candidate(template, "THESIS_WITH_THREE_SUPPORTS" if template == "recap" else "ONE_FEATURE_TWO_SUPPORTS"))
    elif isinstance(slide.get("sides"), list) and len(slide["sides"]) == 2:
        sides = slide["sides"]
        point_counts = [len(side.get("points") or []) if isinstance(side, dict) else 0 for side in sides]
        if point_counts == [2, 2]:
            candidates.append(_candidate("comparison", "TWO_BY_TWO_COMPARISON"))
        elif point_counts == [3, 3]:
            candidates.append(_candidate("comparison-list", "ALIGNED_THREE_ROW_COMPARISON"))
        elif all(isinstance(side, dict) and (side.get("body") or side.get("text")) for side in sides):
            candidates.append(_candidate("tabs", "TWO_STATES_OF_ONE_OBJECT"))

    if image:
        text = _text(slide)
        if re.search(r"(?:全屏|满屏|铺底|铺满|整页照片)", text, re.I):
            candidates.insert(0, _candidate("photo-gradient", "EXPLICIT_FULL_PHOTO"))
            high_confidence = True
        if re.search(r"(?:斜切|斜杠|方向感|冲突)", text, re.I):
            candidates.insert(0, _candidate("diagonal-split", "EXPLICIT_DIAGONAL_DIRECTION"))
            high_confidence = True
        elif re.search(r"(?:出血|破框|边缘主视觉)", text, re.I):
            candidates.insert(0, _candidate("bleed-split", "EXPLICIT_EDGE_BLEED"))
            high_confidence = True
        if re.search(r"(?:界面截图|产品界面|网页截图|浏览器)", text, re.I):
            candidates.insert(0, _candidate("browser-showcase", "INTERFACE_AS_EVIDENCE"))
            high_confidence = True
        if re.search(r"(?:展陈|局部放大|批注|材料画布)", text, re.I):
            candidates.insert(0, _candidate("editorial-canvas", "EDITORIAL_MATERIAL_CANVAS"))

    deduped: list[dict] = []
    seen: set[str] = set()
    for item in candidates:
        if item["template"] not in seen:
            deduped.append(item)
            seen.add(item["template"])
    if not deduped:
        return None
    recommended = [item["template"] for item in deduped]
    return {
        "id": slide["id"],
        "selected": selected,
        "selected_family": TEMPLATE_FAMILIES[selected],
        "candidates": deduped,
        "decision": "review" if high_confidence and selected not in recommended else "pass",
    }


def recommend_outline(data: dict) -> dict:
    slides = [item for slide in data.get("slides") or [] if (item := slide_recommendation(slide))]
    return {
        "schema_version": "oil-slides.recommend/v1",
        "media_composition_menu": MEDIA_MENU,
        "slides": slides,
        "review_count": sum(item["decision"] == "review" for item in slides),
    }
