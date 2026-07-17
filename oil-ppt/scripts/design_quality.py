#!/usr/bin/env python3
"""Deck-level rhythm and media-composition checks for oil-ppt outlines."""
from __future__ import annotations

import json
from collections import Counter

from background_presets import effective_background
from capability_recommender import recommend_outline
from component_contracts import COMPONENT_CONTRACTS, effective_frame_owner, effective_media_surface, quality_for
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


def has_native_visual(slide: dict) -> bool:
    """Count program-owned data/relationship graphics as visual evidence, not as image media."""
    template = slide.get("template")
    return bool(
        template in {"data-story", "metric", "converge", "cycle", "quadrant", "tier-stack"}
        or (template == "case-study-board" and slide.get("variant") == "chart")
    )


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
        "cycle": ("grid-wide", "grid-fade", "soft-spotlight"),
        "rail": ("grid-wide", "grid-fade", "block-field"),
        "timeline": ("grid-wide", "grid-fade", "block-field"),
        "step-grid": ("grid-wide", "grid-fade", "block-field"),
        "card-grid": ("grid-fade", "block-field", "soft-spotlight"),
        "two-panel": ("grid-fade", "block-field", "soft-spotlight"),
        "matrix": ("grid-fade", "grid-wide", "block-field"),
        "quadrant": ("grid-fade", "grid-wide", "soft-spotlight"),
        "metric": ("soft-spotlight", "block-field", "grid-fade"),
        "editorial-list": ("block-field", "grid-fade", "soft-spotlight"),
        "editorial-feature": ("grid-fade", "soft-spotlight", "grid-wide"),
        "catalog": ("grid-fade", "grid-wide", "soft-spotlight"),
        "case-board": ("grid-fade", "soft-spotlight", "grid-wide"),
        "annotated": ("grid-fade", "soft-spotlight", "grid-wide"),
        "bento": ("grid-fade", "soft-spotlight", "grid-wide"),
        "gallery": ("grid-fade", "grid-wide", "soft-spotlight"),
        "tier-stack": ("grid-wide", "grid-fade", "soft-spotlight"),
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


def consecutive_runs(items: list[dict], key) -> list[list[dict]]:
    """Return maximal repeated runs without duplicating window diagnostics."""
    runs: list[list[dict]] = []
    start = 0
    while start < len(items):
        value = key(items[start])
        end = start + 1
        while end < len(items) and key(items[end]) == value:
            end += 1
        runs.append(items[start:end])
        start = end
    return runs


ADVISORY_THEMES = (
    (
        "layout-rhythm",
        "Layout rhythm repeats across the deck; review the grouped signals together instead of changing pages one warning at a time.",
        {
            "surface-dominance", "component-dominance", "missing-focal-beat",
            "repeated-silhouette", "repeated-layout-signature", "low-rhythm-variety",
            "missing-visual-anchor",
        },
    ),
    (
        "media-rhythm",
        "Media coverage has a pacing gap; review the grouped deck and section signals as one issue.",
        {"media-coverage", "missing-section-media", "media-gap"},
    ),
    (
        "media-composition",
        "Media composition energy is concentrated in one shape or part of the deck; review only where the material supports a different treatment.",
        {"missing-cinematic-beat", "media-energy-concentration", "media-shape-monotony", "inset-media-run"},
    ),
    (
        "background-rhythm",
        "Background rhythm is perceptually repetitive; apply a small number of coordinated changes.",
        {"background-monotony", "background-class-monotony", "background-run"},
    ),
    (
        "emphasis-rhythm",
        "Emphasis devices are overused; reduce them together rather than treating each mechanism independently.",
        {"highlight-saturation", "backdrop-saturation"},
    ),
)


def consolidate_issues(items: list[dict]) -> list[dict]:
    """Deduplicate diagnostics and collapse related heuristics into themes."""
    results: list[dict] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for item in items:
        identity = (str(item.get("code") or ""), tuple(item.get("slides") or ()))
        if identity in seen:
            continue
        seen.add(identity)
        results.append(item)

    consumed: set[int] = set()
    consolidated: list[dict] = []
    for theme_code, message, codes in ADVISORY_THEMES:
        matches = [
            (index, item) for index, item in enumerate(results)
            if not item.get("blocking") and item.get("code") in codes
        ]
        if not matches:
            continue
        consumed.update(index for index, _ in matches)
        slide_ids: list[str] = []
        for _, item in matches:
            for slide_id in item.get("slides") or []:
                if slide_id not in slide_ids:
                    slide_ids.append(slide_id)
        signals: list[dict] = []
        for signal_code in dict.fromkeys(str(item["code"]) for _, item in matches):
            occurrences = [item for _, item in matches if item["code"] == signal_code]
            signal_slides: list[str] = []
            for occurrence in occurrences:
                for slide_id in occurrence.get("slides") or []:
                    if slide_id not in signal_slides:
                        signal_slides.append(slide_id)
            signal = {
                "code": signal_code,
                "message": (
                    occurrences[0]["message"]
                    if len(occurrences) == 1
                    else f"{len(occurrences)} related occurrences"
                ),
                "slides": signal_slides,
            }
            if len(occurrences) == 1 and occurrences[0].get("suggestion"):
                signal["suggestion"] = occurrences[0]["suggestion"]
            elif len(occurrences) > 1:
                signal["occurrences"] = [
                    {
                        "message": occurrence["message"],
                        "slides": occurrence.get("slides") or [],
                        **({"suggestion": occurrence["suggestion"]} if occurrence.get("suggestion") else {}),
                    }
                    for occurrence in occurrences
                ]
            signals.append(signal)
        consolidated.append(issue(
            "warning" if any(item.get("level") == "warning" for _, item in matches) else "info",
            theme_code,
            message,
            slide_ids,
            {"signals": signals},
        ))
    consolidated.extend(item for index, item in enumerate(results) if index not in consumed)
    return consolidated


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
    surfaces = Counter(effective_media_surface(slide) for slide in media)
    return {
        "content_slides": len(content),
        "templates": dict(templates),
        "families": dict(families),
        "silhouettes": dict(silhouettes),
        "layout_signatures": dict(signatures),
        "backgrounds": dict(backgrounds),
        "background_classes": dict(background_classes),
        "media": {"slides": len(media), "full_bleed": len(bleed), "surfaces": dict(surfaces)},
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
        owner = effective_frame_owner(slide)
        if owner == "template" and declared != "content":
            results.append(issue(
                "error", "double-frame-risk",
                f"Template {slide['template']!r} owns the outer frame; its media must be frameless content.",
                [slide["id"]],
                blocking=True,
            ))
    require_media = data.get("media_policy", "required") != "text-only"
    visible_media_slides = [slide for slide in slides if has_media(slide) or has_native_visual(slide)]
    media_slides = [slide for slide in content if has_media(slide)]
    if require_media and not visible_media_slides:
        results.append(issue(
            "error", "media-required",
            "media_policy='required' needs at least one visible image, native data chart, or programmatic relationship visual; otherwise explicitly confirm text-only.",
            [slide["id"] for slide in slides],
            blocking=True,
        ))
    if not content:
        return results

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

    missing_focal_beat = False
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
                "info", "missing-focal-beat",
                "The content deck has no dedicated focal pause; review whether the narrative contains a real quote, metric, or single judgment worth isolating.",
                [slide["id"] for slide in candidates],
                {
                    "action": "only if the content supports it, convert one candidate into a focal beat",
                    "templates": ["quote", "metric"],
                    "candidate_slides": [slide["id"] for slide in candidates],
                },
            ))
            missing_focal_beat = True

    missing_cinematic_beat = False
    if require_media and len(content) >= 8 and len(media_slides) >= 2:
        bleed_media = [slide for slide in media_slides if slide_quality(slide)["silhouette"] == "bleed"]
        if not bleed_media:
            eligible = [slide for slide in media_slides if slide["template"] not in BLEED_TEMPLATES]
            candidates = eligible[1::3][:3] or eligible[:2]
            results.append(issue(
                "info", "missing-cinematic-beat",
                f"All {len(media_slides)} media slides stay inside inset frames; review whether one strong image can legitimately carry an edge-bleed beat.",
                [slide["id"] for slide in media_slides],
                {
                    "action": "consider one full-screen media composition where the image can carry the argument",
                    "templates": list(BLEED_TEMPLATES),
                    "candidate_slides": [slide["id"] for slide in candidates],
                },
            ))
            missing_cinematic_beat = True
        elif len(media_slides) >= 5:
            content_positions = {slide["id"]: index for index, slide in enumerate(content)}
            bleed_positions = [content_positions[slide["id"]] for slide in bleed_media]
            sparse = len(bleed_media) / len(media_slides) < .25
            late = min(bleed_positions) >= max(1, (len(content) * 2) // 3)
            if sparse or late:
                eligible = [
                    slide for slide in media_slides
                    if slide_quality(slide)["silhouette"] != "bleed"
                    and slide.get("media_frame") != "self-framed"
                    and slide.get("media_fidelity") != "strict"
                    and content_positions[slide["id"]] < max(1, (len(content) * 2) // 3)
                ]
                candidates = eligible[1::2][:3] or eligible[:2]
                results.append(issue(
                    "warning", "media-energy-concentration",
                    f"Only {len(bleed_media)}/{len(media_slides)} media slides break the safe area, or those beats arrive too late; the visual energy is concentrated instead of paced through the deck.",
                    [slide["id"] for slide in bleed_media],
                    {
                        "action": "promote an early or middle media page to edge bleed; use diagonal split only when the content expresses direction, transition, boundary, or conflict",
                        "templates": ["bleed-split", "diagonal-split", "photo-gradient"],
                        "candidate_slides": [slide["id"] for slide in candidates],
                    },
                ))

        media_silhouettes = Counter(slide_quality(slide)["silhouette"] for slide in media_slides)
        if not missing_cinematic_beat and len(media_slides) >= 3 and len(media_silhouettes) == 1:
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

        if not missing_cinematic_beat:
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
        background_theme_reported = False
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
            background_theme_reported = True

        classes = Counter(BACKGROUND_CLASSES[value] for value in backgrounds)
        dominant_class, dominant_class_count = classes.most_common(1)[0]
        if (
            not background_theme_reported
            and dominant_class != "media"
            and len(counts) > 1
            and dominant_class_count / len(content) > .72
        ):
            same_class = [slide for slide in content if BACKGROUND_CLASSES[effective_background(slide)] == dominant_class]
            candidates = same_class[2::4][:3] or same_class[:1]
            changes = {slide["id"]: suggested_background(slide, effective_background(slide)) for slide in candidates}
            results.append(issue(
                "warning", "background-class-monotony",
                f"Perceptually similar {dominant_class!r} backgrounds appear on {dominant_class_count}/{len(content)} content slides, even though preset names differ.",
                [slide["id"] for slide in same_class],
                {"set_background": changes},
            ))
            background_theme_reported = True

        if not background_theme_reported:
            for run in consecutive_runs(content, effective_background):
                run_background = effective_background(run[0])
                if len(run) < 5 or run_background == "media-owned":
                    continue
                target = run[len(run) // 2]
                results.append(issue(
                    "warning", "background-run",
                    f"{len(run)} consecutive content slides use background {run_background!r}.",
                    [item["id"] for item in run],
                    {"set_background": {target["id"]: suggested_background(target, run_background)}},
                ))

        highlighted = [slide for slide in content if slide.get("highlight")]
        if len(highlighted) / len(content) > .4:
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

    segments = content_segments(slides)
    for segment_index, segment in enumerate(segments, start=1):
        if not segment:
            continue
        silhouette_runs = [run for run in consecutive_runs(segment, lambda slide: slide_quality(slide)["silhouette"]) if len(run) >= 3]
        signature_runs = [run for run in consecutive_runs(segment, lambda slide: slide_quality(slide)["layout_signature"]) if len(run) >= 3]
        signature_sets = [{slide["id"] for slide in run} for run in signature_runs]

        for run in signature_runs:
            signature = slide_quality(run[0])["layout_signature"]
            results.append(issue(
                "warning", "repeated-layout-signature",
                f"Section {segment_index} repeats perceived layout {signature!r} for {len(run)} consecutive slides; mirroring or changing decoration does not create a new rhythm.",
                [slide["id"] for slide in run],
            ))

        for run in silhouette_runs:
            run_ids = {slide["id"] for slide in run}
            if any(run_ids <= signature_ids for signature_ids in signature_sets):
                continue
            silhouette = slide_quality(run[0])["silhouette"]
            results.append(issue(
                "warning", "repeated-silhouette",
                f"Section {segment_index} repeats silhouette {silhouette!r} for {len(run)} consecutive slides.",
                [slide["id"] for slide in run],
            ))

        if len(segment) >= 6:
            repeated_sets = [
                {slide["id"] for slide in run}
                for run in [*signature_runs, *silhouette_runs]
            ]
            for start in range(0, len(segment) - 5):
                window = segment[start:start + 6]
                distinct = {slide_quality(slide)["silhouette"] for slide in window}
                window_ids = {slide["id"] for slide in window}
                if len(distinct) < 3 and not any(window_ids <= repeated for repeated in repeated_sets):
                    results.append(issue(
                        "warning", "low-rhythm-variety",
                        f"Section {segment_index} has only {len(distinct)} silhouettes across six consecutive content slides.",
                        [slide["id"] for slide in window],
                    ))
                    break

        anchors = [slide for slide in segment if slide_quality(slide)["visual_energy"] == "anchor"]
        if len(segment) >= 5 and not anchors and not (len(segments) == 1 and missing_focal_beat):
            results.append(issue(
                "info", "missing-visual-anchor",
                f"Section {segment_index} has {len(segment)} content slides but no visual anchor; review whether its content contains a genuine anchor rather than forcing one.",
                [slide["id"] for slide in segment],
            ))

        if require_media and len(segment) >= 5:
            segment_media = [slide for slide in segment if has_media(slide)]
            minimum = (len(segment) + 4) // 5
            if len(segment_media) < minimum:
                if len(segments) > 1:
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

    return consolidate_issues(results)


def audit_summary(data: dict) -> dict:
    review = recommend_outline(data)
    results = audit_outline(data)
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
    errors = [item for item in results if item["blocking"]]
    if errors:
        lines = []
        for item in errors:
            suffix = f" Slides: {', '.join(item['slides'])}." if item["slides"] else ""
            signals = (item.get("suggestion") or {}).get("signals") or []
            suggestion = (
                f" Signals: {', '.join(str(signal.get('code')) for signal in signals)}."
                if signals
                else f" Suggestion: {json.dumps(item['suggestion'], ensure_ascii=False)}" if item.get("suggestion") else ""
            )
            lines.append(f"{item['code']}: {item['message']}{suffix}{suggestion}")
        raise SystemExit("Deck quality audit failed:\n- " + "\n- ".join(lines))
    return results
