from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from doctor import smoke_slides  # noqa: E402
from editor_bindings import editable_values, slot_pointer  # noqa: E402
from outline_schema import validate_outline  # noqa: E402
from render_outline_review import prepared_slide  # noqa: E402


class StructuredComponentTests(unittest.TestCase):
    templates = SKILL_ROOT / "assets" / "templates"
    base = {
        "title": "structured components",
        "palette": "oil-yellow",
        "typography": "clean",
        "shape": "soft",
        "click_navigation": False,
        "media_policy": "text-only",
    }

    def seed(self, template: str) -> dict:
        return copy.deepcopy(next(slide for slide in smoke_slides() if slide["template"] == template))

    def validate(self, slide: dict) -> None:
        validate_outline({**self.base, "slides": [slide]}, self.templates)

    def test_relationship_map_requires_one_center_and_one_link_per_peripheral(self) -> None:
        slide = self.seed("relationship-map")
        self.validate(slide)

        no_center = copy.deepcopy(slide)
        no_center["nodes"][0].pop("emphasis")
        with self.assertRaisesRegex(SystemExit, "exactly one"):
            self.validate(no_center)

        duplicate_link = copy.deepcopy(slide)
        duplicate_link["links"][2]["target"] = duplicate_link["links"][1]["target"]
        with self.assertRaisesRegex(SystemExit, "more than one center link"):
            self.validate(duplicate_link)

        padded_node_id = copy.deepcopy(slide)
        padded_node_id["nodes"][0]["id"] = " platform "
        with self.assertRaisesRegex(SystemExit, "canonical"):
            self.validate(padded_node_id)

        padded_link_id = copy.deepcopy(slide)
        padded_link_id["links"][0]["source"] = " platform "
        with self.assertRaisesRegex(SystemExit, "canonical"):
            self.validate(padded_link_id)

    def test_decision_matrix_requires_one_unique_winner(self) -> None:
        slide = self.seed("decision-matrix")
        self.validate(slide)

        tied = copy.deepcopy(slide)
        tied["options"][1]["scores"] = tied["options"][0]["scores"]
        with self.assertRaisesRegex(SystemExit, "unique recommendation"):
            self.validate(tied)

    def test_metric_variants_keep_variant_specific_inputs_closed(self) -> None:
        default = self.seed("metric")
        self.validate(default)

        delta = copy.deepcopy(default)
        delta["id"] = "metric-delta"
        delta["variant"] = "delta"
        delta["metric"].update({"change": "+12", "change_label": "较上月"})
        self.validate(delta)

        progress = copy.deepcopy(default)
        progress["id"] = "metric-progress"
        progress["variant"] = "progress"
        progress["metric"] = {
            "value": 86,
            "target": 100,
            "unit": "%",
            "caption": "当前值与目标值使用同一统计口径",
        }
        self.validate(progress)

        invalid = copy.deepcopy(progress)
        invalid["metric"]["value"] = "86"
        with self.assertRaisesRegex(SystemExit, "JSON number"):
            self.validate(invalid)

        extreme_ratio = copy.deepcopy(progress)
        extreme_ratio["metric"].update({"value": 1, "target": 5e-324})
        with self.assertRaisesRegex(SystemExit, "percentage must remain finite"):
            self.validate(extreme_ratio)

        boundary = copy.deepcopy(default)
        boundary["metric"]["value"] = "界" * 6
        self.validate(boundary)
        boundary["metric"]["value"] += "界"
        with self.assertRaisesRegex(SystemExit, "7/6 non-space characters"):
            self.validate(boundary)

    def test_program_owned_geometry_and_recommendation_are_rendered(self) -> None:
        relationship = self.seed("relationship-map")
        _, relationship_fragment = prepared_slide(relationship, 1)
        self.assertEqual(relationship_fragment.count('class="relationship-node oil-surface"'), 6)
        self.assertEqual(relationship_fragment.count('class="relationship-link"'), 5)
        self.assertIn('data-node-role="center"', relationship_fragment)
        self.assertEqual(relationship_fragment.count('data-relationship-arrow="'), 5)
        self.assertNotIn(' style=', relationship_fragment)

        decision = self.seed("decision-matrix")
        _, decision_fragment = prepared_slide(decision, 1)
        self.assertEqual(decision_fragment.count('data-recommended="true"'), 1)
        self.assertIn('<strong class="total-score">14', decision_fragment)

        progress = self.seed("metric")
        progress["id"] = "metric-progress"
        progress["variant"] = "progress"
        progress["metric"] = {"value": 86, "target": 100, "unit": "%", "caption": "同一口径"}
        _, progress_fragment = prepared_slide(progress, 1)
        self.assertIn('data-progress-fill x="0" y="0" width="86.00"', progress_fragment)
        self.assertNotIn(' style=', progress_fragment)
        self.assertRegex(progress_fragment, r'data-slot="metric-progress-label"[^>]*>86%')

    def test_text_editor_binds_copy_but_not_progress_numbers_or_scores(self) -> None:
        relationship = self.seed("relationship-map")
        self.assertEqual(slot_pointer(relationship, 0, "node-title-1"), "/slides/0/nodes/0/title")
        self.assertEqual(slot_pointer(relationship, 0, "link-label-1"), "/slides/0/links/0/label")

        decision = self.seed("decision-matrix")
        self.assertEqual(slot_pointer(decision, 0, "criterion-2"), "/slides/0/criteria/1")
        self.assertEqual(slot_pointer(decision, 0, "option-title-3"), "/slides/0/options/2/title")

        progress = self.seed("metric")
        progress["variant"] = "progress"
        progress["metric"] = {"value": 86, "target": 100, "unit": "%", "caption": "同一口径"}
        values = editable_values({"slides": [progress]})
        self.assertNotIn("/slides/0/metric/value", values)
        self.assertNotIn("/slides/0/metric/target", values)
        self.assertIn("/slides/0/metric/caption", values)


if __name__ == "__main__":
    unittest.main()
