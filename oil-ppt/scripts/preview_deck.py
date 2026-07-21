"""Generate previews from real slide files, without rewriting them."""
from __future__ import annotations

import html
import os
import tempfile
from pathlib import Path

from media_assets import verify_deck_media
from cdp_validate import validate_file
from html_urls import rewrite_css_urls, rewrite_html_urls
from project import deck_chrome, read_deck, slide_path
from slide_html import parse_slide
from state import input_manifest, write_state
from theme import project_theme_css

def _preview_url(value: str) -> str:
    return "assets/" + value.removeprefix("../assets/") if value.startswith("../assets/") else value


def render_preview(project_value: Path, output: Path | None = None) -> Path:
    project, deck = read_deck(project_value)
    verify_deck_media(project, deck)
    slides = [parse_slide(slide_path(project, relative), Path(relative).stem) for relative in deck["slides"]]
    if not slides:
        raise SystemExit("Cannot preview a deck with no slides.")
    runtime_css = (project / "runtime" / "deck.css").read_text(encoding="utf-8")
    runtime_js = (project / "runtime" / "deck.js").read_text(encoding="utf-8")
    result = output or project / "预览.html"
    result = result.resolve()
    if result != (project / "预览.html").resolve():
        raise SystemExit("Preview output is fixed at the project root as 预览.html.")
    # Slide files resolve media from slides/, while this generated preview is at
    # the project root. Rebase only URL-bearing syntax in the generated copy;
    # literal copy such as <code>../assets/example.png</code> stays untouched.
    local_css = "\n".join(rewrite_css_urls(item.css, _preview_url) for item in slides)
    sections = "\n".join(rewrite_html_urls(item.section, _preview_url) for item in slides)
    title = html.escape(str(deck.get("title") or "oil-ppt"))
    controls = deck.get("controls") if isinstance(deck.get("controls"), dict) else {}
    rendered = f'''<!doctype html><html lang="{html.escape(str(deck.get("lang") or "zh-CN"))}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{runtime_css}\n{project_theme_css(project, deck)}\n{local_css}</style></head><body data-click-nav="{str(bool(controls.get("click_navigation", False))).lower()}"><div class="deck-viewport"><div class="deck-stage-shell"><div class="deck-stage">{sections}</div></div></div>{deck_chrome(deck)}<script>{runtime_js}</script></body></html>\n'''
    descriptor, temporary_name = tempfile.mkstemp(prefix=".oil-ppt-preview-", suffix=".html", dir=project)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, result)
    finally:
        temporary.unlink(missing_ok=True)
    manifest = input_manifest(project)
    from build_deck import chrome_binary
    chrome = chrome_binary()
    if chrome:
        report = validate_file(chrome, result)
        if report.get("status") != "ok":
            write_state(
                project,
                phase="repair_browser",
                preview_confirmed=False,
                browser_manifest=manifest,
                browser_issues=report,
            )
            raise SystemExit(f"Browser validation failed: {report}")
    write_state(
        project,
        phase="needs_preview_confirmation",
        preview_confirmed=False,
        preview_manifest=manifest,
        browser_manifest=manifest,
        browser_issues=None,
    )
    return result
