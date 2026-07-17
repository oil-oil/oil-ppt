"""Public contract CLI characterization tests."""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLI = SKILL_ROOT / "scripts" / "oil-ppt"


class ContractCliTests(unittest.TestCase):
    maxDiff = None

    def run_contract(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [str(CLI), "contract", *arguments],
            cwd=SKILL_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(
                f"contract {' '.join(arguments)} exited {result.returncode}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return result

    def compact_payload(self, *arguments: str) -> dict:
        result = self.run_contract(*arguments, "--compact")
        self.assertEqual(
            len(result.stdout.splitlines()),
            1,
            f"compact JSON must occupy one line: {result.stdout!r}",
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            self.fail(f"contract returned invalid JSON: {error}\n{result.stdout}")
        self.assertIsInstance(payload, dict)
        return payload

    def test_compact_selectors_emit_single_line_json(self) -> None:
        cases = (
            ("--list",),
            ("--family", "sequence"),
            ("--example",),
            ("--schema",),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                self.compact_payload(*arguments)

    def test_no_selector_preserves_complete_registry_contract(self) -> None:
        default_payload = self.compact_payload()
        all_payload = self.compact_payload("--all")
        self.assertEqual(default_payload.get("schema_version"), "oil-ppt.contract/v2")
        self.assertEqual(default_payload.get("schema_version"), all_payload.get("schema_version"))
        self.assertEqual(default_payload.get("families"), all_payload.get("families"))

    def test_all_emits_the_complete_registry(self) -> None:
        registry = self.compact_payload("--all")
        listing = self.compact_payload("--list")

        registry_names = [
            template["name"]
            for family in registry["families"].values()
            for template in family["templates"]
        ]
        listed_names = [
            template
            for family in listing["families"]
            for template in family["templates"]
        ]

        self.assertEqual(registry.get("schema_version"), "oil-ppt.contract/v2")
        self.assertEqual(registry.get("showing"), "all")
        self.assertEqual(len(registry_names), len(set(registry_names)))
        self.assertEqual(registry.get("template_count"), len(registry_names))
        self.assertEqual(set(registry_names), set(listed_names))

    def test_component_detail_links_schema_without_embedding_it(self) -> None:
        payload = self.compact_payload("--id", "cycle")
        fill_plan = payload["fill_plan"]

        self.assertNotIn("input_schema", fill_plan)
        self.assertIsInstance(fill_plan.get("input_schema_command"), str)
        self.assertTrue(fill_plan["input_schema_command"].strip())

    def test_component_schema_is_scoped_to_the_selected_template(self) -> None:
        schema = self.compact_payload("--id", "cycle", "--schema")

        self.assertEqual(schema.get("type"), "object")
        self.assertEqual(schema["properties"]["template"].get("const"), "cycle")
        self.assertNotIn("slides", schema["properties"])

    def test_schema_and_list_remain_mutually_exclusive(self) -> None:
        result = self.run_contract("--schema", "--list", check=False)
        self.assertNotEqual(result.returncode, 0)

    def test_structured_component_details_expose_minimal_fill_plans(self) -> None:
        relationship = self.compact_payload("--id", "relationship-map")
        decision = self.compact_payload("--id", "decision-matrix")
        metric = self.compact_payload("--id", "metric")

        self.assertEqual(set(relationship["fill_plan"]["variants"]), {"default"})
        self.assertEqual(set(decision["fill_plan"]["variants"]), {"default"})
        self.assertEqual(set(metric["fill_plan"]["variants"]), {"default", "delta", "progress"})
        self.assertIn("nodes", relationship["fill_plan"]["content_fields"])
        self.assertIn("criteria", decision["fill_plan"]["content_fields"])
        self.assertNotIn("visual_task", relationship["fill_plan"]["content_fields"])
        self.assertEqual(
            relationship["fill_plan"]["variants"]["default"]["required_one_of_top_level"],
            [["content", "note"]],
        )
        self.assertEqual(
            relationship["fill_plan"]["variants"]["default"]["field_shape"]["links[]"],
            {"source": "node-id", "target": "node-id", "label": "text"},
        )
        self.assertEqual(
            decision["fill_plan"]["variants"]["default"]["field_shape"]["options[]"]["scores[]"],
            "3 integers, each 1..5",
        )
        self.assertEqual(
            metric["fill_plan"]["variants"]["progress"]["field_shape"]["metric"]["target"],
            "number > 0",
        )


if __name__ == "__main__":
    unittest.main()
