#!/usr/bin/env python3
"""Single deterministic entry point for oil-slides project operations."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from component_contracts import COMPONENT_CONTRACTS, quality_for
from design_quality import audit_summary, enforce_outline_quality
from outline_schema import TEMPLATE_CONTENT_HELP, TEMPLATE_FAMILIES, validate_outline
from palette_tokens import PALETTES, canonical_name
from profile_tokens import SHAPE_PROFILES, TYPE_PROFILES
from template_tiers import TIER1_TEMPLATES, tier_of


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
TEMPLATES = ROOT / "assets" / "templates"
DEFAULT_FINAL_NAME = "演示文稿.html"
SLIDE_ID = re.compile(r'data-slide-id=["\']([a-z0-9][a-z0-9-]*)["\']')
SLIDE_TITLE = re.compile(r'data-title=["\']([^"\']+)["\']')


def run_script(name: str, arguments: list[str]) -> None:
    proc = subprocess.run([sys.executable, str(SCRIPTS / name), *arguments], check=False)
    if proc.returncode:
        raise SystemExit(proc.returncode)


def read_config(project: Path) -> tuple[Path, dict]:
    project = project.expanduser().resolve()
    path = project / "deck.json"
    if not path.is_file():
        raise SystemExit(f"Not an oil-slides project: {project}")
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


def print_contract(show_all: bool = False) -> None:
    templates = {}
    for name, contract in sorted(COMPONENT_CONTRACTS.items()):
        entry = {
            "use_when": contract["use_when"],
            "family": TEMPLATE_FAMILIES[name],
            **quality_for(name),
            "tier": tier_of(name),
            "variants": list(contract["variants"]),
            "decorations": list(contract["decorations"]),
            "content": TEMPLATE_CONTENT_HELP[name],
        }
        if show_all or name in TIER1_TEMPLATES:
            templates[name] = entry
    payload = {
        "track": "unified",
        "track_note": (
            "默认只列出 tier-1（简化菜单）。"
            "每页必须显式选择 template、variant 和 decor。"
            "特殊页用 contract --all 查看 tier-2。"
        ),
        "tier1": list(TIER1_TEMPLATES),
        "design": {
            "palettes": sorted(PALETTES),
            "typography": sorted(TYPE_PROFILES),
            "shape": sorted(SHAPE_PROFILES),
        },
        "templates": templates,
        "showing": "all" if show_all else "tier1",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


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


def write_outline(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def final_output_path(project_arg: Path) -> Path:
    return project_arg.expanduser().resolve() / DEFAULT_FINAL_NAME


def outline_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def generate_preview(outline_path: Path, output: Path | None, no_open: bool) -> None:
    outline = outline_path.expanduser().resolve()
    if not outline.is_file():
        raise SystemExit(f"Outline not found: {outline}")
    data = json.loads(outline.read_text(encoding="utf-8"))
    validate_outline(data, TEMPLATES)
    enforce_outline_quality(data)
    target = (output or outline.parent / "预览.html").expanduser().resolve()
    command = [str(outline), "--out", str(target)]
    if no_open:
        command.append("--no-open")
    run_script("render_outline_review.py", command)
    preview_state_path(outline).write_text(
        json.dumps(
            {
                "outline": str(outline),
                "outline_sha256": outline_digest(outline),
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
    print(f"Preview ready; wait for user confirmation before scaffold: {target}")


def confirm_preview(outline_path: Path, user_confirmed: bool) -> None:
    if not user_confirmed:
        raise SystemExit("Confirmation requires --user-confirmed after the user explicitly approves the preview.")
    outline = outline_path.expanduser().resolve()
    state_path = preview_state_path(outline)
    if not outline.is_file() or not state_path.is_file():
        raise SystemExit("Preview confirmation requires an existing outline and generated 预览.html.")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("outline_sha256") != outline_digest(outline):
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
    print(f"Preview confirmed for outline: {outline}")


def require_preview_confirmation(outline_path: Path) -> dict:
    outline = outline_path.expanduser().resolve()
    state_path = preview_state_path(outline)
    if not state_path.is_file():
        raise SystemExit("Scaffold blocked: generate 预览.html and wait for user confirmation first.")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("outline_sha256") != outline_digest(outline):
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
        run_script("add_slide.py", command)
    outline_path = resolved / "outline.json"
    outline_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_script("fill_slots.py", [str(resolved), "--outline", str(outline_path)])


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
        allowed_paths = {outline_path, state_path, markdown_outline, project / "assets", project / ".DS_Store"}
        if preview_path.parent == project:
            allowed_paths.add(preview_path)
        allowed = [item for item in existing if item.resolve() in allowed_paths]
        unexpected = [item for item in existing if item.resolve() not in allowed_paths]
        if unexpected:
            raise SystemExit(f"Refusing to overwrite non-empty directory: {project}")
        for item in allowed:
            if item.is_file() and item.resolve() != markdown_outline.resolve():
                item.unlink()
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
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("outline", type=Path)
    contract_parser = sub.add_parser("contract")
    contract_parser.add_argument(
        "--all",
        action="store_true",
        help="include tier-2 templates; default shows tier-1 only",
    )
    preview_parser = sub.add_parser("preview")
    preview_parser.add_argument("outline", type=Path)
    preview_parser.add_argument("--out", type=Path)
    preview_parser.add_argument("--no-open", action="store_true")
    confirm_parser = sub.add_parser("confirm")
    confirm_parser.add_argument("outline", type=Path)
    confirm_parser.add_argument("--user-confirmed", action="store_true")
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
    build_parser = sub.add_parser("build")
    build_parser.add_argument("project", type=Path)
    sync_parser = sub.add_parser("sync")
    sync_parser.add_argument("project", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "doctor":
        run_script("doctor.py", [])
    elif args.command == "audit":
        print_audit(args.outline)
    elif args.command == "contract":
        print_contract(show_all=bool(getattr(args, "all", False)))
    elif args.command == "preview":
        generate_preview(args.outline, args.out, args.no_open)
    elif args.command == "confirm":
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
        project, _ = read_config(args.project)
        _, data = read_outline(project)
        materialize_slides(project, data, data["slides"])
        output = final_output_path(project)
        run_script("build_deck.py", [str(project)])
        if not output.is_file():
            raise SystemExit(f"Build completed without the expected final file: {output}")
        print(f"Final presentation: {output}")
    elif args.command == "sync":
        run_script("sync_runtime.py", [str(args.project)])


if __name__ == "__main__":
    main()
