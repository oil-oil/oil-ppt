#!/usr/bin/env python3
"""Validate the public HTML-first oil-ppt package contract."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from slide_html import parse_slide, style_advice
from theme import theme_css
from workflow_contract import BATCH_NEXT_ACTIONS, STATUS_NEXT_ACTIONS, validate_next_step


ROOT = Path(__file__).resolve().parent.parent
STARTERS = ROOT / "assets" / "starters"
RUNTIME = ROOT / "assets" / "runtime"
REQUIRED_FILES = {
    "SKILL.md",
    "agents/openai.yaml",
    "manifest.json",
    "scripts/oil-ppt",
    "scripts/oil-ppt.cmd",
    "scripts/oil_ppt.py",
    "scripts/project.py",
    "scripts/outline.py",
    "scripts/html_urls.py",
    "scripts/slide_html.py",
    "scripts/state.py",
    "scripts/theme.py",
    "scripts/catalog.py",
    "scripts/workflow.py",
    "scripts/workflow_contract.py",
    "scripts/preview_deck.py",
    "scripts/build_deck.py",
    "scripts/cdp_validate.py",
    "scripts/media_assets.py",
    "scripts/pptx_export.py",
    "scripts/package_manifest.py",
    "scripts/doctor.py",
    "assets/runtime/deck.css",
    "assets/runtime/deck.js",
    "assets/runtime/theme.css",
    "assets/starter/deck.json",
    "references/evolution.md",
    "references/components.md",
    "references/illustration.md",
    "references/media.md",
    "references/programmatic-visuals.md",
    "references/troubleshooting.md",
}
EXPECTED_PYTHON = {
    "build_deck.py", "catalog.py", "cdp_validate.py", "doctor.py", "icon_registry.py",
    "html_urls.py", "media_assets.py", "outline.py", "package_manifest.py", "pptx_export.py",
    "preview_deck.py", "project.py", "slide_html.py",
    "state.py", "theme.py", "validate_skill.py", "workflow.py", "workflow_contract.py",
    "oil_ppt.py",
}


def _validate_starter(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    tokens = set(re.findall(r"__[A-Z][A-Z0-9_]*__", text))
    if tokens != {"__ID__", "__TITLE__"}:
        errors.append(f"{path.relative_to(ROOT)}: starter tokens must be exactly __ID__ and __TITLE__")
        return
    if re.search(r"\son[a-z]+\s*=", text, re.I):
        errors.append(f"{path.relative_to(ROOT)}: inline event handlers are not allowed")
    scripts = re.findall(r"<script\b([^>]*)>(.*?)</script\s*>", text, re.I | re.S)
    if len(scripts) != 1 or "../runtime/deck.js" not in scripts[0][0] or scripts[0][1].strip():
        errors.append(f"{path.relative_to(ROOT)}: starter may load only ../runtime/deck.js")
    rendered = text.replace("__ID__", "starter-check").replace("__TITLE__", "Starter check")
    with tempfile.TemporaryDirectory(prefix="oil-ppt-starter-") as directory:
        project = Path(directory)
        (project / "slides").mkdir()
        shutil.copytree(RUNTIME, project / "runtime")
        output = project / "slides" / "starter-check.html"
        output.write_text(rendered, encoding="utf-8")
        try:
            parse_slide(output, "starter-check")
        except SystemExit as error:
            errors.append(f"{path.relative_to(ROOT)}: {error}")


def validation_errors() -> list[str]:
    errors: list[str] = []
    for relative in sorted(REQUIRED_FILES):
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")

    wrapper = ROOT / "scripts" / "oil-ppt"
    if wrapper.is_file() and not os.access(wrapper, os.X_OK):
        errors.append("scripts/oil-ppt must be executable")

    starter_files = sorted(STARTERS.glob("*.html"))
    expected_starters = {
        "blank", "statement", "title-media", "comparison", "sequence", "data", "evidence", "section", "ending",
        "problem-canvas", "converge", "process-rail", "feature-grid", "annotated-showcase", "browser-showcase",
        "editorial-feature", "relationship-map", "hierarchy-tree", "cycle", "metric-spotlight", "quote-focus",
        "step-focus", "bleed-split", "media-collage",
    }
    actual_starters = {path.stem for path in starter_files}
    if actual_starters != expected_starters:
        errors.append("assets/starters must contain exactly the 24 public standalone starters")
    for path in starter_files:
        _validate_starter(path, errors)

    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8") if (ROOT / "SKILL.md").is_file() else ""
    components_path = ROOT / "references" / "components.md"
    components_text = components_path.read_text(encoding="utf-8") if components_path.is_file() else ""
    documented_actions = set(re.findall(r"`([a-z][a-z_]+)`", skill_text))
    for action in sorted(STATUS_NEXT_ACTIONS):
        if action not in documented_actions:
            errors.append(f"SKILL.md does not document workflow action: {action}")
    if BATCH_NEXT_ACTIONS != STATUS_NEXT_ACTIONS:
        errors.append("batch and single-project workflows must share one action vocabulary")

    actual_python = {
        path.name for path in (ROOT / "scripts").glob("*.py") if path.is_file()
    }
    unexpected_python = sorted(actual_python - EXPECTED_PYTHON)
    missing_python = sorted(EXPECTED_PYTHON - actual_python)
    if unexpected_python:
        errors.append("scripts contains files outside the 1.0 package surface: " + ", ".join(unexpected_python))
    if missing_python:
        errors.append("scripts is missing package files: " + ", ".join(missing_python))
    asset_directories = {
        path.name for path in (ROOT / "assets").iterdir() if path.is_dir()
    }
    if asset_directories != {"icons", "runtime", "starter", "starters"}:
        errors.append("assets directories must be exactly icons, runtime, starter, and starters")

    runtime_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (RUNTIME / "deck.css", RUNTIME / "deck.js")
        if path.is_file()
    )
    if re.search(r"(?:https?:)?//", runtime_text):
        errors.append("runtime must not depend on remote URLs")
    if "1920px" not in runtime_text or "1080px" not in runtime_text:
        errors.append("runtime must declare the 1920 x 1080 stage")
    for token in (
        "oil-text-body", "oil-text-compact", "oil-text-caption",
        "oil-leading-display", "oil-leading-body", "oil-tracking-display",
    ):
        if f"--{token}" not in runtime_text:
            errors.append(f"runtime must declare the typography token: --{token}")
    for selector in (".tag", ".hl"):
        if re.search(rf"(?<![a-z0-9_-]){re.escape(selector)}(?:\b|::)", runtime_text, re.I):
            errors.append(f"runtime author-facing classes must stay in the oil-* namespace: {selector}")
    if ".oil-highlight" not in runtime_text:
        errors.append("runtime must expose the namespaced .oil-highlight helper")
    if ".oil-copy-center" not in runtime_text:
        errors.append("runtime must expose the split-layout .oil-copy-center helper")
    if ".oil-main-fill" not in runtime_text:
        errors.append("runtime must expose the vertical-fill .oil-main-fill helper")
    for contract in (
        'data-bg="grid-wide"', 'data-bg="soft-spotlight"', 'data-bg="block-field"', 'data-bg="media-owned"',
        '.oil-bleed', '.oil-relationship', '.oil-relationship-node', '.oil-relationship-link',
        'data-decor="dots"', 'data-motif="ring"', '.oil-shape-window', 'data-media-treatment="mono"',
    ):
        if contract not in runtime_text:
            errors.append(f"runtime must expose the airy visual contract: {contract}")
    if not re.search(r"(?:4|四)\s*个及以上等宽(?:重复)?单元", components_text) or "第二层信息" not in components_text:
        errors.append("components.md must preserve the repeated-unit load and second-layer guidance")
    for contract in (
        "55%–70%", "浅色比较或特征卡", "垂直居中",
        'data-decor="dots"', "oil-main-fill", "oil-copy-center", "简短内容标签", "可选元素", "把材料写成可以看到的内容", "工具或函数名改成实际动作", "具体对象、动作、数字、文件或状态",
    ):
        if contract not in components_text:
            errors.append(f"components.md must preserve the design contract: {contract}")
    for contract in (
        "oil-tone", "最短执行路径", "slide add <项目> <页面ID>",
        "进入正式预览的条件", "只执行 next", "本页展示的具体对象", "内部界面标识", "[指标] 从 [数值] 变为 [数值]",
    ):
        if contract not in skill_text:
            errors.append(f"SKILL.md must preserve the workflow contract: {contract}")
    process_rail = STARTERS / "process-rail.html"
    process_source = process_rail.read_text(encoding="utf-8") if process_rail.is_file() else ""
    if process_source.count('class="step"') != 4 or process_source.count('class="rail-note"') != 1:
        errors.append("process-rail must model four overview steps and one shared second layer")
    browser_showcase = STARTERS / "browser-showcase.html"
    browser_source = browser_showcase.read_text(encoding="utf-8") if browser_showcase.is_file() else ""
    if 'class="summary"' in browser_source or "oil-lede" in browser_source:
        errors.append("browser-showcase must keep optional external summary copy out of the default starter")
    if browser_source:
        regression_source = browser_source.replace("__ID__", "showcase-check").replace(
            "__TITLE__", "这是一个需要缩短的页面标题，其中包含了过多过程和结果说明"
        ).replace(
            "</header>",
            '<p class="summary">这段说明会和界面争夺注意力。alpha.beta.gamma、delta.epsilon.zeta。</p></header>',
            1,
        )
        with tempfile.TemporaryDirectory(prefix="oil-ppt-style-") as directory:
            project = Path(directory)
            (project / "slides").mkdir()
            shutil.copytree(RUNTIME, project / "runtime")
            output = project / "slides" / "showcase-check.html"
            output.write_text(regression_source, encoding="utf-8")
            slide = parse_slide(output, "showcase-check")
            rules = {item["rule"] for item in style_advice(project, {"slides": []}, slides=[slide])}
            for rule in (
                "long-display-title",
                "redundant-showcase-summary",
                "implementation-identifiers-in-audience-copy",
            ):
                if rule not in rules:
                    errors.append(f"style advice regression is missing rule: {rule}")
    validator_text = (ROOT / "scripts" / "cdp_validate.py").read_text(encoding="utf-8")
    for contract in (
        "minimumFontSize", "data-microcopy", "readability.length",
        "minimumContrastRatio", "low-text-contrast", "contrast.length",
    ):
        if contract not in validator_text:
            errors.append(f"browser validator is missing the typography contract: {contract}")
    valid_authoring = {
        "action": "author_slides",
        "brief": "brief",
        "slide_add_usage": "usage",
        "command_when_ready": "command",
    }
    for field in ("brief", "slide_add_usage", "command_when_ready"):
        invalid = {**valid_authoring, field: ""}
        try:
            validate_next_step(invalid, allowed_actions=STATUS_NEXT_ACTIONS, source="skill validation")
        except SystemExit:
            pass
        else:
            errors.append(f"workflow contract must reject empty author_slides field: {field}")
    expected_theme = theme_css({"theme": {"palette": "oil-yellow", "typography": "clean", "shape": "soft"}})
    theme_path = RUNTIME / "theme.css"
    if not theme_path.is_file() or theme_path.read_text(encoding="utf-8").strip() != expected_theme:
        errors.append("runtime/theme.css must match the default deck theme")
    starter_deck = ROOT / "assets" / "starter" / "deck.json"
    if starter_deck.is_file() and '"direction": "fresh-default"' not in starter_deck.read_text(encoding="utf-8"):
        errors.append("assets/starter/deck.json must declare the fresh-default direction")
    if "24 个真实独立 starter" not in skill_text or "4 类构图" not in skill_text:
        errors.append("SKILL.md must document the 24-starter, four-family visual workflow")
    return errors


def validate_skill() -> None:
    errors = validation_errors()
    if errors:
        raise SystemExit("oil-ppt skill validation failed:\n- " + "\n- ".join(errors))


def main() -> int:
    validate_skill()
    print("oil-ppt skill validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
