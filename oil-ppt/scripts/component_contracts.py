#!/usr/bin/env python3
"""Curated component choices and media policies owned by oil-ppt."""
from __future__ import annotations

from component_registry import (
    CLOSED_STRUCTURE_TEMPLATES,
    COMPONENT_CONTRACTS,
    COMPONENT_QUALITY,
    PAGE_BLEND_TEMPLATES,
    VARIANT_QUALITY,
)


PAGE_BLEND_ROLE_TOKENS = (
    "concept", "illustration", "illustrative", "abstract",
    "概念", "插画", "抽象", "机制", "关系",
)


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
    base.setdefault(
        "visual_energy",
        "anchor"
        if base["silhouette"] in {"bleed", "browser", "canvas", "diagram", "metric", "rail", "timeline"}
        else "structured",
    )
    return base


def effective_media_surface(slide: dict) -> str:
    """Return whether media keeps a component shell or blends into the page."""
    explicit = str(slide.get("media_surface") or "").strip()
    if explicit:
        return explicit
    template = str(slide.get("template") or "")
    if template not in PAGE_BLEND_TEMPLATES:
        return "component"
    if str(slide.get("media_frame") or "").strip() == "self-framed":
        return "page-blend"
    fidelity = str(slide.get("media_fidelity") or "").lower()
    role = str(slide.get("media_role") or "").lower()
    if fidelity == "illustrative" or any(token in role for token in PAGE_BLEND_ROLE_TOKENS):
        return "page-blend"
    return "component"


def effective_media_fit(slide: dict, *, fallback: str = "cover", fidelity: str | None = None) -> str:
    """Choose crop-vs-preserve consistently for planning and rendering."""
    explicit = str(slide.get("media_fit") or "").strip()
    if explicit:
        return explicit
    resolved_fidelity = str(fidelity or slide.get("media_fidelity") or "").lower()
    if resolved_fidelity == "strict" or effective_media_surface(slide) == "page-blend":
        return "contain"
    if resolved_fidelity == "contextual":
        return "cover"
    return fallback


def effective_frame_owner(slide: dict) -> str:
    """Resolve frame ownership after the media-surface policy is applied."""
    if effective_media_surface(slide) == "page-blend":
        return "none"
    return quality_for(str(slide.get("template") or ""), slide.get("variant"))["frame_owner"]


def normalize_component_choices(slide: dict, index: int) -> None:
    contract = choices_for(slide["template"])
    variant = slide.get("variant")
    decor = slide.get("decor")
    if not isinstance(variant, str) or not variant.strip():
        allowed = ", ".join(contract["variants"])
        raise SystemExit(
            f"Outline slide {index} must explicitly choose variant for {slide['template']!r}; allowed: {allowed}."
        )
    if not isinstance(decor, str) or not decor.strip():
        allowed = ", ".join(contract["decorations"])
        raise SystemExit(
            f"Outline slide {index} must explicitly choose decor for {slide['template']!r}; allowed: {allowed}."
        )
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
