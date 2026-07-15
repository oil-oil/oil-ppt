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


def _candidate(template: str, reason_code: str, *, variant: str | None = None) -> dict:
    contract = COMPONENT_CONTRACTS[template]
    skeleton = {
        "template": template,
        "variant": variant or contract["variants"][0],
        "decor": contract["decorations"][0],
        "background": template_background(template),
    }
    if (
        template in MEDIA_TEMPLATES
        or template == "sequence-gallery"
        or (template == "case-study-board" and variant == "evidence")
        or variant in {"visual-evidence", "media-evidence"}
    ):
        skeleton["media_frame"] = "content"
    return {"template": template, "reason_code": reason_code, "choice_patch": skeleton}


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
    secondary_image = slide.get("secondary_image")

    evidence_sides = [
        side for side in (slide.get("sides") or [])
        if isinstance(side, dict) and isinstance(side.get("evidence"), list) and len(side["evidence"]) == 2
    ] if isinstance(slide.get("sides"), list) else []
    media_cards = [
        card for card in cards[:2]
        if isinstance(card, dict) and isinstance(card.get("images"), list) and len(card["images"]) == 2
    ]

    if image and secondary_image and len(cards) == 3:
        candidates.append(_candidate("editorial-feature", "MAIN_AND_SECONDARY_VISUAL_THREE_SUPPORTS", variant="hero-collage"))
        high_confidence = True
    elif len(evidence_sides) == 2:
        candidates.append(_candidate("comparison", "TWO_SIDES_WITH_PAIRED_EVIDENCE", variant="visual-evidence"))
        high_confidence = True
    elif len(cards) == 3 and len(media_cards) == 2:
        candidates.append(_candidate("card-trio", "TWO_MEDIA_CARDS_AND_DECISION", variant="media-evidence"))
        high_confidence = True
    elif image and len(annotations) == 3:
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
            text = _text(slide)
            if re.search(r"(?:时间|年份|季度|里程碑|阶段|演进|历程)", text, re.I):
                candidates.append(_candidate("timeline", "FOUR_TEMPORAL_STAGES"))
                high_confidence = True
            else:
                terminal = isinstance(steps[-1], dict) and str(steps[-1].get("role") or "") in {"result", "outcome", "delivery"}
                candidates.append(_candidate("process-cards", "FOUR_EXPLAINED_STEPS", variant="terminal-focus" if terminal else "linear"))
                high_confidence = True
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
        explicit_diagonal = bool(re.search(r"(?:斜切|斜杠|方向感|方向冲突)", text, re.I))
        semantic_diagonal = bool(re.search(r"(?:转向|转换|转化|过渡|分界|边界|对立|张力|从.{0,18}(?:到|变成|变为|走向))", text, re.I))
        protected_evidence = selected in {
            "cover", "end", "browser-showcase", "annotated-showcase", "case-study-board",
            "editorial-canvas", "bleed-split", "photo-gradient",
        } or slide.get("media_fidelity") == "strict"
        if explicit_diagonal or (semantic_diagonal and not protected_evidence):
            candidates.insert(0, _candidate("diagonal-split", "DIRECTION_TRANSITION_OR_BOUNDARY"))
            high_confidence = True
        elif re.search(r"(?:出血|破框|边缘主视觉)", text, re.I):
            candidates.insert(0, _candidate("bleed-split", "EXPLICIT_EDGE_BLEED"))
            high_confidence = True
        if re.search(r"(?:界面截图|产品界面|网页截图|浏览器)", text, re.I):
            candidates.insert(0, _candidate("browser-showcase", "INTERFACE_AS_EVIDENCE"))
            high_confidence = True
        if re.search(r"(?:展陈|局部放大|批注|材料画布)", text, re.I):
            candidates.insert(0, _candidate("editorial-canvas", "EDITORIAL_MATERIAL_CANVAS"))

    concept_media = (
        str(slide.get("media_fidelity") or "").lower() == "illustrative"
        or bool(re.search(r"(?:概念|插画|抽象|机制|关系|concept|illustrat|abstract)", str(slide.get("media_role") or ""), re.I))
    )
    if concept_media:
        for item in candidates:
            if item["template"] in {"split-visual", "editorial-feature"}:
                item["choice_patch"]["media_surface"] = "page-blend"

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
        "schema_version": "oil-ppt.recommend/v1",
        "media_composition_menu": MEDIA_MENU,
        "slides": slides,
        "review_count": sum(item["decision"] == "review" for item in slides),
    }
