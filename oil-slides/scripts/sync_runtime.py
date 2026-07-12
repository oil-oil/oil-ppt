#!/usr/bin/env python3
"""Sync the deterministic oil-slides runtime into an existing deck project."""
from __future__ import annotations

import argparse
import filecmp
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--check", action="store_true", help="report whether runtime is current without writing")
    args = parser.parse_args()

    project = args.project_dir.expanduser().resolve()
    if not (project / "deck.json").is_file():
        raise SystemExit(f"Not an oil-slides project (deck.json missing): {project}")

    skill_root = Path(__file__).resolve().parent.parent
    source = skill_root / "assets" / "runtime"
    target = project / "runtime"
    names = ("deck.css", "deck.js")
    current = target.is_dir() and all(
        (target / name).is_file() and filecmp.cmp(source / name, target / name, shallow=False)
        for name in names
    )
    icons_src = skill_root / "assets" / "icons"
    icons_dst = project / "assets" / "icons"
    source_icons = sorted(path.name for path in icons_src.iterdir() if path.is_file())
    target_icons = sorted(path.name for path in icons_dst.iterdir() if path.is_file()) if icons_dst.is_dir() else []
    current = current and source_icons == target_icons and all(
        filecmp.cmp(icons_src / name, icons_dst / name, shallow=False) for name in source_icons
    )
    if args.check:
        if current:
            print("Runtime is current.")
            return
        raise SystemExit("Runtime is outdated. Run sync_runtime.py without --check.")

    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy2(source / name, target / name)
    if icons_src.is_dir():
        if icons_dst.exists():
            shutil.rmtree(icons_dst)
        shutil.copytree(icons_src, icons_dst)
    print(f"Synced oil-slides runtime: {target}")


if __name__ == "__main__":
    main()
