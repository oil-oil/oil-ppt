#!/usr/bin/env python3
"""Compile slide-bound media into deterministic slot and fidelity jobs."""
from __future__ import annotations

import json
import shlex
from pathlib import Path

from component_contracts import quality_for
from media_assets import inspect_image


MEDIA_SLOTS = {
    "cover": {"ratio": "4:3", "target": [1440, 1080], "role": "opening-visual", "fit": "cover", "fidelity": "contextual"},
    "end": {"ratio": "1:1", "target": [1200, 1200], "role": "artifact", "fit": "contain", "fidelity": "strict"},
    "bleed-split": {"ratio": "16:9", "target": [1600, 900], "role": "edge-visual", "fit": "cover", "fidelity": "contextual"},
    "browser-showcase": {"ratio": "16:10", "target": [1600, 1000], "role": "product-screenshot", "fit": "contain", "fidelity": "strict"},
    "diagonal-split": {"ratio": "16:9", "target": [1600, 900], "role": "directional-visual", "fit": "cover", "fidelity": "contextual"},
    "editorial-canvas": {"ratio": "16:9", "target": [1600, 900], "role": "evidence-canvas", "fit": "contain", "fidelity": "strict"},
    "photo-gradient": {"ratio": "16:9", "target": [1920, 1080], "role": "full-bleed-photo", "fit": "cover", "fidelity": "contextual"},
    "photo-split": {"ratio": "4:3", "target": [1440, 1080], "role": "supporting-photo", "fit": "cover", "fidelity": "contextual"},
    "split-visual": {"ratio": "16:10", "target": [1600, 1000], "role": "main-evidence", "fit": "contain", "fidelity": "strict"},
    "editorial-feature": {"ratio": "16:10", "target": [1600, 1000], "role": "main-evidence", "fit": "contain", "fidelity": "strict"},
    "case-study-board": {"ratio": "16:10", "target": [1600, 1000], "role": "case-evidence", "fit": "contain", "fidelity": "strict"},
    "annotated-showcase": {"ratio": "16:10", "target": [1600, 1000], "role": "annotated-evidence", "fit": "contain", "fidelity": "strict"},
    "sequence-gallery": {"ratio": "16:10", "target": [1200, 750], "role": "sequence-frame", "fit": "contain", "fidelity": "strict"},
}


def _media_value(slide: dict) -> str:
    return str(slide.get("image") or slide.get("media") or slide.get("artifact_image") or "").strip()


def _slot_for(slide: dict) -> dict | None:
    template = str(slide.get("template") or "")
    if template == "cover" and slide.get("variant") != "media":
        return None
    if template == "end" and slide.get("variant") != "line-artifact":
        return None
    if template == "case-study-board" and slide.get("variant") != "evidence":
        return None
    return MEDIA_SLOTS.get(template)


def build_media_plan(data: dict, project: Path, *, cli: str = "scripts/oil-slides") -> dict:
    project = project.expanduser().resolve()
    items = []
    for index, slide in enumerate(data.get("slides") or [], start=1):
        bindings: list[dict] = []
        value = _media_value(slide)
        if value:
            bindings.append({"field": "image", "value": value, "source": slide.get("media_source"), "question": slide.get("media_question")})
        if slide.get("template") == "sequence-gallery":
            for step_index, step in enumerate(slide.get("steps") or [], start=1):
                if isinstance(step, dict) and step.get("image"):
                    bindings.append({
                        "field": f"steps[{step_index}].image",
                        "value": str(step["image"]),
                        "source": step.get("media_source"),
                        "question": step.get("media_question") or step.get("body") or step.get("title"),
                    })
        slot_template = _slot_for(slide)
        if not bindings and slot_template is None:
            continue
        if not bindings:
            bindings.append({"field": "image", "value": "", "source": slide.get("media_source"), "question": slide.get("media_question")})
        for media_index, binding in enumerate(bindings, start=1):
            slot = dict(slot_template or MEDIA_SLOTS.get(str(slide.get("template") or "")) or {"ratio": "16:9", "target": [1600, 900], "role": "visual", "fit": "contain", "fidelity": "contextual"})
            value = str(binding["value"] or "")
            path = (project / value).resolve() if value else None
            path_inside_project = bool(path and project in path.parents)
            source = None
            source_error = None
            if path and path_inside_project and path.is_file():
                try:
                    source = inspect_image(path)
                except ValueError as error:
                    source_error = str(error)
            elif path and not path_inside_project:
                source_error = "asset path leaves the project"
            elif value:
                source_error = "asset file is missing"
            role = str(slide.get("media_role") or slot["role"])
            fidelity = str(slide.get("media_fidelity") or slot["fidelity"])
            fit = str(slide.get("media_fit") or slot["fit"])
            frame_owner = quality_for(str(slide.get("template") or ""))["frame_owner"]
            output_rel = f"assets/{Path(value).stem or slide.get('id') or f'slide-{index}'}-{media_index}-framed.png"
            frame_argv = None
            frame_command = None
            if value and frame_owner == "none" and role in {"product-screenshot", "evidence-canvas", "main-evidence", "screenshot", "evidence"}:
                frame_argv = [
                    cli, "media", "frame", str(path), str(project / output_rel),
                    "--project", str(project), "--ratio", slot["ratio"], "--fit", "contain",
                ]
                frame_command = " ".join(shlex.quote(part) for part in frame_argv)
            item = {
                "slide": index,
                "media_index": media_index,
                "field": binding["field"],
                "slide_id": slide.get("id"),
                "title": slide.get("title"),
                "template": slide.get("template"),
                "question_answered": binding.get("question") or f"为“{slide.get('title', '')}”提供可见证据",
                "role": role,
                "fidelity": fidelity,
                "asset": {
                    "relative_path": value or None,
                    "resolved_path": str(path) if path else None,
                    "status": "ready" if source else "missing-or-invalid",
                    "inspection": source,
                    "error": source_error,
                    "source": binding.get("source") or None,
                },
                "slot": {**slot, "fit": fit, "frame_owner": frame_owner},
                "adaptation": {
                    "needed": bool(frame_argv),
                    "reason": (
                        "programmatic ratio adaptation keeps screenshot content unchanged"
                        if frame_argv else
                        "template or media already owns the frame; do not add another shell"
                    ),
                    "output_suggestion": output_rel if frame_argv else None,
                    "argv": frame_argv,
                    "command": frame_command,
                },
            }
            items.append(item)
    return {
        "schema_version": "oil-slides.media-plan/v1",
        "project": str(project),
        "items": items,
        "summary": {
            "count": len(items),
            "ready": sum(item["asset"]["status"] == "ready" for item in items),
            "strict": sum(item["fidelity"] == "strict" for item in items),
            "needs_adaptation": sum(item["adaptation"]["needed"] for item in items),
        },
    }


def write_media_plan(plan: dict, path: Path) -> Path:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
