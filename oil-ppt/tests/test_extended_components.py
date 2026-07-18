"""Regression coverage for the reusable extended oil-ppt components."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from component_registry import CLOSED_STRUCTURE_TEMPLATES, COMPONENT_SPECS  # noqa: E402
from component_contracts import effective_media_surface  # noqa: E402
from doctor import smoke_slides  # noqa: E402
from editor_bindings import editable_values  # noqa: E402
from media_plan import MEDIA_SLOTS  # noqa: E402
from outline_schema import validate_outline  # noqa: E402
from render_outline_review import prepared_slide  # noqa: E402


NAMES = {
    "artifact-focus",
    "project-card-grid", "brand-matrix", "dialogue-vs-task",
    "dual-table-matrix", "code-to-render", "step-hero",
}
BASE = {
    "title": "component probe", "palette": "dusty-plum", "typography": "editorial",
    "shape": "crisp", "media_policy": "required", "click_navigation": False,
}


class ExtendedComponentTests(unittest.TestCase):
    def seed(self, name: str) -> dict:
        return copy.deepcopy(next(slide for slide in smoke_slides() if slide["template"] == name))

    def validate(self, slide: dict) -> None:
        validate_outline({**BASE, "slides": [slide]}, ROOT / "assets" / "templates")

    def assert_invalid(self, slide: dict) -> None:
        with self.assertRaises(SystemExit):
            self.validate(slide)

    def test_registry_families_and_closed_structure(self) -> None:
        self.assertTrue(NAMES <= CLOSED_STRUCTURE_TEMPLATES)
        self.assertEqual(COMPONENT_SPECS["project-card-grid"].family, "collection")
        self.assertEqual(COMPONENT_SPECS["brand-matrix"].family, "collection")
        self.assertEqual(COMPONENT_SPECS["dialogue-vs-task"].family, "comparison")
        self.assertEqual(COMPONENT_SPECS["dual-table-matrix"].family, "comparison")
        self.assertEqual(COMPONENT_SPECS["code-to-render"].family, "compound")
        self.assertEqual(COMPONENT_SPECS["step-hero"].family, "sequence")

    def test_generic_smoke_seeds_validate(self) -> None:
        for name in NAMES:
            with self.subTest(component=name):
                self.validate(self.seed(name))

    def test_variable_collections_hide_unused_cells(self) -> None:
        _, brand = prepared_slide(self.seed("brand-matrix"), 0)
        _, tables = prepared_slide(self.seed("dual-table-matrix"), 0)
        self.assertEqual(brand.count("brand-card is-empty"), 5)
        self.assertEqual(tables.count("row is-empty"), 3)
        self.assertNotIn("is-empty is-empty", brand)
        self.assertNotIn("is-empty is-empty", tables)

    def test_brand_groups_keep_their_own_rows(self) -> None:
        slide = self.seed("brand-matrix")
        slide["groups"] = [
            {"title": "海外", "items": [{"title": name, "meta": "海外工具"} for name in ("A", "B", "C")]},
            {"title": "国内", "items": [{"title": name, "meta": "国内工具"} for name in ("Qoder", "D", "E", "F")]},
        ]
        _, fragment = prepared_slide(slide, 0, authoring=True)
        first = fragment.split('data-brand-group="1"', 1)[1].split('data-brand-group="2"', 1)[0]
        second = fragment.split('data-brand-group="2"', 1)[1]
        self.assertEqual(fragment.count("<section"), 1)
        self.assertIn('data-count="3"', fragment)
        self.assertIn('data-count="4"', fragment)
        self.assertNotIn("Qoder", first)
        self.assertIn("Qoder", second)

    def test_dual_table_hides_fourth_row_when_only_three_exist(self) -> None:
        slide = self.seed("dual-table-matrix")
        slide["tables"][0]["rows"].append(["风险", "已记录"])
        _, fragment = prepared_slide(slide, 0)
        self.assertRegex(fragment, r'class="row is-empty"[^>]*>\s*<b[^>]*data-slot="left-label-4"')
        self.assertRegex(fragment, r'class="row"[^>]*data-highlight="true"[^>]*>\s*<b[^>]*data-slot="left-label-3"')

    def test_closed_counts_and_nested_fields_are_rejected(self) -> None:
        brand = self.seed("brand-matrix")
        brand["groups"][0]["items"] = brand["groups"][0]["items"][:2]
        self.assert_invalid(brand)
        tables = self.seed("dual-table-matrix")
        tables["tables"][0]["rows"] = tables["tables"][0]["rows"][:1]
        self.assert_invalid(tables)
        code = self.seed("code-to-render")
        code["panels"].pop()
        self.assert_invalid(code)
        cards = self.seed("project-card-grid")
        cards["cards"][0]["hidden"] = "not rendered"
        self.assert_invalid(cards)

    def test_code_source_is_escaped_and_both_panels_render(self) -> None:
        slide = self.seed("code-to-render")
        slide["panels"][0]["source"] = "<script>alert(1)</script>"
        _, fragment = prepared_slide(slide, 0, authoring=True)
        self.assertNotIn("<script>alert(1)</script>", fragment)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", fragment)
        self.assertIn("## 标题", fragment)
        paths = editable_values({"slides": [slide]})
        self.assertIn("/slides/0/panels/0/source", paths)
        self.assertIn("/slides/0/panels/1/source", paths)

    def test_step_hero_media_contract(self) -> None:
        slot = MEDIA_SLOTS["step-hero"]
        self.assertEqual(slot["ratio"], "4:5")
        self.assertEqual(slot["fit"], "contain")
        self.assertEqual(slot["fidelity"], "illustrative")
        _, fragment = prepared_slide(self.seed("step-hero"), 0, authoring=True)
        self.assertIn('class="media oil-media"', fragment)
        for index in range(1, 5):
            self.assertIn(f'data-slot="point-{index}"', fragment)
        self.assertRegex(fragment, r'class="point is-empty"[^>]*data-slot="point-4"')
        copy, media = fragment.split("<!-- OIL-VISUAL:main:START -->", 1)
        self.assertIn('data-slot="conclusion"', copy)
        self.assertNotIn('data-slot="conclusion"', media)
        self.assertNotIn('data-slot="caption"', fragment)

    def test_artifact_focus_is_large_page_blend_media_without_qr_fields(self) -> None:
        slide = self.seed("artifact-focus")
        self.validate(slide)
        self.assertEqual(COMPONENT_SPECS["artifact-focus"].family, "focal")
        self.assertEqual(COMPONENT_SPECS["artifact-focus"].silhouette, "artifact-focus")
        self.assertEqual(effective_media_surface(slide), "page-blend")
        self.assertEqual(MEDIA_SLOTS["artifact-focus"]["fit"], "contain")
        css, fragment = prepared_slide(slide, 0, authoring=True)
        self.assertIn("height:754px", css)
        self.assertIn('<img class="oil-stock-visual"', fragment)
        self.assertNotIn("artifact-title", fragment)
        self.assertNotIn("artifact-body", fragment)


if __name__ == "__main__":
    unittest.main()
