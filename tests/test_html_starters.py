"""Static contract checks for HTML starters and generic runtime components."""
from __future__ import annotations

import json
import hashlib
import re
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "oil-ppt"
STARTERS = ROOT / "assets" / "starters"
RUNTIME_CSS = ROOT / "assets" / "runtime" / "deck.css"
RUNTIME_JS = ROOT / "assets" / "runtime" / "deck.js"
sys.path.insert(0, str(ROOT / "scripts"))

import oil_ppt  # noqa: E402
from catalog import render_starter_catalog  # noqa: E402
from preview_deck import render_preview  # noqa: E402
from project import init_project  # noqa: E402
NAMES = (
    "blank", "statement", "title-media", "comparison", "sequence",
    "data", "evidence", "section", "ending",
    "problem-canvas", "converge", "process-rail", "feature-grid",
    "annotated-showcase", "browser-showcase",
    "editorial-feature", "relationship-map", "hierarchy-tree", "cycle", "metric-spotlight", "quote-focus",
    "step-focus", "bleed-split", "media-collage",
)


class HtmlStarterTests(unittest.TestCase):
    def starter_text(self, name: str) -> str:
        return (STARTERS / f"{name}.html").read_text(encoding="utf-8")

    def test_starters_have_the_standalone_slide_shape(self) -> None:
        self.assertGreaterEqual({path.stem for path in STARTERS.glob("*.html")}, set(NAMES))
        for name in NAMES:
            html = self.starter_text(name)
            with self.subTest(name=name):
                self.assertEqual(html.count("OIL-SLIDE-CSS:START"), 1)
                self.assertEqual(html.count("OIL-SLIDE-CSS:END"), 1)
                self.assertEqual(html.count("OIL-SLIDE:START"), 1)
                self.assertEqual(html.count("OIL-SLIDE:END"), 1)
                self.assertEqual(html.count('<section class="oil-slide s-__ID__"'), 1)
                self.assertEqual(html.count('data-slide-id="__ID__"'), 1)
                self.assertEqual(html.count('data-title="__TITLE__"'), 1)
                self.assertEqual(html.count('class="slide-safe"'), 1)

    def test_starters_expose_only_copy_time_identity_tokens(self) -> None:
        token_re = re.compile(r"__([A-Z0-9_]+)__")
        for name in NAMES:
            html = self.starter_text(name)
            with self.subTest(name=name):
                self.assertEqual(set(token_re.findall(html)), {"ID", "TITLE"})

    def test_starter_css_is_page_scoped(self) -> None:
        for name in NAMES:
            html = self.starter_text(name)
            css = html.split("OIL-SLIDE-CSS:START", 1)[1].split("OIL-SLIDE-CSS:END", 1)[0]
            css = re.sub(r"/\*.*?\*/", "", css, flags=re.S).replace("*/", "")
            selectors = [part.strip() for part in re.findall(r"([^{}]+)\{", css) if part.strip()]
            with self.subTest(name=name):
                self.assertTrue(selectors)
                self.assertTrue(all(selector.startswith(".s-__ID__") for selector in selectors))

    def test_starters_use_local_runtime_only(self) -> None:
        external = re.compile(r"(?:https?:)?//|url\s*\(", re.I)
        for name in NAMES:
            html = self.starter_text(name)
            with self.subTest(name=name):
                self.assertIsNone(external.search(html))
                self.assertEqual(html.count("<script"), 1)
                self.assertIn('src="../runtime/deck.js"', html)
                self.assertIn('href="../runtime/deck.css"', html)
                self.assertIn('href="../runtime/theme.css"', html)

    def test_runtime_exposes_stage_and_generic_components(self) -> None:
        css = RUNTIME_CSS.read_text(encoding="utf-8")
        js = RUNTIME_JS.read_text(encoding="utf-8")
        self.assertRegex(css, r"width:\s*1920px")
        self.assertRegex(css, r"height:\s*1080px")
        for component in (
            "stack", "grid", "panel", "metric", "quote", "media", "browser",
            "code", "label", "icon", "connector", "timeline", "chart", "table",
            "bleed", "relationship", "relationship-node", "relationship-link", "shape-window",
        ):
            self.assertIn(f".oil-{component}", css)
        for token in ("--oil-text-body", "--oil-text-compact", "--oil-text-caption"):
            self.assertIn(token, css)
        for behavior in ("scaleStage", "show(", "hashchange", "keydown", "validateLayout"):
            self.assertIn(behavior, js)
        self.assertNotIn("applyPreferredTextSize", js)

    def test_runtime_restores_airy_background_media_and_surface_contracts(self) -> None:
        css = RUNTIME_CSS.read_text(encoding="utf-8")
        for contract in (
            'data-bg="grid-fade"', 'data-bg="grid-wide"', 'data-bg="soft-spotlight"', 'data-bg="block-field"',
            'data-bg="media-owned"', 'data-bg="grid-full"', 'data-bg="plain"', 'data-decor="dots"',
            'data-motif="ring"', 'data-motif="triangle"', 'data-motif="slash"', 'data-media-treatment="natural"',
            'data-media-treatment="muted"', 'data-media-treatment="mono"', 'data-overlay="left-fade"',
            'data-mask="soft-edges"',
        ):
            self.assertIn(contract, css)

    def test_process_rail_models_one_shared_second_layer(self) -> None:
        source = self.starter_text("process-rail")
        self.assertEqual(source.count('class="step"'), 4)
        self.assertEqual(source.count('class="rail-note"'), 1)
        self.assertIn("补充信息只出现一次", source)
        self.assertNotIn('class="guard"', source)

    def test_relationship_map_centers_the_core_with_grid_and_svg_connectors(self) -> None:
        source = self.starter_text("relationship-map")
        self.assertIn('grid-template-areas:"a . b" ". center ." "c . d"', source)
        self.assertIn(".s-__ID__ .center{grid-area:center;justify-self:center", source)
        self.assertIn('viewBox="0 0 1760 762"', source)
        self.assertEqual(source.count('class="connector"'), 4)
        self.assertNotIn(".s-__ID__ .l1", source)

    def test_starter_deck_contains_deck_level_metadata(self) -> None:
        data = json.loads((ROOT / "assets" / "starter" / "deck.json").read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"title", "lang", "theme", "controls", "slides"})
        self.assertEqual(data["slides"], [])
        self.assertEqual(set(data["theme"]), {"palette", "typography", "shape", "direction"})
        self.assertEqual(data["theme"]["direction"], "fresh-default")
        self.assertEqual(
            set(data["controls"]),
            {"next_preview", "click_navigation", "show_progress", "show_counter"},
        )

    def test_every_starter_renders_together_without_rewriting_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = init_project(Path(temporary) / "deck", "Starter browser QA")
            for index, name in enumerate(NAMES, start=1):
                oil_ppt.slide_add(project, f"s{index}", f"{name} QA", name, None)
            hashes = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (project / "slides").glob("*.html")
            }
            preview = render_preview(project)
            self.assertTrue(preview.is_file())
            self.assertEqual(
                hashes,
                {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (project / "slides").glob("*.html")},
            )

    def test_component_catalog_examples_use_the_full_slide_scale(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = render_starter_catalog(Path(temporary) / "catalog.html")
            source = output.read_text(encoding="utf-8")
            self.assertGreaterEqual(source.count("min-height:1080px"), 7)
            self.assertEqual(source.count('class="card wide"'), 4)
            self.assertIn("catalog-media-owned-sample", source)
            self.assertNotIn("min-height:190px;padding:22px", source)

    def test_media_treatments_apply_to_images_and_video(self) -> None:
        css = RUNTIME_CSS.read_text(encoding="utf-8")
        for treatment in ("natural", "muted", "mono"):
            self.assertIn(f'.oil-media[data-media-treatment="{treatment}"]>video', css)


if __name__ == "__main__":
    unittest.main()
