#!/usr/bin/env python3
"""Compile slide-bound media into deterministic slot and fidelity jobs."""
from __future__ import annotations

import json
import os
import shlex
import tempfile
from pathlib import Path

from component_contracts import quality_for
from media_assets import inspect_image, outline_media_bindings


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

FRAME_INPUT_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


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


def _nested_slot(field: str) -> dict | None:
    if field == "secondary_image":
        return {"ratio": "4:3", "target": [1200, 900], "role": "supporting-photo", "fit": "cover", "fidelity": "contextual"}
    if ".evidence[" in field or ".images[" in field:
        return {"ratio": "4:5", "target": [1000, 1250], "role": "visual-evidence", "fit": "cover", "fidelity": "contextual"}
    return None


def build_media_plan(data: dict, project: Path, *, cli: str = "scripts/oil-ppt") -> dict:
    project = project.expanduser().resolve()
    items = []
    for index, slide in enumerate(data.get("slides") or [], start=1):
        bindings: list[dict] = []
        for field, value in outline_media_bindings(slide):
            source = slide.get("media_source")
            question = slide.get("media_question")
            if field.startswith("steps["):
                step_index = int(field.split("[", 1)[1].split("]", 1)[0]) - 1
                item = (slide.get("steps") or [])[step_index]
                if isinstance(item, dict):
                    source = item.get("media_source") or source
                    question = item.get("media_question") or item.get("body") or item.get("title") or question
            bindings.append({"field": field, "value": str(value), "source": source, "question": question})
        slot_template = _slot_for(slide)
        if not bindings and slot_template is None:
            continue
        if not bindings:
            bindings.append({"field": "image", "value": "", "source": slide.get("media_source"), "question": slide.get("media_question")})
        for media_index, binding in enumerate(bindings, start=1):
            slot = dict(_nested_slot(str(binding["field"])) or slot_template or MEDIA_SLOTS.get(str(slide.get("template") or "")) or {"ratio": "16:9", "target": [1600, 900], "role": "visual", "fit": "contain", "fidelity": "contextual"})
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
            media_frame = str(slide.get("media_frame") or "")
            source_suffix = Path(value).suffix.lower()
            frame_role = role in {"product-screenshot", "evidence-canvas", "main-evidence", "screenshot", "evidence"}
            can_frame = source_suffix in FRAME_INPUT_SUFFIXES
            if value and frame_owner == "none" and frame_role and media_frame != "self-framed" and can_frame:
                frame_argv = [
                    cli, "media", "frame", str(path), str(project / output_rel),
                    "--project", str(project), "--ratio", slot["ratio"], "--fit", "contain",
                ]
                frame_command = " ".join(shlex.quote(part) for part in frame_argv)
            if media_frame == "self-framed":
                adaptation_reason = "media_frame=self-framed; preserve the asset exactly and do not add a generated frame"
            elif not can_frame and value:
                adaptation_reason = f"{source_suffix or 'extensionless'} media is not accepted by media frame; use it directly"
            elif frame_owner != "none":
                adaptation_reason = "the selected template owns the media frame; do not add another shell"
            elif not frame_role:
                adaptation_reason = "the media role does not need programmatic screenshot framing"
            elif frame_argv:
                adaptation_reason = "programmatic ratio adaptation keeps screenshot content unchanged"
            else:
                adaptation_reason = "no adaptation command is needed"
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
                    "reason": adaptation_reason,
                    "output_suggestion": output_rel if frame_argv else None,
                    "argv": frame_argv,
                    "command": frame_command,
                },
            }
            items.append(item)
    return {
        "schema_version": "oil-ppt.media-plan/v1",
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
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(plan, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return path
