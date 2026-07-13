#!/usr/bin/env python3
"""Single deterministic entry point for oil-ppt project operations."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from background_presets import BACKGROUND_PRESETS, INTERNAL_BACKGROUNDS, template_background
from capability_catalog import (
    FAMILY_GUIDANCE, PROGRAM_OWNED_CAPABILITIES, SELECTION_ORDER,
    TEMPLATE_DISCOVERY, VARIANT_HELP,
)
from capability_recommender import recommend_outline
from component_contracts import COMPONENT_CONTRACTS, VARIANT_QUALITY, quality_for
from design_quality import audit_summary, enforce_outline_quality
from media_assets import print_sources, verify_outline_media
from media_frame import frame_media
from media_plan import build_media_plan, write_media_plan
from render_programmatic_visual import render_html_visual
from icon_registry import print_icon_results
from outline_schema import DECK_FIELDS, MEDIA_TEMPLATES, SHARED_SLIDE_FIELDS, TEMPLATE_CONTENT_HELP, TEMPLATE_FAMILIES, validate_outline
from palette_tokens import PALETTES, canonical_name, named_palette, normalize_palette
from profile_tokens import SHAPE_PROFILES, TYPE_PROFILES


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
TEMPLATES = ROOT / "assets" / "templates"
DEFAULT_FINAL_NAME = "演示文稿.html"
PROJECT_STATE_NAME = ".oil-slides-state.json"
BUILD_STATE_NAME = ".oil-slides-build.json"
SLIDE_ID = re.compile(r'data-slide-id=["\']([a-z0-9][a-z0-9-]*)["\']')
SLIDE_TITLE = re.compile(r'data-title=["\']([^"\']+)["\']')


def cli_path() -> Path:
    return (SCRIPTS / "oil-slides").resolve()


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def project_from_target(target: Path) -> Path:
    path = target.expanduser().resolve()
    return path if path.is_dir() or not path.suffix else path.parent


def outline_from_target(target: Path) -> Path:
    path = target.expanduser().resolve()
    return path if path.is_file() and path.suffix.lower() == ".json" else path / "outline.json"


def project_state_path(project: Path) -> Path:
    return project / PROJECT_STATE_NAME


def read_project_state(project: Path) -> dict:
    path = project_state_path(project)
    if not path.is_file():
        return {"schema_version": "oil-slides.project-state/v1", "history": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid project state {path}: {error}") from error
    return data if isinstance(data, dict) else {"schema_version": "oil-slides.project-state/v1", "history": []}


def run_script(name: str, arguments: list[str]) -> None:
    proc = subprocess.run([sys.executable, str(SCRIPTS / name), *arguments], check=False)
    if proc.returncode:
        raise SystemExit(proc.returncode)


OUTLINE_MARKDOWN_TEMPLATE = """# 演示标题

## 演示设定

- 用途：
- 受众：
- 场景与时长：
- 密度：现场讲述 / 独立阅读
- 鼠标点击翻页：关闭
- 希望观众记住：

## 页面大纲

### 01｜封面

- 核心判断：
- 支撑内容：
- 素材及其回答的问题：

### 02｜

- 核心判断：
- 支撑内容：
- 素材及其回答的问题：
"""


def init_project(project_arg: Path) -> None:
    project = project_arg.expanduser().resolve()
    project.mkdir(parents=True, exist_ok=True)
    allowed = {".DS_Store"}
    unexpected = [path for path in project.iterdir() if path.name not in allowed]
    if unexpected:
        raise SystemExit(f"Init requires an empty directory: {project}. Existing: {unexpected[0].name}")
    (project / "assets").mkdir(exist_ok=True)
    (project / "outline.md").write_text(OUTLINE_MARKDOWN_TEMPLATE, encoding="utf-8")
    atomic_write_json(project_state_path(project), {
        "schema_version": "oil-slides.project-state/v1",
        "history": [{"event": "initialized"}],
    })
    print(json.dumps({
        "ok": True,
        "phase": "needs_outline",
        "project": str(project),
        "created": [str(project / "outline.md"), str(project / "assets")],
        "next": {"action": "fill outline.md and ask the user to confirm it", "command": None},
    }, ensure_ascii=False, indent=2))


def example_outline() -> dict:
    return {
        "title": "演示标题",
        "palette": "oil-yellow",
        "typography": "clean",
        "shape": "soft",
        "media_policy": "text-only",
        "click_navigation": False,
        "slides": [
            {"id": "cover", "title": "一个清楚的开场判断", "template": "cover", "variant": "statement", "decor": "none"},
            {"id": "section", "title": "进入核心内容", "content": "用一句话说明章节变化", "template": "section", "variant": "default", "decor": "none"},
            {
                "id": "points", "title": "三个要点支撑同一个判断", "highlight": "同一个判断",
                "template": "card-trio", "variant": "feature-top", "decor": "none",
                "cards": [
                    {"title": "主要判断", "body": "说明它为什么重要"},
                    {"title": "支撑一", "body": "提供第一条依据"},
                    {"title": "支撑二", "body": "提供第二条依据"},
                ],
            },
            {"id": "end", "title": "让观众带走一句话", "template": "end", "variant": "line", "decor": "none"},
        ],
    }


def contract_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "oil-slides:outline/v1",
        "type": "object",
        "required": ["title", "palette", "typography", "shape", "click_navigation", "slides"],
        "properties": {
            "title": {"type": "string", "minLength": 1},
            "palette": {"oneOf": [{"enum": sorted(PALETTES)}, {"type": "object"}]},
            "palette_source": {"enum": ["user", "brand"]},
            "typography": {"enum": sorted(TYPE_PROFILES)},
            "shape": {"enum": sorted(SHAPE_PROFILES)},
            "media_policy": {"enum": ["required", "text-only"], "default": "required"},
            "click_navigation": {"type": "boolean", "default": False},
            "slides": {
                "type": "array", "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["id", "title", "template", "variant", "decor"],
                    "properties": {
                        "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
                        "title": {"type": "string", "minLength": 1},
                        "template": {"enum": sorted(COMPONENT_CONTRACTS)},
                        "variant": {"type": "string"},
                        "decor": {"type": "string"},
                        "highlight": {"type": "string", "minLength": 1},
                        "background": {"enum": sorted(BACKGROUND_PRESETS)},
                        "backdrop_text": {"type": "string", "minLength": 1, "maxLength": 12},
                        "media_frame": {"enum": ["content", "self-framed"]},
                        "media_fit": {"enum": ["cover", "contain"]},
                        "media_position": {"enum": [
                            "center", "left", "right", "top", "bottom",
                            "top-left", "top-right", "bottom-left", "bottom-right",
                        ]},
                        "media_treatment": {"enum": ["natural", "muted", "mono"]},
                        "media_role": {"type": "string", "minLength": 1},
                        "media_fidelity": {"enum": ["strict", "contextual", "illustrative"]},
                        "media_question": {"type": "string", "minLength": 1},
                        "media_source": {"type": "object"},
                    },
                },
            },
        },
        "note": "Template-specific content fields are validated by `contract --id <template>` and `plan`.",
    }


def confirm_outline(project: Path, user_confirmed: bool) -> None:
    if not user_confirmed:
        raise SystemExit("Outline confirmation requires --user-confirmed after explicit user approval.")
    markdown = project / "outline.md"
    if not markdown.is_file():
        raise SystemExit(f"Missing Markdown outline: {markdown}. Next: edit the file created by init.")
    if markdown.read_text(encoding="utf-8").strip() == OUTLINE_MARKDOWN_TEMPLATE.strip():
        raise SystemExit(f"outline.md is still the empty starter: {markdown}. Fill it before confirmation.")
    state = read_project_state(project)
    state["outline_confirmation"] = {
        "path": str(markdown),
        "sha256": outline_digest(markdown),
        "user_confirmed": True,
    }
    state.setdefault("history", []).append({"event": "outline_confirmed", "sha256": outline_digest(markdown)})
    atomic_write_json(project_state_path(project), state)
    print(json.dumps({
        "ok": True, "phase": "needs_plan", "project": str(project),
        "next": {"command": f"{cli_path()} contract --example"},
    }, ensure_ascii=False, indent=2))


def outline_confirmation_valid(project: Path) -> bool:
    markdown = project / "outline.md"
    if not markdown.is_file():
        return False
    confirmation = read_project_state(project).get("outline_confirmation") or {}
    return confirmation.get("user_confirmed") is True and confirmation.get("sha256") == outline_digest(markdown)


def plan_project(project_arg: Path, input_path: Path | None) -> None:
    project = project_arg.expanduser().resolve()
    if not outline_confirmation_valid(project):
        raise SystemExit(
            f"The current outline.md is not confirmed. Next: {cli_path()} confirm {project} --stage outline --user-confirmed"
        )
    target = project / "outline.json"
    source = input_path.expanduser().resolve() if input_path else target
    if not source.is_file():
        raise SystemExit(
            f"Missing visual plan JSON: {source}. Use {cli_path()} contract --example, write {target}, then run plan again."
        )
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON in {source}: {error}") from error
    validate_outline(data, TEMPLATES)
    enforce_outline_quality(data)
    if source != target:
        atomic_write_json(target, data)
    print(json.dumps({
        "ok": True, "phase": "needs_preview", "project": str(project), "outline": str(target),
        "slides": len(data["slides"]), "next": {"command": f"{cli_path()} preview {project}"},
    }, ensure_ascii=False, indent=2))


def check_project(target: Path) -> dict:
    outline = outline_from_target(target)
    if not outline.is_file():
        raise SystemExit(f"Missing outline.json: {outline}. Next: {cli_path()} contract --example")
    data = json.loads(outline.read_text(encoding="utf-8"))
    validate_outline(data, TEMPLATES)
    audit = audit_summary(data)
    media = verify_outline_media(data, outline.parent)
    return {
        "schema_version": "oil-slides.check/v1",
        "ok": audit["status"] != "error",
        "project": str(outline.parent),
        "outline": str(outline),
        "slides": len(data["slides"]),
        "audit": audit,
        "media": {"count": len(media), "items": media},
        "next": {"command": f"{cli_path()} preview {outline.parent}" if audit["status"] != "error" else None},
    }


def read_config(project: Path) -> tuple[Path, dict]:
    project = project.expanduser().resolve()
    path = project / "deck.json"
    if not path.is_file():
        raise SystemExit(f"Not an oil-ppt project: {project}")
    return project, json.loads(path.read_text(encoding="utf-8"))


def slide_meta(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    id_match = SLIDE_ID.search(text)
    title_match = SLIDE_TITLE.search(text)
    if not id_match:
        raise SystemExit(f"Missing data-slide-id: {path}")
    return id_match.group(1), title_match.group(1) if title_match else ""


def list_project(project_arg: Path) -> None:
    project, config = read_config(project_arg)
    items = []
    for index, relative in enumerate(config.get("slides", []), start=1):
        path = project / relative
        slide_id, title = slide_meta(path)
        items.append({"index": index, "id": slide_id, "title": title, "file": relative})
    print(json.dumps({"project": str(project), "slides": items}, ensure_ascii=False, indent=2))


def print_contract(
    show_all: bool = False, *, item_id: str | None = None, pretty: bool = True,
    show_schema: bool = False, show_example: bool = False, show_list: bool = False,
) -> None:
    """Print every capability in one compact, program-generated map.

    ``show_all`` is retained for command compatibility. The default no longer
    hides templates because hidden tiers were routinely invisible to weaker
    models.
    """
    if show_schema:
        print(json.dumps(contract_schema(), ensure_ascii=False, indent=2))
        return
    if show_example:
        print(json.dumps(example_outline(), ensure_ascii=False, indent=2))
        return
    if show_list:
        print(json.dumps({
            "schema_version": "oil-slides.contract-list/v1",
            "templates": [
                {
                    "name": name,
                    "family": TEMPLATE_FAMILIES[name],
                    "use_when": COMPONENT_CONTRACTS[name]["use_when"],
                }
                for name in sorted(COMPONENT_CONTRACTS)
            ],
            "detail_command": f"{cli_path()} contract --id <template-name>",
        }, ensure_ascii=False, indent=2))
        return
    templates_by_family = {name: [] for name in FAMILY_GUIDANCE}
    for name, contract in sorted(COMPONENT_CONTRACTS.items()):
        entry = {
            "name": name,
            "use_when": contract["use_when"],
            **TEMPLATE_DISCOVERY[name],
            **quality_for(name),
            "variants": list(contract["variants"]),
            **({"variant_help": VARIANT_HELP[name]} if name in VARIANT_HELP else {}),
            "decorations": list(contract["decorations"]),
            "content": TEMPLATE_CONTENT_HELP[name],
            "defaults": {
                "background": template_background(name),
                **({"media_frame": "content"} if name in MEDIA_TEMPLATES else {}),
            },
            **({"variant_quality": VARIANT_QUALITY[name]} if name in VARIANT_QUALITY else {}),
        }
        templates_by_family[TEMPLATE_FAMILIES[name]].append(entry)
    program_owned = json.loads(json.dumps(PROGRAM_OWNED_CAPABILITIES, ensure_ascii=False))
    def resolved_command(value: str) -> str:
        return value.replace("scripts/oil-slides", str(cli_path()), 1) if value.startswith("scripts/oil-slides") else value
    for section in program_owned.values():
        if isinstance(section, dict):
            for key, value in list(section.items()):
                if key.endswith("_command") and isinstance(value, str):
                    section[key] = resolved_command(value)
    payload = {
        "schema_version": "oil-slides.contract/v2",
        "track": "unified",
        "selection_order": list(SELECTION_ORDER),
        "detail_command": f"{cli_path()} contract --id <template-name>",
        "design": {
            "palettes": sorted(PALETTES),
            "typography": sorted(TYPE_PROFILES),
            "shape": sorted(SHAPE_PROFILES),
            "backgrounds": BACKGROUND_PRESETS,
            "click_navigation_default": False,
        },
        "program_owned": program_owned,
        "deck_fields": DECK_FIELDS,
        "slide_fields": SHARED_SLIDE_FIELDS,
        "families": {
            name: {**FAMILY_GUIDANCE[name], "templates": templates_by_family[name]}
            for name in FAMILY_GUIDANCE
        },
        "template_count": len(COMPONENT_CONTRACTS),
        "showing": "all",
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["registry_digest"] = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if item_id:
        normalized = item_id.removeprefix("template.")
        match = next(
            (entry for family in payload["families"].values() for entry in family["templates"] if entry["name"] == normalized),
            None,
        )
        if match is None:
            available = ", ".join(sorted(COMPONENT_CONTRACTS))
            raise SystemExit(f"Unknown contract id: {item_id}. Available templates: {available}")
        payload = {
            "schema_version": payload["schema_version"],
            "registry_digest": payload["registry_digest"],
            "template": match,
            "shared_slide_fields": SHARED_SLIDE_FIELDS,
            "deck_fields": DECK_FIELDS,
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, separators=None if pretty else (",", ":")))


def read_outline(project: Path) -> tuple[Path, dict]:
    path = project / "outline.json"
    if not path.is_file():
        raise SystemExit(f"Missing outline.json: {project}. Restore the confirmed project outline before changing slides.")
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_outline(data, TEMPLATES)
    enforce_outline_quality(data)
    return path, data


def print_audit(outline_path: Path) -> None:
    path = outline_path.expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"Outline not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_outline(data, TEMPLATES)
    summary = audit_summary(data)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["status"] == "error":
        raise SystemExit(1)


def print_media_verification(outline_path: Path) -> None:
    path = outline_from_target(outline_path)
    if not path.is_file():
        raise SystemExit(f"Outline not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_outline(data, TEMPLATES)
    verified = verify_outline_media(data, path.parent)
    print(json.dumps({
        "schema_version": "oil-slides.media-verify/v1",
        "status": "ok",
        "count": len(verified),
        "media": verified,
    }, ensure_ascii=False, separators=(",", ":")))


def palette_for_project(project: Path, fallback: str = "oil-yellow") -> dict:
    outline = project / "outline.json"
    if not outline.is_file():
        return named_palette(fallback)
    data = json.loads(outline.read_text(encoding="utf-8"))
    value = data.get("palette")
    if isinstance(value, str):
        return named_palette(value)
    if isinstance(value, dict):
        return normalize_palette(value)
    return named_palette(fallback)


def print_media_plan(target: Path, *, write: bool, output: Path | None) -> None:
    outline = outline_from_target(target)
    if not outline.is_file():
        raise SystemExit(f"Missing outline.json: {outline}. Next: {cli_path()} plan {outline.parent}")
    data = json.loads(outline.read_text(encoding="utf-8"))
    validate_outline(data, TEMPLATES)
    plan = build_media_plan(data, outline.parent, cli=str(cli_path()))
    if write:
        destination = (output or outline.parent / "media-plan.json").expanduser().resolve()
        write_media_plan(plan, destination)
        plan["written_to"] = str(destination)
    print(json.dumps(plan, ensure_ascii=False, indent=2))


def create_media_frame(
    source: Path, output: Path, *, project: Path | None, palette_name: str | None,
    ratio: str, padding: str, align: str, fit: str,
) -> None:
    if project:
        palette = palette_for_project(project.expanduser().resolve())
    else:
        palette = named_palette(palette_name or "oil-yellow")
    try:
        details = frame_media(
            source, output, ratio=ratio, padding=padding, align=align, fit=fit, palette=palette,
        )
    except ValueError as error:
        raise SystemExit(f"Media frame failed for {source}: {error}") from error
    print(json.dumps({"schema_version": "oil-slides.media-frame/v1", "ok": True, **details}, ensure_ascii=False, indent=2))


def print_recommendations(outline_path: Path, *, pretty: bool = False) -> None:
    path = outline_path.expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"Outline not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_outline(data, TEMPLATES)
    print(json.dumps(recommend_outline(data), ensure_ascii=False, indent=2 if pretty else None, separators=None if pretty else (",", ":")))


def write_outline(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def final_output_path(project_arg: Path) -> Path:
    return project_arg.expanduser().resolve() / DEFAULT_FINAL_NAME


def outline_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_digest(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def asset_manifest(outline: Path) -> dict[str, str]:
    data = json.loads(outline.read_text(encoding="utf-8"))
    result: dict[str, str] = {}
    for slide in data.get("slides") or []:
        if not isinstance(slide, dict):
            continue
        value = slide.get("image") or slide.get("media") or slide.get("artifact_image")
        if not value:
            continue
        path = (outline.parent / str(value)).resolve()
        if outline.parent.resolve() not in path.parents:
            raise SystemExit(f"Preview asset must stay inside the project: {value}")
        if not path.is_file():
            raise SystemExit(f"Preview asset is missing: {value}")
        result[str(value)] = outline_digest(path)
    return result


def preview_state_path(outline_path: Path) -> Path:
    outline = outline_path.expanduser().resolve()
    return outline.parent / f".oil-slides-preview-{outline.stem}.json"


def preview_state_status(outline: Path) -> tuple[str, dict | None, str | None]:
    path = preview_state_path(outline)
    if not path.is_file():
        return "missing", None, "preview state does not exist"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "stale", None, "preview state is invalid JSON"
    if not outline.is_file():
        return "stale", state, "outline.json is missing"
    if state.get("outline_sha256") != json_digest(outline):
        return "stale", state, "outline.json changed after preview"
    preview = Path(str(state.get("preview") or "")).expanduser().resolve()
    if not preview.is_file():
        return "stale", state, "preview HTML is missing"
    if state.get("preview_sha256") != outline_digest(preview):
        return "stale", state, "preview HTML changed after generation"
    try:
        current_assets = asset_manifest(outline)
    except SystemExit as error:
        return "stale", state, str(error)
    if state.get("assets") != current_assets:
        return "stale", state, "media assets changed after preview"
    return "confirmed" if state.get("confirmed") is True else "awaiting-confirmation", state, None


def status_payload(project_arg: Path) -> dict:
    project = project_arg.expanduser().resolve()
    markdown = project / "outline.md"
    outline = project / "outline.json"
    preview = project / "预览.html"
    final = project / DEFAULT_FINAL_NAME
    blockers: list[dict] = []
    artifacts = {
        "outline_markdown": markdown.is_file(),
        "outline_json": outline.is_file(),
        "preview": preview.is_file(),
        "deck_project": (project / "deck.json").is_file(),
        "final": final.is_file(),
    }
    outline_ok = outline_confirmation_valid(project)
    plan_ok = False
    plan_error = None
    if outline.is_file():
        try:
            data = json.loads(outline.read_text(encoding="utf-8"))
            validate_outline(data, TEMPLATES)
            plan_ok = True
        except (json.JSONDecodeError, SystemExit) as error:
            plan_error = str(error)
    preview_status, preview_state, stale_reason = preview_state_status(outline)
    markdown_is_starter = (
        markdown.is_file()
        and markdown.read_text(encoding="utf-8").strip() == OUTLINE_MARKDOWN_TEMPLATE.strip()
    )
    if not markdown.is_file() or markdown_is_starter:
        phase = "needs_outline"
        blockers.append({"path": str(markdown), "message": "Markdown 大纲尚未填写" if markdown_is_starter else "Markdown 大纲尚不存在"})
        next_command = f"{cli_path()} init {project}" if not project.exists() or not any(project.iterdir()) else None
    elif not outline_ok:
        phase = "needs_outline_confirmation"
        blockers.append({"path": str(markdown), "message": "当前 Markdown 大纲尚未被用户确认，或确认后又发生变化"})
        next_command = f"{cli_path()} confirm {project} --stage outline --user-confirmed"
    elif not plan_ok:
        phase = "needs_plan"
        blockers.append({"path": str(outline), "message": plan_error or "outline.json 尚不存在"})
        next_command = f"{cli_path()} contract --example"
    elif preview_status in {"missing", "stale"}:
        phase = "needs_preview"
        blockers.append({"path": str(preview), "message": stale_reason or "尚未生成当前计划对应的预览"})
        next_command = f"{cli_path()} preview {project}"
    elif preview_status == "awaiting-confirmation":
        phase = "needs_preview_confirmation"
        blockers.append({"path": str(preview), "message": "当前预览正在等待用户明确确认"})
        next_command = f"{cli_path()} confirm {project} --stage preview --user-confirmed"
    elif not final.is_file():
        phase = "ready_to_build"
        next_command = f"{cli_path()} build {project}"
    else:
        build_state_path = project / BUILD_STATE_NAME
        stale_build = True
        if build_state_path.is_file():
            try:
                build_state = json.loads(build_state_path.read_text(encoding="utf-8"))
                stale_build = (
                    build_state.get("outline_sha256") != json_digest(outline)
                    or build_state.get("assets") != asset_manifest(outline)
                    or build_state.get("output_sha256") != outline_digest(final)
                )
            except (json.JSONDecodeError, SystemExit):
                stale_build = True
        if stale_build:
            phase = "needs_build"
            blockers.append({"path": str(final), "message": "最终文件存在，但构建证据缺失或输入已变化"})
            next_command = f"{cli_path()} build {project}"
        else:
            phase = "complete"
            next_command = None
    return {
        "schema_version": "oil-slides.status/v1",
        "ok": not blockers,
        "code": "OK" if not blockers else phase.upper(),
        "phase": phase,
        "project": str(project),
        "artifacts": artifacts,
        "confirmations": {
            "outline": outline_ok,
            "preview": preview_status == "confirmed",
        },
        "preview_status": preview_status,
        "blockers": blockers,
        "next": {"command": next_command},
    }


def print_status(project: Path, *, as_json: bool) -> None:
    payload = status_payload(project)
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"phase: {payload['phase']}")
    print(f"project: {payload['project']}")
    for blocker in payload["blockers"]:
        print(f"blocker: {blocker['message']} ({blocker['path']})")
    print(f"next: {payload['next']['command'] or '-'}")


def generate_preview(target_path: Path, output: Path | None, open_browser: bool) -> None:
    outline = outline_from_target(target_path)
    if not outline.is_file():
        raise SystemExit(f"Outline not found: {outline}. Next: {cli_path()} contract --example")
    target_was_project = target_path.expanduser().resolve().is_dir()
    if target_was_project and (outline.parent / "outline.md").is_file() and not outline_confirmation_valid(outline.parent):
        raise SystemExit(
            f"Preview blocked because the current outline.md is not confirmed. "
            f"Next: {cli_path()} confirm {outline.parent} --stage outline --user-confirmed"
        )
    check = check_project(outline)
    if not check["ok"]:
        print(json.dumps(check, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    data = json.loads(outline.read_text(encoding="utf-8"))
    validate_outline(data, TEMPLATES)
    enforce_outline_quality(data)
    target = (output or outline.parent / "预览.html").expanduser().resolve()
    command = [str(outline), "--out", str(target)]
    if not open_browser:
        command.append("--no-open")
    run_script("render_outline_review.py", command)
    preview_state_path(outline).write_text(
        json.dumps(
            {
                "outline": str(outline),
                "outline_sha256": json_digest(outline),
                "preview": str(target),
                "preview_sha256": outline_digest(target),
                "assets": asset_manifest(outline),
                "confirmed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "ok": True,
        "phase": "needs_preview_confirmation",
        "project": str(outline.parent),
        "preview": str(target),
        "opened": open_browser,
        "next": {"command": f"{cli_path()} confirm {outline.parent} --stage preview --user-confirmed"},
    }, ensure_ascii=False, indent=2))


def confirm_preview(target_path: Path, user_confirmed: bool) -> None:
    if not user_confirmed:
        raise SystemExit("Confirmation requires --user-confirmed after the user explicitly approves the preview.")
    outline = outline_from_target(target_path)
    state_path = preview_state_path(outline)
    if not outline.is_file() or not state_path.is_file():
        raise SystemExit("Preview confirmation requires an existing outline and generated 预览.html.")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("outline_sha256") != json_digest(outline):
        raise SystemExit("Outline changed after preview. Regenerate 预览.html before confirmation.")
    preview = Path(str(state.get("preview") or "")).expanduser().resolve()
    if not preview.is_file():
        raise SystemExit("Preview HTML is missing. Regenerate it before confirmation.")
    if state.get("preview_sha256") != outline_digest(preview):
        raise SystemExit("Preview HTML changed after generation. Regenerate it before confirmation.")
    if state.get("assets") != asset_manifest(outline):
        raise SystemExit("Preview assets changed after generation. Regenerate the preview before confirmation.")
    state["confirmed"] = True
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True, "phase": "ready_to_build", "project": str(outline.parent),
        "preview": str(preview), "next": {"command": f"{cli_path()} build {outline.parent}"},
    }, ensure_ascii=False, indent=2))


def require_preview_confirmation(outline_path: Path) -> dict:
    outline = outline_path.expanduser().resolve()
    state_path = preview_state_path(outline)
    if not state_path.is_file():
        raise SystemExit("Scaffold blocked: generate 预览.html and wait for user confirmation first.")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("outline_sha256") != json_digest(outline):
        raise SystemExit("Scaffold blocked: outline changed after preview; regenerate and reconfirm.")
    if state.get("confirmed") is not True:
        raise SystemExit("Scaffold blocked: preview has not been confirmed by the user.")
    preview = Path(str(state.get("preview") or "")).expanduser().resolve()
    if not preview.is_file():
        raise SystemExit("Scaffold blocked: preview HTML is missing.")
    if state.get("preview_sha256") != outline_digest(preview):
        raise SystemExit("Scaffold blocked: preview HTML changed after generation.")
    if state.get("assets") != asset_manifest(outline):
        raise SystemExit("Scaffold blocked: preview assets changed after generation.")
    return state


def remove_slide(project_arg: Path, slide_id: str) -> None:
    project, config = read_config(project_arg)
    outline_path, outline = read_outline(project)
    slides = config.get("slides", [])
    target = None
    for relative in slides:
        if slide_meta(project / relative)[0] == slide_id:
            target = relative
            break
    if target is None:
        raise SystemExit(f"Slide id not found: {slide_id}")
    if len(slides) == 1:
        raise SystemExit("Refusing to remove the only slide.")
    config["slides"] = [item for item in slides if item != target]
    (project / "deck.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (project / target).unlink(missing_ok=True)
    outline["slides"] = [item for item in outline["slides"] if item["id"] != slide_id]
    write_outline(outline_path, outline)
    print(f"Removed {slide_id}: {target}")


def materialize_slides(project: Path, data: dict, slides: list[dict]) -> None:
    resolved, config = read_config(project)
    for path in (resolved / "slides").glob("*.html"):
        path.unlink()
    config["slides"] = []
    (resolved / "deck.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for slide in slides:
        command = [
            str(resolved), "--template", slide["template"], "--id", slide["id"], "--title", slide["title"],
            "--variant", slide["variant"], "--decor", slide["decor"],
        ]
        if slide.get("highlight"):
            command.extend(["--highlight", slide["highlight"]])
        if slide.get("background"):
            command.extend(["--background", slide["background"]])
        run_script("add_slide.py", command)
    outline_path = resolved / "outline.json"
    outline_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_script("fill_slots.py", [str(resolved), "--outline", str(outline_path)])


def build_project(project_arg: Path) -> None:
    project = project_arg.expanduser().resolve()
    outline = project / "outline.json"
    require_preview_confirmation(outline)
    if not (project / "deck.json").is_file():
        scaffold(project, outline)
    project, _ = read_config(project)
    _, data = read_outline(project)
    materialize_slides(project, data, data["slides"])
    output = final_output_path(project)
    run_script("build_deck.py", [str(project)])
    if not output.is_file():
        raise SystemExit(f"Build completed without the expected final file: {output}")
    atomic_write_json(project / BUILD_STATE_NAME, {
        "schema_version": "oil-slides.build/v1",
        "project": str(project),
        "outline_sha256": json_digest(project / "outline.json"),
        "assets": asset_manifest(project / "outline.json"),
        "output": str(output),
        "output_sha256": outline_digest(output),
        "renderer": "oil-ppt deterministic HTML",
    })
    print(json.dumps({
        "ok": True, "phase": "complete", "project": str(project), "output": str(output),
        "next": {"command": None},
    }, ensure_ascii=False, indent=2))


def scaffold(project: Path, outline_path: Path) -> None:
    project = project.expanduser().resolve()
    outline_path = outline_path.expanduser().resolve()
    preview_state = require_preview_confirmation(outline_path)
    outline_text = outline_path.read_text(encoding="utf-8")
    data = json.loads(outline_text)
    slides = validate_outline(data, TEMPLATES)
    if project.exists():
        existing = list(project.iterdir())
        state_path = preview_state_path(outline_path)
        preview_path = Path(preview_state["preview"]).expanduser().resolve()
        markdown_outline = project / "outline.md"
        allowed_paths = {
            outline_path, state_path, markdown_outline, project / "assets", project / ".DS_Store",
            project_state_path(project), project / "media-plan.json",
        }
        if preview_path.parent == project:
            allowed_paths.add(preview_path)
        allowed = [item for item in existing if item.resolve() in allowed_paths]
        unexpected = [item for item in existing if item.resolve() not in allowed_paths]
        if unexpected:
            raise SystemExit(f"Refusing to overwrite non-empty directory: {project}")
    arguments = [str(project), "--title", str(data.get("title") or slides[0]["title"]), "--allow-existing-assets"]
    palette = data["palette"]
    if isinstance(palette, dict):
        if data.get("palette_source") not in {"user", "brand"}:
            raise SystemExit(
                "Custom outline palette is allowed only when palette_source is 'user' or 'brand'. "
                "Otherwise choose a curated named palette."
            )
        colors = [palette.get(key) for key in ("accent", "accent_soft", "accent_strong")]
        if not all(isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value) for value in colors):
            raise SystemExit("Outline palette requires accent, accent_soft and accent_strong as six-digit hex colors.")
        arguments.extend(["--accent", colors[0], "--accent-soft", colors[1], "--accent-strong", colors[2]])
    elif isinstance(palette, str) and canonical_name(palette) in PALETTES:
        arguments.extend(["--palette", palette])
    else:
        choices = ", ".join(sorted(PALETTES))
        raise SystemExit(f"Outline palette must be one curated name ({choices}) or a user/brand custom palette.")
    if data.get("next_preview") is False:
        arguments.append("--no-next-preview")
    if data["click_navigation"]:
        arguments.append("--click-navigation")
    if data.get("show_progress") is False:
        arguments.append("--no-progress")
    if data.get("show_counter") is False:
        arguments.append("--no-counter")
    type_profile = str(data["typography"]).strip().lower()
    shape_profile = str(data["shape"]).strip().lower()
    if type_profile not in TYPE_PROFILES:
        raise SystemExit(f"Outline typography must be one of: {', '.join(TYPE_PROFILES)}.")
    if shape_profile not in SHAPE_PROFILES:
        raise SystemExit(f"Outline shape must be one of: {', '.join(SHAPE_PROFILES)}.")
    arguments.extend(["--type-profile", type_profile, "--shape-profile", shape_profile])
    run_script("init_deck.py", arguments)

    (project / "outline.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scaffolded confirmed project: {project}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create and validate an oil-ppt project through one stateful CLI.",
        epilog=(
            "Workflow: init PROJECT → edit and confirm outline.md → plan PROJECT → "
            "preview PROJECT → confirm preview → build PROJECT. Run `status PROJECT --json` at any time."
        ),
    )
    public_commands = ("init", "status", "plan", "check", "doctor", "contract", "preview", "confirm", "build", "media", "icon")
    sub = parser.add_subparsers(dest="command", metavar="{" + ",".join(public_commands) + "}")
    init_parser = sub.add_parser("init", help="initialize outline.md, assets, and project state")
    init_parser.add_argument("project", type=Path, help="one project root directory")
    status_parser = sub.add_parser("status", help="show the current phase, blockers, and exactly one next command")
    status_parser.add_argument("project", type=Path, help="project root")
    status_parser.add_argument("--json", action="store_true", help="emit a stable machine-readable envelope")
    plan_parser = sub.add_parser("plan", help="validate and install the visual outline.json after Markdown approval")
    plan_parser.add_argument("project", type=Path, help="project root")
    plan_parser.add_argument("--input", type=Path, help="optional candidate JSON to validate and copy into the project")
    check_parser = sub.add_parser("check", help="validate schema, deck rhythm, recommendations, and all bound media")
    check_parser.add_argument("target", type=Path, help="project root or outline.json")
    sub.add_parser("doctor", help="run dependency, contract, browser, and end-to-end self tests")
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("outline", type=Path, help="project root or outline.json")
    recommend_parser = sub.add_parser("recommend")
    recommend_parser.add_argument("outline", type=Path, help="project root or outline.json")
    recommend_parser.add_argument("--pretty", action="store_true")
    contract_parser = sub.add_parser("contract", help="inspect the executable layout and field contract")
    contract_parser.add_argument(
        "--all",
        action="store_true",
        help="compatibility flag; every template is always included",
    )
    contract_parser.add_argument("--id", help="show one template contract, e.g. photo-gradient")
    contract_parser.add_argument("--list", action="store_true", help="list template names, families, and use cases")
    contract_parser.add_argument("--schema", action="store_true", help="print the outline JSON Schema")
    contract_parser.add_argument("--example", action="store_true", help="print a minimal valid outline.json")
    contract_parser.add_argument("--pretty", action="store_true", help=argparse.SUPPRESS)
    contract_parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    preview_parser = sub.add_parser("preview", help="run checks and create the final-material HTML preview")
    preview_parser.add_argument("outline", type=Path, help="project root or outline.json")
    preview_parser.add_argument("--out", type=Path)
    preview_parser.add_argument("--open", action="store_true", help="open the preview in a browser; default is headless")
    preview_parser.add_argument("--no-open", action="store_true", help=argparse.SUPPRESS)
    confirm_parser = sub.add_parser("confirm", help="record explicit user approval for outline or preview")
    confirm_parser.add_argument("outline", type=Path, help="project root or outline.json")
    confirm_parser.add_argument("--stage", choices=("outline", "preview"), help="defaults to preview for compatibility")
    confirm_parser.add_argument("--user-confirmed", action="store_true", help="required explicit attestation")
    scaffold_parser = sub.add_parser("scaffold")
    scaffold_parser.add_argument("project", type=Path)
    scaffold_parser.add_argument("outline", type=Path)
    list_parser = sub.add_parser("list")
    list_parser.add_argument("project", type=Path)
    add_parser = sub.add_parser("add")
    add_parser.add_argument("project", type=Path)
    add_parser.add_argument("--slide-json", type=Path, required=True, help="one complete slide object")
    add_parser.add_argument("--after")
    remove_parser = sub.add_parser("remove")
    remove_parser.add_argument("project", type=Path)
    remove_parser.add_argument("slide_id")
    build_parser = sub.add_parser("build", help="enforce the preview gate, scaffold internally, validate, and emit 演示文稿.html")
    build_parser.add_argument("project", type=Path, help="project root")
    sync_parser = sub.add_parser("sync")
    sync_parser.add_argument("project", type=Path)
    media_parser = sub.add_parser("media", help="plan, verify, adapt, and render media assets")
    media_sub = media_parser.add_subparsers(
        dest="media_command",
        required=True,
        metavar="{plan,frame}",
    )
    media_sub.add_parser("sources")
    media_plan_parser = media_sub.add_parser("plan", help="compile slide media into roles, fidelity, ratios, and commands")
    media_plan_parser.add_argument("target", type=Path, help="project root or outline.json")
    media_plan_parser.add_argument("--write", action="store_true", help="also write media-plan.json in the project")
    media_plan_parser.add_argument("--out", type=Path, help="override the media plan output path")
    media_verify = media_sub.add_parser("verify")
    media_verify.add_argument("outline", type=Path, help="project root or outline.json")
    media_frame_parser = media_sub.add_parser("frame", help="preserve a screenshot on a slot-matched block background")
    media_frame_parser.add_argument("source", type=Path)
    media_frame_parser.add_argument("output", type=Path)
    media_frame_parser.add_argument("--project", type=Path, help="read the current palette from this project")
    media_frame_parser.add_argument("--palette", choices=sorted(PALETTES), help="named palette when no project is supplied")
    media_frame_parser.add_argument("--ratio", choices=("16:9", "16:10", "4:3", "1:1", "21:9"), default="16:10")
    media_frame_parser.add_argument("--padding", choices=("compact", "standard", "spacious"), default="standard")
    media_frame_parser.add_argument("--align", choices=("center", "left", "right", "top", "bottom", "top-left", "top-right", "bottom-left", "bottom-right"), default="center")
    media_frame_parser.add_argument("--fit", choices=("contain", "cover"), default="contain")
    media_render = media_sub.add_parser("render-html")
    media_render.add_argument("source", type=Path)
    media_render.add_argument("output", type=Path)
    media_render.add_argument("--width", type=int, default=1600)
    media_render.add_argument("--height", type=int, default=900)
    icon_parser = sub.add_parser("icon", help="discover and verify the bundled icon vocabulary")
    icon_sub = icon_parser.add_subparsers(dest="icon_command", required=True)
    icon_sub.add_parser("list")
    icon_search = icon_sub.add_parser("search")
    icon_search.add_argument("query")
    icon_sub.add_parser("verify")
    # Compatibility commands remain callable, but they are implementation
    # details and must not compete with the project-level workflow in --help.
    sub._choices_actions = [action for action in sub._choices_actions if action.dest in public_commands]
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        raise SystemExit(0)
    return args


def main() -> None:
    args = parse_args()
    if args.command == "init":
        init_project(args.project)
    elif args.command == "status":
        print_status(args.project, as_json=args.json)
    elif args.command == "plan":
        plan_project(args.project, args.input)
    elif args.command == "check":
        payload = check_project(args.target)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if not payload["ok"]:
            raise SystemExit(1)
    elif args.command == "doctor":
        run_script("doctor.py", [])
    elif args.command == "audit":
        print_audit(outline_from_target(args.outline))
    elif args.command == "recommend":
        print_recommendations(outline_from_target(args.outline), pretty=args.pretty)
    elif args.command == "contract":
        print_contract(
            show_all=bool(getattr(args, "all", False)),
            item_id=getattr(args, "id", None),
            pretty=not bool(getattr(args, "compact", False)),
            show_schema=bool(getattr(args, "schema", False)),
            show_example=bool(getattr(args, "example", False)),
            show_list=bool(getattr(args, "list", False)),
        )
    elif args.command == "preview":
        generate_preview(args.outline, args.out, bool(args.open) and not bool(args.no_open))
    elif args.command == "confirm":
        stage = args.stage or "preview"
        if stage == "outline":
            confirm_outline(project_from_target(args.outline), args.user_confirmed)
        else:
            confirm_preview(args.outline, args.user_confirmed)
    elif args.command == "scaffold":
        scaffold(args.project, args.outline)
    elif args.command == "list":
        list_project(args.project)
    elif args.command == "add":
        project, _ = read_config(args.project)
        outline_path, outline = read_outline(project)
        slide_path = args.slide_json.expanduser().resolve()
        if not slide_path.is_file():
            raise SystemExit(f"Slide JSON not found: {slide_path}")
        slide = json.loads(slide_path.read_text(encoding="utf-8"))
        if not isinstance(slide, dict):
            raise SystemExit("--slide-json must contain one slide object.")
        insert_at = len(outline["slides"])
        if args.after:
            matches = [index for index, item in enumerate(outline["slides"]) if item["id"] == args.after]
            if not matches:
                raise SystemExit(f"Outline slide id not found for --after: {args.after}")
            insert_at = matches[0] + 1
        candidate = dict(outline)
        candidate["slides"] = [*outline["slides"][:insert_at], slide, *outline["slides"][insert_at:]]
        validate_outline(candidate, TEMPLATES)
        command = [str(args.project), "--template", slide["template"], "--id", slide["id"], "--title", slide["title"],
                   "--variant", slide["variant"], "--decor", slide["decor"]]
        if slide.get("highlight"):
            command.extend(["--highlight", slide["highlight"]])
        if slide.get("background"):
            command.extend(["--background", slide["background"]])
        if args.after:
            command.extend(["--after", args.after])
        run_script("add_slide.py", command)
        write_outline(outline_path, candidate)
        run_script("fill_slots.py", [str(project), "--outline", str(outline_path)])
        list_project(args.project)
    elif args.command == "remove":
        remove_slide(args.project, args.slide_id)
        list_project(args.project)
    elif args.command == "build":
        build_project(args.project)
    elif args.command == "sync":
        run_script("sync_runtime.py", [str(args.project)])
    elif args.command == "media":
        if args.media_command == "sources":
            print_sources()
        elif args.media_command == "plan":
            print_media_plan(args.target, write=args.write, output=args.out)
        elif args.media_command == "verify":
            print_media_verification(args.outline)
        elif args.media_command == "frame":
            create_media_frame(
                args.source, args.output, project=args.project, palette_name=args.palette,
                ratio=args.ratio, padding=args.padding, align=args.align, fit=args.fit,
            )
        elif args.media_command == "render-html":
            details = render_html_visual(args.source, args.output, width=args.width, height=args.height)
            print(json.dumps({"schema_version": "oil-slides.programmatic-visual/v1", "status": "ok", **details}, ensure_ascii=False, separators=(",", ":")))
    elif args.command == "icon":
        if args.icon_command == "search":
            print_icon_results(args.query)
        else:
            print_icon_results()


if __name__ == "__main__":
    main()
