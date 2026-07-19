#!/usr/bin/env python3
"""Serve the local, draft-safe oil-ppt text authoring experience."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import mimetypes
import os
import re
import secrets
import tempfile
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from design_quality import enforce_outline_quality
from design_directions import apply_design_updates, matching_direction
from editor_bindings import editable_values, pointer_parts, set_pointer
from media_assets import (
    MAX_EDITOR_UPLOAD_BYTES,
    editable_outline_media,
    inspect_image,
    validate_editor_upload,
    verify_outline_media,
)
from oil_ppt import (
    EDIT_LOCK_NAME,
    TEMPLATES,
    active_editor_pid,
    atomic_write_json,
    editor_lock_owned_by_current_process,
    editor_lock_payload,
    generate_preview,
    json_digest,
    outline_confirmation_valid,
    preview_state_path,
    preview_state_status,
    project_state_path,
    read_project_state,
    visual_plan_valid,
)
from outline_schema import validate_outline
from palette_tokens import PALETTE_META, PALETTES, canonical_name, named_palette, normalize_palette
from profile_tokens import SHAPE_META, SHAPE_PROFILES, TYPE_META, TYPE_PROFILES
from render_outline_review import render


DRAFT_NAME = ".oil-ppt-edit-draft.json"
DRAFT_SCHEMA = "oil-ppt.text-edit-draft/v1"
MAX_REQUEST_BYTES = 1_000_000
MAX_APPLIED_OPERATIONS = 200
EDITOR_ASSET_DIRECTORY = Path("assets") / "oil-ppt-editor"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--port", type=int, default=0, help="local loopback port; 0 chooses an available port")
    parser.add_argument("--no-open", action="store_true", help="do not open the authoring page automatically")
    parser.add_argument("--discard-draft", action="store_true", help="explicitly delete an existing text-edit draft before opening")
    return parser.parse_args()


def _digest(data: dict) -> str:
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Edited text must be a string.")
    if len(value) > 20_000:
        raise ValueError("One text field cannot exceed 20,000 characters.")
    return re.sub(r"\s+", " ", value).strip()


def _setting_values(data: dict) -> dict:
    return {
        "palette": copy.deepcopy(data.get("palette")),
        "palette_source": data.get("palette_source"),
        "typography": data.get("typography"),
        "shape": data.get("shape"),
    }


def _settings_signature(data: dict) -> str:
    return _digest(_setting_values(data))


def _settings_state(data: dict) -> dict:
    raw_palette = data["palette"]
    custom = not isinstance(raw_palette, str)
    resolved = normalize_palette(raw_palette) if custom else named_palette(raw_palette)
    palette_name = None if custom else canonical_name(raw_palette)
    source = str(data.get("palette_source") or "") if custom else "curated"
    return {
        "direction": matching_direction(data),
        "palette": {
            "id": palette_name,
            "label": (
                "品牌配色" if source == "brand" else "用户配色"
            ) if custom else PALETTE_META[palette_name]["label"],
            "source": source,
            "locked": custom,
            "colors": [resolved["accent"], resolved["accent_alt"], resolved["accent_warm"]],
        },
        "typography": {
            "id": data["typography"],
            "label": TYPE_META[data["typography"]]["label"],
        },
        "shape": {
            "id": data["shape"],
            "label": SHAPE_META[data["shape"]]["label"],
        },
    }


def _structure_signature(data: dict) -> str:
    return _digest({
        "slides": [
            {"id": slide.get("id"), "template": slide.get("template")}
            for slide in data.get("slides", [])
            if isinstance(slide, dict)
        ],
    })


def _validate_structural_invariants(data: dict) -> None:
    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        raise ValueError("A deck must contain at least one slide.")
    ids = [slide.get("id") for slide in slides if isinstance(slide, dict)]
    if len(ids) != len(slides) or len(ids) != len(set(ids)):
        raise ValueError("Slide ids must remain unique.")
    cover_indexes = [index for index, slide in enumerate(slides) if slide.get("template") == "cover"]
    end_indexes = [index for index, slide in enumerate(slides) if slide.get("template") == "end"]
    if cover_indexes and cover_indexes != [0]:
        raise ValueError("The cover slide must remain the first slide and cannot be duplicated.")
    if end_indexes and end_indexes != [len(slides) - 1]:
        raise ValueError("The end slide must remain the last slide and cannot be duplicated.")
    if (cover_indexes or end_indexes) and not any(
        slide.get("template") not in {"cover", "end"} for slide in slides
    ):
        raise ValueError("A deck must retain at least one content slide between its boundary slides.")


def _unique_duplicate_id(slides: list[dict], source_id: str) -> str:
    used = {str(slide.get("id") or "") for slide in slides}
    base = f"{source_id}-copy"
    if base not in used:
        return base
    suffix = 2
    while f"{base}-{suffix}" in used:
        suffix += 1
    return f"{base}-{suffix}"


def _atomic_write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _backup(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def _restore(path: Path, value: bytes | None) -> None:
    if value is None:
        path.unlink(missing_ok=True)
    else:
        _atomic_write_bytes(path, value)


class EditorSession:
    def __init__(self, project: Path, *, discard_draft: bool = False) -> None:
        self.project = project.expanduser().resolve()
        self.outline = self.project / "outline.json"
        self.draft_path = self.project / DRAFT_NAME
        self.lock_path = self.project / EDIT_LOCK_NAME
        self.lock_owned = False
        self.editing_complete = False
        self.lock = threading.RLock()
        self.history: list[dict] = []
        self.future: list[dict] = []
        self.revision = 0
        self.applied_operations: dict[str, str] = {}
        self.staged_assets: set[str] = set()
        self.last_edit_path = ""
        self.last_edit_at = 0.0
        self.startup_notices: list[str] = []
        if not self.project.is_dir() or not self.outline.is_file():
            raise ValueError(f"Text editing requires an existing oil-ppt project with outline.json: {self.project}")
        self._acquire_project_lock()
        try:
            if discard_draft:
                self._load_staged_asset_names_for_discard()
                self._delete_staged_assets(self.staged_assets)
                self.staged_assets.clear()
                self.draft_path.unlink(missing_ok=True)
                self._clear_active_edit()
            self.base_data = json.loads(self.outline.read_text(encoding="utf-8"))
            self.base_digest = json_digest(self.outline)
            self.recovery_id = hashlib.sha256(
                f"{self.project}\0{self.base_digest}".encode("utf-8")
            ).hexdigest()[:24]
            self.data = copy.deepcopy(self.base_data)
            has_draft = self.draft_path.is_file()
            if has_draft:
                try:
                    self._load_draft()
                except ValueError as error:
                    backup = self._quarantine_invalid_draft()
                    has_draft = False
                    self.data = copy.deepcopy(self.base_data)
                    self.startup_notices.append(
                        f"无法恢复的旧草稿已保留到 {backup.name}，编辑器已从当前正式内容重新打开。原因：{error}"
                    )
            if not has_draft and not outline_confirmation_valid(self.project):
                raise ValueError("Text editing requires the current Markdown outline to remain confirmed.")
            if not has_draft and not visual_plan_valid(self.project, self.outline):
                raise ValueError("Text editing requires a visual plan bound to the confirmed Markdown outline.")
            preview_status, _, reason = preview_state_status(self.outline)
            if not has_draft and preview_status in {"missing", "stale"}:
                raise ValueError(f"Text editing starts from the current formal preview: {reason or 'run preview first'}")
        except Exception:
            self.close()
            raise

    def _acquire_project_lock(self) -> None:
        for _ in range(2):
            try:
                descriptor = os.open(self.lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pid = active_editor_pid(self.project)
                if pid is None:
                    continue
                raise ValueError(f"Another text editor is already open for this project (pid {pid}).")
            else:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(editor_lock_payload(self.project), stream, ensure_ascii=False)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                self.lock_owned = True
                return
        raise ValueError(f"Could not acquire the text editor lock: {self.lock_path}")

    def close(self) -> None:
        if self.lock_owned:
            try:
                if editor_lock_owned_by_current_process(self.project):
                    self.lock_path.unlink(missing_ok=True)
            except OSError:
                pass
            self.lock_owned = False

    def __del__(self) -> None:
        self.close()

    def _assert_base_unchanged(self) -> None:
        try:
            current = json_digest(self.outline)
        except (json.JSONDecodeError, OSError, SystemExit) as error:
            raise ValueError(f"outline.json can no longer be verified: {error}") from error
        if current != self.base_digest:
            raise ValueError(
                "outline.json changed outside this editor. This session will not overwrite it; "
                "close the editor, reconcile the changes, and reopen."
            )

    def _ensure_editable(self) -> None:
        if self.editing_complete:
            raise ValueError("This text editing session has already completed. Reopen the editor to make more changes.")

    def _memory_snapshot(self) -> tuple[dict, list[dict], list[dict], set[str], str, float, int, dict[str, str]]:
        return (
            copy.deepcopy(self.data), copy.deepcopy(self.history), copy.deepcopy(self.future),
            set(self.staged_assets), self.last_edit_path, self.last_edit_at,
            self.revision, copy.deepcopy(self.applied_operations),
        )

    def _restore_memory(
        self,
        snapshot: tuple[dict, list[dict], list[dict], set[str], str, float, int, dict[str, str]],
    ) -> None:
        (
            self.data, self.history, self.future, self.staged_assets,
            self.last_edit_path, self.last_edit_at, self.revision, self.applied_operations,
        ) = snapshot

    def _managed_asset_path(self, relative: str, *, require_file: bool = False) -> Path:
        if not isinstance(relative, str) or not relative or "\\" in relative:
            raise ValueError("Staged media path is invalid.")
        raw = Path(relative)
        if raw.is_absolute() or any(part in {"", ".", ".."} for part in raw.parts):
            raise ValueError("Staged media path is invalid.")
        if tuple(raw.parts[:len(EDITOR_ASSET_DIRECTORY.parts)]) != EDITOR_ASSET_DIRECTORY.parts:
            raise ValueError("Staged media must stay in the editor-owned asset directory.")
        candidate = (self.project / raw).resolve()
        root = self.project.resolve()
        directory = (self.project / EDITOR_ASSET_DIRECTORY).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_relative_to(directory) or candidate == directory:
            raise ValueError("Staged media must stay inside the project.")
        if require_file and not candidate.is_file():
            raise ValueError(f"Staged media file is missing: {relative}")
        return candidate

    def _draft_staged_asset_names(self) -> set[str]:
        if not self.draft_path.is_file():
            return set()
        try:
            envelope = json.loads(self.draft_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return set()
        raw = envelope.get("staged_assets") if isinstance(envelope, dict) else None
        return set(raw) if isinstance(raw, list) and all(isinstance(item, str) for item in raw) else set()

    def _load_staged_asset_names_for_discard(self) -> None:
        for relative in self._draft_staged_asset_names():
            self._managed_asset_path(relative, require_file=True)
            self.staged_assets.add(relative)

    def _delete_staged_assets(self, paths: set[str]) -> None:
        for relative in sorted(paths):
            self._managed_asset_path(relative).unlink(missing_ok=True)

    def _quarantine_assets(self, paths: set[str]) -> list[tuple[Path, Path]]:
        moved: list[tuple[Path, Path]] = []
        try:
            for relative in sorted(paths):
                original = self._managed_asset_path(relative, require_file=True)
                quarantine = original.with_name(f".{original.name}.discard-{secrets.token_hex(8)}")
                os.replace(original, quarantine)
                moved.append((original, quarantine))
        except OSError:
            for original, quarantine in reversed(moved):
                os.replace(quarantine, original)
            raise
        return moved

    @staticmethod
    def _restore_quarantine(moved: list[tuple[Path, Path]]) -> None:
        for original, quarantine in reversed(moved):
            if quarantine.exists():
                os.replace(quarantine, original)

    @staticmethod
    def _delete_quarantine(moved: list[tuple[Path, Path]]) -> None:
        for _original, quarantine in moved:
            quarantine.unlink(missing_ok=True)


    def _load_draft(self) -> None:
        try:
            envelope = json.loads(self.draft_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"Text edit draft is invalid JSON: {error}") from error
        if not isinstance(envelope, dict) or envelope.get("schema_version") != DRAFT_SCHEMA or not isinstance(envelope.get("data"), dict):
            raise ValueError("Text edit draft has an unsupported structure. Reopen with --discard-draft only if it should be deleted.")
        if envelope.get("base_outline_sha256") != self.base_digest:
            raise ValueError("outline.json changed while a text edit draft existed. Reopen with --discard-draft only after deciding to delete that draft.")
        try:
            validate_outline(envelope["data"], TEMPLATES)
            _validate_structural_invariants(envelope["data"])
        except (SystemExit, ValueError) as error:
            raise ValueError(
                f"Text edit draft no longer matches the current component contract: {error}. "
                "Reopen with --discard-draft only after deciding to delete that draft."
            ) from error
        self.data = envelope["data"]
        revision = envelope.get("revision", 0)
        operations = envelope.get("applied_operations", {})
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise ValueError("Text edit draft has an invalid transaction revision.")
        if not isinstance(operations, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in operations.items()
        ):
            raise ValueError("Text edit draft has invalid applied-operation records.")
        self.revision = revision
        self.applied_operations = dict(list(operations.items())[-MAX_APPLIED_OPERATIONS:])
        staged_assets = envelope.get("staged_assets", [])
        if not isinstance(staged_assets, list) or not all(isinstance(item, str) for item in staged_assets):
            raise ValueError("Text edit draft has invalid staged media metadata.")
        for relative in staged_assets:
            path = self._managed_asset_path(relative, require_file=True)
            inspect_image(path)
        self.staged_assets = set(staged_assets)

    def _quarantine_invalid_draft(self) -> Path:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup = self.draft_path.with_name(
            f"{self.draft_path.stem}.invalid-{timestamp}-{os.getpid()}{self.draft_path.suffix}"
        )
        os.replace(self.draft_path, backup)
        self._clear_active_edit()
        return backup

    def _is_unchanged(self) -> bool:
        return _digest(self.data) == _digest(self.base_data)

    def _write_draft(self) -> None:
        self._assert_base_unchanged()
        state_path = preview_state_path(self.outline)
        project_state = project_state_path(self.project)
        backups = {path: _backup(path) for path in (self.draft_path, state_path, project_state)}
        try:
            if self._is_unchanged() and not self.staged_assets:
                self.draft_path.unlink(missing_ok=True)
                self._clear_active_edit()
                return
            atomic_write_json(self.draft_path, {
                "schema_version": DRAFT_SCHEMA,
                "base_outline_sha256": self.base_digest,
                "updated_at": int(time.time()),
                "revision": self.revision,
                "applied_operations": self.applied_operations,
                "data": self.data,
                "staged_assets": sorted(self.staged_assets),
            })
            self._invalidate_preview_confirmation()
        except (OSError, SystemExit) as error:
            for path, value in backups.items():
                _restore(path, value)
            raise ValueError(f"Could not persist the text-edit draft: {error}") from error

    def _invalidate_preview_confirmation(self) -> None:
        state_path = preview_state_path(self.outline)
        if state_path.is_file():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                state = None
            if isinstance(state, dict):
                state["confirmed"] = False
                state.pop("edit_draft", None)
                atomic_write_json(state_path, state)

    def _clear_active_edit(self) -> None:
        preview = preview_state_path(self.outline)
        if preview.is_file():
            try:
                preview_state = json.loads(preview.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                preview_state = None
            if isinstance(preview_state, dict) and "edit_draft" in preview_state:
                preview_state.pop("edit_draft", None)
                atomic_write_json(preview, preview_state)
        state = read_project_state(self.project)
        if "active_text_edit" in state:
            state.pop("active_text_edit", None)
            atomic_write_json(project_state_path(self.project), state)

    def state(self, *, notices: list[str] | None = None) -> dict:
        current = editable_values(self.data)
        base = editable_values(self.base_data)
        current_settings = _setting_values(self.data)
        base_settings = _setting_values(self.base_data)
        current_media = editable_outline_media(self.data)
        base_media = editable_outline_media(self.base_data)
        return {
            "ok": True,
            "values": current,
            "media_values": current_media,
            "changed_paths": sorted(path for path, value in current.items() if base.get(path) != value),
            "changed_settings": sorted(
                key for key, value in current_settings.items() if base_settings.get(key) != value
            ),
            "changed_media_paths": sorted(
                path for path, value in current_media.items() if base_media.get(path) != value
            ),
            "settings": _settings_state(self.data),
            "settings_signature": _settings_signature(self.data),
            "structure_signature": _structure_signature(self.data),
            "revision": self.revision,
            "can_undo": bool(self.history),
            "can_redo": bool(self.future),
            "draft": self.draft_path.is_file(),
            "notices": [*self.startup_notices, *(notices or [])],
        }

    def _assert_revision(self, expected_revision: object) -> None:
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
            raise ValueError("An editor transaction requires an integer expected_revision.")
        if expected_revision != self.revision:
            raise ValueError(
                f"Stale editor transaction: expected revision {expected_revision}, current revision is {self.revision}."
            )

    def _push_history(self) -> None:
        self.history.append(copy.deepcopy(self.data))
        if len(self.history) > 100:
            self.history.pop(0)
        self.future.clear()

    def _advance_revision(self) -> None:
        self.revision += 1

    def apply_edit(self, path: str, value: object, *, expected_revision: object | None = None) -> dict:
        with self.lock:
            self._ensure_editable()
            snapshot = self._memory_snapshot()
            try:
                if expected_revision is not None:
                    self._assert_revision(expected_revision)
                allowed = editable_values(self.data)
                if path not in allowed:
                    raise ValueError("This text field is not editable in the current component.")
                text = _normalize_text(value)
                if allowed[path] == text:
                    return self.state()
                now = time.monotonic()
                coalesce = path == self.last_edit_path and now - self.last_edit_at < 1.2 and bool(self.history)
                if not coalesce:
                    self._push_history()
                else:
                    self.future.clear()
                set_pointer(self.data, path, text)
                notices: list[str] = []
                parts = pointer_parts(path)
                if len(parts) == 3 and parts[0] == "slides" and parts[2] == "title":
                    slide = self.data["slides"][int(parts[1])]
                    highlight = str(slide.get("highlight") or "")
                    if highlight and highlight not in text:
                        slide.pop("highlight", None)
                        notices.append("标题已改变，原来不再匹配的高亮短语已移除。")
                self.last_edit_path = path
                self.last_edit_at = now
                self._advance_revision()
                self._write_draft()
                return self.state(notices=notices)
            except (ValueError, KeyError, IndexError, OSError):
                self._restore_memory(snapshot)
                raise

    def _store_uploaded_asset(self, filename: str, data: bytes, sha256: str) -> tuple[str, Path]:
        directory = self.project / EDITOR_ASSET_DIRECTORY
        directory.mkdir(parents=True, exist_ok=True)
        resolved_directory = directory.resolve()
        if not resolved_directory.is_relative_to(self.project) or directory.is_symlink():
            raise ValueError("Editor-owned asset directory must be a real directory inside the project.")
        suffix = Path(filename).suffix.lower()
        raw_stem = Path(filename).stem.strip()
        stem = re.sub(r"[^\w.-]+", "-", raw_stem, flags=re.UNICODE).strip(".-_") or "image"
        stem = stem[:48]
        base = f"{stem}-{sha256[:12]}"
        for ordinal in range(1, 10_001):
            name = f"{base}{suffix}" if ordinal == 1 else f"{base}-{ordinal}{suffix}"
            target = resolved_directory / name
            try:
                descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                continue
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            except Exception:
                target.unlink(missing_ok=True)
                raise
            relative = target.relative_to(self.project).as_posix()
            return relative, target
        raise ValueError("Could not allocate a unique editor asset filename.")

    def replace_media(self, path: str, filename: str, content_type: str, payload: bytes) -> dict:
        with self.lock:
            self._ensure_editable()
            snapshot = self._memory_snapshot()
            stored: Path | None = None
            try:
                allowed = editable_outline_media(self.data)
                if path not in allowed:
                    raise ValueError("This media binding is not editable in the current component.")
                details = validate_editor_upload(filename, content_type, payload)
                relative, stored = self._store_uploaded_asset(filename, payload, str(details["sha256"]))
                self._push_history()
                set_pointer(self.data, path, relative)
                self.staged_assets.add(relative)
                self.last_edit_path = ""
                self.last_edit_at = 0.0
                try:
                    validate_outline(self.data, TEMPLATES)
                except SystemExit as error:
                    raise ValueError(str(error)) from error
                self._advance_revision()
                self._write_draft()
                return self.state()
            except (ValueError, KeyError, IndexError, OSError):
                self._restore_memory(snapshot)
                if stored is not None:
                    stored.unlink(missing_ok=True)
                raise

    def apply_settings(self, payload: dict) -> dict:
        with self.lock:
            self._ensure_editable()
            snapshot = self._memory_snapshot()
            try:
                candidate, _, updates = apply_design_updates(
                    self.data, payload, allow_multiple_settings=False,
                )
                if candidate == self.data:
                    return self.state()
                self._push_history()
                self.data = candidate
                self.last_edit_path = ""
                self.last_edit_at = 0.0
                try:
                    validate_outline(self.data, TEMPLATES)
                except SystemExit as error:
                    raise ValueError(str(error)) from error
                self._advance_revision()
                self._write_draft()
                return self.state()
            except (ValueError, KeyError, OSError):
                self._restore_memory(snapshot)
                raise

    def undo(self) -> dict:
        with self.lock:
            self._ensure_editable()
            snapshot = self._memory_snapshot()
            try:
                if self.history:
                    self.future.append(copy.deepcopy(self.data))
                    self.data = self.history.pop()
                    self.last_edit_path = ""
                    self.last_edit_at = 0.0
                    self._advance_revision()
                    self._write_draft()
                return self.state()
            except (ValueError, OSError):
                self._restore_memory(snapshot)
                raise

    def redo(self) -> dict:
        with self.lock:
            self._ensure_editable()
            snapshot = self._memory_snapshot()
            try:
                if self.future:
                    self.history.append(copy.deepcopy(self.data))
                    self.data = self.future.pop()
                    self.last_edit_path = ""
                    self.last_edit_at = 0.0
                    self._advance_revision()
                    self._write_draft()
                return self.state()
            except (ValueError, OSError):
                self._restore_memory(snapshot)
                raise

    def discard(self) -> dict:
        with self.lock:
            self._ensure_editable()
            snapshot = self._memory_snapshot()
            paths = (self.draft_path, preview_state_path(self.outline), project_state_path(self.project))
            backups = {path: _backup(path) for path in paths}
            moved: list[tuple[Path, Path]] = []
            try:
                moved = self._quarantine_assets(self.staged_assets)
                self.data = copy.deepcopy(self.base_data)
                self.history.clear()
                self.future.clear()
                self._advance_revision()
                self.applied_operations.clear()
                self.staged_assets.clear()
                self.draft_path.unlink(missing_ok=True)
                self._clear_active_edit()
                self._delete_quarantine(moved)
                return self.state()
            except (OSError, SystemExit, ValueError) as error:
                self._restore_memory(snapshot)
                for path, value in backups.items():
                    _restore(path, value)
                self._restore_quarantine(moved)
                raise ValueError(f"Could not discard the text-edit draft: {error}") from error

    def apply_slide_operation(self, action: str, payload: dict) -> dict:
        with self.lock:
            self._ensure_editable()
            snapshot = self._memory_snapshot()
            try:
                if action not in {"move", "duplicate", "delete"}:
                    raise ValueError(f"Unsupported slide operation: {action}.")
                if not isinstance(payload, dict):
                    raise ValueError("Slide operation payload must be a JSON object.")
                allowed = {"action", "slide_id", "direction", "expected_revision", "operation_id"}
                unknown = sorted(set(payload) - allowed)
                if unknown:
                    raise ValueError(f"Unsupported slide operation field(s): {', '.join(unknown)}.")
                operation_id = payload.get("operation_id")
                slide_id = payload.get("slide_id")
                direction = payload.get("direction")
                if "action" in payload and payload.get("action") != action:
                    raise ValueError("Slide operation action does not match its endpoint.")
                if not isinstance(operation_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", operation_id):
                    raise ValueError("Slide operation_id must be an 8–128 character stable identifier.")
                if not isinstance(slide_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slide_id):
                    raise ValueError("Slide operation requires a valid slide_id.")
                if action == "move" and direction not in {"up", "down"}:
                    raise ValueError("Move direction must be 'up' or 'down'.")
                if action != "move" and direction is not None:
                    raise ValueError(f"{action.capitalize()} does not accept a direction.")
                signature = _digest({"action": action, "slide_id": slide_id, "direction": direction})
                previous = self.applied_operations.get(operation_id)
                if previous is not None:
                    if previous != signature:
                        raise ValueError("The operation_id was already used for a different slide transaction.")
                    return self.state(notices=["This slide transaction was already applied."])
                self._assert_revision(payload.get("expected_revision"))

                slides = self.data.get("slides")
                if not isinstance(slides, list):
                    raise ValueError("The current deck has no editable slides array.")
                matches = [index for index, slide in enumerate(slides) if slide.get("id") == slide_id]
                if len(matches) != 1:
                    raise ValueError(f"Slide id {slide_id!r} is stale or invalid for the current deck.")
                index = matches[0]
                source = slides[index]
                if source.get("template") in {"cover", "end"}:
                    raise ValueError("Cover and end boundary slides cannot be moved, duplicated, or deleted.")

                candidate = copy.deepcopy(self.data)
                candidate_slides = candidate["slides"]
                notices: list[str] = []
                if action == "move":
                    destination = index - 1 if direction == "up" else index + 1
                    if destination < 0 or destination >= len(candidate_slides):
                        raise ValueError("The requested move is outside the deck.")
                    if candidate_slides[destination].get("template") in {"cover", "end"}:
                        raise ValueError("Content slides cannot move across the cover or end boundary.")
                    candidate_slides[index], candidate_slides[destination] = (
                        candidate_slides[destination], candidate_slides[index],
                    )
                elif action == "duplicate":
                    duplicate = copy.deepcopy(source)
                    duplicate["id"] = _unique_duplicate_id(candidate_slides, slide_id)
                    candidate_slides.insert(index + 1, duplicate)
                    notices.append(f"Duplicated slide as {duplicate['id']}.")
                else:
                    candidate_slides.pop(index)

                _validate_structural_invariants(candidate)
                try:
                    validate_outline(candidate, TEMPLATES)
                except SystemExit as error:
                    raise ValueError(str(error)) from error
                self._push_history()
                self.data = candidate
                self.last_edit_path = ""
                self.last_edit_at = 0.0
                self._advance_revision()
                self.applied_operations[operation_id] = signature
                self.applied_operations = dict(
                    list(self.applied_operations.items())[-MAX_APPLIED_OPERATIONS:]
                )
                self._write_draft()
                return self.state(notices=notices)
            except (ValueError, KeyError, IndexError, OSError):
                self._restore_memory(snapshot)
                raise

    def preview_path(self) -> Path:
        state_path = preview_state_path(self.outline)
        if state_path.is_file():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                state = None
            if isinstance(state, dict) and state.get("preview"):
                candidate = Path(str(state["preview"])).expanduser().resolve()
                if candidate.parent == self.project and candidate.is_file():
                    return candidate
        return self.project / "预览.html"

    def finish(self, client_issues: object, *, report_complete: bool = False) -> dict:
        with self.lock:
            self._ensure_editable()
            if not report_complete:
                raise ValueError("Editor completion requires a complete browser layout report.")
            if not isinstance(client_issues, list):
                raise ValueError("Editor completion requires the current browser layout report.")
            known_reasons = {"text-overflow", "text-budget", "title-orphan"}
            if any(not isinstance(item, dict) or item.get("reason") not in known_reasons for item in client_issues):
                raise ValueError("Editor completion received an invalid browser layout report.")
            if any(item.get("reason") == "text-overflow" for item in client_issues):
                raise ValueError("Resolve the reported text overflow before completing the edit.")
            if not outline_confirmation_valid(self.project) or not visual_plan_valid(self.project, self.outline):
                raise ValueError(
                    "outline.md or the visual plan changed while this text draft was open. "
                    "The draft is preserved; copy any needed text, then use 还原 before reconciling the outline."
                )
            if self._is_unchanged():
                if self.staged_assets:
                    self.discard()
                else:
                    self.draft_path.unlink(missing_ok=True)
                    self._clear_active_edit()
                self.editing_complete = True
                self.close()
                return {"ok": True, "preview_url": "/preview", "changed": False}
            self._assert_base_unchanged()
            try:
                validate_outline(self.data, TEMPLATES)
                _validate_structural_invariants(self.data)
                enforce_outline_quality(self.data)
                verify_outline_media(self.data, self.project)
            except SystemExit as error:
                raise ValueError(str(error)) from error

            project_state = project_state_path(self.project)
            preview_state = preview_state_path(self.outline)
            preview_path = self.preview_path()
            media_plan = self.project / "media-plan.json"
            backups = {
                self.outline: _backup(self.outline),
                project_state: _backup(project_state),
                preview_state: _backup(preview_state),
                preview_path: _backup(preview_path),
                media_plan: _backup(media_plan),
            }
            draft_backup = _backup(self.draft_path)
            referenced_media = set(editable_outline_media(self.data).values())
            unreferenced_staged = self.staged_assets - referenced_media
            moved: list[tuple[Path, Path]] = []
            try:
                moved = self._quarantine_assets(unreferenced_staged)
                atomic_write_json(self.outline, self.data)
                state = read_project_state(self.project)
                visual_plan = state.get("visual_plan")
                if not isinstance(visual_plan, dict):
                    raise ValueError("The confirmed visual plan disappeared during text editing.")
                visual_plan["outline_sha256"] = json_digest(self.outline)
                state["visual_plan"] = visual_plan
                confirmation = state.get("media_policy_confirmation")
                if isinstance(confirmation, dict) and confirmation.get("policy") == "text-only" and confirmation.get("user_confirmed") is True:
                    confirmation["outline_sha256"] = json_digest(self.outline)
                state.pop("active_text_edit", None)
                state.setdefault("history", []).append({"event": "text_edit_completed", "outline_sha256": json_digest(self.outline)})
                atomic_write_json(project_state, state)
                self.draft_path.unlink(missing_ok=True)
                generate_preview(self.project, preview_path, False, emit=False)
                self._delete_quarantine(moved)
            except (SystemExit, ValueError, OSError) as error:
                for path, backup in backups.items():
                    _restore(path, backup)
                _restore(self.draft_path, draft_backup)
                self._restore_quarantine(moved)
                raise ValueError(f"Could not complete text editing: {error}") from error
            self.base_data = copy.deepcopy(self.data)
            self.base_digest = json_digest(self.outline)
            self.history.clear()
            self.future.clear()
            self.staged_assets.clear()
            self.editing_complete = True
            self.close()
            return {"ok": True, "preview_url": "/preview", "changed": True}


class EditorHandler(BaseHTTPRequestHandler):
    session: EditorSession
    token: str

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, payload: dict) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _authorized(self) -> bool:
        return secrets.compare_digest(self.headers.get("X-Oil-Ppt-Token", ""), self.token)

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid request length.") from error
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("Request body is too large.")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Request body must be valid UTF-8 JSON.") from error
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object.")
        return value

    def _decoded_upload_header(self, name: str) -> str:
        raw = self.headers.get(name, "")
        if not raw or re.search(r"%(?![0-9a-fA-F]{2})", raw):
            raise ValueError(f"Missing or malformed {name} header.")
        try:
            return unquote(raw, encoding="utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise ValueError(f"{name} must be URL-encoded UTF-8.") from error

    def _read_upload(self) -> tuple[str, str, str, bytes]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("Upload requires Content-Length.")
        try:
            length = int(raw_length)
        except ValueError as error:
            raise ValueError("Invalid upload request length.") from error
        if length <= 0:
            raise ValueError("Upload payload is empty.")
        if length > MAX_EDITOR_UPLOAD_BYTES:
            raise ValueError(f"Upload exceeds the {MAX_EDITOR_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
        payload = self.rfile.read(length)
        if len(payload) != length:
            raise ValueError("Upload payload ended before Content-Length bytes were received.")
        return (
            self._decoded_upload_header("X-Oil-Ppt-Media-Path"),
            self._decoded_upload_header("X-Oil-Ppt-Filename"),
            self.headers.get("Content-Type", ""),
            payload,
        )

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route == "/favicon.ico":
            self._send(HTTPStatus.NO_CONTENT, b"", "image/x-icon")
            return
        if route == "/":
            with self.session.lock:
                body = render(
                    self.session.data,
                    authoring=True,
                    editor_token=self.token,
                    editor_recovery_id=self.session.recovery_id,
                ).encode("utf-8")
            self._send(HTTPStatus.OK, body, "text/html; charset=utf-8")
            return
        if route == "/preview":
            path = self.session.preview_path()
        elif route.startswith("/assets/"):
            relative = Path(unquote(route.lstrip("/")))
            path = (self.session.project / relative).resolve()
            if self.session.project not in path.parents:
                self._send(HTTPStatus.FORBIDDEN, b"Forbidden", "text/plain; charset=utf-8")
                return
        else:
            self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")
            return
        if not path.is_file():
            self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "image/svg+xml"}:
            content_type += "; charset=utf-8"
        self._send(HTTPStatus.OK, path.read_bytes(), content_type)

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            self._json(HTTPStatus.FORBIDDEN, {"ok": False, "errors": ["Invalid editor session token."]})
            return
        route = urlparse(self.path).path
        try:
            if route == "/api/media":
                path, filename, content_type, media_payload = self._read_upload()
                result = self.session.replace_media(path, filename, content_type, media_payload)
                self._json(HTTPStatus.OK, result)
                return
            payload = self._read_json()
            if route == "/api/state":
                result = self.session.state()
            elif route == "/api/edit":
                result = self.session.apply_edit(
                    str(payload.get("path") or ""), payload.get("value"),
                    expected_revision=payload.get("expected_revision"),
                )
            elif route == "/api/settings":
                result = self.session.apply_settings(payload)
            elif route == "/api/undo":
                result = self.session.undo()
            elif route == "/api/redo":
                result = self.session.redo()
            elif route == "/api/discard":
                result = self.session.discard()
            elif route in {"/api/slides/move", "/api/slides/duplicate", "/api/slides/delete"}:
                result = self.session.apply_slide_operation(route.rsplit("/", 1)[-1], payload)
            elif route == "/api/finish":
                result = self.session.finish(
                    payload.get("issues"),
                    report_complete=payload.get("report_complete") is True,
                )
            else:
                self._json(HTTPStatus.NOT_FOUND, {"ok": False, "errors": ["Unknown editor endpoint."]})
                return
        except (ValueError, KeyError, IndexError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "errors": [str(error)]})
            return
        except OSError as error:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "errors": [f"Could not persist editor state: {error}"]})
            return
        self._json(HTTPStatus.OK, result)


def serve(project: Path, *, port: int, open_browser: bool, discard_draft: bool) -> None:
    session = EditorSession(project, discard_draft=discard_draft)
    token = secrets.token_urlsafe(24)
    handler = type("BoundEditorHandler", (EditorHandler,), {"session": session, "token": token})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    address = f"http://127.0.0.1:{server.server_port}/"
    print(json.dumps({
        "ok": True,
        "mode": "text-editor",
        "project": str(session.project),
        "url": address,
        "draft": session.draft_path.is_file(),
    }, ensure_ascii=False, indent=2), flush=True)
    if open_browser and not webbrowser.open(address):
        print(f"Browser did not open automatically. Open: {address}", flush=True)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        session.close()


def main() -> None:
    args = parse_args()
    try:
        serve(args.project, port=args.port, open_browser=not args.no_open, discard_draft=args.discard_draft)
    except ValueError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
