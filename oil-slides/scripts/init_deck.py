#!/usr/bin/env python3
"""Create an editable one-HTML-per-slide oil-slides project."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from palette_tokens import ALIASES, PALETTES, custom_palette, named_palette
from profile_tokens import SHAPE_PROFILES, TYPE_PROFILES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--palette", choices=sorted(set(PALETTES) | set(ALIASES)))
    parser.add_argument("--accent", help="custom accent, e.g. #FFD54A")
    parser.add_argument("--accent-soft", help="custom soft accent")
    parser.add_argument("--accent-strong", help="custom strong accent")
    parser.add_argument("--no-next-preview", action="store_true")
    parser.add_argument("--click-navigation", action="store_true", help="allow left/right mouse click navigation; off by default")
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--no-counter", action="store_true")
    parser.add_argument("--type-profile", choices=tuple(TYPE_PROFILES), required=True)
    parser.add_argument("--shape-profile", choices=tuple(SHAPE_PROFILES), required=True)
    parser.add_argument("--allow-existing-assets", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target = args.project_dir.expanduser().resolve()
    if target.exists() and any(target.iterdir()):
        existing = list(target.iterdir())
        allowed_existing = all(
            (item.name == "assets" and item.is_dir())
            or (item.name == "outline.md" and item.is_file())
            for item in existing
        )
        if not args.allow_existing_assets or not allowed_existing:
            raise SystemExit(f"Refusing to overwrite non-empty directory: {target}")

    skill_root = Path(__file__).resolve().parent.parent
    starter = skill_root / "assets" / "starter"
    runtime = skill_root / "assets" / "runtime"
    target.mkdir(parents=True, exist_ok=True)
    (target / "slides").mkdir(exist_ok=True)
    shutil.copytree(runtime, target / "runtime", dirs_exist_ok=True)
    (target / "assets").mkdir(exist_ok=True)
    icons_src = skill_root / "assets" / "icons"
    if icons_src.is_dir():
        shutil.copytree(icons_src, target / "assets" / "icons", dirs_exist_ok=True)
    config = json.loads((starter / "deck.json").read_text(encoding="utf-8"))
    config["title"] = args.title
    config["next_preview"] = not args.no_next_preview
    config["click_navigation"] = bool(args.click_navigation)
    config["show_progress"] = not args.no_progress
    config["show_counter"] = not args.no_counter
    config["typography"] = {"profile": args.type_profile}
    config["shape"] = {"profile": args.shape_profile}
    if args.accent or args.accent_soft or args.accent_strong:
        if not (args.accent and args.accent_soft and args.accent_strong):
            raise SystemExit("Custom colors require --accent, --accent-soft and --accent-strong together.")
        palette = custom_palette(args.accent, args.accent_soft, args.accent_strong)
    else:
        if not args.palette:
            raise SystemExit("Choose --palette or provide all three custom accent colors.")
        palette = named_palette(args.palette)
    config["palette"] = palette
    (target / "deck.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Created oil-slides project: {target}")
    print(f"Edit one page at a time in: {target / 'slides'}")


if __name__ == "__main__":
    main()
