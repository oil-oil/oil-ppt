"""Regression coverage for the airy visual system without page contracts."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "oil-ppt"
sys.path.insert(0, str(ROOT / "scripts"))

import oil_ppt  # noqa: E402
from project import init_project, read_deck  # noqa: E402
from theme import DIRECTIONS, theme_css, validate_theme  # noqa: E402
from workflow import confirm_outline  # noqa: E402


class AiryVisualSystemTests(unittest.TestCase):
    def test_five_directions_keep_theme_css_bytes_stable(self) -> None:
        tokens = {"palette": "ink-slate", "typography": "technical", "shape": "crisp"}
        with_direction = {**tokens, "direction": "fresh-default"}
        self.assertEqual(theme_css({"theme": tokens}), theme_css({"theme": with_direction}))
        self.assertEqual(validate_theme(tokens)["direction"], "fresh-default")
        self.assertEqual(set(DIRECTIONS), {
            "fresh-default", "editorial-story", "technical-system",
            "warm-friendly", "calm-research",
        })
        for direction in DIRECTIONS.values():
            self.assertTrue(direction["label"] and direction["description"])
            self.assertGreaterEqual(len(direction["principles"]), 3)
            self.assertEqual(set(direction["recommended"]), {"palette", "typography", "shape"})

    def test_direction_preset_then_explicit_override_preserves_standalone_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "deck", "Theme")
            oil_ppt.slide_add(project, "one", "One", "statement", None)
            source = (project / "slides" / "one.html").read_bytes()
            parser = oil_ppt.parser()
            args = parser.parse_args(["theme", "set", str(project), "--direction", "technical-system", "--shape", "soft"])
            # Exercise the public process, including its order of updates.
            import subprocess
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "oil_ppt.py"), "theme", "set", str(project), "--direction", "technical-system", "--shape", "soft", "--compact"], text=True, capture_output=True, check=True)
            self.assertTrue(json.loads(result.stdout)["ok"])
            _, deck = read_deck(project)
            self.assertEqual(deck["theme"], {"direction": "technical-system", "palette": "ink-slate", "typography": "technical", "shape": "soft"})
            self.assertEqual(source, (project / "slides" / "one.html").read_bytes())
            self.assertEqual(args.direction, "technical-system")

    def test_panel_is_quiet_by_default_and_strokes_are_opt_in(self) -> None:
        css = (ROOT / "assets" / "runtime" / "deck.css").read_text(encoding="utf-8")
        self.assertIn(".oil-panel{padding:var(--panel-padding,32px);border:0", css)
        self.assertIn('.oil-panel[data-stroke="hairline"]{border:1px solid var(--border)}', css)
        self.assertIn('.oil-panel[data-stroke="strong"]{border:2px solid var(--ink)}', css)
        self.assertNotRegex(css, r"(?<![a-z0-9_-])\.tag(?:\b|::)")
        self.assertNotRegex(css, r"(?<![a-z0-9_-])\.hl(?:\b|::)")
        self.assertIn(".oil-highlight", css)

    def test_advice_is_optional_and_cannot_change_status_next(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "deck", "Advice")
            confirm_outline(project)
            oil_ppt.slide_add(project, "one", "One", "feature-grid", None)
            path = project / "slides" / "one.html"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "/* OIL-SLIDE-CSS:END */",
                ".s-one .extra-a{border:2px solid var(--ink)}.s-one .extra-b{border:2px solid var(--ink)}\n/* OIL-SLIDE-CSS:END */",
            ), encoding="utf-8")
            status = oil_ppt.status_payload(project)
            self.assertEqual(status["next"]["action"], "author_slides")
            self.assertTrue(status["style_advice"])
            self.assertNotIn("style_advice", status["next"])
            self.assertEqual(oil_ppt.slide_check(project)["style_advice"], status["style_advice"])

    def test_twenty_four_starters_have_guidance_families_and_copy_without_rewrite(self) -> None:
        listing = oil_ppt.starter_list()
        self.assertEqual(len(listing["starters"]), 24)
        self.assertEqual(set(listing["starters"]), set(listing["guidance"]))
        self.assertGreaterEqual(len(listing["composition_families"]), 4)
        self.assertEqual(set().union(*map(set, listing["composition_families"].values())), set(listing["starters"]))
        self.assertIn("替换全部示例", listing["instruction"])
        self.assertIn("四个及以上等宽单元", listing["instruction"])
        self.assertIn("第二层信息", listing["guidance"]["process-rail"])
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "deck", "Starters")
            first = None
            for index, name in enumerate(listing["starters"], 1):
                result = oil_ppt.slide_add(project, f"s{index}", name, name, None)
                first = first or result
            self.assertEqual(len(oil_ppt.slide_check(project)["slides"]), 24)
            self.assertIn("替换 starter 中的全部示例", first["next"]["brief"])
            confirm_outline(project)
            self.assertIn("不得只改标题", oil_ppt.status_payload(project)["next"]["brief"])

    def test_four_up_rails_with_repeated_second_layers_receive_advice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "deck", "Rail load")
            oil_ppt.slide_add(project, "rail", "Rail", "process-rail", None)
            path = project / "slides" / "rail.html"
            text = path.read_text(encoding="utf-8")
            text = text.replace(
                "</article>",
                '<div class="guard">阶段护栏必须写出范围和证据。</div></article>',
            )
            path.write_text(text, encoding="utf-8")
            rules = {item["rule"] for item in oil_ppt.slide_check(project)["style_advice"]}
            self.assertIn("overloaded-repeated-lanes", rules)

    def test_three_decorated_surfaces_receive_nonblocking_advice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "deck", "Decor advice")
            confirm_outline(project)
            oil_ppt.slide_add(project, "one", "One", "statement", None)
            path = project / "slides" / "one.html"
            text = path.read_text(encoding="utf-8").replace(
                '<div class="slide-safe">',
                '<div class="slide-safe"><div class="oil-surface" data-decor="dots"></div><div class="oil-panel" data-motif="ring"></div><div class="oil-surface" data-motif="slash"></div>',
                1,
            )
            path.write_text(text, encoding="utf-8")
            result = oil_ppt.slide_check(project)
            self.assertEqual(oil_ppt.status_payload(project)["next"]["action"], "author_slides")
            self.assertIn("overdecorated-surfaces", {item["rule"] for item in result["style_advice"]})

    def test_mixed_surface_craft_is_advice_not_a_workflow_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "deck", "Mixed craft")
            confirm_outline(project)
            oil_ppt.slide_add(project, "one", "One", "statement", None)
            path = project / "slides" / "one.html"
            path.write_text(path.read_text(encoding="utf-8").replace('<div class="slide-safe">', '<div class="slide-safe"><div class="oil-surface" data-decor="dots" data-motif="ring"></div>', 1), encoding="utf-8")
            self.assertEqual(oil_ppt.status_payload(project)["next"]["action"], "author_slides")
            self.assertIn("mixed-surface-decoration", {item["rule"] for item in oil_ppt.slide_check(project)["style_advice"]})

    def test_advice_understands_custom_card_walls_and_nested_dark_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "deck", "Custom advice")
            for slide_id in ("one", "two"):
                oil_ppt.slide_add(project, slide_id, slide_id, "feature-grid", None)
                path = project / "slides" / f"{slide_id}.html"
                text = path.read_text(encoding="utf-8")
                text = text.replace(
                    "/* OIL-SLIDE-CSS:END */",
                    f".s-{slide_id} .custom-grid{{display:grid;grid-template-columns:repeat(3,1fr)}}"
                    f".s-{slide_id} .custom-card{{border:1px solid #ddd;border-radius:12px;box-shadow:0 4px 12px #ddd}}"
                    f".s-{slide_id} .frame{{background:#17302b}}.s-{slide_id} .dark-a{{background:#22443b}}.s-{slide_id} .dark-b{{background:#10241f}}\n"
                    "/* OIL-SLIDE-CSS:END */",
                )
                text = text.replace('class="features"', 'class="features custom-grid"')
                text = text.replace('class="feature"', 'class="feature custom-card"')
                path.write_text(text, encoding="utf-8")
            rules = {item["rule"] for item in oil_ppt.slide_check(project)["style_advice"]}
            self.assertIn("equal-card-wall", rules)
            self.assertIn("repeated-card-silhouette", rules)
            self.assertIn("nested-dark-surfaces", rules)

    def test_annotated_showcase_keeps_visible_example_copy_in_dom(self) -> None:
        starter = (ROOT / "assets" / "starters" / "annotated-showcase.html").read_text(encoding="utf-8")
        self.assertIn('<span class="artifact-label">关键证据或界面</span>', starter)
        self.assertNotIn('content:"关键证据或界面"', starter)

    def test_sequence_numbers_are_real_microcopy_text(self) -> None:
        starter = (ROOT / "assets" / "starters" / "sequence.html").read_text(encoding="utf-8")
        self.assertEqual(starter.count('class="step-number" data-microcopy="index"'), 4)
        self.assertNotIn("content:attr(data-step)", starter)
        self.assertNotIn("data-step=", starter)

    def test_repeated_visible_escape_sequences_require_semantic_intent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "deck", "Escapes")
            oil_ppt.slide_add(project, "one", "One", "statement", None)
            path = project / "slides" / "one.html"
            original = path.read_text(encoding="utf-8")
            broken = original.replace("一句清晰、可被记住的主张。", r"first\nsecond\nthird")
            path.write_text(broken, encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "literal escape sequences"):
                oil_ppt.slide_check(project)
            path.write_text(original.replace("一句清晰、可被记住的主张。", r'<code data-literal-escape="true">first\nsecond\nthird</code>'), encoding="utf-8")
            self.assertEqual(oil_ppt.slide_check(project)["checked"], 1)


if __name__ == "__main__":
    unittest.main()
