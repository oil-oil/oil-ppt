#!/usr/bin/env python3
"""Merge, inline, route, and browser-validate an oil-slides project."""
from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import os
import re
import shutil
import tempfile
from pathlib import Path

from cdp_validate import validate_file
from outline_schema import validate_outline
from palette_tokens import TOKEN_KEYS, normalize_palette
from profile_tokens import SHAPE_PROFILES, TYPE_PROFILES


CSS_BLOCK = re.compile(r"/\*\s*OIL-SLIDE-CSS:START\s*\*/(.*?)/\*\s*OIL-SLIDE-CSS:END\s*\*/", re.S)
HTML_BLOCK = re.compile(r"<!--\s*OIL-SLIDE:START\s*-->(.*?)<!--\s*OIL-SLIDE:END\s*-->", re.S)
SLIDE_ID = re.compile(r"data-slide-id=[\"']([a-z0-9][a-z0-9-]*)[\"']")
SLIDE_TITLE = re.compile(r"data-title=[\"']([^\"']+)[\"']")
SLIDE_VARIANT = re.compile(r"data-variant=[\"']([^\"']+)[\"']")
SLIDE_DECOR = re.compile(r"data-component-decor=[\"']([^\"']+)[\"']")
LOCAL_PATHS = [
    re.compile(r"file://", re.I),
    re.compile(r"/(?:Users|home)/[^/\s<>'\"]+", re.I),
    re.compile(r"[A-Za-z]:\\(?:Users|Documents and Settings)\\", re.I),
]
def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    return parser.parse_args()


def assert_no_local_paths(text: str, label: str) -> None:
    for pattern in LOCAL_PATHS:
        hit = pattern.search(text)
        if hit:
            raise SystemExit(f"Local path rejected in {label}: {hit.group(0)}")


def data_uri(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"Missing local asset: {path}")
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def inline_html_assets(fragment: str, slide_file: Path) -> str:
    attr = re.compile(r"(?P<prefix>\b(?:src|poster)\s*=\s*[\"'])(?P<url>[^\"']+)(?P<suffix>[\"'])", re.I)

    def replace(match: re.Match[str]) -> str:
        url = match.group("url")
        if re.match(r"https?:", url, re.I):
            raise SystemExit(f"Remote media is not allowed in delivery HTML: {url}")
        if re.match(r"(?:data:|#)", url, re.I):
            return match.group(0)
        resolved = (slide_file.parent / url).resolve()
        if slide_file.parent.parent.resolve() not in resolved.parents:
            raise SystemExit(f"Media must stay inside project assets: {url}")
        return f"{match.group('prefix')}{data_uri(resolved)}{match.group('suffix')}"

    return attr.sub(replace, fragment)


def inline_css_assets(css: str, slide_file: Path) -> str:
    pattern = re.compile(r"url\(\s*([\"']?)([^)'\"]+)\1\s*\)", re.I)

    def replace(match: re.Match[str]) -> str:
        url = match.group(2).strip()
        if re.match(r"https?:", url, re.I):
            raise SystemExit(f"Remote CSS asset is not allowed in delivery HTML: {url}")
        if re.match(r"(?:data:|#)", url, re.I):
            return match.group(0)
        resolved = (slide_file.parent / url).resolve()
        if slide_file.parent.parent.resolve() not in resolved.parents:
            raise SystemExit(f"CSS media must stay inside project assets: {url}")
        return f'url("{data_uri(resolved)}")'

    return pattern.sub(replace, css)


def static_text_budget_warnings(fragment: str, label: str) -> list[str]:
    warnings: list[str] = []
    pattern = re.compile(
        r"<(?P<tag>[a-z][a-z0-9]*)\b(?P<attrs>[^>]*)data-max-chars=[\"'](?P<max>\d+)[\"'][^>]*>(?P<body>.*?)</(?P=tag)>",
        re.I | re.S,
    )
    for match in pattern.finditer(fragment):
        plain = html.unescape(re.sub(r"<[^>]+>", "", match.group("body")))
        length = len(re.sub(r"\s+", "", plain))
        maximum = int(match.group("max"))
        if length > maximum:
            warnings.append(f"{label}: {length}/{maximum} characters")
    return warnings


def normalized_css(value: str) -> str:
    return re.sub(r"\s+", "", value)


def check_locked_template_css(actual: str, planned: dict, slide_id: str, templates_dir: Path, label: str) -> None:
    template_source = (templates_dir / f"{planned['template']}.html").read_text(encoding="utf-8")
    match = CSS_BLOCK.search(template_source)
    if not match:
        raise SystemExit(f"Bundled template has no CSS block: {planned['template']}")
    expected = match.group(1).replace("__ID__", slide_id)
    if normalized_css(actual) != normalized_css(expected):
        raise SystemExit(
            f"Locked template geometry changed in {label}. Keep the bundled {planned['template']!r} CSS; "
            "edit only the outline content and rebuild."
        )


def chrome_binary() -> str | None:
    home = Path.home()
    program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
    local_app_data = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local"))
    testing_browsers = sorted([
        *home.glob("Library/Caches/ms-playwright/chromium-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"),
        *home.glob(".cache/ms-playwright/chromium-*/chrome-linux/chrome"),
        *home.glob(".cache/ms-playwright/chromium-*/chrome-linux64/chrome"),
        *home.glob("AppData/Local/ms-playwright/chromium-*/chrome-win/chrome.exe"),
        *home.glob("AppData/Local/ms-playwright/chromium-*/chrome-win64/chrome.exe"),
    ], reverse=True)
    candidates = [
        os.environ.get("CHROME_BIN", ""),
        *(str(path) for path in testing_browsers),
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
        shutil.which("msedge") or "",
        shutil.which("brave") or "",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        str(program_files / "Google/Chrome/Application/chrome.exe"),
        str(program_files_x86 / "Microsoft/Edge/Application/msedge.exe"),
        str(program_files / "BraveSoftware/Brave-Browser/Application/brave.exe"),
        str(local_app_data / "Chromium/Application/chrome.exe"),
    ]
    return next((item for item in candidates if item and Path(item).exists()), None)


def browser_validate(path: Path) -> None:
    chrome = chrome_binary()
    if not chrome:
        raise SystemExit("No Chromium browser found. Install Chrome/Chromium/Edge/Brave or set CHROME_BIN; browser loading and structure validation is required for delivery.")
    try:
        report = validate_file(chrome, path)
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"Chromium DOM validation failed: {error}") from error
    if report.get("status") != "ok":
        raise SystemExit("Browser render validation did not complete; final file was not written.")


def build(project: Path) -> str:
    config_path = project / "deck.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for key in ("next_preview", "click_navigation", "show_progress", "show_counter"):
        if not isinstance(config.get(key), bool):
            raise SystemExit(f"deck.json requires boolean {key}.")
    if not isinstance(config.get("palette"), dict):
        raise SystemExit("deck.json requires a resolved palette object.")
    try:
        palette = normalize_palette(config["palette"])
    except ValueError as error:
        raise SystemExit(f"Invalid deck.json palette: {error}") from error
    type_profile = str((config.get("typography") or {}).get("profile") or "")
    shape_profile = str((config.get("shape") or {}).get("profile") or "")
    if type_profile not in TYPE_PROFILES:
        raise SystemExit("deck.json typography.profile must be clean, rounded, editorial, or technical.")
    if shape_profile not in SHAPE_PROFILES:
        raise SystemExit("deck.json shape.profile must be crisp, soft, or round.")

    runtime_css = (project / "runtime" / "deck.css").read_text(encoding="utf-8")
    runtime_js = (project / "runtime" / "deck.js").read_text(encoding="utf-8")
    outline_path = project / "outline.json"
    if not outline_path.is_file():
        raise SystemExit("Missing outline.json. Build requires the confirmed project outline.")
    outline_data = json.loads(outline_path.read_text(encoding="utf-8"))
    outline_slides = validate_outline(outline_data, Path(__file__).resolve().parent.parent / "assets" / "templates")
    slide_paths = config.get("slides")
    if not isinstance(slide_paths, list) or not slide_paths:
        raise SystemExit("deck.json requires a non-empty slides list.")
    if len(slide_paths) != len(outline_slides):
        raise SystemExit(f"Outline/deck count mismatch: {len(outline_slides)} outline slides, {len(slide_paths)} deck slides.")
    ids: set[str] = set()
    css_parts: list[str] = []
    fragments: list[str] = []
    text_budget_warnings: list[str] = []
    templates_dir = Path(__file__).resolve().parent.parent / "assets" / "templates"
    for slide_index, relative in enumerate(slide_paths):
        slide_file = (project / relative).resolve()
        if project.resolve() not in slide_file.parents:
            raise SystemExit(f"Slide must stay inside project: {relative}")
        source = slide_file.read_text(encoding="utf-8")
        assert_no_local_paths(source, relative)
        css_match = CSS_BLOCK.search(source)
        html_match = HTML_BLOCK.search(source)
        if not css_match or not html_match:
            raise SystemExit(f"Missing OIL-SLIDE markers: {relative}")
        fragment = html_match.group(1).strip()
        if re.search(r"\sstyle\s*=", fragment, re.I):
            raise SystemExit(
                f"Inline style is forbidden: {relative}. "
                "Return to locked template slots; do not hand-write layout CSS on the page."
            )
        if re.search(r"\bdata-placeholder\s*=", fragment, re.I):
            raise SystemExit(f"Unresolved template placeholder: {relative}. Replace it before delivery.")
        if re.search(r"<script\b", fragment, re.I) or re.search(r"\son[a-z]+\s*=", fragment, re.I):
            raise SystemExit(f"Custom scripts and inline event handlers are forbidden in slides: {relative}")
        if len(re.findall(r"<section\b", fragment, re.I)) != 1:
            raise SystemExit(f"Each slide marker must contain exactly one <section>: {relative}")
        if not SLIDE_TITLE.search(fragment):
            raise SystemExit(f"Missing data-title: {relative}")
        for image_tag in re.findall(r"<img\b[^>]*>", fragment, re.I):
            if not re.search(r"\balt\s*=\s*[\"'][^\"']*[\"']", image_tag, re.I):
                raise SystemExit(f"Every image needs alt (empty is allowed for decoration): {relative}")
        text_budget_warnings.extend(static_text_budget_warnings(fragment, relative))
        id_match = SLIDE_ID.search(fragment)
        if not id_match:
            raise SystemExit(f"Missing or invalid data-slide-id: {relative}")
        slide_id = id_match.group(1)
        if slide_id in ids:
            raise SystemExit(f"Duplicate data-slide-id: {slide_id}")
        ids.add(slide_id)
        title = html.unescape(SLIDE_TITLE.search(fragment).group(1)).strip()
        planned = outline_slides[slide_index]
        if slide_id != planned["id"] or title != planned["title"].strip():
            raise SystemExit(
                f"Outline/deck mismatch at slide {slide_index + 1}: "
                f"expected {planned['id']!r} / {planned['title']!r}, got {slide_id!r} / {title!r}."
            )
        variant_match = SLIDE_VARIANT.search(fragment)
        decor_match = SLIDE_DECOR.search(fragment)
        if not variant_match or variant_match.group(1) != planned["variant"]:
            got = variant_match.group(1) if variant_match else None
            raise SystemExit(f"Component variant mismatch in {relative}: expected {planned['variant']!r}, got {got!r}.")
        if not decor_match or decor_match.group(1) != planned["decor"]:
            got = decor_match.group(1) if decor_match else None
            raise SystemExit(f"Component decor mismatch in {relative}: expected {planned['decor']!r}, got {got!r}.")
        if planned["template"] == "process-rail" and re.search(r"\boil-surface\b", fragment):
            raise SystemExit(
                f"process-rail must stay an open canvas in {relative}: "
                "remove wrapping .oil-surface from the structure, keep only steps and connectors."
            )
        if planned["template"] == "process-rail" and not re.search(r"\bconnector\b", fragment):
            raise SystemExit(
                f"process-rail in {relative} is missing independent .connector columns for arrows. "
                "Do not hang arrows on step ::after pseudo-elements."
            )
        check_locked_template_css(css_match.group(1), planned, slide_id, templates_dir, relative)
        css_parts.append(inline_css_assets(css_match.group(1).strip(), slide_file))
        fragments.append(inline_html_assets(fragment, slide_file))

    if text_budget_warnings:
        print(f"[INFO] {len(text_budget_warnings)} text-budget suggestions recorded for editorial review; they do not block the build.")

    type_tokens = TYPE_PROFILES[type_profile]
    shape_tokens = SHAPE_PROFILES[shape_profile]
    theme = ":root{" + "".join([
        f"--slide-bg:{palette['canvas']};",
        f"--stage-bg:{palette['canvas']};",
        f"--ink:{palette['ink']};",
        f"--ink-2:{palette['ink_2']};",
        f"--ink-3:{palette['ink_3']};",
        f"--border:{palette['border']};",
        f"--surface:{palette['surface']};",
        f"--surface-2:{palette['surface_2']};",
        f"--accent:{palette['accent']};",
        f"--accent-mark:{palette['accent']};",
        f"--accent-fill:{palette['accent_fill']};",
        f"--accent-soft:{palette['accent_soft']};",
        f"--accent-wash:{palette['accent_soft']};",
        f"--accent-strong:{palette['accent_strong']};",
        f"--accent-ink:{palette['accent_strong']};",
        f"--ambient:{palette['surface']};",
        f"--grid-color:color-mix(in srgb,{palette['ink']} 3.2%,transparent);",
        f"--font-zh:{type_tokens['zh']};",
        f"--font-ui:{type_tokens['ui']};",
        f"--surface-radius:{shape_tokens['radius']};",
        f"--surface-shadow:{shape_tokens['shadow']};",
    ]) + "}"
    preview = "" if not config.get("next_preview", True) else '<aside class="next-preview" aria-label="下一页提示"><span class="next-preview-label">下一页 →</span><span class="next-preview-title"></span></aside>'
    counter = '<div class="deck-counter" aria-live="polite"></div>' if config.get("show_counter", True) else ""
    progress = '<div class="progress-bar" aria-hidden="true"></div>' if config.get("show_progress", True) else ""
    title = html.escape(str(config.get("title", "oil-slides")))
    lang = html.escape(str(config.get("lang", "zh-CN")))
    click_navigation = "true" if config["click_navigation"] else "false"
    slides_html = "\n".join(fragments)
    slide_css = "\n".join(css_parts)
    output = f"""<!doctype html>
<html lang="{lang}" data-validation="pending">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{runtime_css}\n{theme}\n{slide_css}</style>
</head>
<body data-type-profile="{type_profile}" data-shape-profile="{shape_profile}" data-click-nav="{click_navigation}">
<div class="deck-viewport"><div class="deck-stage-shell"><main class="deck-stage">
{slides_html}
</main></div></div>
{progress}
{counter}
{preview}
<script>{runtime_js}</script>
</body>
</html>
"""
    assert_no_local_paths(output, "final HTML")
    return output


def main() -> None:
    options = args()
    project = options.project_dir.expanduser().resolve()
    out = project / "演示文稿.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    content = build(project)
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=out.parent, delete=False, encoding="utf-8") as handle:
        handle.write(content)
        temp = Path(handle.name)
    try:
        browser_validate(temp)
        verified = temp.read_text(encoding="utf-8").replace('data-validation="pending"', 'data-validation="browser"', 1)
        temp.write_text(verified, encoding="utf-8")
        os.replace(temp, out)
    finally:
        temp.unlink(missing_ok=True)
    print(f"Built (browser render validation): {out}")


if __name__ == "__main__":
    main()
