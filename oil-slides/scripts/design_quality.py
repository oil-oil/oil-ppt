#!/usr/bin/env python3
"""Deck-level rhythm and media-composition checks for oil-slides outlines."""
from __future__ import annotations

import json
from collections import Counter

from background_presets import effective_background
from component_contracts import quality_for


EXCLUDED = {"cover", "end", "section"}
ANCHOR_SILHOUETTES = {"bleed", "browser", "canvas", "diagram", "metric", "rail", "split", "timeline"}
MEDIA_KEYS = ("image", "media", "artifact_image")


def has_media(slide: dict) -> bool:
    return any(str(slide.get(key) or "").strip() for key in MEDIA_KEYS)


def issue(
    level: str,
    code: str,
    message: str,
    slide_ids: list[str] | None = None,
    suggestion: dict | None = None,
) -> dict:
    result = {"level": level, "code": code, "message": message, "slides": slide_ids or []}
    if suggestion:
        result["suggestion"] = suggestion
    return result


def suggested_background(slide: dict, current: str) -> str:
    silhouette = quality_for(slide["template"])["silhouette"]
    candidates = {
        "focal": ("section-glow", "soft-spotlight", "paper-wash"),
        "split": ("soft-spotlight", "mist-grid", "paper-wash"),
        "bleed": ("none", "soft-spotlight", "paper-wash"),
        "browser": ("soft-spotlight", "paper-wash", "mist-grid"),
        "canvas": ("mist-grid", "grid-wide", "paper-wash"),
        "diagram": ("mist-grid", "grid-wide", "paper-wash"),
        "rail": ("grid-wide", "mist-grid", "paper-wash"),
        "timeline": ("grid-wide", "mist-grid", "paper-wash"),
        "step-grid": ("grid-wide", "mist-grid", "paper-wash"),
        "card-grid": ("paper-wash", "mist-grid", "soft-spotlight"),
        "two-panel": ("paper-wash", "mist-grid", "soft-spotlight"),
        "metric": ("soft-spotlight", "section-glow", "paper-wash"),
        "editorial-list": ("paper-wash", "mist-grid", "soft-spotlight"),
    }.get(silhouette, ("mist-grid", "paper-wash", "soft-spotlight"))
    return next((value for value in candidates if value != current), "grid-fade")


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


def audit_outline(data: dict) -> list[dict]:
    slides = data.get("slides") or []
    results: list[dict] = []
    content = [slide for slide in slides if slide["template"] not in EXCLUDED]
    if not content:
        return results

    require_media = data.get("media_policy", "required") != "text-only"
    media_slides = [slide for slide in content if has_media(slide)]
    if require_media and len(content) >= 15:
        minimum = (len(content) + 4) // 5
        if len(media_slides) < minimum:
            results.append(issue(
                "error", "media-coverage",
                f"Long decks require media on at least 20% of content slides; found {len(media_slides)}/{len(content)}, need {minimum}.",
                [slide["id"] for slide in media_slides],
            ))

    heavy = [slide for slide in content if quality_for(slide["template"])["surface_density"] == "heavy"]
    heavy_ratio = len(heavy) / len(content)
    if len(content) >= 8 and heavy_ratio > .48:
        results.append(issue(
            "warning", "surface-dominance",
            f"{len(heavy)}/{len(content)} content slides use surface-heavy card or panel silhouettes; keep this at 48% or below.",
            [slide["id"] for slide in heavy],
        ))

    if len(content) >= 8:
        backgrounds = [effective_background(slide) for slide in content]
        counts = Counter(backgrounds)
        dominant, dominant_count = counts.most_common(1)[0]
        if len(counts) == 1 or dominant_count / len(content) > .72:
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

        run: list[dict] = []
        run_background = ""
        for slide in [*content, None]:
            background = effective_background(slide) if slide is not None else ""
            if slide is not None and (not run or background == run_background):
                if not run:
                    run_background = background
                run.append(slide)
                continue
            if len(run) >= 5:
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

    for segment_index, segment in enumerate(content_segments(slides), start=1):
        if not segment:
            continue
        silhouettes = [quality_for(slide["template"])["silhouette"] for slide in segment]
        start = 0
        while start < len(segment):
            end = start + 1
            while end < len(segment) and silhouettes[end] == silhouettes[start]:
                end += 1
            if end - start >= 3:
                run = segment[start:end]
                results.append(issue(
                    "error", "repeated-silhouette",
                    f"Section {segment_index} repeats silhouette {silhouettes[start]!r} for {len(run)} consecutive slides.",
                    [slide["id"] for slide in run],
                ))
            start = end

        if len(segment) >= 6:
            for start in range(0, len(segment) - 5):
                window = segment[start:start + 6]
                distinct = {quality_for(slide["template"])["silhouette"] for slide in window}
                if len(distinct) < 3:
                    results.append(issue(
                        "warning", "low-rhythm-variety",
                        f"Section {segment_index} has only {len(distinct)} silhouettes across six consecutive content slides.",
                        [slide["id"] for slide in window],
                    ))

        anchors = [slide for slide in segment if quality_for(slide["template"])["silhouette"] in ANCHOR_SILHOUETTES]
        if len(segment) >= 5 and not anchors:
            results.append(issue(
                "error", "missing-visual-anchor",
                f"Section {segment_index} has {len(segment)} content slides but no visual anchor.",
                [slide["id"] for slide in segment],
            ))

        if require_media and len(segment) >= 5:
            segment_media = [slide for slide in segment if has_media(slide)]
            if not segment_media:
                results.append(issue(
                    "error", "missing-section-media",
                    f"Section {segment_index} has {len(segment)} content slides but no media slide.",
                    [slide["id"] for slide in segment],
                ))
            else:
                run: list[dict] = []
                for slide in [*segment, None]:
                    if slide is not None and not has_media(slide):
                        run.append(slide)
                        continue
                    if len(run) >= 6:
                        results.append(issue(
                            "error", "media-gap",
                            f"Section {segment_index} has {len(run)} consecutive content slides without media.",
                            [item["id"] for item in run],
                        ))
                    run = []

    for slide in content:
        if not has_media(slide):
            continue
        declared = slide.get("media_frame")
        if declared not in {"content", "self-framed"}:
            results.append(issue(
                "error", "missing-media-frame",
                "Image slides must declare media_frame as 'content' or 'self-framed'.",
                [slide["id"]],
            ))
            continue
        owner = quality_for(slide["template"])["frame_owner"]
        if owner == "template" and declared != "content":
            results.append(issue(
                "error", "double-frame-risk",
                f"Template {slide['template']!r} owns the outer frame; its media must be frameless content.",
                [slide["id"]],
            ))

    return results


def audit_summary(data: dict) -> dict:
    results = audit_outline(data)
    return {
        "status": "error" if any(item["level"] == "error" for item in results) else "ok",
        "issues": results,
        "counts": dict(Counter(item["level"] for item in results)),
    }


def enforce_outline_quality(data: dict) -> list[dict]:
    results = audit_outline(data)
    for item in results:
        if item["level"] == "warning":
            suffix = f" Slides: {', '.join(item['slides'])}." if item["slides"] else ""
            suggestion = f" Suggestion: {json.dumps(item['suggestion'], ensure_ascii=False)}" if item.get("suggestion") else ""
            print(f"[WARN] {item['code']}: {item['message']}{suffix}{suggestion}")
    errors = [item for item in results if item["level"] == "error"]
    if errors:
        lines = []
        for item in errors:
            suffix = f" Slides: {', '.join(item['slides'])}." if item["slides"] else ""
            lines.append(f"{item['code']}: {item['message']}{suffix}")
        raise SystemExit("Deck quality audit failed:\n- " + "\n- ".join(lines))
    return results
