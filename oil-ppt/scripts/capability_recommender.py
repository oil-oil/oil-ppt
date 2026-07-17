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

DATA_RELATIONSHIP_QUESTION = "真实数值要回答什么：比较类别、查看时间变化、解释整体构成，还是观察两个指标的关系与样本分布？"
DATA_RELATIONSHIPS = {
    "category-comparison": "比较类别",
    "trend": "查看时间变化",
    "composition": "解释整体构成",
    "relationship": "观察两指标关系与样本分布",
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
    nodes = slide.get("nodes") if isinstance(slide.get("nodes"), list) else []
    links = slide.get("links") if isinstance(slide.get("links"), list) else []
    criteria = slide.get("criteria") if isinstance(slide.get("criteria"), list) else []
    options = slide.get("options") if isinstance(slide.get("options"), list) else []
    image = slide.get("image") or slide.get("media") or slide.get("artifact_image")
    secondary_image = slide.get("secondary_image")
    data = slide.get("data") if isinstance(slide.get("data"), dict) else None
    axes = slide.get("axes") if isinstance(slide.get("axes"), dict) else None

    evidence_sides = [
        side for side in (slide.get("sides") or [])
        if isinstance(side, dict) and isinstance(side.get("evidence"), list) and len(side["evidence"]) == 2
    ] if isinstance(slide.get("sides"), list) else []
    media_cards = [
        card for card in cards[:2]
        if isinstance(card, dict) and isinstance(card.get("images"), list) and len(card["images"]) == 2
    ]

    if (
        selected == "relationship-map"
        and 4 <= len(nodes) <= 6
        and len(links) == len(nodes) - 1
        and sum(isinstance(node, dict) and node.get("emphasis") is True for node in nodes) == 1
    ):
        candidates.append(_candidate("relationship-map", "ONE_CENTER_THREE_TO_FIVE_NAMED_RELATIONSHIPS"))
    elif (
        selected == "decision-matrix"
        and len(criteria) == 3
        and len(options) == 3
        and all(isinstance(option, dict) and len(option.get("scores") or []) == 3 for option in options)
    ):
        candidates.append(_candidate("decision-matrix", "THREE_OPTIONS_THREE_SHARED_CRITERIA"))
    elif selected == "cycle" and len(steps) == 4 and slide.get("statement") and slide.get("statement_body"):
        candidates.append(_candidate("cycle", "FOUR_STAGES_WITH_FEEDBACK_LOOP"))
    elif axes is not None and len(groups) == 4 and sum(
        isinstance(group, dict) and group.get("emphasis") is True for group in groups
    ) == 1:
        candidates.append(_candidate("quadrant", "TWO_AXES_FOUR_GROUPS_ONE_EMPHASIS"))
    elif selected == "tier-stack" and len(steps) == 4:
        candidates.append(_candidate("tier-stack", "FOUR_ORDERED_LEVELS", variant=str(slide.get("variant") or "funnel")))
    elif selected == "data-story" and data is not None:
        variant = str(slide.get("variant") or "")
        item = _candidate("data-story", f"REAL_VALUES_{variant.replace('-', '_').upper()}", variant=variant)
        item["selection_question"] = DATA_RELATIONSHIP_QUESTION
        item["relationship_answer"] = DATA_RELATIONSHIPS[variant]
        candidates.append(item)
    elif image and secondary_image and len(cards) == 3:
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
        metric_variant = str(slide.get("variant") or "default")
        reason = {
            "default": "EXPLICIT_SINGLE_METRIC",
            "delta": "EXPLICIT_METRIC_WITH_PRIOR_CHANGE",
            "progress": "EXPLICIT_METRIC_AGAINST_TARGET",
        }.get(metric_variant, "EXPLICIT_SINGLE_METRIC")
        candidates.append(_candidate("metric", reason, variant=metric_variant))
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
        "data_relationship_question": DATA_RELATIONSHIP_QUESTION,
        "media_composition_menu": MEDIA_MENU,
        "slides": slides,
        "review_count": sum(item["decision"] == "review" for item in slides),
    }
