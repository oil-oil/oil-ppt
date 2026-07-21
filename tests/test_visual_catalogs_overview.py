"""Regression coverage for offline catalogs and the aggregate deck overview."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "oil-ppt"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from catalog import render_starter_catalog, render_theme_catalog  # noqa: E402
from preview_deck import render_preview  # noqa: E402
from project import deck_chrome, init_project  # noqa: E402
from theme import DIRECTIONS, PALETTES, SHAPES, TYPOGRAPHY  # noqa: E402
from build_deck import chrome_binary  # noqa: E402
from cdp_validate import _stop_browser  # noqa: E402
import oil_ppt  # noqa: E402


class VisualCatalogAndOverviewTests(unittest.TestCase):
    def test_theme_catalog_uses_the_real_registry_and_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.html"
            second = Path(directory) / "second.html"
            render_theme_catalog(first)
            render_theme_catalog(second)
            contents = first.read_text(encoding="utf-8")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(len(PALETTES), 5)
            self.assertEqual(len(TYPOGRAPHY), 3)
            self.assertEqual(len(SHAPES), 3)
            self.assertEqual(len(DIRECTIONS), 5)
            for name in (*DIRECTIONS, *PALETTES, *TYPOGRAPHY, *SHAPES):
                self.assertIn(name, contents)
            self.assertNotRegex(contents, r"(?:https?:)?//")
            self.assertIn("ResizeObserver", contents)
            self.assertIn("preview.clientWidth / 1920", contents)

    def test_starter_catalog_covers_real_sources_without_mutating_them(self) -> None:
        starters = sorted((ROOT / "assets" / "starters").glob("*.html"))
        hashes = {item.name: hashlib.sha256(item.read_bytes()).hexdigest() for item in starters}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "starters.html"
            render_starter_catalog(output)
            contents = output.read_text(encoding="utf-8")
            self.assertEqual(len(starters), 24)
            self.assertEqual(contents.count("assets/starters/"), 24)
            self.assertIn("Generic .oil-* primitives", contents)
            self.assertIn("oil-panel", contents)
            self.assertIn("Composition families", contents)
            self.assertIn("oil-relationship", contents)
            for sample in ("grid-fade", "grid-wide", "soft-spotlight", "block-field", "media-owned", "grid-full", "plain", "DOTS", "RING", "TRIANGLE", "SLASH", "NATURAL", "MUTED", "MONO", "CENTER", "INPUT"):
                self.assertIn(sample, contents)
            self.assertNotRegex(contents, r"(?:https?:)?//")
        self.assertEqual(hashes, {item.name: hashlib.sha256(item.read_bytes()).hexdigest() for item in starters})

    def test_cli_catalog_dispatch_and_list_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            theme = Path(directory) / "theme.html"
            starter = Path(directory) / "starter.html"
            command = [sys.executable, str(SCRIPTS / "oil_ppt.py")]
            for args in (("theme", "list", "--compact"), ("starter", "list", "--compact"), ("theme", "catalog", "--output", str(theme), "--compact"), ("starter", "catalog", "--output", str(starter), "--compact")):
                result = subprocess.run([*command, *args], cwd=ROOT.parent, check=True, text=True, capture_output=True)
                self.assertIn('"ok":true', result.stdout)
            self.assertTrue(theme.is_file())
            self.assertTrue(starter.is_file())

    def test_cli_catalog_defaults_are_user_home_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            command = [sys.executable, str(SCRIPTS / "oil_ppt.py")]
            environment = {**os.environ, "HOME": directory}
            for args, filename in (("theme", "oil-ppt-theme-catalog.html"), ("starter", "oil-ppt-starter-catalog.html")):
                subprocess.run([*command, args, "catalog", "--compact"], cwd=ROOT.parent, env=environment, check=True, text=True, capture_output=True)
                self.assertTrue((Path(directory) / filename).is_file())

    def test_overview_chrome_and_generated_deck_keep_one_slide_set(self) -> None:
        chrome = deck_chrome({"controls": {"next_preview": True, "click_navigation": True, "show_progress": True, "show_counter": True}})
        self.assertEqual(chrome.count("data-deck-overview"), 4)
        self.assertIn("aria-modal", chrome)
        runtime = (ROOT / "assets" / "runtime" / "deck.js").read_text(encoding="utf-8")
        css = (ROOT / "assets" / "runtime" / "deck.css").read_text(encoding="utf-8")
        self.assertNotIn("cloneNode", runtime)
        self.assertNotIn("deck-overview-thumb", runtime)
        for contract in ("openOverview", "closeOverview", "restoreSlides", "aria-current", "setAttribute(\"aria-current\", \"page\")", "inertAttribute", "overviewOpenerState", "Escape", "sizeOverviewSlides", "go(i)", "beforeprint", "event.metaKey", "event.ctrlKey", "event.altKey", "event.target instanceof Element", "event.key === \"Tab\""):
            self.assertIn(contract, runtime)
        self.assertIn("deck-overview-card", runtime)
        self.assertIn("deck-overview-hit", runtime)
        self.assertIn("@media print", css)
        self.assertIn(".deck-overview", css)
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "deck", "Overview")
            oil_ppt.slide_add(project, "one", "One", "statement", None)
            oil_ppt.slide_add(project, "two", "Two", "comparison", None)
            before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (project / "slides").glob("*.html")}
            preview = render_preview(project)
            rendered = preview.read_text(encoding="utf-8")
            self.assertEqual(rendered.count('<section class="oil-slide'), 2)
            self.assertEqual(rendered.count('<button class="deck-overview-toggle"'), 1)
            self.assertEqual(before, {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (project / "slides").glob("*.html")})

    @unittest.skipUnless(chrome_binary(), "Chrome/Chromium is required for overview focus regression")
    def test_overview_uses_inert_and_traps_tab_in_its_dialog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "deck", "Overview focus")
            oil_ppt.slide_add(project, "one", "One", "statement", None)
            oil_ppt.slide_add(project, "two", "Two", "comparison", None)
            first = project / "slides" / "one.html"
            first.write_text(first.read_text(encoding="utf-8").replace('<div class="slide-safe">', '<div class="slide-safe"><input aria-label="editable test">', 1), encoding="utf-8")
            preview = render_preview(project)
            import pptx_export
            process, profile_context, socket = pptx_export._browser_session(chrome_binary() or "", preview)
            try:
                pptx_export._cdp_command(socket, 1, "Runtime.enable")
                result = pptx_export._cdp_command(socket, 2, "Runtime.evaluate", {"awaitPromise": True, "returnByValue": True, "expression": r'''(async () => {
                  const nextFrame = () => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)));
                  const toggle = document.querySelector('[data-deck-overview-toggle]');
                  const dialog = document.querySelector('[data-deck-overview]');
                  const close = document.querySelector('[data-deck-overview-close]');
                  const stage = document.querySelector('.deck-stage');
                  const slides = [...document.querySelectorAll('.oil-slide')];
                  toggle.click(); await nextFrame();
                  const hits = [...document.querySelectorAll('[data-deck-overview-slide]')];
                  const focusable = [...document.querySelectorAll('button,input,textarea,select,[contenteditable]')]
                    .filter(node => node.getClientRects().length && !node.closest('[inert]'))
                    .map(node => node.matches('[data-deck-overview-close]') ? 'close' : node.matches('[data-deck-overview-slide]') ? 'hit' : 'other');
                  hits.at(-1).focus(); window.dispatchEvent(new KeyboardEvent('keydown', {key:'Tab', bubbles:true, cancelable:true}));
                  const forwardTrapped = document.activeElement === close;
                  close.focus(); window.dispatchEvent(new KeyboardEvent('keydown', {key:'Tab', shiftKey:true, bubbles:true, cancelable:true}));
                  const backwardTrapped = document.activeElement === hits.at(-1);
                  const current = hits.filter(hit => hit.getAttribute('aria-current') === 'page').length;
                  const openInert = slides.every(slide => slide.inert && slide.hasAttribute('inert')) && toggle.inert;
                  close.click(); await nextFrame();
                  const input = document.querySelector('input'); input.focus();
                  const letter = new KeyboardEvent('keydown', {key:'o', bubbles:true, cancelable:true}); input.dispatchEvent(letter);
                  return {forwardTrapped, backwardTrapped, current, openInert, focusable, restored: slides.every(slide => !slide.inert && !slide.hasAttribute('inert')) && !toggle.inert && [...stage.querySelectorAll(':scope > .oil-slide')].length === slides.length, editableUntouched: !letter.defaultPrevented && dialog.hidden};
                })()'''})
                value = result["result"].get("value")
                self.assertEqual(value, {"forwardTrapped": True, "backwardTrapped": True, "current": 1, "openInert": True, "focusable": ["close", "hit", "hit"], "restored": True, "editableUntouched": True})
            finally:
                socket.close()
                _stop_browser(process, Path(profile_context.name))
                profile_context.cleanup()


if __name__ == "__main__":
    unittest.main()
