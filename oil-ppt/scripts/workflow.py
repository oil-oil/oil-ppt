"""State-machine decisions without deriving pages from an outline."""
from __future__ import annotations

from pathlib import Path

from media_assets import scan_deck_media
from outline import outline_digest, outline_path, read_outline
from project import read_deck, slide_path
from slide_html import parse_slide, style_advice
from state import input_manifest, read_state, write_state


AUTHORING_RULE = "每次只完成一张真实页面：先确定聚焦、比较、顺序、汇聚、关系、证据或数据中的主要视觉关系，再选择 starter；如果使用 starter，必须替换其全部示例文案、数值、来源和占位视觉，并让 DOM/CSS 服务当前页的真实判断。四个及以上等宽重复单元只保留编号或时间、标题和一句短解释，不在每个单元里重复嵌套护栏、指标、引用或第二段说明；第二层信息改成一个共享区、只展开一个重点，或拆页。不得只改标题或带着示例内容继续下一页。"


def _authoring_brief(project: Path) -> str:
    reference = read_outline(project).strip()
    return f"{reference}\n\n{AUTHORING_RULE}" if reference else AUTHORING_RULE


def status(project_value: Path, command: callable, *, intent: str = "continue", slide: str | None = None) -> dict:
    project, deck = read_deck(project_value)
    state = read_state(project)
    if intent == "edit":
        if slide:
            try:
                index = int(slide) - 1
                relative = deck["slides"][index] if index >= 0 else None
            except (ValueError, IndexError):
                relative = next((item for item in deck["slides"] if Path(item).stem == slide), None)
            if not relative:
                raise SystemExit(f"Unknown slide: {slide}")
            next_step = {"action": "edit_slide", "command": None, "path": str(slide_path(project, relative)), "issues": [], "rerun": command("status", project, "--json")}
            phase = "editing_slide"
        else:
            next_step = {"action": "edit_outline", "command": None, "path": str(outline_path(project)), "rerun": command("status", project, "--json")}
            phase = "editing_outline"
    elif not state.get("outline_confirmed"):
        if state.get("outline_seed_sha256") == outline_digest(project):
            next_step = {
                "action": "edit_outline",
                "path": str(outline_path(project)),
                "brief": "Write a concise creative reference: audience, setting, core claim, evidence, and a possible narrative. Do not prescribe a slide list.",
                "rerun": command("status", project, "--json"),
            }
            phase = "edit_outline"
        else:
            next_step = {"action": "ask_user_to_confirm_outline", "command": None, "artifact": str(outline_path(project)), "command_on_confirm": command("confirm", project, "outline")}
            phase = "needs_outline_confirmation"
    elif not deck["slides"]:
        next_step = {"action": "author_slides", "brief": _authoring_brief(project), "command_when_ready": command("preview", project)}
        phase = "author_slides"
    elif issue := _first_slide_issue(project, deck, command):
        next_step, phase = issue
    elif state.get("browser_manifest") == input_manifest(project) and isinstance(state.get("browser_issues"), dict):
        report = state["browser_issues"]
        findings = [
            *report.get("missingSafeArea", []),
            *report.get("invalidLayouts", []),
            *report.get("invalidBleeds", []),
            *report.get("invalidText", []),
            *report.get("visualFindings", []),
        ]
        first = next((item for item in findings if isinstance(item, dict)), {"reason": "browser-validation"})
        slide_id = str(first.get("slide") or Path(deck["slides"][0]).stem)
        relative = next((item for item in deck["slides"] if Path(item).stem == slide_id), deck["slides"][0])
        next_step = {
            "action": "edit_slide",
            "path": str(slide_path(project, relative)),
            "issues": findings or [report],
            "rerun": command("preview", project),
        }
        phase = "repair_browser"
    elif not (project / "预览.html").is_file() or state.get("preview_manifest") != input_manifest(project):
        # The author, not the program, decides when the open-ended deck is ready.
        next_step = {"action": "author_slides", "brief": _authoring_brief(project), "command_when_ready": command("preview", project)}
        phase = "author_slides"
    elif state.get("phase") == "complete" and (project / "演示文稿.html").is_file():
        next_step = {"action": "complete", "command": None}
        phase = "complete"
    else:
        next_step = {"action": "ask_user_to_confirm_preview", "command": None, "artifact": str(project / "预览.html"), "command_on_confirm": command("confirm", project, "preview")}
        phase = "needs_preview_confirmation"
    return {
        "schema_version": "oil-ppt.status/v1",
        "ok": True,
        "project": str(project),
        "phase": phase,
        "slides": len(deck["slides"]),
        "style_advice": style_advice(project, deck),
        "next": next_step,
    }


def _first_slide_issue(project: Path, deck: dict, command: callable) -> tuple[dict, str] | None:
    for relative in deck["slides"]:
        path = slide_path(project, relative)
        try:
            parse_slide(path, Path(relative).stem)
        except SystemExit as error:
            message = str(error)
            action = "fix_media" if any(
                phrase in message
                for phrase in ("asset", "URL", "path escapes slide assets")
            ) else "edit_slide"
            return ({
                "action": action,
                "path": str(path),
                "issues": [message],
                "rerun": command("status", project, "--json"),
            }, "repair_media" if action == "fix_media" else "repair_slide")
    media = scan_deck_media(project, deck)
    errors = media.get("errors") or []
    if errors:
        first_file = str(errors[0].get("file") or deck["slides"][0])
        page_errors = [item for item in errors if item.get("file") == first_file]
        return ({
            "action": "fix_media",
            "path": str((project / first_file).resolve()),
            "issues": page_errors,
            "rerun": command("status", project, "--json"),
        }, "repair_media")
    return None


def confirm_outline(project: Path) -> None:
    write_state(project, outline_confirmed=True)


def confirm_preview(project: Path) -> None:
    state = read_state(project)
    if state.get("preview_manifest") != input_manifest(project):
        raise SystemExit("Preview confirmation is stale: deck, slides, assets, or runtime changed. Run preview again.")
    write_state(project, phase="ready_to_build", preview_confirmed=True)


def batch(projects: list[Path], command: callable) -> dict:
    payloads = [status(project, command) for project in projects]
    active = [item["next"] for item in payloads if item["next"]["action"] != "complete"]
    non_preview = [item for item in active if item["action"] != "ask_user_to_confirm_preview"]
    previews = [item for item in active if item["action"] == "ask_user_to_confirm_preview"]
    if non_preview:
        next_step = non_preview[0]
    elif previews:
        # One confirmation is one explicit user decision. Returning the first
        # project's real action keeps the batch contract executable; rerunning
        # batch advances to the next unconfirmed preview.
        next_step = previews[0]
    else:
        next_step = {"action": "complete", "command": None}
    return {"schema_version": "oil-ppt.batch/v1", "ok": True, "projects": payloads, "next": next_step}
