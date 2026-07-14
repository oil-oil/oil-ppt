#!/usr/bin/env python3
"""Deck-level rhythm and media-composition checks for oil-ppt outlines."""
from __future__ import annotations

import json
from collections import Counter

from background_presets import effective_background
from capability_recommender import recommend_outline
from component_contracts import COMPONENT_CONTRACTS, quality_for
from media_assets import outline_media_bindings
from outline_schema import TEMPLATE_FAMILIES


EXCLUDED = {"cover", "end", "section"}
MEDIA_KEYS = ("image", "media", "artifact_image")
BLEED_TEMPLATES = ("bleed-split", "diagonal-split", "photo-gradient")
BACKGROUND_CLASSES = {
    "grid-fade": "grid", "grid-wide": "grid",
    "soft-spotlight": "light", "block-field": "block", "media-owned": "media",
}


def has_media(slide: dict) -> bool:
    return bool(outline_media_bindings(slide))


def slide_quality(slide: dict) -> dict:
    return quality_for(slide["template"], slide.get("variant"))


def issue(
    level: str,
    code: str,
    message: str,
    slide_ids: list[str] | None = None,
    suggestion: dict | None = None,
    *,
    blocking: bool = False,
) -> dict:
    result = {
        "level": level,
        "blocking": blocking,
        "code": code,
        "message": message,
        "slides": slide_ids or [],
    }
    if suggestion:
        result["suggestion"] = suggestion
    return result


def suggested_background(slide: dict, current: str) -> str:
    silhouette = slide_quality(slide)["silhouette"]
    candidates = {
        "focal": ("block-field", "soft-spotlight", "grid-fade"),
        "split": ("soft-spotlight", "grid-fade", "grid-wide"),
        "bleed": ("soft-spotlight", "grid-fade", "block-field"),
        "browser": ("soft-spotlight", "grid-fade", "grid-wide"),
        "canvas": ("grid-wide", "grid-fade", "block-field"),
        "diagram": ("grid-wide", "grid-fade", "block-field"),
        "rail": ("grid-wide", "grid-fade", "block-field"),
        "timeline": ("grid-wide", "grid-fade", "block-field"),
        "step-grid": ("grid-wide", "grid-fade", "block-field"),
        "card-grid": ("grid-fade", "block-field", "soft-spotlight"),
        "two-panel": ("grid-fade", "block-field", "soft-spotlight"),
        "matrix": ("grid-fade", "grid-wide", "block-field"),
        "metric": ("soft-spotlight", "block-field", "grid-fade"),
        "editorial-list": ("block-field", "grid-fade", "soft-spotlight"),
        "editorial-feature": ("grid-fade", "soft-spotlight", "grid-wide"),
        "catalog": ("grid-fade", "grid-wide", "soft-spotlight"),
        "case-board": ("grid-fade", "soft-spotlight", "grid-wide"),
        "annotated": ("grid-fade", "soft-spotlight", "grid-wide"),
        "bento": ("grid-fade", "soft-spotlight", "grid-wide"),
        "gallery": ("grid-fade", "grid-wide", "soft-spotlight"),
    }.get(silhouette, ("grid-fade", "block-field", "soft-spotlight"))
    current_class = BACKGROUND_CLASSES[current]
    return next(
        (value for value in candidates if value != current and BACKGROUND_CLASSES[value] != current_class),
        next((value for value in candidates if value != current), "grid-fade"),
    )


def content_segments(slides: list[dict]) -> list[list[dict]]:
    segments: list[list[dict]] = []
    current: list[dict] = []
    for slide in slides:
        template = slide["template"]
        if template == "section":
            if current:
                segments.append(current)
            current = []
            continue
        if template in {"cover", "end"}:
            continue
        current.append(slide)
    if current:
        segments.append(current)
    return segments


def coverage_summary(data: dict) -> dict:
    """Expose deck-level capability usage without pretending every deck needs everything."""
    slides = data.get("slides") or []
    content = [slide for slide in slides if slide.get("template") not in EXCLUDED]
    templates = Counter(str(slide.get("template") or "") for slide in content)
    families = Counter(TEMPLATE_FAMILIES[slide["template"]] for slide in content)
    silhouettes = Counter(slide_quality(slide)["silhouette"] for slide in content)
    signatures = Counter(slide_quality(slide)["layout_signature"] for slide in content)
    backgrounds = Counter(effective_background(slide) for slide in content)
    background_classes = Counter(BACKGROUND_CLASSES[effective_background(slide)] for slide in content)
    media = [slide for slide in content if has_media(slide)]
    bleed = [slide for slide in media if slide_quality(slide)["silhouette"] == "bleed"]
    return {
        "content_slides": len(content),
        "templates": dict(templates),
        "families": dict(families),
        "silhouettes": dict(silhouettes),
        "layout_signatures": dict(signatures),
        "backgrounds": dict(backgrounds),
        "background_classes": dict(background_classes),
        "media": {"slides": len(media), "full_bleed": len(bleed)},
        "emphasis": {
            "highlight": sum(bool(slide.get("highlight")) for slide in content),
            "backdrop_text": sum(bool(slide.get("backdrop_text")) for slide in content),
            "quote": templates.get("quote", 0),
        },
        "available_templates_not_used": sorted(set(COMPONENT_CONTRACTS) - set(templates)),
    }


def audit_outline(data: dict) -> list[dict]:
    slides = data.get("slides") or []
    results: list[dict] = []
    content = [slide for slide in slides if slide["template"] not in EXCLUDED]
    for slide in slides:
        if not has_media(slide):
            continue
        declared = slide.get("media_frame")
        if declared not in {"content", "self-framed"}:
            results.append(issue(
                "error", "missing-media-frame",
                "Image slides must declare media_frame as 'content' or 'self-framed'.",
                [slide["id"]],
                blocking=True,
            ))
            continue
        owner = slide_quality(slide)["frame_owner"]
        if owner == "template" and declared != "content":
            results.append(issue(
                "error", "double-frame-risk",
                f"Template {slide['template']!r} owns the outer frame; its media must be frameless content.",
                [slide["id"]],
                blocking=True,
            ))
    require_media = data.get("media_policy", "required") != "text-only"
    media_slides = [slide for slide in content if has_media(slide)]
    if require_media and not media_slides:
        results.append(issue(
            "error", "media-required",
            "media_policy='required' needs at least one visible media slide in the content deck; use a real local asset or explicitly confirm text-only.",
            [slide["id"] for slide in content],
            blocking=True,
        ))
    if not content:
        return results

    capability_review = recommend_outline(data)
    for review in capability_review["slides"]:
        if review["decision"] != "review":
            continue
        candidates = [item["template"] for item in review["candidates"]]
        results.append(issue(
            "warning", "specialized-capability-suggestion",
            f"Slide {review['id']!r} may also fit a specialized component; the selected component remains valid when it satisfies its contract.",
            [review["id"]],
            {
                "action": "consider a specialized candidate only when it expresses the content relation more clearly",
                "templates": candidates,
                "candidates": [item["choice_patch"] for item in review["candidates"]],
                "candidate_slides": [review["id"]],
            },
        ))

    if require_media and media_slides:
        minimum = (len(content) + 4) // 5
        if len(media_slides) < minimum:
            missing_media = [slide for slide in content if not has_media(slide)]
            results.append(issue(
                "warning", "media-coverage",
                f"The content deck needs at least one real visual every five slides; found {len(media_slides)}/{len(content)}, need {minimum}.",
                [slide["id"] for slide in missing_media],
            ))

    heavy = [slide for slide in content if slide_quality(slide)["surface_density"] == "heavy"]
    heavy_ratio = len(heavy) / len(content)
    if len(content) >= 8 and heavy_ratio > .48:
        results.append(issue(
            "warning", "surface-dominance",
            f"{len(heavy)}/{len(content)} content slides use surface-heavy card or panel silhouettes; keep this at 48% or below.",
            [slide["id"] for slide in heavy],
        ))

    if len(content) >= 8:
        template_counts = Counter(slide["template"] for slide in content)
        dominant_template, dominant_count = template_counts.most_common(1)[0]
        if dominant_count >= 4 and dominant_count / len(content) > .38:
            results.append(issue(
                "warning", "component-dominance",
                f"Template {dominant_template!r} appears on {dominant_count}/{len(content)} content slides; semantic correctness is not enough when the deck silhouette becomes repetitive.",
                [slide["id"] for slide in content if slide["template"] == dominant_template],
                {
                    "action": "reclassify some pages by content relation before changing decoration",
                    "available_families": sorted(set(TEMPLATE_FAMILIES.values())),
                },
            ))

        focal = [slide for slide in content if slide_quality(slide)["silhouette"] in {"focal", "metric"}]
        if len(content) >= 10 and not focal:
            candidates = [content[len(content) // 3], content[(len(content) * 2) // 3]]
            results.append(issue(
                "warning", "missing-focal-beat",
                "The content deck has no dedicated focal pause such as a quote, metric, or single-judgment page.",
                [slide["id"] for slide in candidates],
                {
                    "action": "only if the content supports it, convert one candidate into a focal beat",
                    "templates": ["quote", "metric"],
                    "candidate_slides": [slide["id"] for slide in candidates],
                },
            ))

    if require_media and len(content) >= 8 and len(media_slides) >= 2:
        bleed_media = [slide for slide in media_slides if slide_quality(slide)["silhouette"] == "bleed"]
        if not bleed_media:
            eligible = [slide for slide in media_slides if slide["template"] not in BLEED_TEMPLATES]
            candidates = eligible[1::3][:3] or eligible[:2]
            results.append(issue(
                "warning", "missing-cinematic-beat",
                f"All {len(media_slides)} media slides stay inside inset frames; the deck never uses a full-screen or edge-bleed visual beat.",
                [slide["id"] for slide in media_slides],
                {
                    "action": "consider one full-screen media composition where the image can carry the argument",
                    "templates": list(BLEED_TEMPLATES),
                    "candidate_slides": [slide["id"] for slide in candidates],
                },
            ))

        media_silhouettes = Counter(slide_quality(slide)["silhouette"] for slide in media_slides)
        if len(media_slides) >= 3 and len(media_silhouettes) == 1:
            results.append(issue(
                "warning", "media-shape-monotony",
                f"All {len(media_slides)} media slides use silhouette {next(iter(media_silhouettes))!r}.",
                [slide["id"] for slide in media_slides],
                {
                    "action": "mix inset, canvas, browser, split, and bleed compositions according to what the material proves",
                    "templates": [
                        "split-visual", "photo-split", "browser-showcase", "editorial-canvas",
                        *BLEED_TEMPLATES,
                    ],
                },
            ))

        inset_run: list[dict] = []
        for slide in [*content, None]:
            is_inset_media = (
                slide is not None
                and has_media(slide)
                and slide_quality(slide)["silhouette"] != "bleed"
            )
            if is_inset_media:
                inset_run.append(slide)
                continue
            if len(inset_run) >= 3:
                target = inset_run[len(inset_run) // 2]
                results.append(issue(
                    "warning", "inset-media-run",
                    f"{len(inset_run)} consecutive media slides remain inset inside the safe area.",
                    [item["id"] for item in inset_run],
                    {
                        "action": "if the middle image is strong enough, use one edge-bleed composition",
                        "templates": list(BLEED_TEMPLATES),
                        "candidate_slides": [target["id"]],
                    },
                ))
            inset_run = []

    if len(content) >= 8:
        backgrounds = [effective_background(slide) for slide in content]
        counts = Counter(backgrounds)
        dominant, dominant_count = counts.most_common(1)[0]
        if dominant != "media-owned" and (len(counts) == 1 or dominant_count / len(content) > .72):
            dominant_slides = [slide for slide in content if effective_background(slide) == dominant]
            candidates = dominant_slides[2::4] or dominant_slides[len(dominant_slides) // 2:len(dominant_slides) // 2 + 1]
            candidates = candidates[:3]
            changes = {slide["id"]: suggested_background(slide, dominant) for slide in candidates}
            results.append(issue(
                "warning", "background-monotony",
                f"Background {dominant!r} appears on {dominant_count}/{len(content)} content slides; introduce a small number of deliberate background changes.",
                [slide["id"] for slide in dominant_slides],
                {"set_background": changes},
            ))

        classes = Counter(BACKGROUND_CLASSES[value] for value in backgrounds)
        dominant_class, dominant_class_count = classes.most_common(1)[0]
        if dominant_class != "media" and len(counts) > 1 and dominant_class_count / len(content) > .72:
            same_class = [slide for slide in content if BACKGROUND_CLASSES[effective_background(slide)] == dominant_class]
            candidates = same_class[2::4][:3] or same_class[:1]
            changes = {slide["id"]: suggested_background(slide, effective_background(slide)) for slide in candidates}
            results.append(issue(
                "warning", "background-class-monotony",
                f"Perceptually similar {dominant_class!r} backgrounds appear on {dominant_class_count}/{len(content)} content slides, even though preset names differ.",
                [slide["id"] for slide in same_class],
                {"set_background": changes},
            ))

        run: list[dict] = []
        run_background = ""
        for slide in [*content, None]:
            background = effective_background(slide) if slide is not None else ""
            if slide is not None and (not run or background == run_background):
                if not run:
                    run_background = background
                run.append(slide)
                continue
            if len(run) >= 5 and run_background != "media-owned":
                target = run[len(run) // 2]
                results.append(issue(
                    "warning", "background-run",
                    f"{len(run)} consecutive content slides use background {run_background!r}.",
                    [item["id"] for item in run],
                    {"set_background": {target["id"]: suggested_background(target, run_background)}},
                ))
            run = [slide] if slide is not None else []
            run_background = background

        highlighted = [slide for slide in content if slide.get("highlight")]
        if not highlighted:
            candidates = content[2::4][:4] or content[:1]
            results.append(issue(
                "warning", "highlight-absence",
                "Long decks have no title marker highlights; choose a few key titles rather than emphasizing every page.",
                [slide["id"] for slide in candidates],
                {
                    "action": "set highlight to one exact phrase inside title",
                    "candidate_slides": [slide["id"] for slide in candidates],
                },
            ))
        elif len(highlighted) / len(content) > .4:
            results.append(issue(
                "warning", "highlight-saturation",
                f"{len(highlighted)}/{len(content)} content slides use title highlights; keep emphasis selective.",
                [slide["id"] for slide in highlighted],
                {"action": "remove highlight from supporting slides"},
            ))

        backdrops = [slide for slide in content if slide.get("backdrop_text")]
        if len(backdrops) / len(content) > .3:
            results.append(issue(
                "warning", "backdrop-saturation",
                f"{len(backdrops)}/{len(content)} content slides use oversized background type; keep it as an occasional rhythm change.",
                [slide["id"] for slide in backdrops],
                {"action": "remove backdrop_text from supporting slides"},
            ))

    for segment_index, segment in enumerate(content_segments(slides), start=1):
        if not segment:
            continue
        silhouettes = [slide_quality(slide)["silhouette"] for slide in segment]
        signatures = [slide_quality(slide)["layout_signature"] for slide in segment]
        start = 0
        while start < len(segment):
            end = start + 1
            while end < len(segment) and silhouettes[end] == silhouettes[start]:
                end += 1
            if end - start >= 3:
                run = segment[start:end]
                results.append(issue(
                    "warning", "repeated-silhouette",
                    f"Section {segment_index} repeats silhouette {silhouettes[start]!r} for {len(run)} consecutive slides.",
                    [slide["id"] for slide in run],
                ))
            start = end

        start = 0
        while start < len(segment):
            end = start + 1
            while end < len(segment) and signatures[end] == signatures[start]:
                end += 1
            if end - start >= 3:
                run = segment[start:end]
                results.append(issue(
                    "warning", "repeated-layout-signature",
                    f"Section {segment_index} repeats perceived layout {signatures[start]!r} for {len(run)} consecutive slides; mirroring or changing decoration does not create a new rhythm.",
                    [slide["id"] for slide in run],
                ))
            start = end

        if len(segment) >= 6:
            for start in range(0, len(segment) - 5):
                window = segment[start:start + 6]
                distinct = {slide_quality(slide)["silhouette"] for slide in window}
                if len(distinct) < 3:
                    results.append(issue(
                        "warning", "low-rhythm-variety",
                        f"Section {segment_index} has only {len(distinct)} silhouettes across six consecutive content slides.",
                        [slide["id"] for slide in window],
                    ))

        anchors = [slide for slide in segment if slide_quality(slide)["visual_energy"] == "anchor"]
        if len(segment) >= 5 and not anchors:
            results.append(issue(
                "warning", "missing-visual-anchor",
                f"Section {segment_index} has {len(segment)} content slides but no visual anchor.",
                [slide["id"] for slide in segment],
            ))

        if require_media and len(segment) >= 5:
            segment_media = [slide for slide in segment if has_media(slide)]
            minimum = (len(segment) + 4) // 5
            if len(segment_media) < minimum:
                results.append(issue(
                    "warning", "missing-section-media",
                    f"Section {segment_index} has {len(segment)} content slides but only {len(segment_media)} media slide(s); need {minimum}.",
                    [slide["id"] for slide in segment],
                ))
            else:
                run: list[dict] = []
                for slide in [*segment, None]:
                    if slide is not None and not has_media(slide):
                        run.append(slide)
                        continue
                    if len(run) >= 5:
                        results.append(issue(
                            "warning", "media-gap",
                            f"Section {segment_index} has {len(run)} consecutive content slides without media.",
                            [item["id"] for item in run],
                        ))
                    run = []

    return results


def audit_summary(data: dict) -> dict:
    results = audit_outline(data)
    review = recommend_outline(data)
    return {
        "status": (
            "error" if any(item["blocking"] for item in results)
            else "warning" if any(item["level"] == "warning" for item in results)
            else "ok"
        ),
        "issues": results,
        "counts": dict(Counter(item["level"] for item in results)),
        "coverage": coverage_summary(data),
        "capability_review": {
            "review_count": review["review_count"],
            "slides": [item for item in review["slides"] if item["decision"] == "review"],
        },
    }


def enforce_outline_quality(data: dict) -> list[dict]:
    results = audit_outline(data)
    for item in results:
        if item["level"] == "warning":
            suffix = f" Slides: {', '.join(item['slides'])}." if item["slides"] else ""
            suggestion = f" Suggestion: {json.dumps(item['suggestion'], ensure_ascii=False)}" if item.get("suggestion") else ""
            print(f"[WARN] {item['code']}: {item['message']}{suffix}{suggestion}")
    errors = [item for item in results if item["blocking"]]
    if errors:
        lines = []
        for item in errors:
            suffix = f" Slides: {', '.join(item['slides'])}." if item["slides"] else ""
            suggestion = f" Suggestion: {json.dumps(item['suggestion'], ensure_ascii=False)}" if item.get("suggestion") else ""
            lines.append(f"{item['code']}: {item['message']}{suffix}{suggestion}")
        raise SystemExit("Deck quality audit failed:\n- " + "\n- ".join(lines))
    return results
