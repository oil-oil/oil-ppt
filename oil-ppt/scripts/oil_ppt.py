#!/usr/bin/env python3
"""Single deterministic entry point for oil-ppt project operations."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import webbrowser
from pathlib import Path

from background_presets import BACKGROUND_PRESETS, INTERNAL_BACKGROUNDS, template_background
from build_deck import VALIDATION_STATE_NAME, browser_validate, current_validation_failure, validation_state_path
from capability_catalog import (
    FAMILY_GUIDANCE, PROGRAM_OWNED_CAPABILITIES, SELECTION_ORDER,
    TEMPLATE_DISCOVERY, VARIANT_HELP,
)
from capability_recommender import recommend_outline
from component_contracts import COMPONENT_CONTRACTS, PAGE_BLEND_TEMPLATES, VARIANT_QUALITY, quality_for
from design_quality import audit_summary, enforce_outline_quality
from media_assets import inspect_outline_media, outline_media_bindings, print_sources, verify_outline_media
from media_frame import frame_media
from media_plan import MEDIA_SLOTS, MEDIA_VARIANT_SLOTS, build_media_plan, write_media_plan
from render_programmatic_visual import render_html_visual
from icon_registry import print_icon_results
from outline_schema import BASE_VISIBLE_FIELDS, DECK_FIELDS, MAX_ABS_DATA_VALUE, MEDIA_TEMPLATES, SHARED_SLIDE_FIELDS, SLIDE_ALLOWED_FIELDS, TEMPLATE_CONTENT_HELP, TEMPLATE_FAMILIES, TEMPLATE_VISIBLE_FIELDS, VARIANT_INPUT_GUIDANCE, text_budgets_for, validate_outline
from palette_tokens import PALETTES, TOKEN_KEYS, canonical_name, named_palette, normalize_palette
from profile_tokens import SHAPE_PROFILES, TYPE_PROFILES


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
TEMPLATES = ROOT / "assets" / "templates"
DEFAULT_FINAL_NAME = "演示文稿.html"
PROJECT_STATE_NAME = ".oil-ppt-state.json"
BUILD_STATE_NAME = ".oil-ppt-build.json"
EDIT_DRAFT_NAME = ".oil-ppt-edit-draft.json"
EDIT_LOCK_NAME = ".oil-ppt-edit.lock"
LEGACY_STATE_NAMES = {
    ".oil-slides-state.json": PROJECT_STATE_NAME,
    ".oil-slides-preview-outline.json": ".oil-ppt-preview-outline.json",
    ".oil-slides-build.json": BUILD_STATE_NAME,
}
SLIDE_ID = re.compile(r'data-slide-id=["\']([a-z0-9][a-z0-9-]*)["\']')
SLIDE_TITLE = re.compile(r'data-title=["\']([^"\']+)["\']')


def cli_display() -> str:
    """Resolved executable used by machine-readable commands."""
    return str((SCRIPTS / "oil-ppt").resolve())


def cli_command(*arguments: object) -> str:
    """Return one shell-safe command that works from any current directory."""
    return shlex.join([cli_display(), *(str(argument) for argument in arguments)])


def emit_json(value: object, *, pretty: bool) -> None:
    """Write one JSON value with a consistent compact/pretty policy."""
    print(json.dumps(
        value,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    ))


def verify_expected_sha256(path: Path, expected_sha256: str | None, *, stage: str) -> str:
    """Bind a generated confirmation command to the artifact the user saw."""
    actual = outline_digest(path)
    if expected_sha256 is not None and expected_sha256 != actual:
        raise SystemExit(
            f"{stage} confirmation is stale: the reviewed artifact changed after the command was generated. "
            "Run status again and show the new artifact to the user before confirming it."
        )
    return actual


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


def enclosing_project(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).expanduser().resolve()
    for candidate in (current, *current.parents):
        if project_state_path(candidate).is_file():
            return candidate
    return None


def require_initialized_project(project_arg: Path, action: str) -> Path:
    """Resolve an existing project before reporting any downstream workflow error."""
    requested = project_arg.expanduser()
    project = requested.resolve()
    if not project.is_dir():
        raise SystemExit(
            f"{action} requires an existing oil-ppt project root. "
            f"The supplied path {str(project_arg)!r} resolved to {str(project)!r}, which is not a directory. "
            "Run status from any directory and execute its absolute next.command exactly."
        )
    migrate_legacy_state_files(project)
    if not project_state_path(project).is_file():
        raise SystemExit(
            f"{action} requires an initialized oil-ppt project root, but no {PROJECT_STATE_NAME} exists in {project}. "
            "Do not point build or preview at an output subdirectory."
        )
    return project


def edit_draft_path(project: Path) -> Path:
    return project.expanduser().resolve() / EDIT_DRAFT_NAME


def edit_lock_path(project: Path) -> Path:
    return project.expanduser().resolve() / EDIT_LOCK_NAME


def editor_process_identity(pid: int) -> str | None:
    """Return a stable identity for one live process, not merely its reusable PID."""
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.is_file():
        try:
            fields = proc_stat.read_text(encoding="utf-8").split()
            if len(fields) > 21:
                return f"proc-start:{fields[21]}"
        except OSError:
            pass
    try:
        process = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart=", "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    rendered = process.stdout.strip()
    if process.returncode or not rendered:
        return None
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def editor_lock_payload(project: Path, pid: int | None = None) -> dict:
    process_pid = int(pid or os.getpid())
    return {
        "schema_version": "oil-ppt.editor-lock/v1",
        "pid": process_pid,
        "project": str(project.expanduser().resolve()),
        "process_identity": editor_process_identity(process_pid),
        "created_at": int(time.time()),
    }


def read_editor_lock(project: Path) -> dict | None:
    path = edit_lock_path(project)
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        # An unreadable lock is still a lock. Do not silently remove it and
        # allow a second editor to enter the same project.
        raise
    try:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"pid": int(raw), "legacy": True}
        if isinstance(data, int):
            data = {"pid": data, "legacy": True}
        if (
            not isinstance(data, dict)
            or isinstance(data.get("pid"), bool)
            or not isinstance(data.get("pid"), int)
        ):
            raise ValueError
    except ValueError:
        path.unlink(missing_ok=True)
        return None
    if data.get("project") not in {None, str(project.expanduser().resolve())}:
        path.unlink(missing_ok=True)
        return None
    return data


def active_editor_pid(project: Path) -> int | None:
    path = edit_lock_path(project)
    lock = read_editor_lock(project)
    if lock is None:
        return None
    pid = int(lock["pid"])
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        path.unlink(missing_ok=True)
        return None
    except PermissionError:
        pass
    expected_identity = lock.get("process_identity")
    if expected_identity and editor_process_identity(pid) != expected_identity:
        path.unlink(missing_ok=True)
        return None
    return pid


def editor_lock_owned_by_current_process(project: Path) -> bool:
    lock = read_editor_lock(project)
    if lock is None or lock.get("pid") != os.getpid():
        return False
    expected_identity = lock.get("process_identity")
    return not expected_identity or editor_process_identity(os.getpid()) == expected_identity


def launch_text_editor(project: Path, *, port: int = 0) -> dict:
    """Start the authoring server in the background and return its stable local URL."""
    project = require_initialized_project(project, "Preview editor")
    existing = active_editor_pid(project)
    if existing is not None:
        raise SystemExit(
            f"A preview editor is already open for {project} (pid {existing}). "
            "Return to that browser tab or close it before starting another editor."
        )
    if port == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = int(probe.getsockname()[1])
    process = subprocess.Popen(
        [sys.executable, str(SCRIPTS / "text_editor.py"), str(project), "--port", str(port)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if active_editor_pid(project) == process.pid:
            return {
                "pid": process.pid,
                "url": f"http://127.0.0.1:{port}/",
            }
        if process.poll() is not None:
            break
        time.sleep(.05)
    if process.poll() is None:
        process.terminate()
    raise SystemExit(
        f"Could not start the editable preview for {project}. "
        f"Run {cli_command('edit', project)} to see the editor error directly."
    )


def require_no_edit_draft(project: Path, action: str) -> None:
    draft = edit_draft_path(project)
    if draft.is_file():
        raise SystemExit(
            f"{action} blocked while a text-edit draft exists: {draft}. "
            f"Reopen {cli_command('edit', project)} and finish or explicitly discard the draft."
        )
    pid = active_editor_pid(project)
    if pid is not None and pid != os.getpid():
        raise SystemExit(
            f"{action} blocked while the text editor is open for this project (pid {pid}). "
            "Finish editing or close that editor process first."
        )


def migrate_legacy_state_files(project: Path) -> None:
    """Atomically adopt state written by the retired public command name."""
    if not project.is_dir():
        return
    for legacy_name, current_name in LEGACY_STATE_NAMES.items():
        legacy = project / legacy_name
        if not legacy.is_file():
            continue
        current = project / current_name
        if current.exists():
            legacy.unlink()
        else:
            os.replace(legacy, current)


def read_project_state(project: Path) -> dict:
    migrate_legacy_state_files(project)
    path = project_state_path(project)
    if not path.is_file():
        return {"schema_version": "oil-ppt.project-state/v1", "history": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("project state must be a JSON object")
        return data
    except (json.JSONDecodeError, ValueError) as error:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"{path.stem}.invalid-{timestamp}-{os.getpid()}{path.suffix}")
        os.replace(path, backup)
        recovered = {
            "schema_version": "oil-ppt.project-state/v1",
            "history": [{"event": "invalid_state_recovered", "backup": str(backup)}],
            "recovery": {"invalid_state_backup": str(backup), "reason": str(error)},
        }
        atomic_write_json(path, recovered)
        return recovered


def run_script(name: str, arguments: list[str]) -> None:
    try:
        proc = subprocess.run([sys.executable, str(SCRIPTS / name), *arguments], check=False)
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    if proc.returncode:
        raise SystemExit(proc.returncode)


def run_script_quiet(name: str, arguments: list[str]) -> None:
    """Run one internal renderer without contaminating the public JSON stream."""
    try:
        process = subprocess.run(
            [sys.executable, str(SCRIPTS / name), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    if process.returncode:
        detail = process.stderr.strip() or process.stdout.strip() or f"{name} exited with {process.returncode}"
        raise SystemExit(detail)


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
- 素材及其回答的问题（已有 / 搜索 / 生成 / 程序化 / 确认无需；只写内容关系，不指定组件或图表类型）：

### 02｜

- 核心判断：
- 支撑内容：
- 素材及其回答的问题（已有 / 搜索 / 生成 / 程序化 / 确认无需；只写内容关系，不指定组件或图表类型）：
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
        "schema_version": "oil-ppt.project-state/v1",
        "history": [{"event": "initialized"}],
    })
    print(json.dumps({
        "ok": True,
        "phase": "needs_outline",
        "project": str(project),
        "created": [str(project / "outline.md"), str(project / "assets")],
        "next": {"action": "edit_outline", "command": None, "path": str(project / "outline.md")},
    }, ensure_ascii=False, indent=2))


def example_outline() -> dict:
    return {
        "title": "演示标题",
        "palette": "oil-yellow",
        "typography": "clean",
        "shape": "soft",
        "media_policy": "required",
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
            {
                "id": "evidence", "title": "真实证据承担主要画面",
                "content": "用一句话解释这张素材如何支持本页判断。",
                "template": "split-visual", "variant": "media-dominant", "decor": "none",
                "image": "assets/main-evidence.png", "image_alt": "与核心判断直接相关的真实证据",
                "media_frame": "content", "media_role": "main-evidence", "media_fidelity": "strict",
                "media_question": "这张证据如何支持本页判断？",
            },
            {"id": "end", "title": "让观众带走一句话", "template": "end", "variant": "line", "decor": "none"},
        ],
    }


def contract_schema() -> dict:
    def bounded_text(template: str, path: str, variant: str | None = None) -> dict:
        maximum = text_budgets_for(template, variant)[path]
        return {
            "type": "string",
            "minLength": 1,
            "pattern": rf"^(?:\s*\S){{1,{maximum}}}\s*$",
        }

    definitions = {
        "evidence": {
            "oneOf": [
                {"type": "string", "minLength": 1},
                {
                    "type": "object", "required": ["image"], "additionalProperties": False,
                    "properties": {
                        "image": {"type": "string", "minLength": 1},
                        "caption": {"type": "string", "minLength": 1},
                        "alt": {"type": "string", "minLength": 1},
                    },
                },
            ],
        },
        "card": {
            "type": "object", "required": ["body"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
                "icon": {"type": "string", "minLength": 1},
                "backdrop": {"type": "string", "minLength": 1},
                "images": {"type": "array", "items": {"$ref": "#/$defs/evidence"}},
            },
        },
        "plainCard": {
            "type": "object", "required": ["body"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
            },
        },
        "iconCard": {
            "type": "object", "required": ["body"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
                "icon": {"type": "string", "minLength": 1},
            },
        },
        "evidenceCard": {
            "type": "object", "required": ["body", "images"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
                "images": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"$ref": "#/$defs/evidence"}},
            },
        },
        "decisionCard": {
            "type": "object", "required": ["body"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
                "backdrop": {"type": "string", "minLength": 1},
            },
        },
        "step": {
            "type": "object", "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
                "icon": {"type": "string", "minLength": 1},
                "image": {"type": "string", "minLength": 1},
                "image_alt": {"type": "string", "minLength": 1},
                "media_question": {"type": "string", "minLength": 1},
                "media_source": {"$ref": "#/$defs/mediaSource"},
            },
        },
        "stepBody": {
            "type": "object", "required": ["body"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
            },
        },
        "cycleStep": {
            "type": "object", "required": ["body"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": bounded_text("cycle", "steps[].title"),
                "label": bounded_text("cycle", "steps[].title"),
                "body": bounded_text("cycle", "steps[].body"),
            },
        },
        "tierStep": {
            "type": "object", "required": ["body"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": bounded_text("tier-stack", "steps[].title"),
                "label": bounded_text("tier-stack", "steps[].title"),
                "body": bounded_text("tier-stack", "steps[].body"),
            },
        },
        "stepIconBody": {
            "type": "object", "required": ["body"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
                "icon": {"type": "string", "minLength": 1},
            },
        },
        "stepMediaBody": {
            "type": "object", "required": ["body", "image"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
                "image": {"type": "string", "minLength": 1},
                "image_alt": {"type": "string", "minLength": 1},
                "media_question": {"type": "string", "minLength": 1},
                "media_source": {"$ref": "#/$defs/mediaSource"},
            },
        },
        "stepLabel": {
            "type": "object", "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
            },
        },
        "point": {
            "oneOf": [
                {"type": "string", "minLength": 1},
                {
                    "type": "object", "required": ["body"], "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string", "minLength": 1},
                        "body": {"type": "string", "minLength": 1},
                    },
                },
            ],
        },
        "pointBody": {
            "oneOf": [
                {"type": "string", "minLength": 1},
                {
                    "type": "object", "required": ["body"], "additionalProperties": False,
                    "properties": {"body": {"type": "string", "minLength": 1}},
                },
            ],
        },
        "pointFinding": {
            "oneOf": [
                {"type": "string", "minLength": 1},
                {
                    "type": "object", "required": ["body"], "additionalProperties": False,
                    "not": {"required": ["title", "label"]},
                    "properties": {
                        "title": {"type": "string", "minLength": 1},
                        "label": {"type": "string", "minLength": 1},
                        "body": {"type": "string", "minLength": 1},
                    },
                },
            ],
        },
        "side": {
            "type": "object", "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
                "lead": {"type": "string", "minLength": 1},
                "points": {"type": "array", "items": {"$ref": "#/$defs/point"}},
                "evidence": {"type": "array", "items": {"$ref": "#/$defs/evidence"}},
            },
        },
        "plainSide": {
            "type": "object", "required": ["points"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "points": {"type": "array", "items": {"$ref": "#/$defs/pointBody"}},
            },
        },
        "visualSide": {
            "type": "object", "required": ["points", "evidence"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "lead": {"type": "string", "minLength": 1},
                "points": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"$ref": "#/$defs/pointFinding"}},
                "evidence": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"$ref": "#/$defs/evidence"}},
            },
        },
        "tabSide": {
            "type": "object", "required": ["body"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
            },
        },
        "groupItem": {
            "type": "object", "required": ["title", "body"], "additionalProperties": False,
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
            },
        },
        "group": {
            "type": "object", "required": ["items"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "meta": {"type": "string", "minLength": 1},
                "items": {"type": "array", "items": {"oneOf": [
                    {"type": "string", "minLength": 1}, {"$ref": "#/$defs/groupItem"},
                ]}},
            },
        },
        "convergeGroup": {
            "type": "object", "required": ["items"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "items": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "string", "minLength": 1}},
            },
        },
        "quadrantGroup": {
            "type": "object", "required": ["meta", "items"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": bounded_text("quadrant", "groups[].title"),
                "label": bounded_text("quadrant", "groups[].title"),
                "meta": bounded_text("quadrant", "groups[].meta"),
                "emphasis": {"type": "boolean"},
                "items": {
                    "type": "array", "minItems": 1, "maxItems": 3,
                    "items": bounded_text("quadrant", "groups[].items[]"),
                },
            },
        },
        "axes": {
            "type": "object", "required": ["x", "y"], "additionalProperties": False,
            "properties": {
                "x": bounded_text("quadrant", "axes.x"),
                "y": bounded_text("quadrant", "axes.y"),
            },
        },
        "measurement": {
            "type": "object", "required": ["value", "label"], "additionalProperties": False,
            "properties": {
                "value": {"oneOf": [
                    {"type": "string", "minLength": 1, "pattern": ".*\\S.*"}, {"type": "number"},
                ]},
                "label": {"type": "string", "minLength": 1},
            },
        },
        "catalogMeasurement": {
            "type": "object", "required": ["value", "label"], "additionalProperties": False,
            "properties": {
                "value": {
                    "oneOf": [bounded_text("catalog-board", "metrics[].value"), {"type": "number"}],
                    "x-oil-nonspace-max": text_budgets_for("catalog-board")["metrics[].value"],
                },
                "label": bounded_text("catalog-board", "metrics[].label"),
            },
        },
        "catalogGroupItem": {
            "type": "object", "required": ["body"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": bounded_text("catalog-board", "groups[].items[].title"),
                "label": bounded_text("catalog-board", "groups[].items[].title"),
                "body": bounded_text("catalog-board", "groups[].items[].body"),
            },
        },
        "catalogGroup": {
            "type": "object", "required": ["meta", "items"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": bounded_text("catalog-board", "groups[].title"),
                "label": bounded_text("catalog-board", "groups[].title"),
                "meta": bounded_text("catalog-board", "groups[].meta"),
                "items": {
                    "type": "array", "minItems": 3, "maxItems": 3,
                    "items": {"$ref": "#/$defs/catalogGroupItem"},
                },
            },
        },
        "dataValueItem": {
            "type": "object", "required": ["label", "value"], "additionalProperties": False,
            "properties": {
                "label": {"type": "string", "minLength": 1},
                "value": {"type": "number", "minimum": -MAX_ABS_DATA_VALUE, "maximum": MAX_ABS_DATA_VALUE},
            },
        },
        "dataRelationshipItem": {
            "type": "object", "required": ["label", "x", "y"], "additionalProperties": False,
            "properties": {
                "label": bounded_text("data-story", "data.items[].label", "relationship"),
                "x": {"type": "number", "minimum": -MAX_ABS_DATA_VALUE, "maximum": MAX_ABS_DATA_VALUE},
                "y": {"type": "number", "minimum": -MAX_ABS_DATA_VALUE, "maximum": MAX_ABS_DATA_VALUE},
            },
        },
        "relationshipNode": {
            "type": "object",
            "required": ["id", "title", "body"],
            "additionalProperties": False,
            "properties": {
                "id": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
                "title": bounded_text("relationship-map", "nodes[].title"),
                "body": bounded_text("relationship-map", "nodes[].body"),
                "emphasis": {"type": "boolean"},
            },
        },
        "relationshipLink": {
            "type": "object",
            "required": ["source", "target", "label"],
            "additionalProperties": False,
            "properties": {
                "source": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
                "target": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
                "label": bounded_text("relationship-map", "links[].label"),
            },
        },
        "decisionOption": {
            "type": "object",
            "required": ["title", "scores"],
            "additionalProperties": False,
            "properties": {
                "title": bounded_text("decision-matrix", "options[].title"),
                "scores": {
                    "type": "array", "minItems": 3, "maxItems": 3,
                    "items": {"type": "integer", "minimum": 1, "maximum": 5},
                },
            },
        },
        "annotation": {
            "type": "object", "required": ["body"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": bounded_text("annotated-showcase", "annotations[].title"),
                "label": bounded_text("annotated-showcase", "annotations[].title"),
                "body": bounded_text("annotated-showcase", "annotations[].body"),
            },
        },
        "mediaSource": {
            "type": "object",
            "description": "Source and rights metadata such as kind, url, author, license, rights and modifications.",
            "properties": {
                "kind": {"type": "string", "minLength": 1, "description": "user-material, generated, programmatic-visual, Wikimedia, Pexels, or another explicit source type"},
                "url": {"type": "string", "minLength": 1},
                "author": {"type": "string", "minLength": 1},
                "license": {"type": "string", "minLength": 1},
                "rights": {"type": "string", "minLength": 1, "description": "why this deck may use the asset"},
                "modifications": {"type": "string", "minLength": 1},
            },
        },
    }
    string_fields = {
        key: ({"type": "string"} if key in {"image_alt", "secondary_image_alt"} else {"type": "string", "minLength": 1})
        for key in SLIDE_ALLOWED_FIELDS
        if key not in {
            "cards", "steps", "sides", "groups", "nodes", "links", "criteria", "options",
            "metrics", "annotations", "measurements", "metric", "insight", "chart", "data",
            "axes", "media_source",
        }
    }
    structured_fields = {
        "cards": {"type": "array", "items": {"$ref": "#/$defs/card"}},
        "steps": {"type": "array", "items": {"$ref": "#/$defs/step"}},
        "sides": {"type": "array", "items": {"$ref": "#/$defs/side"}},
        "groups": {"type": "array"},
        "nodes": {"type": "array", "items": {"$ref": "#/$defs/relationshipNode"}},
        "links": {"type": "array", "items": {"$ref": "#/$defs/relationshipLink"}},
        "criteria": {"type": "array", "items": bounded_text("decision-matrix", "criteria[]")},
        "options": {"type": "array", "items": {"$ref": "#/$defs/decisionOption"}},
        "metrics": {"type": "array", "items": {"$ref": "#/$defs/measurement"}},
        "annotations": {"type": "array", "items": {"$ref": "#/$defs/annotation"}},
        "measurements": {"type": "array", "items": {"$ref": "#/$defs/measurement"}},
        "metric": {
            "type": "object", "required": ["value", "unit", "caption"], "additionalProperties": False,
            "properties": {
                "value": {"oneOf": [
                    bounded_text("metric", "metric.value"), {"type": "number"},
                ]},
                "unit": bounded_text("metric", "metric.unit"),
                "caption": bounded_text("metric", "metric.caption"),
                "change": {"oneOf": [
                    bounded_text("metric", "metric.change", "delta"), {"type": "number"},
                ]},
                "change_label": bounded_text("metric", "metric.change_label", "delta"),
                "target": {"type": "number", "exclusiveMinimum": 0, "maximum": MAX_ABS_DATA_VALUE},
            },
        },
        "insight": {
            "type": "object", "required": ["body"], "additionalProperties": False,
            "oneOf": [{"required": ["title"]}, {"required": ["label"]}],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "label": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
                "icon": {"type": "string", "minLength": 1},
            },
        },
        "chart": {
            "type": "object", "required": ["label", "values"], "additionalProperties": False,
            "properties": {
                "label": {"type": "string", "minLength": 1},
                "values": {"type": "array", "minItems": 3, "maxItems": 7, "items": {"type": "number", "minimum": 0}},
            },
        },
        "data": {
            "oneOf": [
                {
                    "type": "object", "required": ["items"], "additionalProperties": False,
                    "properties": {
                        "items": {"type": "array", "minItems": 2, "maxItems": 8, "items": {"$ref": "#/$defs/dataValueItem"}},
                        "unit": bounded_text("data-story", "data.unit", "category-comparison"),
                        "precision": {"type": "integer", "minimum": 0, "maximum": 6},
                    },
                },
                {
                    "type": "object", "required": ["items", "x_label", "y_label"], "additionalProperties": False,
                    "properties": {
                        "items": {"type": "array", "minItems": 3, "maxItems": 12, "items": {"$ref": "#/$defs/dataRelationshipItem"}},
                        "x_label": bounded_text("data-story", "data.x_label", "relationship"),
                        "y_label": bounded_text("data-story", "data.y_label", "relationship"),
                        "x_unit": bounded_text("data-story", "data.x_unit", "relationship"),
                        "y_unit": bounded_text("data-story", "data.y_unit", "relationship"),
                        "precision": {"type": "integer", "minimum": 0, "maximum": 6},
                    },
                },
            ],
        },
        "axes": {"$ref": "#/$defs/axes"},
        "media_source": {"$ref": "#/$defs/mediaSource"},
    }
    slide_properties = {**string_fields, **structured_fields}
    slide_properties.update({
        "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
        "title": {"type": "string", "minLength": 1},
        "template": {"enum": sorted(COMPONENT_CONTRACTS)},
        "variant": {"type": "string", "minLength": 1},
        "decor": {"type": "string", "minLength": 1},
        "highlight": {"type": "string", "minLength": 1},
        "background": {"enum": sorted(BACKGROUND_PRESETS)},
        "backdrop_text": {"type": "string", "minLength": 1, "maxLength": 12},
        "media_frame": {"enum": ["content", "self-framed"]},
        "media_fit": {"enum": ["cover", "contain"]},
        "media_surface": {"enum": ["component", "page-blend"]},
        "media_position": {"enum": [
            "center", "left", "right", "top", "bottom",
            "top-left", "top-right", "bottom-left", "bottom-right",
        ]},
        "media_treatment": {"enum": ["natural", "muted", "mono"]},
        "media_fidelity": {"enum": ["strict", "contextual", "illustrative"]},
        "visual_task": {"type": "string", "minLength": 1, "description": "planning-only recommender hint; not rendered"},
        "media_intent": {"type": "string", "minLength": 1, "description": "planning-only recommender hint; not rendered"},
    })
    def exactly_one_required(*fields: str) -> dict:
        return {
            "oneOf": [
                {
                    "required": [field],
                    "not": {"anyOf": [{"required": [other]} for other in fields if other != field]},
                }
                for field in fields
            ]
        }

    copy_required = exactly_one_required("content", "note")
    image_required = exactly_one_required("image", "media")
    media_contract_fields = (
        "image", "media", "artifact_image", "image_alt", "media_frame", "media_fit", "media_surface",
        "media_position", "media_treatment", "media_role", "media_fidelity", "media_question", "media_source",
    )

    def forbid_fields(*fields: str) -> dict:
        return {"not": {"anyOf": [{"required": [field]} for field in fields]}}

    component_rules: dict[str, dict] = {
        "section": copy_required,
        "three-steps": {"required": ["steps"], "properties": {"steps": {"minItems": 3, "maxItems": 3, "items": {"$ref": "#/$defs/stepBody"}}}},
        "timeline": {"required": ["steps"], "properties": {"steps": {"minItems": 4, "maxItems": 4, "items": {"$ref": "#/$defs/stepBody"}}}},
        "quote": {"required": ["quote", "source"]},
        "recap": {"required": ["cards"], "allOf": [copy_required], "properties": {"cards": {"minItems": 3, "maxItems": 3, "items": {"$ref": "#/$defs/plainCard"}}}},
        "comparison-list": {
            "required": ["sides"],
            "properties": {"sides": {"minItems": 2, "maxItems": 2, "items": {"allOf": [
                {"$ref": "#/$defs/plainSide"},
                {"properties": {"points": {"minItems": 3, "maxItems": 3}}},
            ]}}},
        },
        "tabs": {
            "required": ["sides"],
            "properties": {"sides": {"minItems": 2, "maxItems": 2, "items": {"$ref": "#/$defs/tabSide"}}},
        },
        "metric": {"required": ["metric"], "allOf": [copy_required]},
        "relationship-map": {
            "required": ["nodes", "links"],
            "allOf": [copy_required],
            "properties": {
                "content": bounded_text("relationship-map", "content"),
                "note": bounded_text("relationship-map", "content"),
                "nodes": {
                    "minItems": 4,
                    "maxItems": 6,
                    "contains": {"required": ["emphasis"], "properties": {"emphasis": {"const": True}}},
                    "minContains": 1,
                    "maxContains": 1,
                },
                "links": {"minItems": 3, "maxItems": 5},
            },
        },
        "decision-matrix": {
            "required": ["source", "criteria", "options"],
            "allOf": [copy_required],
            "properties": {
                "content": bounded_text("decision-matrix", "content"),
                "note": bounded_text("decision-matrix", "content"),
                "source": bounded_text("decision-matrix", "source"),
                "criteria": {"minItems": 3, "maxItems": 3},
                "options": {"minItems": 3, "maxItems": 3},
            },
        },
        "data-story": {
            "required": ["source", "data"],
            "allOf": [copy_required],
            "properties": {
                "content": bounded_text("data-story", "content"),
                "note": bounded_text("data-story", "content"),
                "source": bounded_text("data-story", "source"),
            },
        },
        "converge": {
            "required": ["groups", "outcome"],
            "properties": {"groups": {"minItems": 2, "maxItems": 2, "items": {"$ref": "#/$defs/convergeGroup"}}},
        },
        "cycle": {
            "required": ["statement", "statement_body", "steps"],
            "allOf": [copy_required],
            "properties": {
                "content": bounded_text("cycle", "content"),
                "note": bounded_text("cycle", "content"),
                "statement": bounded_text("cycle", "statement"),
                "statement_body": bounded_text("cycle", "statement_body"),
                "steps": {"minItems": 4, "maxItems": 4, "items": {"$ref": "#/$defs/cycleStep"}},
            },
        },
        "editorial-feature": {"required": ["media_frame", "cards"], "allOf": [copy_required, image_required], "properties": {"cards": {"minItems": 3, "maxItems": 3}}},
        "catalog-board": {
            "required": ["metrics", "groups"],
            "properties": {
                "metrics": {
                    "minItems": 3, "maxItems": 3, "items": {"$ref": "#/$defs/catalogMeasurement"},
                },
                "groups": {
                    "minItems": 4, "maxItems": 4, "items": {"$ref": "#/$defs/catalogGroup"},
                },
            },
        },
        "annotated-showcase": {
            "required": ["media_frame", "annotations"],
            "allOf": [copy_required, image_required],
            "properties": {
                "annotations": {
                    "minItems": 3, "maxItems": 3, "items": {"$ref": "#/$defs/annotation"},
                },
            },
        },
        "narrative-bento": {"required": ["statement", "statement_body", "quote", "cards"], "allOf": [copy_required], "properties": {"cards": {"minItems": 2, "maxItems": 2, "items": {"$ref": "#/$defs/iconCard"}}}},
        "sequence-gallery": {
            "required": ["conclusion", "media_frame", "steps"],
            "allOf": [copy_required],
            "properties": {"steps": {"minItems": 3, "maxItems": 3, "items": {"$ref": "#/$defs/stepMediaBody"}}},
        },
        "process-cards": {
            "required": ["steps"],
            "allOf": [copy_required, {"oneOf": [
                {"properties": {"steps": {"contains": {"required": ["icon"]}, "minContains": 4, "maxContains": 4}}},
                {"properties": {"steps": {"not": {"contains": {"required": ["icon"]}}}}},
            ]}],
            "properties": {
                "steps": {"minItems": 4, "maxItems": 4, "items": {"$ref": "#/$defs/stepIconBody"}},
                "measurements": {"minItems": 4, "maxItems": 4},
            },
            "dependentRequired": {
                "measurements": ["measurement_note", "measurement_meta"],
                "measurement_note": ["measurements"],
                "measurement_meta": ["measurements"],
            },
        },
        "quadrant": {
            "required": ["axes", "groups"],
            "allOf": [copy_required],
            "properties": {
                "content": bounded_text("quadrant", "content"),
                "note": bounded_text("quadrant", "content"),
                "groups": {
                    "minItems": 4,
                    "maxItems": 4,
                    "items": {"$ref": "#/$defs/quadrantGroup"},
                    "contains": {"required": ["emphasis"], "properties": {"emphasis": {"const": True}}},
                    "minContains": 1,
                    "maxContains": 1,
                },
            },
        },
        "tier-stack": {
            "required": ["steps"],
            "allOf": [copy_required],
            "properties": {
                "content": bounded_text("tier-stack", "content"),
                "note": bounded_text("tier-stack", "content"),
                "steps": {"minItems": 4, "maxItems": 4, "items": {"$ref": "#/$defs/tierStep"}},
            },
        },
    }
    for name in ("bleed-split", "browser-showcase", "diagonal-split", "editorial-canvas", "photo-gradient", "photo-split", "split-visual"):
        component_rules[name] = {"required": ["media_frame"], "allOf": [copy_required, image_required]}
    component_conditions = []
    for name, contract in sorted(COMPONENT_CONTRACTS.items()):
        forbidden = sorted(set(SLIDE_ALLOWED_FIELDS) - set(BASE_VISIBLE_FIELDS) - set(TEMPLATE_VISIBLE_FIELDS[name]))
        then = {
            "properties": {
                "variant": {"enum": list(contract["variants"])},
                "decor": {"enum": list(contract["decorations"])},
            }
        }
        if forbidden:
            then["not"] = {"anyOf": [{"required": [field]} for field in forbidden]}
        if name in component_rules:
            rule = component_rules[name]
            then.update({key: value for key, value in rule.items() if key != "properties"})
            if rule.get("properties"):
                then["properties"] = {**then["properties"], **rule["properties"]}
        variant_rules = []
        if name == "cover":
            variant_rules.extend([
                {
                    "if": {"properties": {"variant": {"const": "statement"}}},
                    "then": forbid_fields(*media_contract_fields),
                },
                {
                    "if": {"properties": {"variant": {"const": "media"}}},
                    "then": {"required": ["media_frame"], **image_required},
                },
            ])
        elif name == "end":
            variant_rules.extend([
                {
                    "if": {"properties": {"variant": {"const": "line"}}},
                    "then": {"not": {"anyOf": [{"required": [field]} for field in (
                        "content", "note", "meta", "aside", "aside_label", "artifact_title", "artifact_body",
                        *media_contract_fields,
                    )]}},
                },
                {
                    "if": {"properties": {"variant": {"const": "line-note"}}},
                    "then": {
                        "oneOf": [
                            {"required": [field], "not": {"anyOf": [{"required": [other]} for other in ("aside", "content", "note") if other != field]}}
                            for field in ("aside", "content", "note")
                        ],
                        "not": {"anyOf": [{"required": [field]} for field in (
                            "meta", "artifact_title", "artifact_body", *media_contract_fields,
                        )]},
                    },
                },
                {
                    "if": {"properties": {"variant": {"const": "line-artifact"}}},
                    "then": {
                        "required": ["media_frame", "artifact_title", "artifact_body"],
                        "allOf": [exactly_one_required("image", "artifact_image")],
                        "not": {"anyOf": [
                            *[{"required": [field]} for field in ("meta", "aside", "aside_label")],
                            {"required": ["content", "note"]},
                        ]},
                    },
                },
            ])
        elif name == "process-rail":
            variant_rules.extend([
                {
                    "if": {"properties": {"variant": {"const": "steps-6"}}},
                    "then": {"required": ["steps"], "properties": {"steps": {"minItems": 6, "maxItems": 6, "items": {"$ref": "#/$defs/stepBody"}}}},
                },
                {
                    "if": {"properties": {"variant": {"const": "steps-8"}}},
                    "then": {"required": ["steps"], "properties": {"steps": {"minItems": 8, "maxItems": 8, "items": {"$ref": "#/$defs/stepLabel"}}}},
                },
            ])
        elif name == "card-trio":
            then.update({"required": ["cards"], "properties": {**then["properties"], "cards": {"minItems": 3, "maxItems": 3}}})
            variant_rules.extend([
                {
                    "if": {"properties": {"variant": {"enum": ["feature-left", "feature-right", "feature-top"]}}},
                    "then": {
                        **forbid_fields("content", "note", "kicker", "media_frame", "media_fit", "media_position", "media_treatment", "media_role", "media_fidelity", "media_question", "media_source"),
                        "properties": {"cards": {"items": {"$ref": "#/$defs/plainCard"}}},
                    },
                },
                {
                    "if": {"properties": {"variant": {"const": "media-evidence"}}},
                    "then": {
                        "required": ["media_frame"],
                        "allOf": [copy_required],
                        "properties": {"cards": {"prefixItems": [
                            {"$ref": "#/$defs/evidenceCard"},
                            {"$ref": "#/$defs/evidenceCard"},
                            {"$ref": "#/$defs/decisionCard"},
                        ], "items": False}},
                    },
                },
            ])
        elif name == "data-story":
            for variant, minimum, maximum in (
                ("category-comparison", 2, 6),
                ("trend", 3, 8),
                ("composition", 2, 5),
            ):
                variant_rules.append({
                    "if": {"properties": {"variant": {"const": variant}}},
                    "then": {"properties": {"data": {
                        "not": {"anyOf": [{"required": ["x_label"]}, {"required": ["y_label"]}]},
                        "properties": {
                            "items": {
                                "minItems": minimum,
                                "maxItems": maximum,
                                "items": {"properties": {
                                    "label": bounded_text("data-story", "data.items[].label", variant),
                                }},
                            },
                        },
                    }}},
                })
            variant_rules.append({
                "if": {"properties": {"variant": {"const": "relationship"}}},
                "then": {"properties": {"data": {"required": ["x_label", "y_label"]}}},
            })
        elif name == "metric":
            variant_rules.extend([
                {
                    "if": {"properties": {"variant": {"const": "default"}}},
                    "then": {"properties": {"metric": {
                        "not": {"anyOf": [
                            {"required": ["change"]}, {"required": ["change_label"]}, {"required": ["target"]},
                        ]},
                    }}},
                },
                {
                    "if": {"properties": {"variant": {"const": "delta"}}},
                    "then": {"properties": {"metric": {
                        "required": ["change", "change_label"],
                        "not": {"required": ["target"]},
                    }}},
                },
                {
                    "if": {"properties": {"variant": {"const": "progress"}}},
                    "then": {"properties": {"metric": {
                        "required": ["target"],
                        "not": {"anyOf": [{"required": ["change"]}, {"required": ["change_label"]}]},
                        "properties": {
                            "value": {"type": "number", "minimum": 0, "maximum": MAX_ABS_DATA_VALUE},
                            "target": {"type": "number", "exclusiveMinimum": 0, "maximum": MAX_ABS_DATA_VALUE},
                        },
                    }}},
                },
            ])
        elif name == "comparison":
            then.update({"required": ["sides"], "properties": {**then["properties"], "sides": {"minItems": 2, "maxItems": 2}}})
            variant_rules.extend([
                {
                    "if": {"properties": {"variant": {"const": "default"}}},
                    "then": {
                        **forbid_fields("content", "note", "kicker", "media_frame", "media_fit", "media_position", "media_treatment", "media_role", "media_fidelity", "media_question", "media_source"),
                        "properties": {"sides": {"items": {"allOf": [
                            {"$ref": "#/$defs/plainSide"},
                            {"properties": {"points": {"minItems": 2, "maxItems": 2}}},
                        ]}}},
                    },
                },
                {
                    "if": {"properties": {"variant": {"const": "visual-evidence"}}},
                    "then": {"required": ["media_frame"], "allOf": [copy_required], "properties": {"sides": {"items": {"$ref": "#/$defs/visualSide"}}}},
                },
            ])
        elif name == "editorial-feature":
            variant_rules.extend([
                {
                    "if": {"properties": {"variant": {"const": "default"}}},
                    "then": {
                        **forbid_fields("badge", "media_note", "secondary_image", "secondary_image_alt"),
                        "properties": {"cards": {"items": {"$ref": "#/$defs/iconCard"}}},
                    },
                },
                {
                    "if": {"properties": {"variant": {"const": "hero-collage"}}},
                    "then": {"required": ["secondary_image"], "properties": {"cards": {"items": {"$ref": "#/$defs/plainCard"}}}},
                },
            ])
        elif name == "case-study-board":
            then.update({"required": ["metrics", "insight"], "allOf": [copy_required], "properties": {**then["properties"], "metrics": {"minItems": 2, "maxItems": 2}}})
            variant_rules.extend([
                {
                    "if": {"properties": {"variant": {"const": "evidence"}}},
                    "then": {"required": ["media_frame"], **image_required, **forbid_fields("chart")},
                },
                {
                    "if": {"properties": {"variant": {"const": "chart"}}},
                    "then": {"required": ["chart"], **forbid_fields(*media_contract_fields)},
                },
            ])
        if variant_rules:
            then.setdefault("allOf", []).extend(variant_rules)
        component_conditions.append({
            "if": {"properties": {"template": {"const": name}}, "required": ["template"]},
            "then": then,
        })
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "oil-ppt:outline/v1",
        "$defs": definitions,
        "type": "object",
        "required": ["title", "palette", "typography", "shape", "click_navigation", "slides"],
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string", "minLength": 1},
            "palette": {"oneOf": [
                {"enum": sorted(PALETTES)},
                {
                    "type": "object",
                    "required": ["accent", "accent_soft", "accent_strong"],
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string", "const": "custom"},
                        **{key: {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"} for key in TOKEN_KEYS},
                    },
                },
            ]},
            "palette_source": {"enum": ["user", "brand"]},
            "typography": {"enum": sorted(TYPE_PROFILES)},
            "shape": {"enum": sorted(SHAPE_PROFILES)},
            "media_policy": {"enum": ["required", "text-only"], "default": "required"},
            "click_navigation": {"type": "boolean", "default": False},
            "next_preview": {"type": "boolean", "default": True},
            "show_progress": {"type": "boolean", "default": True},
            "show_counter": {"type": "boolean", "default": True},
            "slides": {
                "type": "array", "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["id", "title", "template", "variant", "decor"],
                    "additionalProperties": False,
                    "properties": slide_properties,
                    "allOf": [
                        {"not": {"required": ["content", "note"]}},
                        {"not": {"anyOf": [
                            {"required": ["image", "media"]},
                            {"required": ["image", "artifact_image"]},
                            {"required": ["media", "artifact_image"]},
                        ]}},
                        *component_conditions,
                    ],
                },
            },
        },
        "allOf": [{
            "if": {"properties": {"palette": {"type": "object"}}, "required": ["palette"]},
            "then": {"required": ["palette_source"]},
        }],
        "note": "Template-specific variants, exact counts, visible fields and media rules are validated by `contract --id <template>` and `plan`.",
    }


def _schema_clone(value: object) -> object:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _selected_variant_names(condition: dict) -> set[str]:
    selector = (((condition.get("if") or {}).get("properties") or {}).get("variant") or {})
    if isinstance(selector.get("const"), str):
        return {selector["const"]}
    values = selector.get("enum")
    return {str(value) for value in values} if isinstance(values, list) else set()


def _required_choice_groups(value: object) -> list[list[str]]:
    """Expose compact top-level one-of requirements without dumping JSON Schema."""
    groups: list[list[str]] = []

    def visit(item: object) -> None:
        if isinstance(item, dict):
            branches = item.get("oneOf")
            if isinstance(branches, list) and len(branches) > 1:
                fields: list[str] = []
                for branch in branches:
                    required = branch.get("required") if isinstance(branch, dict) else None
                    if not isinstance(required, list) or len(required) != 1 or not isinstance(required[0], str):
                        fields = []
                        break
                    fields.append(required[0])
                if fields and len(set(fields)) == len(fields):
                    groups.append(fields)
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    deduped: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for group in groups:
        key = tuple(group)
        if key not in seen:
            deduped.append(group)
            seen.add(key)
    return deduped


def _collect_schema_definitions(value: object, definitions: dict) -> dict:
    names: set[str] = set()

    def visit(item: object) -> None:
        if isinstance(item, dict):
            reference = item.get("$ref")
            if isinstance(reference, str) and reference.startswith("#/$defs/"):
                names.add(reference.removeprefix("#/$defs/"))
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    previous = -1
    while previous != len(names):
        previous = len(names)
        for name in list(names):
            visit(definitions.get(name))
    return {name: _schema_clone(definitions[name]) for name in sorted(names) if name in definitions}


def component_fill_plan(template: str) -> dict:
    """Build one self-contained authoring schema from the executable contract."""
    if template not in COMPONENT_CONTRACTS:
        raise SystemExit(f"Unknown template for fill plan: {template}")
    full = contract_schema()
    slide_schema = full["properties"]["slides"]["items"]
    base_constraints: list[dict] = []
    template_rules: dict | None = None
    for condition in slide_schema.get("allOf") or []:
        selected = ((((condition.get("if") or {}).get("properties") or {}).get("template") or {}).get("const"))
        if selected is None:
            base_constraints.append(_schema_clone(condition))
        elif selected == template:
            template_rules = _schema_clone(condition.get("then") or {})
    if template_rules is None:
        raise RuntimeError(f"contract schema is missing template rules for {template}")

    base_required = list(slide_schema.get("required") or [])
    allowed_fields = sorted(set(BASE_VISIBLE_FIELDS) | set(TEMPLATE_VISIBLE_FIELDS[template]))
    properties = {
        field: _schema_clone(slide_schema["properties"][field])
        for field in allowed_fields
        if field in slide_schema["properties"]
    }
    properties["template"] = {"const": template}
    properties["variant"] = {"enum": list(COMPONENT_CONTRACTS[template]["variants"])}
    properties["decor"] = {"enum": list(COMPONENT_CONTRACTS[template]["decorations"])}
    input_schema = {
        "$schema": full["$schema"],
        "$id": f"https://oil-ppt.local/schema/fill-plan/{template}/v1",
        "type": "object",
        "additionalProperties": False,
        "required": base_required,
        "properties": properties,
        "allOf": [*base_constraints, template_rules],
    }
    definitions = _collect_schema_definitions(input_schema, full.get("$defs") or {})
    if definitions:
        input_schema["$defs"] = definitions

    template_required = set(template_rules.get("required") or [])
    variant_conditions = [
        condition for condition in (template_rules.get("allOf") or [])
        if _selected_variant_names(condition)
    ]
    variants: dict[str, dict] = {}
    guidance_by_variant = VARIANT_INPUT_GUIDANCE.get(template) or {}
    base_template_rules = {
        key: value for key, value in template_rules.items() if key != "allOf"
    }
    base_template_constraints = [
        condition for condition in (template_rules.get("allOf") or [])
        if not _selected_variant_names(condition)
    ]
    for variant in COMPONENT_CONTRACTS[template]["variants"]:
        guidance = _schema_clone(guidance_by_variant.get(variant) or {
            "minimum": [TEMPLATE_CONTENT_HELP[template]],
            "optional": [],
        })
        required = set(base_required) | template_required
        selected_variant_rules: list[dict] = []
        for condition in variant_conditions:
            if variant in _selected_variant_names(condition):
                selected = condition.get("then") or {}
                required.update(selected.get("required") or [])
                selected_variant_rules.append(selected)
        required_choices = _required_choice_groups([
            base_template_rules,
            *base_template_constraints,
            *selected_variant_rules,
        ])
        budgets = text_budgets_for(template, variant)
        variants[variant] = {
            **guidance,
            "required_top_level": sorted(required),
            **({"required_one_of_top_level": required_choices} if required_choices else {}),
            **({"text_budgets_nonspace": budgets} if budgets else {}),
        }
    canonical = json.dumps(input_schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "schema_version": "oil-ppt.component-fill-plan/v1",
        "template": template,
        "authoritative_constraints": "input_schema+plan/check",
        # Keep the normal detail view focused on component-owned inputs. Shared
        # design and planning hints remain legal in input_schema, but should not
        # compete with the minimum fields a weaker model needs to fill first.
        "content_fields": sorted(TEMPLATE_VISIBLE_FIELDS[template]),
        "variants": variants,
        "schema_digest": "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "input_schema": input_schema,
        "validation_note": "Non-space budgets and semantic rules are enforced by plan/check in addition to JSON Schema.",
    }


def confirm_outline(project: Path, user_confirmed: bool, expected_sha256: str | None = None) -> None:
    project = require_initialized_project(project, "Outline confirmation")
    require_no_edit_draft(project, "Outline confirmation")
    if not user_confirmed:
        raise SystemExit("Outline confirmation requires --user-confirmed after explicit user approval.")
    markdown = project / "outline.md"
    if not markdown.is_file():
        raise SystemExit(f"Missing Markdown outline: {markdown}. Next: edit the file created by init.")
    if markdown.read_text(encoding="utf-8").strip() == OUTLINE_MARKDOWN_TEMPLATE.strip():
        raise SystemExit(f"outline.md is still the empty starter: {markdown}. Fill it before confirmation.")
    state = read_project_state(project)
    markdown_sha256 = verify_expected_sha256(
        markdown, expected_sha256, stage="Outline",
    )
    previous = state.get("outline_confirmation")
    previous_sha256 = previous.get("sha256") if isinstance(previous, dict) else None
    if previous_sha256 != markdown_sha256:
        state.pop("visual_plan", None)
        state.pop("media_policy_confirmation", None)
    state["outline_confirmation"] = {
        "path": str(markdown),
        "sha256": markdown_sha256,
        "user_confirmed": True,
    }
    state.pop("recovery", None)
    state.setdefault("history", []).append({"event": "outline_confirmed", "sha256": markdown_sha256})
    atomic_write_json(project_state_path(project), state)
    workflow = status_payload(project)
    print(json.dumps({
        "ok": True, "phase": workflow["phase"], "project": str(project),
        "next": workflow["next"],
    }, ensure_ascii=False, indent=2))


def outline_confirmation_valid(project: Path) -> bool:
    markdown = project / "outline.md"
    if not markdown.is_file():
        return False
    confirmation = read_project_state(project).get("outline_confirmation") or {}
    if not isinstance(confirmation, dict):
        return False
    return confirmation.get("user_confirmed") is True and confirmation.get("sha256") == outline_digest(markdown)


def visual_plan_valid(project: Path, outline: Path | None = None) -> bool:
    path = (outline or project / "outline.json").expanduser().resolve()
    markdown = project / "outline.md"
    if not outline_confirmation_valid(project) or not path.is_file() or not markdown.is_file():
        return False
    visual_plan = read_project_state(project).get("visual_plan") or {}
    if not isinstance(visual_plan, dict):
        return False
    try:
        return (
            visual_plan.get("markdown_sha256") == outline_digest(markdown)
            and visual_plan.get("outline_sha256") == json_digest(path)
        )
    except (json.JSONDecodeError, SystemExit):
        return False


def text_only_confirmation_valid(project: Path, outline: Path | None = None) -> bool:
    path = (outline or project / "outline.json").expanduser().resolve()
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict):
        return False
    if data.get("media_policy", "required") != "text-only":
        return True
    confirmation = read_project_state(project).get("media_policy_confirmation") or {}
    if not isinstance(confirmation, dict):
        return False
    return (
        confirmation.get("policy") == "text-only"
        and confirmation.get("user_confirmed") is True
        and confirmation.get("outline_sha256") == json_digest(path)
    )


def text_only_confirmation_message(project: Path) -> str:
    return (
        "media_policy='text-only' disables every image requirement and needs explicit user approval. "
        "Ask whether the entire deck should contain no images. If yes, run "
        f"{cli_command('plan', project, '--user-confirmed-text-only')}; otherwise use media_policy='required'."
    )


def plan_project(project_arg: Path, input_path: Path | None, user_confirmed_text_only: bool = False) -> None:
    project = require_initialized_project(project_arg, "Plan")
    require_no_edit_draft(project, "Plan")
    if not outline_confirmation_valid(project):
        raise SystemExit(
            "The current outline.md is not confirmed. Show it to the user and record confirmation only after explicit approval."
        )
    target = project / "outline.json"
    source = input_path.expanduser().resolve() if input_path else target
    if not source.is_file():
        raise SystemExit(
            f"Missing visual plan JSON: {source}. Use {cli_command('contract', '--example')}, write {target}, then run plan again."
        )
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON in {source}: {error}") from error
    validate_outline(data, TEMPLATES)
    enforce_outline_quality(data)
    if data.get("media_policy", "required") == "text-only" and not user_confirmed_text_only:
        raise SystemExit(text_only_confirmation_message(project))
    if source != target:
        atomic_write_json(target, data)
    state = read_project_state(project)
    outline_sha256 = json_digest(target)
    if data.get("media_policy", "required") == "text-only":
        state["media_policy_confirmation"] = {
            "policy": "text-only",
            "outline_sha256": outline_sha256,
            "user_confirmed": True,
        }
        state.setdefault("history", []).append({"event": "text_only_confirmed", "outline_sha256": outline_sha256})
    else:
        state.pop("media_policy_confirmation", None)
    state["visual_plan"] = {
        "markdown_sha256": outline_digest(project / "outline.md"),
        "outline_sha256": outline_sha256,
    }
    atomic_write_json(project_state_path(project), state)
    print(json.dumps({
        "ok": True, "phase": "needs_preview", "project": str(project), "outline": str(target),
        "slides": len(data["slides"]),
        "next": {"action": "start_editor", "command": cli_command("preview", project)},
    }, ensure_ascii=False, indent=2))


def check_project(
    target: Path,
    *,
    include_next: bool = True,
) -> dict:
    outline = outline_from_target(target)
    if not outline.is_file():
        raise SystemExit(f"Missing outline.json: {outline}. Next: {cli_command('contract', '--example')}")
    try:
        data = json.loads(outline.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON in {outline}: {error}") from error
    validate_outline(data, TEMPLATES)
    audit = audit_summary(data)
    project = outline.parent

    def add_gate_issue(code: str, message: str) -> None:
        audit["status"] = "error"
        audit.setdefault("issues", []).append({
            "level": "error", "blocking": True, "code": code, "message": message, "slides": [],
        })
        audit.setdefault("counts", {})["error"] = int(audit.get("counts", {}).get("error", 0)) + 1

    if not outline_confirmation_valid(project):
        add_gate_issue("unconfirmed-markdown", "当前 outline.md 尚未由用户确认，或确认后又发生变化。")
    elif not visual_plan_valid(project, outline):
        add_gate_issue("unbound-visual-plan", "outline.json 尚未通过 plan 绑定到当前已确认的 Markdown 大纲。")
    if data.get("media_policy", "required") == "text-only" and not text_only_confirmation_valid(outline.parent, outline):
        add_gate_issue("unconfirmed-text-only", text_only_confirmation_message(outline.parent))
    media = inspect_outline_media(data, outline.parent)
    if media["errors"]:
        add_gate_issue(
            "invalid-media",
            f"{len(media['errors'])} 个素材绑定不可用；查看 media.errors 后一次性补齐。",
        )
    payload = {
        "schema_version": "oil-ppt.check/v1",
        "ok": audit["status"] != "error",
        "project": str(outline.parent),
        "outline": str(outline),
        "slides": len(data["slides"]),
        "audit": audit,
        "media": media,
    }
    if include_next:
        payload["next"] = (
            {
                "action": "fix_media",
                "command": None,
                "path": str(outline),
                "rerun": cli_command("check", project),
            }
            if media["errors"]
            else status_payload(project)["next"]
        )
    return payload


BATCH_PRUNE_DIRS = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__"}


def discover_projects(targets: list[Path]) -> list[Path]:
    """Resolve project roots from explicit projects or parent directories."""
    projects: set[Path] = set()
    for target_arg in targets:
        target = target_arg.expanduser().resolve()
        if not target.exists():
            raise SystemExit(f"Batch target does not exist: {target}")
        if target.is_file():
            if target.name not in {PROJECT_STATE_NAME, *LEGACY_STATE_NAMES}:
                raise SystemExit(f"Batch target must be a project or parent directory: {target}")
            target = target.parent
        migrate_legacy_state_files(target)
        if project_state_path(target).is_file():
            projects.add(target)
            continue
        for root, dirs, files in os.walk(target):
            dirs[:] = [name for name in dirs if name not in BATCH_PRUNE_DIRS]
            if PROJECT_STATE_NAME in files or any(name in files for name in LEGACY_STATE_NAMES):
                project = Path(root).resolve()
                migrate_legacy_state_files(project)
                projects.add(project)
                dirs[:] = []
    if not projects:
        rendered = ", ".join(str(item.expanduser().resolve()) for item in targets)
        raise SystemExit(f"No initialized oil-ppt projects found under: {rendered}")
    return sorted(projects, key=lambda item: str(item).casefold())


def run_batch_step(command: str, project: Path, *arguments: str) -> dict:
    """Run one public CLI step in isolation and retain its complete diagnostics."""
    process = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), command, str(project), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    stdout = process.stdout.strip()
    parsed: dict | None = None
    if stdout:
        try:
            candidate = json.loads(stdout)
            parsed = candidate if isinstance(candidate, dict) else None
        except json.JSONDecodeError:
            parsed = None
    result = {
        "ok": process.returncode == 0,
        "returncode": process.returncode,
        **({"result": parsed} if parsed is not None else {}),
    }
    diagnostic = process.stderr.strip() or (stdout if parsed is None else "")
    if diagnostic:
        result["diagnostic"] = diagnostic[-4000:]
    return result


def parse_expected_previews(values: list[str] | None) -> dict[Path, str]:
    """Parse repeatable PROJECT::SHA256 bindings emitted by batch itself."""
    bindings: dict[Path, str] = {}
    for value in values or []:
        try:
            raw_project, digest = value.rsplit("::", 1)
        except ValueError as error:
            raise SystemExit("--expected-preview must use PROJECT::SHA256.") from error
        if not raw_project or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise SystemExit("--expected-preview must use PROJECT::SHA256 with a lowercase SHA256 digest.")
        bindings[Path(raw_project).expanduser().resolve()] = digest
    return bindings


def batch_projects(
    targets: list[Path], *, user_confirmed_preview: bool,
    expected_previews: list[str] | None = None,
) -> dict:
    """Advance deterministic phases without confirming a newly rendered preview.

    A confirmation flag applies only to previews already awaiting approval when
    this invocation starts. This preserves the user's opportunity to inspect any
    preview generated by the same batch call.
    """
    projects = discover_projects(targets)
    resolved_targets = [target.expanduser().resolve() for target in targets]
    expected_by_project = parse_expected_previews(expected_previews)
    bound_confirmation = bool(expected_previews)
    results: list[dict] = []
    for project in projects:
        actions: list[str] = []
        failure: dict | None = None
        initial_status = status_payload(project)
        initial_phase = initial_status["phase"]

        def advance(stage: str, command: str, *arguments: str) -> bool:
            nonlocal failure
            step = run_batch_step(command, project, *arguments)
            if not step["ok"]:
                failure = {"stage": stage, **step}
                return False
            actions.append(stage)
            return True

        if initial_phase == "needs_plan" and (initial_status.get("next") or {}).get("action") == "run_command":
            if advance("plan", "plan"):
                advance("preview", "preview", "--no-open")
        elif initial_phase == "needs_preview":
            advance("preview", "preview", "--no-open")
        elif initial_phase == "needs_preview_confirmation" and user_confirmed_preview:
            expected = expected_by_project.get(project)
            if bound_confirmation and expected is None:
                failure = {
                    "stage": "confirm-preview",
                    "ok": False,
                    "returncode": 1,
                    "diagnostic": "This preview was not part of the artifact set shown to the user. Run batch again.",
                }
            else:
                confirmation_arguments = ["--stage", "preview"]
                if expected is not None:
                    confirmation_arguments.extend(["--expected-sha256", expected])
                confirmation_arguments.append("--user-confirmed")
                if advance("confirm-preview", "confirm", *confirmation_arguments):
                    advance("build", "build")
        elif initial_phase in {"ready_to_build", "needs_build"}:
            advance("build", "build")

        final_status = status_payload(project) if actions or failure else initial_status
        blocked = failure is not None or final_status["phase"] not in {"complete", "needs_preview_confirmation"}
        results.append({
            "project": str(project),
            "actions": actions,
            "phase": final_status["phase"],
            "blocked": blocked,
            **(
                {
                    "preview": (final_status.get("next") or {}).get("artifact"),
                    "preview_sha256": (final_status.get("next") or {}).get("artifact_sha256"),
                }
                if final_status["phase"] == "needs_preview_confirmation" else {}
            ),
            "blockers": final_status.get("blockers") or [],
            "next": final_status.get("next") or {},
            **({"failure": failure} if failure else {}),
        })

    summary = {
        "projects": len(results),
        "complete": sum(item["phase"] == "complete" for item in results),
        "awaiting_preview_confirmation": sum(item["phase"] == "needs_preview_confirmation" for item in results),
        "blocked": sum(bool(item["blocked"]) for item in results),
    }
    if summary["blocked"]:
        first_blocked = next(item for item in results if item["blocked"])
        next_step = {"project": first_blocked["project"], **first_blocked["next"]}
    elif summary["awaiting_preview_confirmation"]:
        awaiting = [item for item in results if item["phase"] == "needs_preview_confirmation"]
        confirmation_arguments: list[object] = ["batch", *resolved_targets]
        for item in awaiting:
            if item.get("preview_sha256"):
                confirmation_arguments.extend([
                    "--expected-preview",
                    f"{item['project']}::{item['preview_sha256']}",
                ])
        confirmation_arguments.append("--user-confirmed-preview")
        next_step = {
            "action": "ask_user_to_confirm_previews",
            "command": None,
            "artifacts": [item["preview"] for item in awaiting],
            "artifact_sha256": {
                item["project"]: item["preview_sha256"]
                for item in awaiting if item.get("preview_sha256")
            },
            "command_on_confirm": cli_command(*confirmation_arguments),
        }
    else:
        next_step = {"action": "complete", "command": None}
    return {
        "schema_version": "oil-ppt.batch/v1",
        # An actionable human/model gate is a valid batch result, not a CLI
        # failure. Reserve the non-zero exit for a deterministic step that
        # actually failed to run.
        "ok": not any(item.get("failure") for item in results),
        "summary": summary,
        "projects": results,
        "next": next_step,
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
    family_id: str | None = None,
) -> None:
    """Print a progressively disclosed, program-generated capability map."""
    if show_schema and item_id:
        normalized = item_id.removeprefix("template.")
        emit_json(component_fill_plan(normalized)["input_schema"], pretty=pretty)
        return
    if show_schema:
        emit_json(contract_schema(), pretty=pretty)
        return
    if show_example:
        emit_json(example_outline(), pretty=pretty)
        return
    if family_id:
        if family_id not in FAMILY_GUIDANCE:
            raise SystemExit(f"Unknown family: {family_id}. Available: {', '.join(FAMILY_GUIDANCE)}")
        guide = FAMILY_GUIDANCE[family_id]
        emit_json({
            "schema_version": "oil-ppt.contract-family/v1",
            "family": {
                "name": family_id,
                **guide,
                "templates": [
                    {
                        "name": name,
                        "use_when": COMPONENT_CONTRACTS[name]["use_when"],
                        "avoid_when": TEMPLATE_DISCOVERY[name]["avoid_when"],
                    }
                    for name in sorted(COMPONENT_CONTRACTS)
                    if TEMPLATE_FAMILIES[name] == family_id
                ],
            },
            "detail_command": cli_command("contract", "--id", "<template-name>"),
        }, pretty=pretty)
        return
    if show_list:
        emit_json({
            "schema_version": "oil-ppt.contract-list/v2",
            "selection": "先回答 family 的问题，再只查询该 family；不要一次比较全部模板。",
            "families": [
                {
                    "name": family,
                    **FAMILY_GUIDANCE[family],
                    "templates": [
                        name for name in sorted(COMPONENT_CONTRACTS)
                        if TEMPLATE_FAMILIES[name] == family
                    ],
                }
                for family in FAMILY_GUIDANCE
            ],
            "family_command": cli_command("contract", "--family", "<family>"),
            "detail_command": cli_command("contract", "--id", "<template-name>"),
        }, pretty=pretty)
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
            "template_fields": sorted(TEMPLATE_VISIBLE_FIELDS[name]),
            **(
                {"input_by_variant": VARIANT_INPUT_GUIDANCE[name]}
                if name in VARIANT_INPUT_GUIDANCE
                else {"content": TEMPLATE_CONTENT_HELP[name]}
            ),
            "defaults": {
                "background": template_background(name),
                **({"media_frame": "content"} if name in MEDIA_TEMPLATES or name == "sequence-gallery" else {}),
            },
            **({"variant_quality": VARIANT_QUALITY[name]} if name in VARIANT_QUALITY else {}),
        }
        if name in MEDIA_SLOTS:
            entry["media_contract"] = {
                "slot": MEDIA_SLOTS[name],
                "fit_rule": "strict UI/document/chart uses contain; contextual photo uses cover; page-blend illustration stays frameless",
                **(
                    {"surface_modes": ["component", "page-blend"], "page_blend_frame_owner": "none"}
                    if name in PAGE_BLEND_TEMPLATES else {}
                ),
                **(
                    {"variant_slot_overrides": {
                        variant: slot for (template, variant), slot in MEDIA_VARIANT_SLOTS.items() if template == name
                    }}
                    if any(template == name for template, _ in MEDIA_VARIANT_SLOTS) else {}
                ),
            }
        templates_by_family[TEMPLATE_FAMILIES[name]].append(entry)
    program_owned = json.loads(json.dumps(PROGRAM_OWNED_CAPABILITIES, ensure_ascii=False))
    def resolved_command(value: str) -> str:
        return value
    for section in program_owned.values():
        if isinstance(section, dict):
            for key, value in list(section.items()):
                if key.endswith("_command") and isinstance(value, str):
                    section[key] = resolved_command(value)
    payload = {
        "schema_version": "oil-ppt.contract/v2",
        "track": "unified",
        "selection_order": list(SELECTION_ORDER),
        "detail_command": cli_command("contract", "--id", "<template-name>"),
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
        fill_plan = component_fill_plan(normalized)
        fill_plan.pop("input_schema", None)
        fill_plan["input_schema_command"] = cli_command(
            "contract", "--id", normalized, "--schema", "--compact",
        )
        payload = {
            "schema_version": payload["schema_version"],
            "registry_digest": payload["registry_digest"],
            "template": match,
            "fill_plan": fill_plan,
            "base_fields": ["id", "title", "template", "variant", "decor"],
            "common_optional": ["highlight", "background", "backdrop_text"],
            "media_rule": "出现图片时通常设置 media_frame='content'。照片默认 cover 铺满版位；不可裁切的 UI/文档用 contain。split-visual/editorial-feature 的概念插画可用 media_surface='page-blend' 融入页面；只有素材自带必须保留的外框时才用 self-framed。",
            "full_schema_command": cli_command("contract", "--schema", "--compact"),
        }
    emit_json(payload, pretty=pretty)


def read_outline(project: Path) -> tuple[Path, dict]:
    path = project / "outline.json"
    if not path.is_file():
        raise SystemExit(f"Missing outline.json: {project}. Restore the confirmed project outline before changing slides.")
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_outline(data, TEMPLATES)
    enforce_outline_quality(data)
    if data.get("media_policy", "required") == "text-only" and not text_only_confirmation_valid(project, path):
        raise SystemExit(text_only_confirmation_message(project))
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
        "schema_version": "oil-ppt.media-verify/v1",
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
        raise SystemExit(f"Missing outline.json: {outline}. Next: {cli_command('plan', outline.parent)}")
    data = json.loads(outline.read_text(encoding="utf-8"))
    validate_outline(data, TEMPLATES)
    plan = build_media_plan(data, outline.parent, cli=cli_display())
    if write:
        destination = (output or outline.parent / "media-plan.json").expanduser().resolve()
        if destination.suffix.lower() != ".json":
            raise SystemExit("Media plan output must use the .json extension.")
        protected = {
            outline.resolve(), project_state_path(outline.parent).resolve(), preview_state_path(outline).resolve(),
            (outline.parent / BUILD_STATE_NAME).resolve(), (outline.parent / "deck.json").resolve(),
            validation_state_path(outline.parent).resolve(),
        }
        if destination in protected:
            raise SystemExit(f"Media plan output conflicts with a protected project file: {destination.name}")
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
    print(json.dumps({"schema_version": "oil-ppt.media-frame/v1", "ok": True, **details}, ensure_ascii=False, indent=2))


def print_recommendations(outline_path: Path, *, pretty: bool = False) -> None:
    path = outline_path.expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"Outline not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_outline(data, TEMPLATES)
    print(json.dumps(recommend_outline(data), ensure_ascii=False, indent=2 if pretty else None, separators=None if pretty else (",", ":")))


def write_outline(path: Path, data: dict) -> None:
    atomic_write_json(path, data)


def final_output_path(project_arg: Path) -> Path:
    return project_arg.expanduser().resolve() / DEFAULT_FINAL_NAME


def outline_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_digest(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def renderer_digest() -> str:
    """Fingerprint only files that can change preview or final visual output."""
    script_names = {
        "add_slide.py", "background_presets.py", "build_deck.py", "cdp_validate.py",
        "component_contracts.py", "fill_slots.py", "icon_registry.py", "init_deck.py",
        "palette_tokens.py", "profile_tokens.py", "render_outline_review.py", "sync_runtime.py",
    }
    files = [path for path in (ROOT / "assets").rglob("*") if path.is_file()]
    files.extend(SCRIPTS / name for name in sorted(script_names))
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(ROOT).as_posix()):
        relative = path.relative_to(ROOT).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def asset_manifest(outline: Path) -> dict[str, str]:
    data = json.loads(outline.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Outline JSON must contain an object at the top level.")
    result: dict[str, str] = {}
    for slide in data.get("slides") or []:
        if not isinstance(slide, dict):
            continue
        for field, value in outline_media_bindings(slide):
            path = (outline.parent / str(value)).resolve()
            if outline.parent.resolve() not in path.parents:
                raise SystemExit(f"Preview asset must stay inside the project: {field}={value}")
            if not path.is_file():
                raise SystemExit(f"Preview asset is missing: {field}={value}")
            result[str(value)] = outline_digest(path)
    return result


def preview_state_path(outline_path: Path) -> Path:
    outline = outline_path.expanduser().resolve()
    migrate_legacy_state_files(outline.parent)
    return outline.parent / f".oil-ppt-preview-{outline.stem}.json"


def preview_state_status(outline: Path) -> tuple[str, dict | None, str | None]:
    path = preview_state_path(outline)
    if not path.is_file():
        return "missing", None, "preview state does not exist"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "stale", None, "preview state is invalid JSON"
    if not isinstance(state, dict):
        return "stale", None, "preview state must be a JSON object"
    if not outline.is_file():
        return "stale", state, "outline.json is missing"
    try:
        current_outline_sha256 = json_digest(outline)
    except (json.JSONDecodeError, SystemExit) as error:
        return "stale", state, f"outline.json is invalid: {error}"
    if state.get("outline_sha256") != current_outline_sha256:
        return "stale", state, "outline.json changed after preview"
    markdown = outline.parent / "outline.md"
    if not visual_plan_valid(outline.parent, outline):
        return "stale", state, "visual plan is no longer bound to the confirmed Markdown outline"
    if not markdown.is_file() or state.get("markdown_sha256") != outline_digest(markdown):
        return "stale", state, "confirmed Markdown outline changed after preview"
    if state.get("renderer_sha256") != renderer_digest():
        return "stale", state, "oil-ppt renderer changed after preview"
    preview = Path(str(state.get("preview") or "")).expanduser().resolve()
    try:
        preview_output_path(outline, preview)
    except SystemExit as error:
        return "stale", state, str(error)
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


def status_payload(project_arg: Path, *, intent: str = "continue") -> dict:
    if intent not in {"continue", "edit"}:
        raise ValueError(f"Unsupported status intent: {intent}")
    requested = project_arg.expanduser()
    project = requested.resolve()
    if project.exists() and not project.is_dir():
        return {
            "schema_version": "oil-ppt.status/v1", "ok": False, "code": "INVALID_PROJECT",
            "phase": "invalid_project", "project": str(project), "artifacts": {}, "confirmations": {},
            "preview_status": "missing",
            "blockers": [{"path": str(project), "message": "项目路径必须是目录"}],
            "next": {"action": "choose_project_directory", "command": None},
        }
    if not project.exists() or not any(project.iterdir()):
        parent_project = enclosing_project(project)
        if parent_project is not None and project != parent_project:
            return {
                "schema_version": "oil-ppt.status/v1", "ok": False, "code": "WRONG_PROJECT_PATH",
                "phase": "wrong_project_path", "project": str(project), "artifacts": {}, "confirmations": {},
                "preview_status": "missing",
                "blockers": [{
                    "path": str(project),
                    "message": (
                        f"路径 {str(project_arg)!r} 解析到了项目子目录 {project}，"
                        f"项目根目录是 {parent_project}；不要把输出子目录当作项目根目录"
                    ),
                }],
                "next": {
                    "action": "run_command",
                    "command": cli_command("status", parent_project, "--json"),
                },
            }
        return {
            "schema_version": "oil-ppt.status/v1", "ok": False, "code": "NEEDS_INIT",
            "phase": "needs_init", "project": str(project), "artifacts": {}, "confirmations": {},
            "preview_status": "missing", "blockers": [],
            "next": {"action": "run_command", "command": cli_command("init", project)},
        }
    migrate_legacy_state_files(project)
    if not project_state_path(project).is_file():
        parent_project = enclosing_project(project)
        if parent_project is not None and project != parent_project:
            return {
                "schema_version": "oil-ppt.status/v1", "ok": False, "code": "WRONG_PROJECT_PATH",
                "phase": "wrong_project_path", "project": str(project), "artifacts": {}, "confirmations": {},
                "preview_status": "missing",
                "blockers": [{
                    "path": str(project),
                    "message": f"当前路径位于项目 {parent_project} 内；不要把输出子目录当成项目根目录",
                }],
                "next": {"action": "run_command", "command": cli_command("status", parent_project, "--json")},
            }
        return {
            "schema_version": "oil-ppt.status/v1", "ok": False, "code": "INVALID_PROJECT",
            "phase": "invalid_project", "project": str(project), "artifacts": {}, "confirmations": {},
            "preview_status": "missing",
            "blockers": [{"path": str(project), "message": "该非空目录没有 oil-ppt 项目标记；不要在其中创建或覆盖文件"}],
            "next": {"action": "choose_project_directory", "command": None},
        }
    project_state = read_project_state(project)
    markdown = project / "outline.md"
    outline = project / "outline.json"
    preview = project / "预览.html"
    final = project / DEFAULT_FINAL_NAME
    edit_draft = edit_draft_path(project)
    editor_pid = active_editor_pid(project)
    blockers: list[dict] = []
    next_action: str | None = None
    artifacts = {
        "outline_markdown": markdown.is_file(),
        "outline_json": outline.is_file(),
        "preview": preview.is_file(),
        "edit_draft": edit_draft.is_file(),
        "editor_open": editor_pid is not None,
        "deck_project": (project / "deck.json").is_file(),
        "final": final.is_file(),
    }
    outline_ok = outline_confirmation_valid(project)
    plan_ok = False
    outline_structure_valid = False
    plan_error = None
    text_only_needs_confirmation = False
    media_errors: list[dict] = []
    if outline.is_file():
        try:
            data = json.loads(outline.read_text(encoding="utf-8"))
            validate_outline(data, TEMPLATES)
            outline_structure_valid = True
            text_only_needs_confirmation = (
                data.get("media_policy", "required") == "text-only"
                and not text_only_confirmation_valid(project, outline)
            )
            if text_only_needs_confirmation:
                plan_error = text_only_confirmation_message(project)
            elif not visual_plan_valid(project, outline):
                plan_error = "outline.json 尚未由当前已确认的 Markdown 大纲生成或重新验证"
            else:
                plan_ok = True
                media_errors = inspect_outline_media(data, project).get("errors") or []
        except (json.JSONDecodeError, SystemExit) as error:
            plan_error = str(error)
    preview_status, preview_state, stale_reason = preview_state_status(outline)
    validation_failure = current_validation_failure(project)
    if isinstance(preview_state, dict) and preview_state.get("preview"):
        candidate = Path(str(preview_state["preview"])).expanduser().resolve()
        if candidate.parent == project:
            preview = candidate
            artifacts["preview"] = preview.is_file()
    markdown_is_starter = (
        markdown.is_file()
        and markdown.read_text(encoding="utf-8").strip() == OUTLINE_MARKDOWN_TEMPLATE.strip()
    )
    if editor_pid is not None:
        phase = "editing_in_progress"
        blockers.append({"path": str(edit_lock_path(project)), "message": "文字编辑器正在运行；等待用户完成或关闭"})
        next_command = None
        next_action = "wait_for_editor"
        next_details = {"pid": editor_pid, "long_running": True}
    elif edit_draft.is_file():
        phase = "needs_edit_completion"
        blockers.append({"path": str(edit_draft), "message": "文字编辑草稿尚未完成或还原"})
        next_command = cli_command("edit", project)
        next_action = "start_editor"
        next_details = {"long_running": True, "wait_for_exit": False}
    elif not markdown.is_file() or markdown_is_starter:
        phase = "needs_outline"
        blockers.append({"path": str(markdown), "message": "Markdown 大纲尚未填写" if markdown_is_starter else "Markdown 大纲尚不存在"})
        next_command = None
        next_action = "edit_outline"
        next_details = {"path": str(markdown)}
    elif not outline_ok:
        phase = "needs_outline_confirmation"
        blockers.append({"path": str(markdown), "message": "当前 Markdown 大纲尚未被用户确认，或确认后又发生变化"})
        next_command = None
        next_action = "ask_user_to_confirm_outline"
        markdown_sha256 = outline_digest(markdown)
        next_details = {
            "artifact": str(markdown),
            "artifact_sha256": markdown_sha256,
            "command_on_confirm": cli_command(
                "confirm", project, "--stage", "outline",
                "--expected-sha256", markdown_sha256, "--user-confirmed",
            ),
        }
    elif not plan_ok:
        phase = "needs_plan"
        blockers.append({"path": str(outline), "message": plan_error or "outline.json 尚不存在"})
        next_command = None
        next_details = {}
        if text_only_needs_confirmation:
            next_action = "ask_user_to_confirm_text_only"
            next_details = {
                "artifact": str(outline),
                "command_on_confirm": cli_command("plan", project, "--user-confirmed-text-only"),
            }
        elif outline_structure_valid:
            next_action = "run_command"
            next_command = cli_command("plan", project)
        else:
            next_action = "write_visual_plan"
            next_details = {
                "path": str(outline),
                "reference_command": cli_command("contract", "--example"),
            }
    elif media_errors:
        phase = "needs_media"
        blockers.append({
            "path": str(outline),
            "message": f"{len(media_errors)} 个素材绑定缺失或不可用；一次性处理 next.issues 后重新运行 status",
        })
        next_command = None
        next_action = "fix_media"
        next_details = {
            "path": str(outline),
            "issues": media_errors,
            "reference_command": cli_command("media", "plan", project, "--write"),
            "rerun": cli_command("status", project, "--json"),
        }
    elif validation_failure:
        phase = "needs_render_fix"
        blockers.append({
            "path": str(validation_state_path(project)),
            "message": str(validation_failure.get("message") or "真实浏览器检测到渲染问题"),
        })
        next_command = None
        next_action = str((validation_failure.get("next") or {}).get("action") or "edit_outline")
        next_details = {
            "path": str((validation_failure.get("next") or {}).get("path") or outline),
            "issues": validation_failure.get("issues") or [],
            "rerun": str((validation_failure.get("next") or {}).get("rerun") or cli_command("status", project, "--json")),
        }
    elif preview_status in {"missing", "stale"}:
        phase = "needs_preview"
        blockers.append({"path": str(preview), "message": stale_reason or "尚未生成当前计划对应的预览"})
        next_command = cli_command("preview", project)
        next_action = "start_editor"
        next_details = {"wait_for_exit": False}
    elif preview_status == "awaiting-confirmation":
        phase = "needs_preview_confirmation"
        blockers.append({"path": str(preview), "message": "当前预览正在等待用户明确确认"})
        next_command = None
        next_action = "ask_user_to_confirm_preview"
        preview_sha256 = str((preview_state or {}).get("preview_sha256") or outline_digest(preview))
        next_details = {
            "artifact": str(preview),
            "artifact_sha256": preview_sha256,
            "command_on_confirm": cli_command(
                "confirm", project, "--stage", "preview",
                "--expected-sha256", preview_sha256, "--user-confirmed",
            ),
        }
    elif intent == "edit":
        phase = "ready_to_edit"
        next_command = cli_command("edit", project)
        next_action = "start_editor"
        next_details = {"long_running": True, "wait_for_exit": False}
    elif not final.is_file():
        phase = "ready_to_build"
        next_command = cli_command("build", project)
        next_details = {}
    else:
        build_state_path = project / BUILD_STATE_NAME
        stale_build = True
        if build_state_path.is_file():
            try:
                build_state = json.loads(build_state_path.read_text(encoding="utf-8"))
                stale_build = not isinstance(build_state, dict) or (
                    build_state.get("outline_sha256") != json_digest(outline)
                    or build_state.get("assets") != asset_manifest(outline)
                    or build_state.get("output_sha256") != outline_digest(final)
                    or build_state.get("renderer_sha256") != renderer_digest()
                )
            except (json.JSONDecodeError, SystemExit):
                stale_build = True
        if stale_build:
            phase = "needs_build"
            blockers.append({"path": str(final), "message": "最终文件存在，但构建证据缺失或输入已变化"})
            next_command = cli_command("build", project)
            next_details = {}
        else:
            phase = "complete"
            next_command = None
            next_action = "complete"
            next_details = {}
    if next_action is None:
        next_action = "run_command" if next_command else None
    return {
        "schema_version": "oil-ppt.status/v1",
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
        **({"recovery": project_state["recovery"]} if isinstance(project_state.get("recovery"), dict) else {}),
        "blockers": blockers,
        "next": {"action": next_action, "command": next_command, **next_details},
    }


def print_status(project: Path, *, as_json: bool, intent: str = "continue") -> None:
    payload = status_payload(project, intent=intent)
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"phase: {payload['phase']}")
    print(f"project: {payload['project']}")
    for blocker in payload["blockers"]:
        print(f"blocker: {blocker['message']} ({blocker['path']})")
    if payload["next"].get("action"):
        print(f"action: {payload['next']['action']}")
    if payload["next"].get("command_on_confirm"):
        print(f"after confirmation: {payload['next']['command_on_confirm']}")
    print(f"next: {payload['next']['command'] or '-'}")


def preview_output_path(outline: Path, output: Path | None) -> Path:
    project = outline.parent.resolve()
    target = (output or project / "预览.html").expanduser().resolve()
    if target.parent != project or target.suffix.lower() not in {".html", ".htm"}:
        raise SystemExit("Preview output must be an .html file directly inside the project root.")
    reserved = {
        outline.resolve(), project / "outline.md", project_state_path(project), preview_state_path(outline),
        project / BUILD_STATE_NAME, project / "deck.json", project / "media-plan.json",
        project / DEFAULT_FINAL_NAME, edit_draft_path(project), project / VALIDATION_STATE_NAME,
    }
    if target in {path.resolve() for path in reserved}:
        raise SystemExit(f"Preview output conflicts with a protected project file: {target.name}")
    return target


def generate_preview(
    target_path: Path,
    output: Path | None,
    open_browser: bool,
    *,
    emit: bool = True,
) -> dict:
    project = require_initialized_project(target_path, "Preview")
    require_no_edit_draft(project, "Preview")
    outline = project / "outline.json"
    if not outline.is_file():
        raise SystemExit(f"Outline not found: {outline}. Next: {cli_command('contract', '--example')}")
    # Preview only needs the blocking project checks. Computing the next-step
    # recommendation here would repeat media and state inspection immediately
    # before the actual preview build.
    check = check_project(outline, include_next=False)
    if not check["ok"]:
        print(json.dumps(check, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    data = json.loads(outline.read_text(encoding="utf-8"))
    write_media_plan(
        build_media_plan(data, outline.parent, cli=cli_display()),
        outline.parent / "media-plan.json",
    )
    target = preview_output_path(outline, output)
    state_path = preview_state_path(outline)
    previous_preview: Path | None = None
    if state_path.is_file():
        try:
            previous_state = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(previous_state, dict) and previous_state.get("preview"):
                candidate = Path(str(previous_state["preview"])).expanduser().resolve()
                if (
                    candidate.parent == outline.parent.resolve()
                    and candidate.suffix.lower() in {".html", ".htm"}
                    and candidate.name != DEFAULT_FINAL_NAME
                    and candidate.is_file()
                    and previous_state.get("preview_sha256") == outline_digest(candidate)
                ):
                    previous_preview = candidate
        except json.JSONDecodeError:
            previous_preview = None
    # Render first, validate the actual thumbnail iframes, and only then open it.
    # This keeps the public preview command as the single render-quality gate.
    command = [str(outline), "--out", str(target), "--no-open"]
    run_script_quiet("render_outline_review.py", command)
    browser_validate(target, project=project, stage="preview")
    if previous_preview and previous_preview != target:
        previous_preview.unlink(missing_ok=True)
    preview_sha256 = outline_digest(target)
    atomic_write_json(state_path, {
        "outline": str(outline),
        "outline_sha256": json_digest(outline),
        "markdown_sha256": outline_digest(outline.parent / "outline.md"),
        "renderer_sha256": renderer_digest(),
        "preview": str(target),
        "preview_sha256": preview_sha256,
        "assets": asset_manifest(outline),
        "confirmed": False,
    })
    if open_browser:
        webbrowser.open(target.as_uri())
    payload = {
        "ok": True,
        "phase": "needs_preview_confirmation",
        "project": str(outline.parent),
        "preview": str(target),
        "opened": open_browser,
        "next": {
            "action": "ask_user_to_confirm_preview",
            "command": None,
            "artifact": str(target),
            "artifact_sha256": preview_sha256,
            "command_on_confirm": cli_command(
                "confirm", outline.parent, "--stage", "preview",
                "--expected-sha256", preview_sha256, "--user-confirmed",
            ),
        },
    }
    if emit:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def confirm_preview(
    target_path: Path, user_confirmed: bool, expected_sha256: str | None = None,
) -> None:
    if not user_confirmed:
        raise SystemExit("Confirmation requires --user-confirmed after the user explicitly approves the preview.")
    project = require_initialized_project(target_path, "Preview confirmation")
    require_no_edit_draft(project, "Preview confirmation")
    outline = project / "outline.json"
    if not outline_confirmation_valid(outline.parent):
        raise SystemExit("Preview confirmation requires the current outline.md to be explicitly confirmed first.")
    if not visual_plan_valid(outline.parent, outline):
        raise SystemExit("Preview confirmation requires a plan bound to the current confirmed Markdown outline.")
    state_path = preview_state_path(outline)
    preview_status, state, reason = preview_state_status(outline)
    if preview_status in {"missing", "stale"} or state is None:
        raise SystemExit(f"Preview confirmation is unavailable: {reason or 'regenerate 预览.html first'}.")
    preview = Path(str(state["preview"])).expanduser().resolve()
    verify_expected_sha256(preview, expected_sha256, stage="Preview")
    state["confirmed"] = True
    atomic_write_json(state_path, state)
    print(json.dumps({
        "ok": True, "phase": "ready_to_build", "project": str(outline.parent),
        "preview": str(preview),
        "next": {"action": "run_command", "command": cli_command("build", outline.parent)},
    }, ensure_ascii=False, indent=2))


def require_preview_confirmation(outline_path: Path) -> dict:
    outline = outline_path.expanduser().resolve()
    if not outline_confirmation_valid(outline.parent):
        raise SystemExit("Build blocked: the current outline.md is missing or no longer confirmed.")
    if not visual_plan_valid(outline.parent, outline):
        raise SystemExit("Build blocked: outline.json is not bound to the current confirmed Markdown outline.")
    status, state, reason = preview_state_status(outline)
    if status != "confirmed" or state is None:
        if status == "awaiting-confirmation":
            raise SystemExit("Build blocked: preview has not been confirmed by the user.")
        raise SystemExit(f"Build blocked: {reason or 'generate and confirm 预览.html first'}.")
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
    atomic_write_json(outline_path, data)
    run_script("fill_slots.py", [str(resolved), "--outline", str(outline_path)])


def sync_project_configuration(project: Path) -> None:
    outline_path = project / "outline.json"
    config_path = project / "deck.json"
    if not outline_path.is_file() or not config_path.is_file():
        raise SystemExit("Existing project synchronization requires outline.json and deck.json.")
    data = json.loads(outline_path.read_text(encoding="utf-8"))
    validate_outline(data, TEMPLATES)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise SystemExit("deck.json must contain a JSON object.")
    palette = data["palette"]
    try:
        resolved_palette = named_palette(palette) if isinstance(palette, str) else normalize_palette(palette)
    except ValueError as error:
        raise SystemExit(f"Cannot synchronize project palette: {error}") from error
    config.update({
        "title": str(data["title"]),
        "next_preview": data.get("next_preview", True),
        "click_navigation": data["click_navigation"],
        "show_progress": data.get("show_progress", True),
        "show_counter": data.get("show_counter", True),
        "typography": {"profile": data["typography"]},
        "shape": {"profile": data["shape"]},
        "palette": resolved_palette,
    })
    atomic_write_json(config_path, config)
    run_script("sync_runtime.py", [str(project)])


def build_project(project_arg: Path) -> None:
    project = require_initialized_project(project_arg, "Build")
    require_no_edit_draft(project, "Build")
    outline = project / "outline.json"
    if not outline_confirmation_valid(project):
        raise SystemExit("Build blocked: the current outline.md is missing or no longer confirmed.")
    require_preview_confirmation(outline)
    if not (project / "deck.json").is_file():
        scaffold(project, outline)
    else:
        sync_project_configuration(project)
    project, _ = read_config(project)
    _, data = read_outline(project)
    materialize_slides(project, data, data["slides"])
    output = final_output_path(project)
    run_script("build_deck.py", [str(project)])
    if not output.is_file():
        raise SystemExit(f"Build completed without the expected final file: {output}")
    atomic_write_json(project / BUILD_STATE_NAME, {
        "schema_version": "oil-ppt.build/v1",
        "project": str(project),
        "outline_sha256": json_digest(project / "outline.json"),
        "assets": asset_manifest(project / "outline.json"),
        "output": str(output),
        "output_sha256": outline_digest(output),
        "renderer_sha256": renderer_digest(),
        "renderer": "oil-ppt deterministic HTML",
    })
    print(json.dumps({
        "ok": True, "phase": "complete", "project": str(project), "output": str(output),
        "next": {"action": "complete", "command": None},
    }, ensure_ascii=False, indent=2))


def scaffold(project: Path, outline_path: Path) -> None:
    project = require_initialized_project(project, "Scaffold")
    require_no_edit_draft(project, "Scaffold")
    outline_path = outline_path.expanduser().resolve()
    if project != outline_path.parent:
        raise SystemExit("Scaffold project and outline.json must share the same project root.")
    if not outline_confirmation_valid(project):
        raise SystemExit("Scaffold blocked: the current outline.md is missing or no longer confirmed.")
    require_preview_confirmation(outline_path)
    outline_text = outline_path.read_text(encoding="utf-8")
    data = json.loads(outline_text)
    slides = validate_outline(data, TEMPLATES)
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

    if isinstance(palette, dict):
        config_path = project / "deck.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise SystemExit("Scaffolded deck.json must contain a JSON object.")
        config["palette"] = normalize_palette(palette)
        atomic_write_json(config_path, config)

    atomic_write_json(project / "outline.json", data)
    print(f"Scaffolded confirmed project: {project}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="oil-ppt",
        description="Create and validate an oil-ppt project through one stateful CLI.",
        epilog=(
            "Existing work: batch TARGET [TARGET ...]. New work: init PROJECT, write outline.md, then repeat "
            "status PROJECT --json and follow its single next action. Run command_on_confirm only after user approval."
        ),
    )
    public_commands = ("init", "batch", "status", "contract", "media", "icon", "doctor", "version")
    sub = parser.add_subparsers(dest="command", metavar="{" + ",".join(public_commands) + "}")
    init_parser = sub.add_parser("init", help="initialize outline.md, assets, and project state")
    init_parser.add_argument("project", type=Path, help="one project root directory")
    batch_parser = sub.add_parser("batch", help="discover projects and advance every deterministic stage without opening editors")
    batch_parser.add_argument("targets", type=Path, nargs="+", help="one or more project roots or parent directories")
    batch_parser.add_argument(
        "--user-confirmed-preview",
        action="store_true",
        help="attest that the user approved every awaiting preview, then build all ready projects",
    )
    batch_parser.add_argument(
        "--expected-preview",
        action="append",
        default=[],
        metavar="PROJECT::SHA256",
        help="bind approval to one preview digest; repeat for batch confirmations",
    )
    status_parser = sub.add_parser("status", help="show the current phase and one explicit next action")
    status_parser.add_argument("project", type=Path, help="project root")
    status_parser.add_argument("--json", action="store_true", help="emit a stable machine-readable envelope")
    status_parser.add_argument(
        "--intent", choices=("continue", "edit"), default="continue",
        help="continue the workflow, or explicitly reopen the current formal preview for text editing",
    )
    plan_parser = sub.add_parser("plan", help="validate and install the visual outline.json after Markdown approval")
    plan_parser.add_argument("project", type=Path, help="project root")
    plan_parser.add_argument("--input", type=Path, help="optional candidate JSON to validate and copy into the project")
    plan_parser.add_argument(
        "--user-confirmed-text-only",
        action="store_true",
        help="attest that the user explicitly requested a deck with no images",
    )
    check_parser = sub.add_parser("check", help="validate schema, deck rhythm, recommendations, and all bound media")
    check_parser.add_argument("target", type=Path, help="project root or outline.json")
    sub.add_parser("doctor", help="run dependency, contract, browser, and end-to-end self tests")
    version_parser = sub.add_parser("version", help="show package version, provenance, and integrity")
    version_parser.add_argument("--json", action="store_true", help="emit a machine-readable integrity report")
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("outline", type=Path, help="project root or outline.json")
    recommend_parser = sub.add_parser("recommend")
    recommend_parser.add_argument("outline", type=Path, help="project root or outline.json")
    recommend_parser.add_argument("--pretty", action="store_true")
    contract_parser = sub.add_parser("contract", help="inspect the executable layout and field contract")
    contract_selector = contract_parser.add_mutually_exclusive_group()
    contract_selector.add_argument(
        "--all",
        action="store_true",
        help="print the complete registry instead of the compact directory",
    )
    contract_selector.add_argument("--list", action="store_true", help="list families and their template names")
    contract_selector.add_argument("--family", choices=tuple(FAMILY_GUIDANCE), help="show templates in one content-relation family")
    contract_selector.add_argument("--example", action="store_true", help="print a minimal valid outline.json")
    contract_parser.add_argument("--id", help="show one compact template contract, e.g. photo-gradient")
    contract_parser.add_argument("--schema", action="store_true", help="print the full schema, or one component schema with --id")
    contract_parser.add_argument("--pretty", action="store_true", help=argparse.SUPPRESS)
    contract_parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    preview_parser = sub.add_parser("preview", help="create and open the editable final-material preview")
    preview_parser.add_argument("outline", type=Path, help="project root")
    preview_parser.add_argument("--out", type=Path)
    preview_parser.add_argument("--open", action="store_true", help=argparse.SUPPRESS)
    preview_parser.add_argument("--no-open", action="store_true", help=argparse.SUPPRESS)
    edit_parser = sub.add_parser("edit", help="open the local draft-safe text editor for the current preview")
    edit_parser.add_argument("project", type=Path, help="project root")
    edit_parser.add_argument("--port", type=int, default=0, help="local loopback port; 0 chooses an available port")
    edit_parser.add_argument("--no-open", action="store_true", help="do not open the browser automatically")
    edit_parser.add_argument("--discard-draft", action="store_true", help="explicitly delete an existing text-edit draft")
    confirm_parser = sub.add_parser("confirm", help="record explicit user approval for outline or preview")
    confirm_parser.add_argument("outline", type=Path, help="project root")
    confirm_parser.add_argument("--stage", choices=("outline", "preview"), help="defaults to preview for compatibility")
    confirm_parser.add_argument(
        "--expected-sha256",
        help="bind this confirmation to the artifact digest returned by status",
    )
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
        metavar="{sources,plan,verify,frame,render-html}",
    )
    media_sub.add_parser("sources", help="show machine-readable source and delivery policy")
    media_plan_parser = media_sub.add_parser("plan", help="compile slide media into roles, fidelity, ratios, and commands")
    media_plan_parser.add_argument("target", type=Path, help="project root or outline.json")
    media_plan_parser.add_argument("--write", action="store_true", help="also write media-plan.json in the project")
    media_plan_parser.add_argument("--out", type=Path, help="override the media plan output path")
    media_verify = media_sub.add_parser("verify", help="verify every bound media file and source record")
    media_verify.add_argument("outline", type=Path, help="project root or outline.json")
    media_frame_parser = media_sub.add_parser("frame", help="preserve a screenshot on a slot-matched block background")
    media_frame_parser.add_argument("source", type=Path)
    media_frame_parser.add_argument("output", type=Path)
    media_frame_parser.add_argument("--project", type=Path, help="read the current palette from this project")
    media_frame_parser.add_argument("--palette", choices=sorted(PALETTES), help="named palette when no project is supplied")
    media_frame_parser.add_argument("--ratio", choices=("16:9", "16:10", "4:3", "4:5", "1:1", "21:9"), default="16:10")
    media_frame_parser.add_argument("--padding", choices=("compact", "standard", "spacious"), default="standard")
    media_frame_parser.add_argument("--align", choices=("center", "left", "right", "top", "bottom", "top-left", "top-right", "bottom-left", "bottom-right"), default="center")
    media_frame_parser.add_argument("--fit", choices=("contain", "cover"), default="contain")
    media_render = media_sub.add_parser("render-html", help="render an authoring HTML visual into a local PNG")
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
    if args.command == "contract":
        primary_selector = any((args.all, args.list, args.family, args.example))
        if args.id and primary_selector:
            parser.error("contract --id cannot be combined with --all, --list, --family, or --example")
        if args.schema and primary_selector:
            parser.error("contract --schema can only be combined with --id")
    return args


def main() -> None:
    args = parse_args()
    if args.command == "init":
        init_project(args.project)
    elif args.command == "batch":
        payload = batch_projects(
            args.targets,
            user_confirmed_preview=args.user_confirmed_preview,
            expected_previews=args.expected_preview,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if not payload["ok"]:
            raise SystemExit(1)
    elif args.command == "status":
        print_status(args.project, as_json=args.json, intent=args.intent)
    elif args.command == "plan":
        plan_project(args.project, args.input, args.user_confirmed_text_only)
    elif args.command == "check":
        payload = check_project(args.target)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if not payload["ok"]:
            raise SystemExit(1)
    elif args.command == "doctor":
        run_script("doctor.py", [])
    elif args.command == "version":
        from package_manifest import package_status

        payload = package_status(ROOT)
        if args.json:
            emit_json(payload, pretty=True)
        else:
            print(f"oil-ppt {payload['version']} ({payload['tree_sha256']})")
            print(f"integrity: {'ok' if payload['ok'] else 'failed'}")
        if not payload["ok"]:
            raise SystemExit(1)
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
            family_id=getattr(args, "family", None),
        )
    elif args.command == "preview":
        interactive = not bool(args.no_open)
        payload = generate_preview(args.outline, args.out, False, emit=not interactive)
        if interactive:
            editor = launch_text_editor(Path(payload["project"]))
            print(json.dumps({
                **payload,
                "phase": "editing_in_progress",
                "opened": True,
                "editor": editor,
                "next": {"action": "wait_for_editor", "command": None},
            }, ensure_ascii=False, indent=2))
    elif args.command == "edit":
        command = [str(args.project), "--port", str(args.port)]
        if args.no_open:
            command.append("--no-open")
        if args.discard_draft:
            command.append("--discard-draft")
        run_script("text_editor.py", command)
    elif args.command == "confirm":
        stage = args.stage or "preview"
        if stage == "outline":
            confirm_outline(
                project_from_target(args.outline), args.user_confirmed, args.expected_sha256,
            )
        else:
            confirm_preview(args.outline, args.user_confirmed, args.expected_sha256)
    elif args.command == "scaffold":
        scaffold(args.project, args.outline)
    elif args.command == "list":
        list_project(args.project)
    elif args.command == "add":
        project, _ = read_config(args.project)
        require_no_edit_draft(project, "Add slide")
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
        require_no_edit_draft(args.project, "Remove slide")
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
            print_media_plan(args.target, write=args.write or args.out is not None, output=args.out)
        elif args.media_command == "verify":
            print_media_verification(args.outline)
        elif args.media_command == "frame":
            create_media_frame(
                args.source, args.output, project=args.project, palette_name=args.palette,
                ratio=args.ratio, padding=args.padding, align=args.align, fit=args.fit,
            )
        elif args.media_command == "render-html":
            details = render_html_visual(args.source, args.output, width=args.width, height=args.height)
            print(json.dumps({"schema_version": "oil-ppt.programmatic-visual/v1", "status": "ok", **details}, ensure_ascii=False, separators=(",", ":")))
    elif args.command == "icon":
        if args.icon_command == "search":
            print_icon_results(args.query)
        else:
            print_icon_results()


if __name__ == "__main__":
    main()
