#!/usr/bin/env python3
"""Deterministic capability candidates for an already structured outline.

Recommendations deliberately use typed fields and exact cardinalities. Free-text
copy can describe the same idea in too many ways to be a safe component switch.
"""
from __future__ import annotations

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


def _candidate(
    template: str,
    reason_code: str,
    *,
    variant: str | None = None,
    confidence: str = "high",
) -> dict:
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
    return {
        "template": template,
        "reason_code": reason_code,
        "confidence": confidence,
        "choice_patch": skeleton,
    }


def slide_recommendation(slide: dict) -> dict | None:
    selected = slide["template"]
    candidates: list[dict] = []
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
    elif len(evidence_sides) == 2:
        candidates.append(_candidate("comparison", "TWO_SIDES_WITH_PAIRED_EVIDENCE", variant="visual-evidence"))
    elif len(cards) == 3 and len(media_cards) == 2:
        candidates.append(_candidate("card-trio", "TWO_MEDIA_CARDS_AND_DECISION", variant="media-evidence"))
    elif image and len(annotations) == 3:
        candidates.append(_candidate("annotated-showcase", "IMAGE_WITH_THREE_ANNOTATIONS"))
    elif len(groups) == 4 and len(metrics) == 3 and all(isinstance(group, dict) and len(group.get("items") or []) == 3 for group in groups):
        candidates.append(_candidate("catalog-board", "FOUR_GROUPS_THREE_ITEMS"))
    elif len(metrics) == 2 and isinstance(slide.get("insight"), dict) and (image or isinstance(slide.get("chart"), dict)):
        candidates.append(_candidate("case-study-board", "CASE_EVIDENCE_METRICS_INSIGHT"))
    elif slide.get("statement") and slide.get("quote") and len(cards) == 2:
        candidates.append(_candidate("narrative-bento", "THESIS_TWO_SUPPORTS_QUOTE"))
    elif len(steps) == 3 and all(isinstance(step, dict) and step.get("image") for step in steps):
        candidates.append(_candidate("sequence-gallery", "THREE_VISUAL_STAGES"))
    elif image and len(cards) == 3:
        candidates.append(_candidate("editorial-feature", "MAIN_VISUAL_THREE_SUPPORTS"))
    elif slide.get("quote") and slide.get("source"):
        candidates.append(_candidate("quote", "EXPLICIT_QUOTE_SOURCE"))
    elif isinstance(slide.get("metric"), dict):
        candidates.append(_candidate("metric", "EXPLICIT_SINGLE_METRIC"))
    elif len(groups) == 2 and slide.get("outcome"):
        candidates.append(_candidate("converge", "TWO_GROUPS_TO_OUTCOME"))
    elif steps:
        count = len(steps)
        if count == 3:
            candidates.append(_candidate("three-steps", "THREE_EXPLAINED_STEPS"))
        elif count == 4:
            # Four items alone do not distinguish chronology from a procedure.
            # Keep both discoverable without pressuring the selected component.
            candidates.extend([
                _candidate("timeline", "FOUR_STAGES_POSSIBLY_TEMPORAL", confidence="candidate"),
                _candidate("process-cards", "FOUR_STAGES_POSSIBLY_PROCEDURAL", variant="linear", confidence="candidate"),
            ])
        elif count in {6, 8}:
            candidates.append(_candidate("process-rail", f"{count}_SHORT_ACTIONS"))
    elif len(cards) == 3:
        template = "recap" if slide.get("content") or slide.get("note") else "card-trio"
        candidates.append(_candidate(
            template,
            "THESIS_WITH_THREE_SUPPORTS" if template == "recap" else "ONE_FEATURE_TWO_SUPPORTS",
            confidence="candidate",
        ))
    elif isinstance(slide.get("sides"), list) and len(slide["sides"]) == 2:
        sides = slide["sides"]
        point_counts = [len(side.get("points") or []) if isinstance(side, dict) else 0 for side in sides]
        if point_counts == [2, 2]:
            candidates.append(_candidate("comparison", "TWO_BY_TWO_COMPARISON", confidence="candidate"))
        elif point_counts == [3, 3]:
            candidates.append(_candidate("comparison-list", "ALIGNED_THREE_ROW_COMPARISON", confidence="candidate"))
        elif all(isinstance(side, dict) and (side.get("body") or side.get("text")) for side in sides):
            candidates.append(_candidate("tabs", "TWO_STATES_OF_ONE_OBJECT", confidence="candidate"))

    concept_media = str(slide.get("media_fidelity") or "").lower() == "illustrative"
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
    recommended = [item["template"] for item in deduped if item["confidence"] == "high"]
    return {
        "id": slide["id"],
        "selected": selected,
        "selected_family": TEMPLATE_FAMILIES[selected],
        "candidates": deduped,
        "decision": "review" if recommended and selected not in recommended else "pass",
    }


def recommend_outline(data: dict) -> dict:
    slides = [item for slide in data.get("slides") or [] if (item := slide_recommendation(slide))]
    return {
        "schema_version": "oil-ppt.recommend/v1",
        "media_composition_menu": MEDIA_MENU,
        "slides": slides,
        "review_count": sum(item["decision"] == "review" for item in slides),
    }
