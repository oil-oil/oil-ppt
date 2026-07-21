"""Project shell and deck metadata operations; slide content lives in HTML."""
from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import tempfile
from pathlib import Path

from state import state_path, write_json, write_state
from theme import project_theme_css, validate_theme, write_project_theme

ROOT = Path(__file__).resolve().parent.parent
RUNTIME_SOURCE = ROOT / "assets" / "runtime"
SLIDE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def resolve_project(value: Path) -> Path:
    return value.expanduser().resolve()


def deck_path(project: Path) -> Path:
    return project / "deck.json"


def require_project(value: Path) -> Path:
    project = resolve_project(value)
    required_files = (
        deck_path(project),
        state_path(project),
        project / "outline.md",
        project / "runtime" / "deck.css",
        project / "runtime" / "theme.css",
        project / "runtime" / "deck.js",
    )
    required_directories = (project / "slides", project / "assets")
    if (
        not project.is_dir()
        or not all(path.is_file() for path in required_files)
        or not all(path.is_dir() for path in required_directories)
    ):
        raise SystemExit(f"Not an initialized oil-ppt project: {project}")
    return project


def sync_project_runtime(project: Path) -> None:
    """Refresh only package-owned runtime files without touching authored content."""
    runtime = project / "runtime"
    if runtime.is_symlink() or not runtime.is_dir():
        raise SystemExit(f"Project runtime directory must be a real directory, not a symlink: {runtime}")
    for name in ("deck.css", "deck.js"):
        source = RUNTIME_SOURCE / name
        destination = runtime / name
        if destination.is_symlink():
            raise SystemExit(f"Project runtime file must not be a symlink: {destination}")
        if not source.is_file():
            raise SystemExit(f"Package runtime file is missing: {source}")
        expected = source.read_bytes()
        if destination.is_file() and destination.read_bytes() == expected:
            continue
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{name}.", suffix=".tmp", dir=runtime)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(expected)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)


def discover_projects(values: list[Path]) -> list[Path]:
    """Resolve explicit projects or search only inside explicitly supplied parents."""
    found: list[Path] = []
    seen: set[Path] = set()
    for value in values:
        root = resolve_project(value)
        if not root.is_dir():
            raise SystemExit(f"Project or parent directory does not exist: {root}")
        candidates = [root]
        if not (deck_path(root).is_file() and state_path(root).is_file()):
            candidates = sorted(
                path.parent
                for path in root.rglob("deck.json")
                if state_path(path.parent).is_file()
            )
        for candidate in candidates:
            if deck_path(candidate).is_file() and state_path(candidate).is_file() and candidate not in seen:
                found.append(candidate)
                seen.add(candidate)
    if not found:
        raise SystemExit("No initialized oil-ppt projects found in the supplied paths.")
    return found


def default_deck(title: str) -> dict:
    return {
        "title": title,
        "lang": "zh-CN",
        "theme": {"palette": "oil-yellow", "typography": "clean", "shape": "soft", "direction": "fresh-default"},
        "controls": {"next_preview": True, "click_navigation": False, "show_progress": True, "show_counter": True},
        "slides": [],
    }


def validate_deck(value: object) -> dict:
    if not isinstance(value, dict):
        raise SystemExit("Invalid deck.json: root must be an object.")
    allowed = {"title", "lang", "theme", "controls", "slides"}
    unknown = sorted(set(value) - allowed)
    missing = sorted(allowed - set(value))
    if unknown or missing:
        raise SystemExit(f"Invalid deck.json keys: missing={missing}, unsupported={unknown}")
    if not isinstance(value["title"], str) or not value["title"].strip():
        raise SystemExit("Invalid deck.json: title must be a non-empty string.")
    if not isinstance(value["lang"], str) or not value["lang"].strip():
        raise SystemExit("Invalid deck.json: lang must be a non-empty string.")
    value["theme"] = validate_theme(value["theme"])
    controls = value["controls"]
    control_keys = {"next_preview", "click_navigation", "show_progress", "show_counter"}
    if not isinstance(controls, dict) or set(controls) != control_keys or not all(
        isinstance(controls[key], bool) for key in control_keys
    ):
        raise SystemExit("Invalid deck.json: controls must contain four boolean presentation controls.")
    slides = value["slides"]
    if not isinstance(slides, list) or not all(isinstance(item, str) for item in slides):
        raise SystemExit("Invalid deck.json: slides must be an array of HTML paths.")
    if len(slides) != len(set(slides)):
        raise SystemExit("Invalid deck.json: slide paths must be unique.")
    for relative in slides:
        match = re.fullmatch(r"slides/([a-z0-9][a-z0-9-]*)\.html", relative)
        if not match:
            raise SystemExit(f"Invalid deck.json slide path: {relative}")
    return value


def deck_chrome(deck: dict) -> str:
    controls = deck.get("controls") if isinstance(deck.get("controls"), dict) else {}
    # Overview is runtime chrome, deliberately not a fifth deck.json control.
    parts: list[str] = [
        '<button class="deck-overview-toggle" type="button" aria-label="打开演示总览" aria-expanded="false" data-deck-overview-toggle>总览 <kbd>O</kbd></button>',
        '<section class="deck-overview" aria-label="演示总览" aria-hidden="true" data-deck-overview hidden><div class="deck-overview-panel" role="dialog" aria-modal="true" aria-label="演示缩略图"><header><strong>演示总览</strong><button type="button" data-deck-overview-close aria-label="关闭总览">关闭 <kbd>Esc</kbd></button></header><div class="deck-overview-grid" data-deck-overview-grid></div></div></section>',
    ]
    if controls.get("show_progress", True):
        parts.append('<div class="progress-bar" aria-hidden="true"></div>')
    if controls.get("show_counter", True):
        parts.append('<div class="deck-counter" aria-live="polite"></div>')
    if controls.get("next_preview", True):
        parts.append(
            '<aside class="next-preview" aria-hidden="true">'
            '<span class="next-preview-label">NEXT</span>'
            '<span class="next-preview-title"></span></aside>'
        )
    return "".join(parts)


def init_project(target: Path, title: str | None = None) -> Path:
    project = resolve_project(target)
    if project.exists() and any(project.iterdir()):
        raise SystemExit(f"Refusing to initialize a non-empty directory: {project}")
    project.mkdir(parents=True, exist_ok=True)
    for directory in ("slides", "assets", ".oil-ppt"):
        (project / directory).mkdir(exist_ok=True)
    shutil.copytree(RUNTIME_SOURCE, project / "runtime", dirs_exist_ok=True)
    icons = ROOT / "assets" / "icons"
    if icons.is_dir():
        shutil.copytree(icons, project / "assets" / "icons", dirs_exist_ok=True)
    chosen_title = title or project.name
    outline = project / "outline.md"
    outline.write_text(f"# {chosen_title}\n\n", encoding="utf-8")
    deck = default_deck(chosen_title)
    write_json(deck_path(project), deck)
    write_project_theme(project, deck)
    write_state(
        project,
        phase="edit_outline",
        outline_seed_sha256=hashlib.sha256(outline.read_bytes()).hexdigest(),
        outline_confirmed=False,
    )
    return project


def read_deck(project_value: Path) -> tuple[Path, dict]:
    project = require_project(project_value)
    sync_project_runtime(project)
    try:
        deck = json.loads(deck_path(project).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid deck.json: {error}") from error
    deck = validate_deck(deck)
    project_theme_css(project, deck)
    return project, deck


def save_deck(project: Path, deck: dict) -> None:
    deck = validate_deck(deck)
    previous: dict | None = None
    try:
        previous = validate_deck(json.loads(deck_path(project).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, SystemExit):
        previous = None
    write_project_theme(project, deck)
    try:
        write_json(deck_path(project), deck)
    except BaseException:
        if previous is not None:
            write_project_theme(project, previous)
        raise
    write_state(project, phase="author_slides")


def valid_slide_id(value: str) -> str:
    if not SLIDE_ID.fullmatch(value):
        raise SystemExit("Slide id must match [a-z0-9][a-z0-9-]*.")
    return value


def slide_relative(slide_id: str) -> str:
    return f"slides/{valid_slide_id(slide_id)}.html"


def slide_path(project: Path, relative: str) -> Path:
    candidate = (project / relative).resolve()
    slides = (project / "slides").resolve()
    if slides not in candidate.parents or candidate.suffix.lower() != ".html":
        raise SystemExit(f"Invalid slide path in deck.json: {relative}")
    return candidate
