#!/usr/bin/env python3
"""oil-ppt 1.0: author each presentation page as standalone HTML."""
from __future__ import annotations

import argparse
import html
import json
import re
import shlex
from pathlib import Path

from build_deck import build_project, chrome_binary
from catalog import COMPOSITION_FAMILIES, STARTER_GUIDANCE, render_starter_catalog, render_theme_catalog
from preview_deck import render_preview
from project import ROOT, discover_projects, init_project, read_deck, require_project, save_deck, slide_path, slide_relative, valid_slide_id
from slide_html import parse_slide, new_slide_document, style_advice
from state import input_manifest
from theme import DIRECTIONS, catalog as theme_catalog, validate_theme
from workflow import AUTHORING_RULE, batch as workflow_batch
from workflow import confirm_outline, confirm_preview, status as workflow_status
from workflow_contract import validate_batch_payload, validate_status_payload

SCRIPTS = Path(__file__).resolve().parent
STARTER_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def cli_command(*parts: object) -> str:
    return shlex.join([str((SCRIPTS / "oil-ppt").resolve()), *(str(part) for part in parts)])


def emit(value: object, compact: bool = False) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=None if compact else 2, separators=(",", ":") if compact else None))


def export_pptx_project(project_value: Path, output_value: Path | None = None, report_value: Path | None = None) -> dict:
    """Rebuild canonical HTML from current inputs, then export its rendered DOM."""
    project, deck = read_deck(project_value)
    from pptx_export import export_hybrid_pptx
    from state import read_state
    state = read_state(project)
    if not state.get("preview_confirmed") or state.get("preview_manifest") != input_manifest(project):
        raise SystemExit("PPTX export requires a current confirmed preview.")
    chrome = chrome_binary()
    if not chrome:
        raise SystemExit("PPTX export requires Chrome/Chromium.")
    output = (output_value or project / "演示文稿.pptx").resolve()
    report = (report_value or project / "pptx-editability.json").resolve()
    # A prior final HTML may belong to an older manifest, so export never trusts it.
    build_project(project)
    return export_hybrid_pptx(
        project=project,
        deck=deck,
        html_path=project / "演示文稿.html",
        chrome=chrome,
        output=output,
        report_output=report,
    )


def _deck_slide(project: Path, deck: dict, slide_id: str) -> tuple[int, str, Path]:
    relative = slide_relative(slide_id)
    try:
        index = deck["slides"].index(relative)
    except ValueError as error:
        raise SystemExit(f"Unknown slide id: {slide_id}") from error
    return index, relative, slide_path(project, relative)


def _copy_starter(slide_id: str, title: str, starter: str | None) -> str:
    if not starter:
        return new_slide_document(slide_id, title)
    if not STARTER_NAME.fullmatch(starter):
        raise SystemExit("Starter name must use lowercase letters, numbers, and hyphens.")
    source = ROOT / "assets" / "starters" / f"{starter}.html"
    if not source.is_file():
        raise SystemExit(f"Starter not found: {starter}")
    text = source.read_text(encoding="utf-8")
    return text.replace("__ID__", slide_id).replace("__TITLE__", html.escape(title, quote=True))


def slide_add(project_value: Path, slide_id: str, title: str | None, starter: str | None, after: str | None) -> dict:
    project, deck = read_deck(project_value)
    valid_slide_id(slide_id)
    relative = slide_relative(slide_id)
    if relative in deck["slides"] or (project / relative).exists():
        raise SystemExit(f"Slide already exists: {slide_id}")
    after_index: int | None = None
    if after:
        after_index, _, _ = _deck_slide(project, deck, after)
    rendered_title = title or slide_id.replace("-", " ").title()
    path = project / relative
    path.write_text(_copy_starter(slide_id, rendered_title, starter), encoding="utf-8")
    # Reject a copied starter that does not satisfy the standalone contract.
    try:
        parse_slide(path, slide_id)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    if after_index is not None:
        deck["slides"].insert(after_index + 1, relative)
    else:
        deck["slides"].append(relative)
    try:
        save_deck(project, deck)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return {
        "ok": True,
        "project": str(project),
        "slide": relative,
        "next": {
            "action": "edit_slide",
            "command": None,
            "path": str(path),
            "brief": AUTHORING_RULE,
            "rerun": cli_command("status", project, "--json"),
        },
    }


def slide_list(project_value: Path) -> dict:
    project, deck = read_deck(project_value)
    slide_rows = []
    parsed_slides = []
    seen: set[str] = set()
    for index, relative in enumerate(deck["slides"], 1):
        path = slide_path(project, relative)
        item = parse_slide(path, Path(relative).stem)
        parsed_slides.append(item)
        if item.slide_id in seen:
            raise SystemExit(f"Duplicate slide ID: {item.slide_id}")
        seen.add(item.slide_id)
        slide_rows.append({"index": index, "id": item.slide_id, "title": item.title, "file": relative})
    return {
        "ok": True,
        "project": str(project),
        "slides": slide_rows,
        "style_advice": style_advice(project, deck, slides=parsed_slides),
    }


def slide_check(project_value: Path) -> dict:
    listing = slide_list(project_value)
    listing["checked"] = len(listing["slides"])
    return listing


def slide_remove(project_value: Path, slide_id: str) -> dict:
    project, deck = read_deck(project_value)
    index, relative, path = _deck_slide(project, deck, slide_id)
    source = path.read_bytes()
    deck["slides"].pop(index)
    path.unlink(missing_ok=True)
    try:
        save_deck(project, deck)
    except BaseException:
        path.write_bytes(source)
        raise
    return {"ok": True, "removed": relative}


def slide_move(project_value: Path, slide_id: str, position: int) -> dict:
    project, deck = read_deck(project_value)
    index, relative, _ = _deck_slide(project, deck, slide_id)
    deck["slides"].pop(index)
    target = max(0, min(position - 1, len(deck["slides"])))
    deck["slides"].insert(target, relative)
    save_deck(project, deck)
    return {"ok": True, "slide": relative, "index": target + 1}


def slide_duplicate(project_value: Path, source_id: str, new_id: str, title: str | None) -> dict:
    project, deck = read_deck(project_value)
    valid_slide_id(new_id)
    source_index, _, source = _deck_slide(project, deck, source_id)
    relative = slide_relative(new_id)
    destination = project / relative
    if relative in deck["slides"] or destination.exists():
        raise SystemExit(f"Slide already exists: {new_id}")
    text = source.read_text(encoding="utf-8")
    text = re.sub(
        r"(data-slide-id=['\"])" + re.escape(source_id) + r"(['\"])",
        lambda match: match.group(1) + new_id + match.group(2),
        text,
    )
    text = re.sub(
        rf"\.s-{re.escape(source_id)}(?![a-z0-9-])",
        f".s-{new_id}",
        text,
    )
    text = re.sub(
        rf"(?<=\s)s-{re.escape(source_id)}(?=[\s'\"])",
        f"s-{new_id}",
        text,
    )
    if title:
        safe_title = html.escape(title, quote=True)
        text = re.sub(r"(data-title=['\"])[^'\"]*(['\"])", lambda m: m.group(1) + safe_title + m.group(2), text, count=1)
        text = re.sub(r"(<title>).*?(</title>)", lambda m: m.group(1) + safe_title + m.group(2), text, count=1, flags=re.S)
    destination.write_text(text, encoding="utf-8")
    try:
        parse_slide(destination, new_id)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    deck["slides"].insert(source_index + 1, relative)
    try:
        save_deck(project, deck)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return {"ok": True, "slide": relative}


def starter_list() -> dict:
    location = ROOT / "assets" / "starters"
    names = sorted(path.stem for path in location.glob("*.html")) if location.is_dir() else []
    return {
        "ok": True,
        "starters": names,
        "guidance": {name: STARTER_GUIDANCE[name] for name in names},
        "composition_families": {family: [name for name in starters if name in names] for family, starters in COMPOSITION_FAMILIES.items()},
        "instruction": "starter 只是构图起点；先按聚焦、比较、顺序、汇聚、关系、证据或数据选择构图，再替换全部示例文案、数值、来源和占位视觉。正常 8–10 页至少混用四类构图。四个及以上等宽单元保持总览密度，不重复嵌套第二层信息。",
    }


def starter_show(name: str) -> dict:
    if not STARTER_NAME.fullmatch(name):
        raise SystemExit("Starter name must use lowercase letters, numbers, and hyphens.")
    source = ROOT / "assets" / "starters" / f"{name}.html"
    if not source.is_file():
        raise SystemExit(f"Starter not found: {name}")
    return {
        "ok": True,
        "name": name,
        "path": str(source),
        "instruction": "复制后替换全部示例文案、数值、来源和占位视觉；不要只改标题。四个及以上等宽单元只保留编号或时间、标题和一句短解释，第二层信息使用共享区、单点展开或拆页。",
        "html": source.read_text(encoding="utf-8"),
    }


def status_payload(project_arg: Path, *, intent: str = "continue", slide: str | None = None) -> dict:
    return validate_status_payload(workflow_status(project_arg, cli_command, intent=intent, slide=slide))


def cmd_check(project: Path) -> dict:
    result = slide_check(project)
    result["next"] = status_payload(project)["next"]
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--version", action="version", version="oil-ppt 1.0.0")
    sub = root.add_subparsers(dest="command", required=True)
    version = sub.add_parser("version", help="report package version and integrity")
    version.add_argument("--compact", action="store_true"); version.add_argument("--json", action="store_true")
    init = sub.add_parser("init", help="create an HTML-first oil-ppt project")
    init.add_argument("project", type=Path); init.add_argument("--title"); init.add_argument("--compact", action="store_true")
    status = sub.add_parser("status", help="report the closed workflow next action")
    status.add_argument("project", type=Path); status.add_argument("--compact", action="store_true"); status.add_argument("--json", action="store_true"); status.add_argument("--intent", default="continue", choices=["continue", "edit"]); status.add_argument("--slide")
    batch = sub.add_parser("batch", help="report status across projects")
    batch.add_argument("projects", type=Path, nargs="+"); batch.add_argument("--compact", action="store_true")
    preview = sub.add_parser("preview", help="render a preview from current slide HTML")
    preview.add_argument("project", type=Path); preview.add_argument("--compact", action="store_true")
    confirm = sub.add_parser("confirm", help="record user confirmation of the preview")
    confirm.add_argument("project", type=Path); confirm.add_argument("stage", choices=["outline", "preview"]); confirm.add_argument("--compact", action="store_true")
    build = sub.add_parser("build", help="create 演示文稿.html without mutating slide sources")
    build.add_argument("project", type=Path); build.add_argument("--browser", action="store_true"); build.add_argument("--compact", action="store_true")
    export = sub.add_parser("export-pptx", help="export the confirmed canonical HTML as a hybrid PPTX")
    export.add_argument("project", type=Path); export.add_argument("--output", type=Path); export.add_argument("--report", type=Path); export.add_argument("--compact", action="store_true")
    theme = sub.add_parser("theme", help="inspect or update deck-level tokens without rewriting slides")
    theme_sub = theme.add_subparsers(dest="theme_command", required=True)
    theme_list = theme_sub.add_parser("list"); theme_list.add_argument("--compact", action="store_true"); theme_list.add_argument("--json", action="store_true")
    theme_catalog_parser = theme_sub.add_parser("catalog", help="render an offline visual theme catalog"); theme_catalog_parser.add_argument("--output", type=Path); theme_catalog_parser.add_argument("--compact", action="store_true")
    theme_set = theme_sub.add_parser("set"); theme_set.add_argument("project", type=Path); theme_set.add_argument("--direction"); theme_set.add_argument("--palette"); theme_set.add_argument("--typography"); theme_set.add_argument("--shape"); theme_set.add_argument("--compact", action="store_true")
    check = sub.add_parser("check", help="validate actual standalone slide HTML")
    check.add_argument("project", type=Path); check.add_argument("--compact", action="store_true")
    slide = sub.add_parser("slide", help="manage standalone slide HTML files")
    slide_sub = slide.add_subparsers(dest="slide_command", required=True)
    add = slide_sub.add_parser("add"); add.add_argument("project", type=Path); add.add_argument("id"); add.add_argument("--title"); add.add_argument("--starter"); add.add_argument("--after"); add.add_argument("--compact", action="store_true")
    listing = slide_sub.add_parser("list"); listing.add_argument("project", type=Path); listing.add_argument("--compact", action="store_true"); listing.add_argument("--json", action="store_true")
    slide_check_parser = slide_sub.add_parser("check"); slide_check_parser.add_argument("project", type=Path); slide_check_parser.add_argument("--compact", action="store_true")
    remove = slide_sub.add_parser("remove"); remove.add_argument("project", type=Path); remove.add_argument("id"); remove.add_argument("--compact", action="store_true")
    move = slide_sub.add_parser("move"); move.add_argument("project", type=Path); move.add_argument("id"); move.add_argument("--to", type=int, required=True); move.add_argument("--compact", action="store_true")
    duplicate = slide_sub.add_parser("duplicate"); duplicate.add_argument("project", type=Path); duplicate.add_argument("id"); duplicate.add_argument("new_id"); duplicate.add_argument("--title"); duplicate.add_argument("--compact", action="store_true")
    starter = sub.add_parser("starter", help="discover copy-once HTML starters")
    starter_sub = starter.add_subparsers(dest="starter_command", required=True)
    starter_list_parser = starter_sub.add_parser("list"); starter_list_parser.add_argument("--compact", action="store_true"); starter_list_parser.add_argument("--json", action="store_true")
    starter_catalog_parser = starter_sub.add_parser("catalog", help="render an offline visual starter and component catalog"); starter_catalog_parser.add_argument("--output", type=Path); starter_catalog_parser.add_argument("--compact", action="store_true")
    show = starter_sub.add_parser("show"); show.add_argument("name"); show.add_argument("--compact", action="store_true")
    doctor = sub.add_parser("doctor", help="run package integrity and HTML workflow checks")
    doctor.add_argument("--compact", action="store_true"); doctor.add_argument("--json", action="store_true")
    return root


def main() -> None:
    args = parser().parse_args()
    compact = bool(getattr(args, "compact", False))
    if args.command == "version":
        from package_manifest import package_status
        emit(package_status(), compact); return
    if args.command == "init":
        project = init_project(args.project, args.title); emit({"ok": True, "project": str(project), "next": status_payload(project)["next"]}, compact); return
    if args.command == "status": emit(status_payload(args.project, intent=args.intent, slide=args.slide), compact); return
    if args.command == "batch": emit(validate_batch_payload(workflow_batch(discover_projects(args.projects), cli_command)), compact); return
    if args.command == "preview":
        output = render_preview(args.project); emit({"ok": True, "artifact": str(output), "next": status_payload(args.project)["next"]}, compact); return
    if args.command == "confirm":
        project = require_project(args.project)
        if args.stage == "outline":
            confirm_outline(project); emit({"ok": True, "project": str(project), "next": status_payload(project)["next"]}, compact)
        else:
            confirm_preview(project); emit({"ok": True, "project": str(project), "next": {"action": "run_command", "command": cli_command("build", project)}}, compact)
        return
    if args.command == "build":
        output = build_project(args.project, browser=args.browser); emit({"ok": True, "artifact": str(output), "next": {"action": "complete", "command": None}}, compact); return
    if args.command == "export-pptx":
        emit(export_pptx_project(args.project, args.output, args.report), compact); return
    if args.command == "theme":
        if args.theme_command == "list":
            emit({"ok": True, "themes": theme_catalog()}, compact); return
        if args.theme_command == "catalog":
            output = render_theme_catalog(args.output)
            emit({"ok": True, "artifact": str(output), "palettes": 5, "typography": 3, "shapes": 3}, compact); return
        project, deck = read_deck(args.project)
        updates = {key: value for key, value in {"direction": args.direction, "palette": args.palette, "typography": args.typography, "shape": args.shape}.items() if value is not None}
        choices = theme_catalog()
        allowed = {"palette": choices["palettes"], "typography": choices["typography"], "shape": choices["shapes"], "direction": choices["directions"]}
        for key, value in updates.items():
            if value not in allowed[key]:
                raise SystemExit(f"Unsupported {key}: {value}. Allowed: {', '.join(allowed[key])}")
        if not updates:
            raise SystemExit("theme set requires --direction, --palette, --typography, or --shape.")
        current = deck.setdefault("theme", {})
        if not isinstance(current, dict):
            raise SystemExit("Invalid deck.json: theme must be an object.")
        if args.direction:
            current.update(DIRECTIONS[args.direction]["recommended"])
        current.update(updates)
        deck["theme"] = validate_theme(current)
        save_deck(project, deck)
        emit({"ok": True, "project": str(project), "theme": deck["theme"], "next": status_payload(project)["next"]}, compact); return
    if args.command == "check": emit(cmd_check(args.project), compact); return
    if args.command == "starter":
        if args.starter_command == "catalog":
            output = render_starter_catalog(args.output)
            emit({"ok": True, "artifact": str(output), "starters": len(starter_list()["starters"])}, compact); return
        emit(starter_list() if args.starter_command == "list" else starter_show(args.name), compact); return
    if args.command == "doctor":
        from doctor import run_doctor
        report = run_doctor(); emit(report, compact)
        if not report.get("ok"):
            raise SystemExit(1)
        return
    if args.command == "slide":
        if args.slide_command == "add": result = slide_add(args.project, args.id, args.title, args.starter, args.after)
        elif args.slide_command == "list": result = slide_list(args.project)
        elif args.slide_command == "check": result = slide_check(args.project)
        elif args.slide_command == "remove": result = slide_remove(args.project, args.id)
        elif args.slide_command == "move": result = slide_move(args.project, args.id, args.to)
        else: result = slide_duplicate(args.project, args.id, args.new_id, args.title)
        emit(result, compact); return
    raise AssertionError(args.command)


if __name__ == "__main__":
    main()
