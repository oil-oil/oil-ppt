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
from editor_bindings import editable_values, pointer_parts, set_pointer
from media_assets import verify_outline_media
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
from render_outline_review import render


DRAFT_NAME = ".oil-ppt-edit-draft.json"
DRAFT_SCHEMA = "oil-ppt.text-edit-draft/v1"
MAX_REQUEST_BYTES = 1_000_000


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
        self.last_edit_path = ""
        self.last_edit_at = 0.0
        self.startup_notices: list[str] = []
        if not self.project.is_dir() or not self.outline.is_file():
            raise ValueError(f"Text editing requires an existing oil-ppt project with outline.json: {self.project}")
        self._acquire_project_lock()
        try:
            if discard_draft:
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

    def _memory_snapshot(self) -> tuple[dict, list[dict], list[dict], str, float]:
        return (
            copy.deepcopy(self.data), copy.deepcopy(self.history), copy.deepcopy(self.future),
            self.last_edit_path, self.last_edit_at,
        )

    def _restore_memory(self, snapshot: tuple[dict, list[dict], list[dict], str, float]) -> None:
        self.data, self.history, self.future, self.last_edit_path, self.last_edit_at = snapshot

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
        except SystemExit as error:
            raise ValueError(
                f"Text edit draft no longer matches the current component contract: {error}. "
                "Reopen with --discard-draft only after deciding to delete that draft."
            ) from error
        self.data = envelope["data"]

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
            if self._is_unchanged():
                self.draft_path.unlink(missing_ok=True)
                self._clear_active_edit()
                return
            atomic_write_json(self.draft_path, {
                "schema_version": DRAFT_SCHEMA,
                "base_outline_sha256": self.base_digest,
                "updated_at": int(time.time()),
                "data": self.data,
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
        return {
            "ok": True,
            "values": current,
            "changed_paths": sorted(path for path, value in current.items() if base.get(path) != value),
            "can_undo": bool(self.history),
            "can_redo": bool(self.future),
            "draft": self.draft_path.is_file(),
            "notices": [*self.startup_notices, *(notices or [])],
        }

    def apply_edit(self, path: str, value: object) -> dict:
        with self.lock:
            self._ensure_editable()
            snapshot = self._memory_snapshot()
            try:
                allowed = editable_values(self.data)
                if path not in allowed:
                    raise ValueError("This text field is not editable in the current component.")
                text = _normalize_text(value)
                if allowed[path] == text:
                    return self.state()
                now = time.monotonic()
                coalesce = path == self.last_edit_path and now - self.last_edit_at < 1.2 and bool(self.history)
                if not coalesce:
                    self.history.append(copy.deepcopy(self.data))
                    if len(self.history) > 100:
                        self.history.pop(0)
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
                self._write_draft()
                return self.state(notices=notices)
            except (ValueError, KeyError, IndexError, OSError):
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
            try:
                self.data = copy.deepcopy(self.base_data)
                self.history.clear()
                self.future.clear()
                self.draft_path.unlink(missing_ok=True)
                self._clear_active_edit()
                return self.state()
            except (OSError, SystemExit) as error:
                self._restore_memory(snapshot)
                for path, value in backups.items():
                    _restore(path, value)
                raise ValueError(f"Could not discard the text-edit draft: {error}") from error

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
                self.draft_path.unlink(missing_ok=True)
                self._clear_active_edit()
                self.editing_complete = True
                self.close()
                return {"ok": True, "preview_url": "/preview", "changed": False}
            self._assert_base_unchanged()
            try:
                validate_outline(self.data, TEMPLATES)
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
            try:
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
            except (SystemExit, ValueError, OSError) as error:
                for path, backup in backups.items():
                    _restore(path, backup)
                _restore(self.draft_path, draft_backup)
                raise ValueError(f"Could not complete text editing: {error}") from error
            self.base_data = copy.deepcopy(self.data)
            self.base_digest = json_digest(self.outline)
            self.history.clear()
            self.future.clear()
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
            payload = self._read_json()
            if route == "/api/state":
                result = self.session.state()
            elif route == "/api/edit":
                result = self.session.apply_edit(str(payload.get("path") or ""), payload.get("value"))
            elif route == "/api/undo":
                result = self.session.undo()
            elif route == "/api/redo":
                result = self.session.redo()
            elif route == "/api/discard":
                result = self.session.discard()
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
