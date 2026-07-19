from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from capability_recommender import slide_recommendation  # noqa: E402
from component_registry import (  # noqa: E402
    CLOSED_STRUCTURE_TEMPLATES,
    COMPONENT_CONTRACTS,
    COMPONENT_QUALITY,
    COMPONENT_SPECS,
    TEMPLATE_DISCOVERY,
    TEMPLATE_FAMILIES,
)
from doctor import smoke_slides  # noqa: E402
from editor_bindings import slot_pointer  # noqa: E402
from oil_ppt import component_fill_plan  # noqa: E402
from outline_schema import TEMPLATE_CONTENT_HELP, TEMPLATE_VISIBLE_FIELDS, validate_outline  # noqa: E402
from render_outline_review import prepared_slide  # noqa: E402


NAMES = {"evidence-matrix", "gantt-roadmap", "hierarchy-tree"}
BASE = {
    "title": "information relationships",
    "palette": "oil-yellow",
    "typography": "clean",
    "shape": "soft",
    "click_navigation": False,
    "media_policy": "text-only",
}


class InformationComponentTests(unittest.TestCase):
    templates = ROOT / "assets" / "templates"

    def seed(self, name: str) -> dict:
        return copy.deepcopy(next(slide for slide in smoke_slides() if slide["template"] == name))

    def validate(self, slide: dict) -> None:
        validate_outline({**BASE, "slides": [slide]}, self.templates)

    def assert_invalid(self, slide: dict, message: str) -> None:
        with self.assertRaisesRegex(SystemExit, message):
            self.validate(slide)

    def test_registry_and_authoring_projections_are_complete(self) -> None:
        for name in NAMES:
            with self.subTest(component=name):
                self.assertIn(name, COMPONENT_SPECS)
                self.assertIn(name, COMPONENT_CONTRACTS)
                self.assertIn(name, COMPONENT_QUALITY)
                self.assertIn(name, TEMPLATE_DISCOVERY)
                self.assertIn(name, TEMPLATE_FAMILIES)
                self.assertIn(name, TEMPLATE_CONTENT_HELP)
                self.assertIn(name, TEMPLATE_VISIBLE_FIELDS)
                self.assertIn(name, CLOSED_STRUCTURE_TEMPLATES)
                self.assertEqual(COMPONENT_CONTRACTS[name]["variants"], ("default",))
                self.assertTrue(COMPONENT_SPECS[name].native_visual)

                plan = component_fill_plan(name)
                self.assertEqual(plan["template"], name)
                self.assertEqual(plan["authoritative_constraints"], "input_schema+plan/check")
                self.assertTrue(plan["variants"]["default"]["minimum"])
                self.assertTrue(plan["variants"]["default"]["text_budgets_nonspace"])
                self.assertFalse(plan["input_schema"]["additionalProperties"])

    def test_generic_minimum_fixtures_validate_and_recommend(self) -> None:
        for name in NAMES:
            with self.subTest(component=name):
                slide = self.seed(name)
                self.validate(slide)
                recommendation = slide_recommendation(slide)
                self.assertIsNotNone(recommendation)
                self.assertEqual(recommendation["candidates"][0]["template"], name)
                self.assertEqual(recommendation["candidates"][0]["confidence"], "high")

    def test_evidence_matrix_rejects_duplicate_unknown_missing_and_fake_evidence(self) -> None:
        slide = self.seed("evidence-matrix")

        duplicate = copy.deepcopy(slide)
        duplicate["claims"][1]["id"] = duplicate["claims"][0]["id"]
        self.assert_invalid(duplicate, "claim ids must be unique")

        unknown = copy.deepcopy(slide)
        unknown["evidence"][0]["links"][0]["claim"] = "missing-claim"
        self.assert_invalid(unknown, "unknown claim")

        uncovered = copy.deepcopy(slide)
        uncovered["evidence"][1]["links"] = [uncovered["evidence"][1]["links"][1]]
        self.assert_invalid(uncovered, "without evidence")

        fake = copy.deepcopy(slide)
        fake["evidence"][0]["source"] = {"label": "Placeholder", "url": "https://example.com/evidence"}
        self.assert_invalid(fake, "real source")

        ignored = copy.deepcopy(slide)
        ignored["evidence"][0]["score"] = 5
        self.assert_invalid(ignored, "optional note only")

    def test_gantt_rejects_duplicate_keys_invalid_spans_and_links(self) -> None:
        slide = self.seed("gantt-roadmap")

        duplicate = copy.deepcopy(slide)
        duplicate["lanes"][1]["items"][0]["id"] = duplicate["lanes"][0]["items"][0]["id"]
        self.assert_invalid(duplicate, "task ids must be unique")

        reversed_span = copy.deepcopy(slide)
        reversed_span["lanes"][0]["items"][0].update({"start": "p3", "end": "p1"})
        self.assert_invalid(reversed_span, "invalid span")

        unknown_period = copy.deepcopy(slide)
        unknown_period["lanes"][0]["items"][0]["end"] = "p9"
        self.assert_invalid(unknown_period, "declared period ids")

        invalid_dependency = copy.deepcopy(slide)
        invalid_dependency["lanes"][1]["items"][0]["depends_on"] = ["missing-task"]
        self.assert_invalid(invalid_dependency, "invalid dependency link")

        late_dependency = copy.deepcopy(slide)
        late_dependency["lanes"][0]["items"][1]["depends_on"] = ["verify"]
        self.assert_invalid(late_dependency, "must finish before the task starts")

    def test_hierarchy_rejects_disconnected_cycles_extra_roots_and_excess_depth(self) -> None:
        slide = self.seed("hierarchy-tree")

        disconnected = copy.deepcopy(slide)
        disconnected["nodes"][1]["parent"] = "unknown"
        self.assert_invalid(disconnected, "invalid or missing parent link")

        extra_root = copy.deepcopy(slide)
        extra_root["nodes"][1].pop("parent")
        self.assert_invalid(extra_root, "exactly one root")

        cycle = copy.deepcopy(slide)
        cycle["nodes"][1]["parent"] = "documents"
        self.assert_invalid(cycle, "cycle or disconnected")

        deep = copy.deepcopy(slide)
        deep["nodes"][6]["parent"] = "documents"
        self.assert_invalid(deep, "at most three visible levels")

    def test_program_owned_rendering_and_optional_fields_collapse(self) -> None:
        evidence = self.seed("evidence-matrix")
        evidence["evidence"][0].pop("note")
        _, evidence_fragment = prepared_slide(evidence, 0)
        self.assertEqual(evidence_fragment.count('class="evidence-row oil-surface"'), 2)
        self.assertEqual(evidence_fragment.count('class="relation relation-'), 6)
        self.assertNotIn('data-slot="evidence-note-1"', evidence_fragment)
        self.assertNotIn(" style=", evidence_fragment)

        roadmap = self.seed("gantt-roadmap")
        roadmap["lanes"][0]["items"][0].pop("note")
        _, roadmap_fragment = prepared_slide(roadmap, 0)
        self.assertEqual(roadmap_fragment.count('class="roadmap-task '), 5)
        self.assertEqual(roadmap_fragment.count('class="roadmap-connector"'), 4)
        self.assertNotIn('data-slot="roadmap-note-1-1"', roadmap_fragment)
        self.assertIn("task-start-3 task-span-3", roadmap_fragment)
        self.assertNotIn(" style=", roadmap_fragment)

        hierarchy = self.seed("hierarchy-tree")
        _, hierarchy_fragment = prepared_slide(hierarchy, 0)
        self.assertEqual(hierarchy_fragment.count('class="tree-node oil-surface"'), 7)
        self.assertEqual(hierarchy_fragment.count('class="tree-connector"'), 6)
        self.assertNotIn('data-slot="tree-body-2"', hierarchy_fragment)
        self.assertNotIn(" style=", hierarchy_fragment)

    def test_editor_bindings_follow_semantic_reading_order(self) -> None:
        evidence = self.seed("evidence-matrix")
        self.assertEqual(slot_pointer(evidence, 0, "claim-title-2"), "/slides/0/claims/1/title")
        self.assertEqual(slot_pointer(evidence, 0, "evidence-source-1"), "/slides/0/evidence/0/source/label")

        roadmap = self.seed("gantt-roadmap")
        self.assertEqual(slot_pointer(roadmap, 0, "period-label-3"), "/slides/0/periods/2/label")
        self.assertEqual(slot_pointer(roadmap, 0, "roadmap-title-2-1"), "/slides/0/lanes/1/items/0/title")

        hierarchy = self.seed("hierarchy-tree")
        self.assertEqual(slot_pointer(hierarchy, 0, "tree-title-4"), "/slides/0/nodes/3/title")
        self.assertIsNone(slot_pointer(hierarchy, 0, "tree-body-2"))


if __name__ == "__main__":
    unittest.main()
