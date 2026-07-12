#!/usr/bin/env python3
"""Check that oil-slides documentation, contracts, schemas, and templates agree."""
from __future__ import annotations

import re
from pathlib import Path

from component_contracts import COMPONENT_CONTRACTS, COMPONENT_QUALITY
from fill_slots import FILLERS
from outline_schema import TEMPLATE_CONTENT_HELP, TEMPLATE_FAMILIES


ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "assets" / "templates"
SKILL = ROOT / "SKILL.md"


def validate_skill() -> None:
    errors: list[str] = []
    required_files = (
        "SKILL.md",
        "scripts/oil-slides",
        "scripts/oil_slides.py",
        "scripts/init_deck.py",
        "scripts/add_slide.py",
        "scripts/build_deck.py",
        "scripts/doctor.py",
        "scripts/cdp_validate.py",
        "scripts/design_quality.py",
        "scripts/fill_slots.py",
        "scripts/render_outline_review.py",
        "scripts/sync_runtime.py",
        "scripts/icon_registry.py",
        "scripts/template_tiers.py",
        "assets/runtime/deck.css",
        "assets/runtime/deck.js",
        "assets/starter/deck.json",
    )
    for relative in required_files:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")
    template_names = {path.stem for path in TEMPLATES.glob("*.html")}
    contract_names = set(COMPONENT_CONTRACTS)
    quality_names = set(COMPONENT_QUALITY)
    family_names = set(TEMPLATE_FAMILIES)
    filler_names = set(FILLERS)
    content_names = set(TEMPLATE_CONTENT_HELP)

    for label, names in (
        ("component contracts", contract_names),
        ("component quality metadata", quality_names),
        ("template families", family_names),
        ("content fillers", filler_names),
        ("content contracts", content_names),
    ):
        missing = sorted(template_names - names)
        extra = sorted(names - template_names)
        if missing:
            errors.append(f"{label} missing templates: {', '.join(missing)}")
        if extra:
            errors.append(f"{label} names without templates: {', '.join(extra)}")

    for path in sorted(TEMPLATES.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        contract = COMPONENT_CONTRACTS.get(path.stem)
        if contract:
            if not isinstance(contract.get("use_when"), str) or not contract["use_when"].strip():
                errors.append(f"{path.name}: contract requires use_when")
            if any(value != "none" for value in contract["decorations"]):
                if 'data-decor="__DECOR__"' not in text:
                    errors.append(f"{path.name}: declares decorations but has no rendered data-decor slot")
            quality = COMPONENT_QUALITY.get(path.stem) or {}
            if quality.get("silhouette") not in {"bleed", "browser", "canvas", "card-grid", "diagram", "editorial-list", "focal", "metric", "rail", "split", "step-grid", "timeline", "two-panel"}:
                errors.append(f"{path.name}: invalid or missing silhouette metadata")
            if quality.get("surface_density") not in {"none", "light", "heavy"}:
                errors.append(f"{path.name}: invalid or missing surface_density metadata")
            if quality.get("frame_owner") not in {"none", "media", "template"}:
                errors.append(f"{path.name}: invalid or missing frame_owner metadata")

    process_rail = TEMPLATES / "process-rail.html"
    if process_rail.is_file():
        text = process_rail.read_text(encoding="utf-8")
        if "oil-surface" in text:
            errors.append("process-rail.html: relationship canvas must not use oil-surface")
        if COMPONENT_CONTRACTS["process-rail"]["decorations"] != ("none",):
            errors.append("process-rail: relationship canvas decorations must be none")
        if 'class="connector"' not in text:
            errors.append("process-rail.html: requires explicit connector elements")
    text_sources = [SKILL, *sorted((ROOT / "scripts").glob("*.py"))]
    for source in text_sources:
        source_text = source.read_text(encoding="utf-8")
        for relative in sorted(set(re.findall(r"references/([A-Za-z0-9._-]+)", source_text))):
            if not (ROOT / "references" / relative).is_file():
                errors.append(f"{source.relative_to(ROOT)} references missing file: references/{relative}")

    docs = [SKILL, *sorted((ROOT / "references").glob("*.md"))]
    commands = r"(?:doctor|audit|contract|preview|confirm|scaffold|build|list|add|remove|sync)"
    bare_cli = re.compile(rf"(?<![/\w-])oil-slides\s+{commands}\b")
    hardcoded_install = re.compile(r"(?:\$HOME|~|/Users/[^/]+)/(?:\.codex|\.agents)/.*?/oil-slides")
    for source in docs:
        source_text = source.read_text(encoding="utf-8")
        if bare_cli.search(source_text):
            errors.append(f"{source.relative_to(ROOT)} contains a bare oil-slides command; use scripts/oil-slides relative to SKILL.md")
        if hardcoded_install.search(source_text):
            errors.append(f"{source.relative_to(ROOT)} hardcodes an installation root; use paths relative to SKILL.md")
    if "scripts/oil-slides" not in SKILL.read_text(encoding="utf-8"):
        errors.append("SKILL.md must declare scripts/oil-slides relative to its own directory")

    runtime_css = (ROOT / "assets/runtime/deck.css").read_text(encoding="utf-8")
    compact_runtime = re.sub(r"\s+", "", runtime_css)
    for token in ("--slide-safe-x", "--slide-safe-y", "--slide-grid-gap", ".oil-grid"):
        if token not in runtime_css:
            errors.append(f"runtime grid system missing {token}")
    if "repeat(12,minmax(0,1fr))" not in compact_runtime:
        errors.append("runtime grid system must use twelve minmax(0,1fr) tracks")
    for path in sorted(TEMPLATES.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        if re.search(r"\.slide-safe[^\{]*\{[^\}]*height\s*:\s*100%", text, re.S):
            errors.append(f"{path.name}: slide-safe must not override inset with height:100%")

    if errors:
        raise SystemExit("oil-slides consistency check failed:\n- " + "\n- ".join(errors))
    print(f"oil-slides consistency is valid ({len(template_names)} templates).")


if __name__ == "__main__":
    validate_skill()
