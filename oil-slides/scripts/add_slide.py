#!/usr/bin/env python3
"""Add a validated oil-slides page from a bundled layout template."""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

from background_presets import BACKGROUND_PRESETS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--template", required=True)
    parser.add_argument("--id", dest="slide_id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--highlight", help="one exact title phrase to render with the marker highlight")
    parser.add_argument("--background", choices=tuple(BACKGROUND_PRESETS), help="page background preset; defaults to the template value")
    parser.add_argument("--variant", required=True, help="template-owned composition variant")
    parser.add_argument("--decor", required=True, help="template-owned decoration preset")
    parser.add_argument("--after", help="insert after this data-slide-id; default append")
    return parser.parse_args()


def slide_id_from_file(path: Path) -> str | None:
    match = re.search(r'data-slide-id=["\']([a-z0-9][a-z0-9-]*)["\']', path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def main() -> None:
    args = parse_args()
    skill_root = Path(__file__).resolve().parent.parent
    templates = skill_root / "assets" / "templates"
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.slide_id):
        raise SystemExit("--id must use lowercase letters, digits, and hyphens.")
    template = templates / f"{args.template}.html"
    if not template.is_file():
        raise SystemExit(f"Unknown template: {args.template}. Use --list.")

    project = args.project_dir.expanduser().resolve()
    config_path = project / "deck.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    slide_files = config.get("slides", [])
    existing_ids = {slide_id_from_file(project / item) for item in slide_files}
    if args.slide_id in existing_ids:
        raise SystemExit(f"Duplicate slide id: {args.slide_id}")

    used_numbers = []
    for item in slide_files:
        match = re.match(r"slides/(\d+)-", item)
        if match:
            used_numbers.append(int(match.group(1)))
    number = max(used_numbers, default=0) + 1
    filename = f"slides/{number:03d}-{args.slide_id}.html"
    output = project / filename
    title = html.escape(args.title, quote=True)
    text = template.read_text(encoding="utf-8")
    text = (text.replace("__ID__", args.slide_id)
            .replace("__TITLE__", title)
            .replace("__INDEX__", f"{number:02d}")
            .replace("__VARIANT__", html.escape(args.variant, quote=True))
            .replace("__DECOR__", html.escape(args.decor, quote=True)))
    section = re.compile(r"<section\b(?P<attrs>[^>]*)>", re.I)
    match = section.search(text)
    if not match:
        raise SystemExit(f"Template {args.template} has no section element.")
    attrs = match.group("attrs")
    additions = []
    if not re.search(r"\bdata-variant\s*=", attrs, re.I):
        additions.append(f' data-variant="{html.escape(args.variant, quote=True)}"')
    if not re.search(r"\bdata-component-decor\s*=", attrs, re.I):
        additions.append(f' data-component-decor="{html.escape(args.decor, quote=True)}"')
    if additions:
        text = text[:match.end() - 1] + "".join(additions) + text[match.end() - 1:]
    if args.background:
        text, count = re.subn(
            r'(data-bg=["\'])[^"\']+(["\'])',
            rf'\g<1>{html.escape(args.background, quote=True)}\g<2>',
            text,
            count=1,
        )
        if count != 1:
            raise SystemExit(f"Template {args.template} does not expose data-bg.")
    if args.highlight:
        highlight = html.escape(args.highlight, quote=True)
        if highlight not in title:
            raise SystemExit("--highlight must be an exact phrase inside --title.")
        marked = title.replace(highlight, f'<span class="hl">{highlight}</span>', 1)
        needle = f">{title}</h1>"
        if needle not in text:
            raise SystemExit(f"Template {args.template} does not expose a standard h1 title slot.")
        text = text.replace(needle, f">{marked}</h1>", 1)
    output.write_text(text, encoding="utf-8")

    if args.after:
        positions = [i for i, item in enumerate(slide_files) if slide_id_from_file(project / item) == args.after]
        if not positions:
            output.unlink(missing_ok=True)
            raise SystemExit(f"--after id not found: {args.after}")
        slide_files.insert(positions[0] + 1, filename)
    else:
        slide_files.append(filename)
    config["slides"] = slide_files
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Added {filename} from template={args.template} variant={args.variant} decor={args.decor}"
        + (f" highlight={args.highlight}" if args.highlight else "")
        + (f" background={args.background}" if args.background else "")
    )


if __name__ == "__main__":
    main()
