#!/usr/bin/env python3
"""Check that oil-ppt documentation, contracts, schemas, and templates agree."""
from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from pathlib import Path

from background_presets import ALL_BACKGROUNDS, BACKGROUND_PRESETS, template_background
from capability_catalog import PROGRAM_OWNED_CAPABILITIES, TEMPLATE_DISCOVERY, VARIANT_HELP
from component_contracts import COMPONENT_CONTRACTS, COMPONENT_QUALITY, VARIANT_QUALITY
from fill_slots import FILLERS
from icon_registry import ICON_CATALOG, verify_icons
from outline_schema import DECK_FIELDS, SHARED_SLIDE_FIELDS, SLIDE_ALLOWED_FIELDS, TEMPLATE_CONTENT_HELP, TEMPLATE_FAMILIES, TEMPLATE_VISIBLE_FIELDS, VARIANT_INPUT_GUIDANCE
from palette_tokens import PALETTES


ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "assets" / "templates"
SKILL = ROOT / "SKILL.md"


class TemplateTextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ignored = 0
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"style", "script", "title"}:
            self.ignored += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script", "title"} and self.ignored:
            self.ignored -= 1

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value and not self.ignored:
            self.values.append(value)


def validate_skill() -> None:
    errors: list[str] = []
    required_files = (
        "SKILL.md",
        "agents/openai.yaml",
        "scripts/oil-ppt",
        "scripts/oil-ppt.cmd",
        "scripts/oil_ppt.py",
        "scripts/init_deck.py",
        "scripts/add_slide.py",
        "scripts/build_deck.py",
        "scripts/background_presets.py",
        "scripts/capability_catalog.py",
        "scripts/capability_recommender.py",
        "scripts/doctor.py",
        "scripts/cdp_validate.py",
        "scripts/design_quality.py",
        "scripts/fill_slots.py",
        "scripts/media_assets.py",
        "scripts/media_frame.py",
        "scripts/media_plan.py",
        "scripts/render_programmatic_visual.py",
        "scripts/render_outline_review.py",
        "scripts/sync_runtime.py",
        "scripts/icon_registry.py",
        "assets/runtime/deck.css",
        "assets/runtime/deck.js",
        "assets/starter/deck.json",
        "references/evolution.md",
        "references/illustration.md",
        "references/media.md",
        "references/programmatic-visuals.md",
        "references/troubleshooting.md",
    )
    for relative in required_files:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")
    wrapper = ROOT / "scripts" / "oil-ppt"
    if wrapper.is_file() and not os.access(wrapper, os.X_OK):
        errors.append("scripts/oil-ppt must be executable")
    template_names = {path.stem for path in TEMPLATES.glob("*.html")}
    contract_names = set(COMPONENT_CONTRACTS)
    quality_names = set(COMPONENT_QUALITY)
    family_names = set(TEMPLATE_FAMILIES)
    filler_names = set(FILLERS)
    content_names = set(TEMPLATE_CONTENT_HELP)
    discovery_names = set(TEMPLATE_DISCOVERY)
    visible_field_names = set(TEMPLATE_VISIBLE_FIELDS)

    for label, names in (
        ("component contracts", contract_names),
        ("component quality metadata", quality_names),
        ("template families", family_names),
        ("content fillers", filler_names),
        ("content contracts", content_names),
        ("capability discovery metadata", discovery_names),
        ("template visible-field contracts", visible_field_names),
    ):
        missing = sorted(template_names - names)
        extra = sorted(names - template_names)
        if missing:
            errors.append(f"{label} missing templates: {', '.join(missing)}")
        if extra:
            errors.append(f"{label} names without templates: {', '.join(extra)}")
    for template, help_by_variant in VARIANT_HELP.items():
        if template not in COMPONENT_CONTRACTS:
            errors.append(f"variant help references unknown template: {template}")
        elif set(help_by_variant) != set(COMPONENT_CONTRACTS[template]["variants"]):
            errors.append(f"variant help must cover every variant for {template}")
    for template, quality_by_variant in VARIANT_QUALITY.items():
        if template not in COMPONENT_CONTRACTS:
            errors.append(f"variant quality references unknown template: {template}")
        elif set(quality_by_variant) != set(COMPONENT_CONTRACTS[template]["variants"]):
            errors.append(f"variant quality must cover every variant for {template}")
    for template, guidance_by_variant in VARIANT_INPUT_GUIDANCE.items():
        if template not in COMPONENT_CONTRACTS:
            errors.append(f"variant input guidance references unknown template: {template}")
        elif set(guidance_by_variant) != set(COMPONENT_CONTRACTS[template]["variants"]):
            errors.append(f"variant input guidance must cover every variant for {template}")
    for template, fields in TEMPLATE_VISIBLE_FIELDS.items():
        unknown = sorted(set(fields) - set(SLIDE_ALLOWED_FIELDS))
        if unknown:
            errors.append(f"visible field contract for {template} contains unknown fields: {', '.join(unknown)}")

    for path in sorted(TEMPLATES.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        contract = COMPONENT_CONTRACTS.get(path.stem)
        if "placeholder" in text.lower():
            errors.append(f"{path.name}: bundled templates must not contain visible placeholder visuals")
        collector = TemplateTextCollector()
        collector.feed(text)
        structural_text = {"__TITLE__", *(f"{index:02d}" for index in range(1, 9)), "→", "←", "↓"}
        seeded_text = [value for value in collector.values if value not in structural_text]
        if seeded_text:
            errors.append(f"{path.name}: bundled template seeds visible content: {seeded_text[0]}")
        fragment_match = re.search(r"<!--\s*OIL-SLIDE:START\s*-->(.*?)<!--\s*OIL-SLIDE:END\s*-->", text, re.I | re.S)
        fragment = fragment_match.group(1) if fragment_match else ""
        for tag_name in ("h2", "p", "button"):
            for body in re.findall(rf"<{tag_name}\b[^>]*>(.*?)</{tag_name}>", fragment, re.I | re.S):
                if re.sub(r"<[^>]+>", "", body).strip():
                    errors.append(f"{path.name}: bundled templates must not contain example copy in <{tag_name}>")
                    break
        for class_name in ("item", "outcome", "symbol"):
            for body in re.findall(rf'<div\b[^>]*class="[^"]*\b{class_name}\b[^"]*"[^>]*>([^<]*)</div>', fragment, re.I | re.S):
                if body.strip():
                    errors.append(f"{path.name}: bundled templates must not seed example content in .{class_name}")
                    break
        for readable_tag in re.findall(r"<[^>]*\bdata-sentence\b[^>]*>", fragment, re.I):
            if "data-small-ok" in readable_tag:
                continue
            minimum = re.search(r'data-min-size=["\'](\d+)["\']', readable_tag, re.I)
            if minimum and int(minimum.group(1)) < 20:
                errors.append(f"{path.name}: sentence text may not declare a minimum below 20px")
        for forbidden in ('class="ghost"', 'class="bar"', "__INDEX__"):
            if forbidden in text:
                errors.append(f"{path.name}: template-owned decorative or fake-data element is forbidden: {forbidden}")
        surface_tags = re.findall(r'<[^>]+class="[^"]*\boil-surface\b[^"]*"[^>]*>', text, re.I)
        for tag in surface_tags:
            tone = re.search(r'data-tone=["\']([^"\']+)["\']', tag, re.I)
            if not tone or tone.group(1) not in {"neutral", "soft", "accent", "alt", "warm", "ink"}:
                errors.append(f"{path.name}: every oil-surface container must choose a registered surface tone")
        if contract:
            if not isinstance(contract.get("use_when"), str) or not contract["use_when"].strip():
                errors.append(f"{path.name}: contract requires use_when")
            if any(value != "none" for value in contract["decorations"]):
                if 'data-decor="__DECOR__"' not in text:
                    errors.append(f"{path.name}: declares decorations but has no rendered data-decor slot")
            quality = COMPONENT_QUALITY.get(path.stem) or {}
            if quality.get("silhouette") not in {"bleed", "browser", "canvas", "card-grid", "diagram", "editorial-list", "focal", "matrix", "metric", "rail", "split", "state-panel", "step-grid", "step-cards", "timeline", "two-panel", "editorial-feature", "catalog", "case-board", "annotated", "bento", "gallery"}:
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
        if 'data-c="turn"] .oil-icon' not in text or "rotate(90deg)" not in text:
            errors.append("process-rail.html: turn connector must rotate the system arrow downward")
        if 'data-c="56"] .oil-icon' not in text or "rotate(180deg)" not in text:
            errors.append("process-rail.html: return-row connectors must rotate the system arrow left")
    text_sources = [SKILL, *sorted((ROOT / "scripts").glob("*.py"))]
    for source in text_sources:
        source_text = source.read_text(encoding="utf-8")
        for relative in sorted(set(re.findall(r"references/([A-Za-z0-9._-]+)", source_text))):
            if not (ROOT / "references" / relative).is_file():
                errors.append(f"{source.relative_to(ROOT)} references missing file: references/{relative}")

    docs = [SKILL, *sorted((ROOT / "references").glob("*.md"))]
    repo_root = ROOT.parent
    repo_readme = repo_root / "README.md"
    in_source_repository = (repo_root / ".git").exists()
    public_files = [*docs, ROOT / "agents" / "openai.yaml"]
    if repo_readme.is_file():
        public_files.append(repo_readme)
    commands = r"(?:init|status|plan|check|doctor|audit|recommend|contract|preview|confirm|scaffold|build|list|add|remove|sync|media|icon)"
    bare_cli = re.compile(rf"(?<![/\w-])oil-ppt\s+{commands}\b")
    hardcoded_install = re.compile(r"(?:\$HOME|~|/Users/[^/]+)/(?:\.codex|\.agents|\.claude|\.workbuddy)/.*?/oil-ppt")
    old_public_name = re.compile(r"\boil-slides\b|\$oil-slides")
    for source in docs:
        source_text = source.read_text(encoding="utf-8")
        if bare_cli.search(source_text):
            errors.append(f"{source.relative_to(ROOT)} contains a bare oil-ppt command; use scripts/oil-ppt relative to SKILL.md")
        if hardcoded_install.search(source_text):
            errors.append(f"{source.relative_to(ROOT)} hardcodes an installation root; use paths relative to SKILL.md")
    for source in public_files:
        if source.is_file() and old_public_name.search(source.read_text(encoding="utf-8")):
            label = source.relative_to(ROOT) if ROOT in source.parents else source.name
            errors.append(f"{label} still exposes the retired oil-slides public name")
    skill_text = SKILL.read_text(encoding="utf-8")
    for reference in sorted((ROOT / "references").glob("*.md")):
        relative = f"references/{reference.name}"
        if relative not in skill_text:
            errors.append(f"{relative} is orphaned; SKILL.md must route to every shipped reference")
    agent_file = ROOT / "agents" / "openai.yaml"
    if agent_file.is_file():
        agent_text = agent_file.read_text(encoding="utf-8")
        for required in ('display_name: "oil-ppt"', "next.action", "action=run_command"):
            if required not in agent_text:
                errors.append(f"agents/openai.yaml must include {required!r}")
    if in_source_repository and not repo_readme.is_file():
        errors.append("repository README.md is missing")
    if ROOT.name != "oil-ppt":
        errors.append("skill directory must be named oil-ppt")
    if (ROOT / "scripts" / "oil-slides").exists() or (ROOT / "scripts" / "oil-slides.cmd").exists():
        errors.append("retired public oil-slides CLI wrappers must not remain")
    if "scripts/oil-ppt" not in SKILL.read_text(encoding="utf-8"):
        errors.append("SKILL.md must declare scripts/oil-ppt relative to its own directory")
    highlight = SHARED_SLIDE_FIELDS.get("highlight")
    if not isinstance(highlight, dict) or highlight.get("required") is not False or "title" not in str(highlight.get("rule")):
        errors.append("contract must expose optional highlight as an exact phrase inside title")
    background = SHARED_SLIDE_FIELDS.get("background")
    if not isinstance(background, dict) or set(background.get("allowed") or ()) != set(BACKGROUND_PRESETS):
        errors.append("contract must expose every runtime background preset")
    backdrop_text = SHARED_SLIDE_FIELDS.get("backdrop_text")
    if not isinstance(backdrop_text, dict) or backdrop_text.get("required") is not False:
        errors.append("contract must expose optional backdrop_text")
    media_frame = SHARED_SLIDE_FIELDS.get("media_frame")
    if not isinstance(media_frame, dict) or set(media_frame.get("allowed") or ()) != {"content", "self-framed"}:
        errors.append("contract must expose media_frame with content and self-framed choices")
    if set((DECK_FIELDS.get("media_policy") or {}).get("allowed") or ()) != {"required", "text-only"}:
        errors.append("contract must expose both media policies")
    companion_keys = {"accent_alt", "accent_alt_soft", "accent_warm", "accent_warm_soft"}
    for name, palette in PALETTES.items():
        if not companion_keys.issubset(palette):
            errors.append(f"named palette {name} must explicitly curate all companion colors")

    runtime_css = (ROOT / "assets/runtime/deck.css").read_text(encoding="utf-8")
    compact_runtime = re.sub(r"\s+", "", runtime_css)
    for obsolete in ("oil-bleed-art", "oil-browser-mock", "oil-photo-placeholder"):
        if obsolete in runtime_css:
            errors.append(f"runtime must not retain template stand-in visual: {obsolete}")
    icon_license = (ROOT / "assets/icons/LICENSE").read_text(encoding="utf-8")
    if "Permission is hereby granted" not in icon_license or "Phosphor Icons" not in icon_license:
        errors.append("bundled icon license must include the full Phosphor MIT notice")
    try:
        verified_icons = verify_icons()
    except ValueError as error:
        errors.append(str(error))
    else:
        if len(verified_icons) != len(ICON_CATALOG):
            errors.append("icon verification count does not match the icon catalog")
    for token in ("--slide-safe-x", "--slide-safe-y", "--slide-grid-gap", ".oil-grid"):
        if token not in runtime_css:
            errors.append(f"runtime grid system missing {token}")
    if ".hl" not in runtime_css or "--accent-mark" not in runtime_css or "--highlight-opacity: 58%" not in runtime_css:
        errors.append("runtime must retain the program-rendered marker highlight")
    if ".oil-backdrop-text" not in runtime_css:
        errors.append("runtime must render content-owned oversized background type")
    if '.oil-surface[data-tone]::before' not in runtime_css:
        errors.append("runtime must own automatic surface texture geometry")
    declared_tones = tuple(PROGRAM_OWNED_CAPABILITIES["surface"]["tones"])
    for tone in declared_tones:
        if f'.oil-surface[data-tone="{tone}"]::before' not in runtime_css:
            errors.append(f"runtime surface tone {tone} must include an automatic texture treatment")
    for motif in PROGRAM_OWNED_CAPABILITIES["surface"]["automatic_motifs"]:
        if f'.oil-surface[data-motif="{motif}"]::after' not in runtime_css:
            errors.append(f"runtime surface motif {motif} is declared but missing")
    if ".oil-icon-frame" not in runtime_css or "--icon-frame: 70px" not in runtime_css or "--icon-size: 38px" not in runtime_css:
        errors.append("runtime must provide the enlarged, reduced-padding icon frame contract")
    if ".oil-chart-bars" not in runtime_css:
        errors.append("runtime must provide deterministic native chart bars")
    for background_name in BACKGROUND_PRESETS:
        if f'data-bg="{background_name}"' not in runtime_css:
            errors.append(f"runtime background preset missing selector for {background_name}")
    if 'data-bg="media-owned"' not in runtime_css:
        errors.append("runtime internal media-owned background state is missing")
    for removed_visual in ("contour", 'data-decor="orbit"', 'data-decor="halo"'):
        if removed_visual in runtime_css:
            errors.append(f"runtime retains removed circular decoration: {removed_visual}")
    if "repeat(12,minmax(0,1fr))" not in compact_runtime:
        errors.append("runtime grid system must use twelve minmax(0,1fr) tracks")
    for path in sorted(TEMPLATES.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        if len(re.findall(r'data-bg=["\'][^"\']+["\']', text)) != 1:
            errors.append(f"{path.name}: template must expose exactly one data-bg")
        elif template_background(path.stem) not in ALL_BACKGROUNDS:
            errors.append(f"{path.name}: template background is not registered")
        if re.search(r"\.slide-safe[^\{]*\{[^\}]*height\s*:\s*100%", text, re.S):
            errors.append(f"{path.name}: slide-safe must not override inset with height:100%")

    if errors:
        raise SystemExit("oil-ppt consistency check failed:\n- " + "\n- ".join(errors))
    print(f"oil-ppt consistency is valid ({len(template_names)} templates).")


if __name__ == "__main__":
    validate_skill()
