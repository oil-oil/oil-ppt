#!/usr/bin/env python3
"""Build one self-contained delivery deck from standalone slide HTML sources."""
from __future__ import annotations

import argparse
import base64
import html
import mimetypes
import os
import re
import tempfile
from pathlib import Path

from cdp_validate import validate_file
from html_urls import rewrite_css_urls, rewrite_html_urls
from media_assets import verify_deck_media
from project import deck_chrome, read_deck, slide_path
from slide_html import Slide, parse_slide
from state import input_manifest, read_state, write_state
from theme import project_theme_css

def chrome_binary() -> str | None:
    from shutil import which
    candidates = [os.environ.get("CHROME_BIN", ""), which("google-chrome") or "", which("chromium") or "", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    return next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)


def _data_uri(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"Missing local asset: {path}")
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _asset_url(url: str, slide: Slide, project: Path) -> str:
    if url.startswith(("data:", "#")):
        return url
    if re.match(r"(?:https?:|//|file:|/|[A-Za-z]:[\\/])", url, re.I):
        raise SystemExit(f"{slide.path}: unsupported delivery asset URL: {url}")
    resolved = (slide.path.parent / url).resolve()
    assets = (project / "assets").resolve()
    if assets not in resolved.parents:
        raise SystemExit(f"{slide.path}: asset must remain under assets/: {url}")
    return _data_uri(resolved)


def _inline(slide: Slide, project: Path) -> tuple[str, str]:
    transform = lambda value: _asset_url(value, slide, project)
    section = rewrite_html_urls(slide.section, transform)
    css = rewrite_css_urls(slide.css, transform)
    return css, section


def build_project(project_value: Path, *, browser: bool = False) -> Path:
    project, deck = read_deck(project_value)
    verify_deck_media(project, deck)
    state = read_state(project)
    if not state.get("preview_confirmed"):
        raise SystemExit("Build requires explicit preview confirmation. Run confirm PROJECT preview after the user reviews 预览.html.")
    if state.get("preview_manifest") != input_manifest(project):
        raise SystemExit("Preview confirmation is stale: deck, slides, assets, or runtime changed. Run preview again.")
    slides = [parse_slide(slide_path(project, relative), Path(relative).stem) for relative in deck["slides"]]
    if not slides:
        raise SystemExit("Cannot build a deck with no slides.")
    pieces = [_inline(slide, project) for slide in slides]
    runtime_css = (project / "runtime" / "deck.css").read_text(encoding="utf-8")
    runtime_js = (project / "runtime" / "deck.js").read_text(encoding="utf-8")
    title = html.escape(str(deck.get("title") or "oil-ppt"))
    output = project / "演示文稿.html"
    rendered = f'''<!doctype html><html lang="{html.escape(str(deck.get("lang") or "zh-CN"))}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{runtime_css}\n{project_theme_css(project, deck)}\n{"\n".join(css for css, _ in pieces)}</style></head><body data-click-nav="{str(bool((deck.get("controls") or {}).get("click_navigation", False))).lower()}"><div class="deck-viewport"><div class="deck-stage-shell"><div class="deck-stage">{"\n".join(section for _, section in pieces)}</div></div></div>{deck_chrome(deck)}<script>{runtime_js}</script></body></html>\n'''
    descriptor, temporary_name = tempfile.mkstemp(prefix=".oil-ppt-build-", suffix=".html", dir=project)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        chrome = chrome_binary()
        if browser and not chrome:
            raise SystemExit("Browser validation requested but Chrome/Chromium is unavailable.")
        if chrome:
            report = validate_file(chrome, temporary)
            page_scroll = any(item.get("category") == "page-scroll" for item in report.get("visualFindings") or [] if isinstance(item, dict))
            if report.get("status") != "ok" or report.get("brokenImages") or report.get("missingSafeArea") or report.get("invalidLayouts") or report.get("invalidBleeds") or report.get("invalidText") or page_scroll:
                write_state(
                    project,
                    phase="repair_browser",
                    preview_confirmed=False,
                    browser_manifest=input_manifest(project),
                    browser_issues=report,
                )
                raise SystemExit(f"Browser validation failed: {report}")
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    write_state(project, phase="complete", preview_confirmed=True, build=str(output), build_manifest=input_manifest(project))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--browser", action="store_true")
    values = parser.parse_args()
    print(build_project(values.project_dir, browser=values.browser))


if __name__ == "__main__":
    main()
