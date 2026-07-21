"""Small, private workflow state for the HTML-first project format."""
from __future__ import annotations

import json
import hashlib
import os
import tempfile
from pathlib import Path

STATE_DIR = ".oil-ppt"
STATE_NAME = "state.json"
RUNTIME_SOURCE = Path(__file__).resolve().parent.parent / "assets" / "runtime"


def state_path(project: Path) -> Path:
    return project / STATE_DIR / STATE_NAME


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_state(project: Path) -> dict:
    path = state_path(project)
    if not path.is_file():
        return {"schema_version": "oil-ppt.state/v1"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid internal state: {path}: {error}") from error
    if not isinstance(data, dict):
        raise SystemExit(f"Invalid internal state: {path} must contain an object.")
    return data


def write_state(project: Path, **updates: object) -> dict:
    value = read_state(project)
    value.update(updates)
    value.setdefault("schema_version", "oil-ppt.state/v1")
    write_json(state_path(project), value)
    return value


def input_manifest(project: Path) -> dict[str, str]:
    """Inputs whose changes invalidate preview confirmation (not outline.md)."""
    paths: list[Path] = [project / "deck.json"]
    for directory in ("slides", "assets", "runtime"):
        root = project / directory
        if root.is_dir():
            paths.extend(path for path in root.rglob("*") if path.is_file())
    manifest = {
        path.relative_to(project).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths, key=lambda item: item.relative_to(project).as_posix()) if path.is_file()
    }
    renderer = Path(__file__).resolve().parent
    for name in ("slide_html.py", "preview_deck.py", "build_deck.py", "project.py", "theme.py", "cdp_validate.py"):
        path = renderer / name
        if path.is_file():
            manifest[f"@renderer/{name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ("deck.css", "deck.js"):
        path = RUNTIME_SOURCE / name
        if not path.is_file():
            raise SystemExit(f"Package runtime source is missing: {path}")
        manifest[f"@runtime-source/{name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest
