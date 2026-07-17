from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from capability_catalog import TEMPLATE_DISCOVERY, VARIANT_HELP  # noqa: E402
from component_registry import (  # noqa: E402
    CLOSED_STRUCTURE_TEMPLATES,
    COMPONENT_CONTRACTS,
    COMPONENT_QUALITY,
    COMPONENT_SPECS,
    MEDIA_TEMPLATES,
    PAGE_BLEND_TEMPLATES,
    TEMPLATE_FAMILIES,
    VARIANT_QUALITY,
)
from design_quality import audit_outline, has_native_visual  # noqa: E402


class ComponentRegistryTests(unittest.TestCase):
    def test_every_public_projection_comes_from_the_same_registry(self) -> None:
        names = set(COMPONENT_SPECS)
        self.assertEqual(names, set(COMPONENT_CONTRACTS))
        self.assertEqual(names, set(COMPONENT_QUALITY))
        self.assertEqual(names, set(TEMPLATE_FAMILIES))
        self.assertEqual(names, set(TEMPLATE_DISCOVERY))

        for name, spec in COMPONENT_SPECS.items():
            with self.subTest(component=name):
                self.assertEqual(COMPONENT_CONTRACTS[name]["use_when"], spec.use_when)
                self.assertEqual(COMPONENT_CONTRACTS[name]["variants"], spec.variants)
                self.assertEqual(COMPONENT_CONTRACTS[name]["decorations"], spec.decorations)
                self.assertEqual(COMPONENT_QUALITY[name]["silhouette"], spec.silhouette)
                self.assertEqual(TEMPLATE_FAMILIES[name], spec.family)
                self.assertEqual(TEMPLATE_DISCOVERY[name]["aliases"], list(spec.aliases))
                self.assertEqual(TEMPLATE_DISCOVERY[name]["effects"], list(spec.effects))
                self.assertEqual(TEMPLATE_DISCOVERY[name]["avoid_when"], spec.avoid_when)
                self.assertEqual(name in MEDIA_TEMPLATES, spec.media)
                self.assertEqual(name in PAGE_BLEND_TEMPLATES, spec.page_blend)
                self.assertEqual(name in CLOSED_STRUCTURE_TEMPLATES, spec.closed_structure)
                self.assertTrue(set(spec.native_visual_variants).issubset(spec.variants))
                if spec.variant_quality:
                    self.assertEqual(set(VARIANT_QUALITY[name]), set(spec.variants))
                if spec.variant_help:
                    self.assertEqual(set(VARIANT_HELP[name]), set(spec.variants))

    def test_new_structured_components_have_small_explicit_choices(self) -> None:
        self.assertEqual(COMPONENT_SPECS["relationship-map"].variants, ("default",))
        self.assertEqual(COMPONENT_SPECS["decision-matrix"].variants, ("default",))
        self.assertEqual(COMPONENT_SPECS["metric"].variants, ("default", "delta", "progress"))
        self.assertTrue(COMPONENT_SPECS["relationship-map"].closed_structure)
        self.assertTrue(COMPONENT_SPECS["decision-matrix"].closed_structure)

    def test_native_visual_media_gate_is_registry_owned(self) -> None:
        for name in ("relationship-map", "decision-matrix"):
            with self.subTest(component=name):
                slide = {
                    "id": name,
                    "title": name,
                    "template": name,
                    "variant": "default",
                    "decor": "none",
                }
                self.assertTrue(has_native_visual(slide))
                issues = audit_outline({"media_policy": "required", "slides": [slide]})
                self.assertFalse(any(issue["code"] == "media-required" for issue in issues))

        self.assertTrue(has_native_visual({"template": "case-study-board", "variant": "chart"}))
        self.assertFalse(has_native_visual({"template": "case-study-board", "variant": "evidence"}))


if __name__ == "__main__":
    unittest.main()
