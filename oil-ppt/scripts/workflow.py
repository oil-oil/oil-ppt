"""State-machine decisions without deriving pages from an outline."""
from __future__ import annotations

from pathlib import Path

from media_assets import scan_deck_media
from outline import outline_digest, outline_path, read_outline
from project import read_deck, slide_path
from slide_html import parse_slide
from state import input_manifest, read_state, write_state


AUTHORING_RULE = "按大纲逐页制作真实页面；大纲是页序参考，可随内容调整。每页先确定主画面，正文只保留观众理解它所必需的文字；内容放不下就删重复说明或拆页，不删必要事实、原因和步骤，也不缩小字号。替换 starter 的全部示例内容，完成一页再做下一页。"


def _authoring_brief(project: Path) -> str:
    reference = read_outline(project).strip()
    return f"{reference}\n\n{AUTHORING_RULE}" if reference else AUTHORING_RULE


def _authoring_next(project: Path, command: callable) -> dict:
    return {
        "action": "author_slides",
        "brief": _authoring_brief(project),
        "slide_add_usage": (
            f"{command('slide', 'add', project, '<页面ID>', '--title', '<标题>')} "
            "[--starter <名称>] [--after <页面ID>]"
        ),
        "command_when_ready": command("preview", project),
    }


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
    elif not deck["slides"] and state.get("outline_seed_sha256") == outline_digest(project):
        next_step = {
            "action": "edit_outline",
            "path": str(outline_path(project)),
            "brief": "只写逐页大纲：每页一句话，说明这页讲什么、主要画面是什么。不要写受众分析、叙事建议、制作过程、事实核验清单或给模型看的说明；不必为了凑页数增加总结页。",
            "rerun": command("status", project, "--json"),
        }
        phase = "edit_outline"
    elif not deck["slides"]:
        next_step = _authoring_next(project, command)
        phase = "author_slides"
    elif (slide_issue := _validate_slides(project, deck, command)) is not None:
        next_step, phase = slide_issue
    elif state.get("browser_manifest") == (current_manifest := input_manifest(project)) and isinstance(state.get("browser_issues"), dict):
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
    elif not (project / "预览.html").is_file() or state.get("preview_manifest") != current_manifest:
        # The author, not the program, decides when the open-ended deck is ready.
        next_step = _authoring_next(project, command)
        phase = "author_slides"
    elif state.get("phase") == "complete" and (project / "演示文稿.html").is_file():
        next_step = {"action": "complete", "command": None}
        phase = "complete"
    elif state.get("preview_confirmed"):
        next_step = {"action": "run_command", "command": command("build", project)}
        phase = "ready_to_build"
    else:
        next_step = {"action": "ask_user_to_confirm_preview", "command": None, "artifact": str(project / "预览.html"), "command_on_confirm": command("confirm", project, "preview")}
        phase = "needs_preview_confirmation"
    return {
        "schema_version": "oil-ppt.status/v1",
        "ok": True,
        "project": str(project),
        "phase": phase,
        "slides": len(deck["slides"]),
        "next": next_step,
    }


def _validate_slides(
    project: Path,
    deck: dict,
    command: callable,
) -> tuple[dict, str] | None:
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
