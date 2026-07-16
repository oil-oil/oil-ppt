#!/usr/bin/env python3
"""Check that oil-ppt documentation, contracts, schemas, and templates agree."""
from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from pathlib import Path

from background_presets import ALL_BACKGROUNDS, BACKGROUND_PRESETS, BACKGROUND_UI_LABELS, template_background
from capability_catalog import DECOR_UI_LABELS, PROGRAM_OWNED_CAPABILITIES, TEMPLATE_DISCOVERY, VARIANT_HELP, VARIANT_UI_LABELS
from cdp_validate import VISUAL_FINDING_CATEGORIES
from component_contracts import COMPONENT_CONTRACTS, COMPONENT_QUALITY, PAGE_BLEND_TEMPLATES, VARIANT_QUALITY, effective_media_fit, effective_media_surface
from fill_slots import FILLERS, MEDIA_FIT_DEFAULTS
from fill_templates import format_number
from icon_registry import ICON_CATALOG, verify_icons
from outline_schema import DATA_STORY_QUESTIONS, DECK_FIELDS, SHARED_SLIDE_FIELDS, SLIDE_ALLOWED_FIELDS, TEMPLATE_CONTENT_HELP, TEMPLATE_FAMILIES, TEMPLATE_VISIBLE_FIELDS, VARIANT_INPUT_GUIDANCE
from palette_tokens import PALETTES
from media_plan import MEDIA_SLOTS, MEDIA_VARIANT_SLOTS


ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "assets" / "templates"
SKILL = ROOT / "SKILL.md"
TEMPLATE_CLIP_ROLES = {"media", "browser", "shape"}
ADAPTIVE_COPY_TEMPLATES = {
    "bleed-split", "browser-showcase", "cover", "diagonal-split", "editorial-feature", "end",
    "metric", "photo-gradient", "photo-split", "recap", "section", "split-visual",
}


def gradient_design_issues(text: str) -> list[str]:
    """Return token-level gradient issues without depending on business copy or pixel snapshots."""
    def channel_spread(channels: list[float]) -> float:
        return max(channels) - min(channels)

    def hex_channels(color: str) -> list[float]:
        digits = color.removeprefix("#")
        if len(digits) in {3, 4}:
            return [float(int(digit * 2, 16)) for digit in digits[:3]]
        return [float(int(digits[index:index + 2], 16)) for index in (0, 2, 4)]

    def rgb_channels(value: str) -> list[float]:
        channels: list[float] = []
        for token in re.findall(r"\d+(?:\.\d+)?%?", value)[:3]:
            channels.append(float(token[:-1]) * 2.55 if token.endswith("%") else float(token))
        return channels

    issues: list[str] = []
    declarations = re.findall(
        r"(?:background(?:-image)?|(?:-webkit-)?mask-image)\s*:\s*([^;}]*gradient[^;}]*)(?:;|})",
        text,
        re.I,
    )
    for value in declarations:
        layer_count = len(re.findall(r"(?:repeating-)?(?:linear|radial|conic)-gradient\s*\(", value, re.I))
        if layer_count > 2:
            issues.append(f"uses {layer_count} stacked gradient layers")
        chromatic_hex = [
            color for color in re.findall(r"#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})\b", value, re.I)
            if channel_spread(hex_channels(color)) > 20
        ]
        if chromatic_hex:
            issues.append(f"hardcodes chromatic gradient color {chromatic_hex[0]}")
        for rgb in re.findall(r"rgba?\(([^)]*)\)", value, re.I):
            channels = rgb_channels(rgb)
            if len(channels) == 3 and channel_spread(channels) > 20:
                issues.append("hardcodes a chromatic rgb gradient color instead of a design token")
                break
        for hsl in re.findall(r"hsla?\(([^)]*)\)", value, re.I):
            channels = re.findall(r"-?\d+(?:\.\d+)?%?", hsl)
            saturation = float(channels[1].removesuffix("%")) if len(channels) >= 2 else 0
            if saturation > 12:
                issues.append("hardcodes a chromatic hsl gradient color instead of a design token")
                break
    return issues


def clipped_circle_selectors(text: str) -> list[str]:
    """Find circular CSS decorations that destroy their geometry with clip-path."""
    normalized = text.replace("{{", "{").replace("}}", "}")
    selectors: list[str] = []
    for selector, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", normalized, re.S):
        if (
            re.search(r"border-radius\s*:\s*50%(?:\s|;|$)", declarations, re.I)
            and re.search(r"clip-path\s*:\s*(?!none\b)", declarations, re.I)
        ):
            selectors.append(" ".join(selector.split()))
    return selectors


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
        "scripts/editor_bindings.py",
        "scripts/fill_slots.py",
        "scripts/fill_templates.py",
        "scripts/media_assets.py",
        "scripts/media_frame.py",
        "scripts/media_plan.py",
        "scripts/render_programmatic_visual.py",
        "scripts/render_component_catalog.py",
        "scripts/render_outline_review.py",
        "scripts/sync_runtime.py",
        "scripts/text_editor.py",
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
    registered_variants = {variant for contract in COMPONENT_CONTRACTS.values() for variant in contract["variants"]}
    registered_decorations = {decor for contract in COMPONENT_CONTRACTS.values() for decor in contract["decorations"]}
    if set(VARIANT_UI_LABELS) != registered_variants:
        missing = sorted(registered_variants - set(VARIANT_UI_LABELS))
        extra = sorted(set(VARIANT_UI_LABELS) - registered_variants)
        errors.append(f"variant UI labels mismatch; missing={missing}, extra={extra}")
    if set(DECOR_UI_LABELS) != registered_decorations:
        missing = sorted(registered_decorations - set(DECOR_UI_LABELS))
        extra = sorted(set(DECOR_UI_LABELS) - registered_decorations)
        errors.append(f"decoration UI labels mismatch; missing={missing}, extra={extra}")
    if set(BACKGROUND_UI_LABELS) != set(ALL_BACKGROUNDS):
        missing = sorted(set(ALL_BACKGROUNDS) - set(BACKGROUND_UI_LABELS))
        extra = sorted(set(BACKGROUND_UI_LABELS) - set(ALL_BACKGROUNDS))
        errors.append(f"background UI labels mismatch; missing={missing}, extra={extra}")
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

    runtime_css = ROOT / "assets" / "runtime" / "deck.css"
    runtime_text = runtime_css.read_text(encoding="utf-8")
    for problem in gradient_design_issues(runtime_text):
        errors.append(f"{runtime_css.name}: {problem}")
    for selector in clipped_circle_selectors(runtime_text):
        errors.append(f"{runtime_css.name}: circular decoration may not use clip-path: {selector}")

    catalog_renderer = ROOT / "scripts" / "render_component_catalog.py"
    catalog_source = catalog_renderer.read_text(encoding="utf-8")
    for selector in clipped_circle_selectors(catalog_source):
        errors.append(f"{catalog_renderer.name}: circular decoration may not use clip-path: {selector}")
    if 'class="primitive ring"><span class="shape-window"' not in catalog_source:
        errors.append(f"{catalog_renderer.name}: ring primitive requires a dedicated shape window")
    if ".primitive.ring>.shape-window::after" not in catalog_source:
        errors.append(f"{catalog_renderer.name}: ring primitive geometry must belong to its shape window")

    for path in sorted(TEMPLATES.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        contract = COMPONENT_CONTRACTS.get(path.stem)
        for match in re.finditer(r"([^{}]+)\{[^{}]*overflow\s*:\s*(?:hidden|clip)\b", text, re.I):
            selector = " ".join(match.group(1).split())
            roles = re.findall(r'data-clip=["\']([^"\']+)["\']', selector, re.I)
            if len(roles) != 1 or roles[0] not in TEMPLATE_CLIP_ROLES:
                errors.append(f"{path.name}: clipping requires one explicit data-clip role (media, browser, or shape): {selector}")
        for problem in gradient_design_issues(text):
            errors.append(f"{path.name}: {problem}")
        for selector in clipped_circle_selectors(text):
            errors.append(f"{path.name}: circular decoration may not use clip-path: {selector}")
        for selector, _ in re.findall(r"([^{}]+)\{([^{}]*)\}", text, re.S):
            if 'data-motif="ring"' in selector and "::after" in selector and "oil-shape-window" not in selector:
                errors.append(f"{path.name}: ring geometry may only render inside oil-shape-window")
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
        copy_flow_count = len(re.findall(r"<[^>]+\bdata-copy-flow\b[^>]*>", fragment, re.I))
        copy_title_count = len(re.findall(r"<[^>]+\bdata-copy-title\b[^>]*>", fragment, re.I))
        copy_body_count = len(re.findall(r"<[^>]+\bdata-copy-body\b[^>]*>", fragment, re.I))
        ring_motif_count = len(re.findall(r'<[^>]+\bdata-motif=["\']ring["\'][^>]*>', fragment, re.I))
        ring_window_count = sum(
            1 for tag in re.findall(r"<[^>]+>", fragment, re.I)
            if re.search(r'\bclass=["\'][^"\']*\boil-shape-window\b[^"\']*["\']', tag, re.I)
            and re.search(r'\bdata-clip=["\']shape["\']', tag, re.I)
        )
        if ring_motif_count != ring_window_count:
            errors.append(f"{path.name}: every ring motif requires one explicit oil-shape-window with data-clip='shape'")
        if path.stem in ADAPTIVE_COPY_TEMPLATES and copy_flow_count != 1:
            errors.append(f"{path.name}: focal title/body composition must use the adaptive copy flow")
        if copy_flow_count and (copy_title_count != copy_flow_count or copy_body_count != copy_flow_count):
            errors.append(f"{path.name}: every adaptive copy flow requires exactly one title and one body marker")
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
            if not tone or tone.group(1) not in {"neutral", "soft", "accent", "ink"}:
                errors.append(f"{path.name}: every oil-surface container must choose a registered surface tone")
        if contract:
            if not isinstance(contract.get("use_when"), str) or not contract["use_when"].strip():
                errors.append(f"{path.name}: contract requires use_when")
            if any(value != "none" for value in contract["decorations"]):
                if "none" in contract["decorations"]:
                    errors.append(f"{path.name}: decorated components must not expose a weaker none variant")
                if 'data-decor="__DECOR__"' not in text:
                    errors.append(f"{path.name}: declares decorations but has no rendered data-decor slot")
            quality = COMPONENT_QUALITY.get(path.stem) or {}
            if quality.get("silhouette") not in {"bleed", "browser", "canvas", "card-grid", "cycle", "data-story", "diagram", "editorial-list", "focal", "matrix", "metric", "quadrant", "rail", "split", "state-panel", "step-grid", "step-cards", "tier-stack", "timeline", "two-panel", "editorial-feature", "catalog", "case-board", "annotated", "bento", "gallery"}:
                errors.append(f"{path.name}: invalid or missing silhouette metadata")
            if quality.get("surface_density") not in {"none", "light", "heavy"}:
                errors.append(f"{path.name}: invalid or missing surface_density metadata")
            if quality.get("frame_owner") not in {"none", "media", "template"}:
                errors.append(f"{path.name}: invalid or missing frame_owner metadata")
            tones = [match for match in re.findall(r'data-tone=["\']([^"\']+)["\']', fragment, re.I)]
            if set(tones).intersection({"alt", "warm"}) or "var(--accent-alt" in text or "var(--accent-warm" in text:
                errors.append(f"{path.name}: ordinary components must stay inside the theme accent family")
            if quality.get("surface_density") == "heavy":
                carries_texture = (
                    'data-decor="__DECOR__"' in fragment
                    or 'data-decor="dots"' in fragment
                    or 'data-motif=' in fragment
                )
                if len(set(tones)) < 2 and not carries_texture:
                    errors.append(f"{path.name}: heavy component needs multiple surface tones or a declared texture")
            if tones.count("ink") > 1:
                errors.append(f"{path.name}: more than one ink surface weakens the single visual center")
            if path.stem == "converge":
                if "data-visual-edge" not in fragment:
                    errors.append("converge.html: the merge relationship requires a visible program-owned edge")
                if re.search(r"\.merge\s*\{[^}]*display\s*:\s*none", text, re.I | re.S):
                    errors.append("converge.html: the merge relationship must not be hidden")

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

    cycle = TEMPLATES / "cycle.html"
    if cycle.is_file():
        text = cycle.read_text(encoding="utf-8")
        if text.count('data-step="') != 4 or "data-visual-edge" not in text:
            errors.append("cycle.html: requires exactly four stages and a visible program-owned cycle edge")
        if 'data-slot="statement"' not in text or 'data-slot="statement-body"' not in text:
            errors.append("cycle.html: requires a center statement and supporting body")

    quadrant = TEMPLATES / "quadrant.html"
    if quadrant.is_file():
        text = quadrant.read_text(encoding="utf-8")
        if text.count('data-quadrant="') != 4:
            errors.append("quadrant.html: requires exactly four semantic groups")
        if 'data-slot="axis-x"' not in text or 'data-slot="axis-y"' not in text:
            errors.append("quadrant.html: requires program-owned x and y axes")

    tier_stack = TEMPLATES / "tier-stack.html"
    if tier_stack.is_file():
        text = tier_stack.read_text(encoding="utf-8")
        if text.count('data-step="') != 4:
            errors.append("tier-stack.html: requires exactly four tiers")
        if 'data-variant="__VARIANT__"' not in text:
            errors.append("tier-stack.html: must render the selected semantic variant")
        if '[data-variant="pyramid"]' not in text or "clip-path:polygon" not in text:
            errors.append("tier-stack.html: requires distinct funnel and pyramid silhouettes")
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
    commands = r"(?:init|batch|status|plan|check|doctor|audit|recommend|contract|preview|edit|confirm|scaffold|build|list|add|remove|sync|media|icon)"
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
        for required in ('display_name: "oil-ppt"', "next.action", "command_on_confirm", "start_editor"):
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
    media_surface = SHARED_SLIDE_FIELDS.get("media_surface")
    if not isinstance(media_surface, dict) or set(media_surface.get("allowed") or ()) != {"component", "page-blend"}:
        errors.append("contract must expose media_surface with component and page-blend choices")
    surface_templates = {template for template, fields in TEMPLATE_VISIBLE_FIELDS.items() if "media_surface" in fields}
    if surface_templates != set(PAGE_BLEND_TEMPLATES):
        errors.append(f"media_surface exposure mismatch; expected={sorted(PAGE_BLEND_TEMPLATES)}, actual={sorted(surface_templates)}")
    if effective_media_surface({"template": "split-visual", "media_fidelity": "illustrative"}) != "page-blend":
        errors.append("illustrative split media must infer page-blend")
    if effective_media_surface({"template": "split-visual", "media_fidelity": "strict", "media_frame": "self-framed"}) != "page-blend":
        errors.append("self-framed split evidence must infer page-blend instead of receiving a second shell")
    if effective_media_fit({"template": "split-visual", "media_fidelity": "strict", "media_frame": "self-framed"}) != "contain":
        errors.append("self-framed strict evidence must remain uncropped while blending into the page")
    if effective_media_fit({"template": "split-visual", "media_fidelity": "illustrative"}) != "contain":
        errors.append("page-blend illustration must preserve its full subject with contain")
    if MEDIA_FIT_DEFAULTS.get("cover") != "cover" or MEDIA_SLOTS.get("cover", {}).get("ratio") != "4:5":
        errors.append("cover media must default to cover in a portrait-oriented 4:5 generation slot")
    if MEDIA_SLOTS.get("browser-showcase", {}).get("ratio") != "4:3":
        errors.append("browser media plan must match the template's 4:3 evidence area")
    sequence_slot = MEDIA_SLOTS.get("sequence-gallery", {})
    if sequence_slot.get("fit") != "cover" or sequence_slot.get("fidelity") != "contextual":
        errors.append("sequence-gallery must default to crop-safe contextual process photography")
    if MEDIA_VARIANT_SLOTS.get(("split-visual", "copy-dominant"), {}).get("ratio") != "4:5":
        errors.append("copy-dominant split media must expose its portrait slot ratio")
    if set((DECK_FIELDS.get("media_policy") or {}).get("allowed") or ()) != {"required", "text-only"}:
        errors.append("contract must expose both media policies")
    data_variants = set((COMPONENT_CONTRACTS.get("data-story") or {}).get("variants") or ())
    if data_variants != set(DATA_STORY_QUESTIONS):
        errors.append("data-story relationship questions must cover every public variant")
    if (
        format_number(12500, compact=True) != "12.5k"
        or format_number(42.0) != "42"
        or format_number(0.0049) != "0.0049"
        or format_number(1e-10) == "0"
    ):
        errors.append("data-story number formatting is not deterministic")
    data_template = TEMPLATES / "data-story.html"
    if data_template.is_file() and re.search(r"https?://|//cdn\.", data_template.read_text(encoding="utf-8"), re.I):
        errors.append("data-story must render without CDN or remote runtime dependencies")
    companion_keys = {"accent_alt", "accent_alt_soft", "accent_warm", "accent_warm_soft"}
    for name, palette in PALETTES.items():
        if not companion_keys.issubset(palette):
            errors.append(f"named palette {name} must explicitly curate all companion colors")

    runtime_css = (ROOT / "assets/runtime/deck.css").read_text(encoding="utf-8")
    compact_runtime = re.sub(r"\s+", "", runtime_css)
    surface_rule = re.search(r"\.oil-surface\s*\{([^}]*)\}", runtime_css, re.S)
    if not surface_rule or not re.search(r"overflow\s*:\s*visible", surface_rule.group(1)):
        errors.append("runtime .oil-surface must keep overflow visible; clipping belongs to media wrappers")
    if '[data-media-surface="page-blend"]' not in runtime_css:
        errors.append("runtime must implement the page-blend media surface")
    cover_text = (TEMPLATES / "cover.html").read_text(encoding="utf-8")
    if 'class="media oil-surface oil-media"' in cover_text or COMPONENT_QUALITY["cover"]["frame_owner"] != "none":
        errors.append("cover media must stay open and frameless; it may not use the generic oil-surface shell")
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
    if ".hl" not in runtime_css or "--accent-mark" not in runtime_css or "--highlight-opacity" not in runtime_css:
        errors.append("runtime must retain the program-rendered marker highlight")
    if ".oil-backdrop-text" not in runtime_css:
        errors.append("runtime must render content-owned oversized background type")
    declared_tones = tuple(PROGRAM_OWNED_CAPABILITIES["surface"]["tones"])
    for tone in declared_tones:
        if f'.oil-surface[data-tone="{tone}"]' not in runtime_css:
            errors.append(f"runtime surface tone {tone} is declared but missing")
    tone_layer = re.search(r"\.oil-surface\[data-tone\]::before\s*\{([^}]*)\}", runtime_css, re.S)
    if not tone_layer or "content:none" not in re.sub(r"\s+", "", tone_layer.group(1)):
        errors.append("runtime surface tones must stay flat; local motifs own decorative geometry")
    ring_surface_rule = re.search(r'\.oil-surface\[data-motif="ring"\]::after\s*\{([^}]*)\}', runtime_css, re.S)
    ring_surface_declarations = re.sub(r"\s+", "", ring_surface_rule.group(1)) if ring_surface_rule else ""
    if "content:none" not in ring_surface_declarations or "display:none" not in ring_surface_declarations:
        errors.append("runtime ring motif must disable the unclipped surface pseudo-element")
    ring_window_rule = re.search(r'\[data-motif="ring"\]\s*>\s*\.oil-shape-window\s*\{([^}]*)\}', runtime_css, re.S)
    if not ring_window_rule or not re.search(r"overflow\s*:\s*(?:hidden|clip)\b", ring_window_rule.group(1), re.I):
        errors.append("runtime ring motif requires a clipping oil-shape-window")
    ring_geometry_rule = re.search(r'\[data-motif="ring"\]\s*>\s*\.oil-shape-window::after\s*\{([^}]*)\}', runtime_css, re.S)
    if not ring_geometry_rule:
        errors.append("runtime ring geometry must belong to the oil-shape-window")
    else:
        declarations = ring_geometry_rule.group(1)
        if not re.search(r"\bright\s*:\s*-", declarations) or not re.search(r"\btop\s*:\s*-", declarations):
            errors.append("runtime ring geometry must cross the top-right shape-window boundary")
    for motif in PROGRAM_OWNED_CAPABILITIES["surface"]["automatic_motifs"]:
        if motif == "ring":
            continue
        motif_rule = re.search(
            rf'\.oil-surface\[data-motif="{re.escape(motif)}"\]::after\s*\{{([^}}]*)\}}',
            runtime_css,
            re.S,
        )
        if not motif_rule:
            errors.append(f"runtime surface motif {motif} is declared but missing")
            continue
        declarations = motif_rule.group(1)
        if not re.search(r"\bright\s*:", declarations) or not re.search(r"\btop\s*:", declarations):
            errors.append(f"runtime surface motif {motif} must use the fixed top-right anchor")
        if re.search(r"\b(?:left|bottom)\s*:", declarations):
            errors.append(f"runtime surface motif {motif} may not declare an opposite-corner anchor")
    if ".oil-icon-frame" not in runtime_css or "--icon-frame" not in runtime_css or "--icon-size" not in runtime_css:
        errors.append("runtime must provide the enlarged, reduced-padding icon frame contract")
    if ".oil-chart-bars" not in runtime_css:
        errors.append("runtime must provide deterministic native chart bars")
    for token in ("[data-copy-flow] > [data-copy-title]", "[data-copy-flow] > [data-copy-body]", "--oil-copy-title-max", "--oil-copy-body-max"):
        if token not in runtime_css:
            errors.append(f"runtime adaptive copy flow missing {token}")
    runtime_js = (ROOT / "assets/runtime/deck.js").read_text(encoding="utf-8")
    if "checkCopyFlow" not in runtime_js or 'warningReason = "copy-gap"' not in runtime_js:
        errors.append("runtime must audit excessive title-to-body gaps in adaptive copy flows")
    cdp_source = (ROOT / "scripts/cdp_validate.py").read_text(encoding="utf-8")
    if "invalidCopyFlows" not in cdp_source or "reason:'copy-gap'" not in cdp_source:
        errors.append("browser validation must reject excessive title-to-body gaps")
    expected_visual_categories = {
        "content-bounds", "surface-clipping", "decoration", "ring-geometry", "surface-paint", "line-density",
    }
    if set(VISUAL_FINDING_CATEGORIES) != expected_visual_categories:
        errors.append("browser visual maintenance finding categories are incomplete")
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
