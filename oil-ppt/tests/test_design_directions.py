from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import text_editor  # noqa: E402
from design_directions import DESIGN_DIRECTIONS, registry_issues  # noqa: E402
from oil_ppt import atomic_write_json, preview_state_path, project_state_path  # noqa: E402
from palette_tokens import PALETTES, custom_palette  # noqa: E402
from profile_tokens import SHAPE_PROFILES, TYPE_PROFILES  # noqa: E402
from render_outline_review import render  # noqa: E402


def outline_data(*, palette: object = "oil-yellow", palette_source: str | None = None) -> dict:
    data = {
        "title": "设计方向测试",
        "palette": palette,
        "typography": "clean",
        "shape": "soft",
        "media_policy": "text-only",
        "click_navigation": False,
        "slides": [{
            "id": "section",
            "title": "一个清楚的章节",
            "content": "用真实模板验证设计设置。",
            "template": "section",
            "variant": "default",
            "decor": "none",
        }],
    }
    if palette_source:
        data["palette_source"] = palette_source
    return data


class DesignDirectionRegistryTests(unittest.TestCase):
    def test_registry_is_unique_complete_and_legal(self) -> None:
        self.assertEqual(registry_issues(), [])
        self.assertGreaterEqual(len(DESIGN_DIRECTIONS), 5)
        self.assertEqual(len({item.id for item in DESIGN_DIRECTIONS}), len(DESIGN_DIRECTIONS))
        self.assertEqual(
            len({(item.palette, item.typography, item.shape) for item in DESIGN_DIRECTIONS}),
            len(DESIGN_DIRECTIONS),
        )
        for item in DESIGN_DIRECTIONS:
            with self.subTest(direction=item.id):
                self.assertIn(item.palette, PALETTES)
                self.assertIn(item.typography, TYPE_PROFILES)
                self.assertIn(item.shape, SHAPE_PROFILES)
                self.assertTrue(item.label and item.use_when and item.visual)


class EditorDesignTransactionTests(unittest.TestCase):
    @contextmanager
    def editor(self, data: dict):
        with tempfile.TemporaryDirectory(prefix="oil-ppt-design-editor-") as temporary:
            project = Path(temporary)
            outline = project / "outline.json"
            atomic_write_json(outline, data)
            atomic_write_json(project_state_path(project), {"visual_plan": {"outline_sha256": "initial"}})

            def fake_preview(_project: Path, target: Path, *_args: object, **_kwargs: object) -> None:
                target.write_text("<!doctype html><title>new preview</title>", encoding="utf-8")
                atomic_write_json(preview_state_path(outline), {
                    "preview": str(target),
                    "confirmed": False,
                })

            with (
                mock.patch.object(text_editor, "outline_confirmation_valid", return_value=True),
                mock.patch.object(text_editor, "visual_plan_valid", return_value=True),
                mock.patch.object(text_editor, "preview_state_status", return_value=("awaiting-confirmation", {}, None)),
                mock.patch.object(text_editor, "enforce_outline_quality"),
                mock.patch.object(text_editor, "verify_outline_media"),
                mock.patch.object(text_editor, "generate_preview", side_effect=fake_preview),
            ):
                session = text_editor.EditorSession(project)
                try:
                    yield session, outline
                finally:
                    session.close()

    def test_server_rejects_unknown_or_mixed_setting_values_atomically(self) -> None:
        with self.editor(outline_data()) as (session, _outline):
            original = copy.deepcopy(session.data)
            invalid = (
                {"direction": "freeform"},
                {"palette": "neon-rainbow"},
                {"typography": "comic"},
                {"shape": "floating-cards"},
                {"palette": "oil-yellow", "shape": "soft"},
                {"layout": "drag-anywhere"},
            )
            for payload in invalid:
                with self.subTest(payload=payload), self.assertRaises(ValueError):
                    session.apply_settings(payload)
                self.assertEqual(session.data, original)
                self.assertFalse(session.history)
                self.assertFalse(session.draft_path.exists())

    def test_settings_share_draft_undo_redo_and_discard(self) -> None:
        with self.editor(outline_data()) as (session, _outline):
            changed = session.apply_settings({"palette": "ink-slate"})
            self.assertTrue(changed["draft"])
            self.assertEqual(changed["changed_settings"], ["palette"])
            self.assertTrue(changed["can_undo"])

            undone = session.undo()
            self.assertEqual(session.data["palette"], "oil-yellow")
            self.assertFalse(undone["draft"])
            self.assertTrue(undone["can_redo"])

            session.redo()
            self.assertEqual(session.data["palette"], "ink-slate")
            self.assertTrue(session.draft_path.is_file())

            discarded = session.discard()
            self.assertEqual(session.data["palette"], "oil-yellow")
            self.assertFalse(discarded["draft"])
            self.assertFalse(discarded["can_undo"])

    def test_settings_only_finish_writes_outline_and_unconfirmed_preview(self) -> None:
        with self.editor(outline_data()) as (session, outline):
            session.apply_settings({"typography": "editorial"})
            result = session.finish([], report_complete=True)
            saved = json.loads(outline.read_text(encoding="utf-8"))
            preview_state = json.loads(preview_state_path(outline).read_text(encoding="utf-8"))

            self.assertTrue(result["changed"])
            self.assertEqual(saved["typography"], "editorial")
            self.assertFalse(preview_state["confirmed"])
            self.assertFalse(session.draft_path.exists())

    def test_custom_palette_stays_locked_until_explicit_palette_choice(self) -> None:
        brand = custom_palette("#2255AA", "#EEF4FF", "#173263")
        with self.editor(outline_data(palette=brand, palette_source="brand")) as (session, _outline):
            initial = copy.deepcopy(session.data["palette"])
            state = session.state()
            self.assertTrue(state["settings"]["palette"]["locked"])
            self.assertEqual(state["settings"]["palette"]["source"], "brand")

            session.apply_settings({"typography": "editorial"})
            self.assertEqual(session.data["palette"], initial)
            self.assertEqual(session.data["palette_source"], "brand")

            session.apply_settings({"direction": "technical-system"})
            self.assertEqual(session.data["palette"], "ocean-cobalt")
            self.assertNotIn("palette_source", session.data)
            session.undo()
            self.assertEqual(session.data["palette"], initial)
            self.assertEqual(session.data["palette_source"], "brand")


class DesignSummaryHtmlTests(unittest.TestCase):
    def test_authoring_and_formal_preview_show_the_same_read_only_summary(self) -> None:
        data = outline_data()
        authoring = render(data, authoring=True, editor_token="token", editor_recovery_id="recovery")
        formal = render(data)

        for preview in (authoring, formal):
            with self.subTest(authoring=preview is authoring):
                self.assertIn('class="design-summary"', preview)
                self.assertIn('data-readonly-design-summary', preview)
                self.assertIn('aria-label="当前视觉"', preview)
                self.assertIn("当前视觉：", preview)
                self.assertIn("清爽默认", preview)
                self.assertIn("明亮黄", preview)
                self.assertIn("清爽无衬线", preview)
                self.assertIn("柔和圆角", preview)
                self.assertIn("需要调整，直接告诉 Agent。", preview)
                self.assertNotIn('class="design-panel"', preview)
                self.assertNotIn('data-design-direction="', preview)
                self.assertNotIn('data-design-setting="', preview)
                self.assertNotIn("/api/settings", preview)

        self.assertIn('aria-label="内容编辑工具栏"', authoring)
        self.assertNotIn('aria-label="内容与设计编辑工具栏"', authoring)

    def test_summary_describes_matching_direction(self) -> None:
        data = outline_data(palette="glacier-teal")
        data["shape"] = "crisp"
        authoring = render(data, authoring=True, editor_token="token", editor_recovery_id="recovery")

        self.assertIn("冷静研究", authoring)
        self.assertIn("冰川青", authoring)
        self.assertIn("清爽无衬线", authoring)
        self.assertIn("利落圆角", authoring)
        self.assertIn("视觉影响：冰川青、低对比表面与清晰边界。", authoring)

    def test_custom_palette_is_identified_without_exposing_replacement_controls(self) -> None:
        data = outline_data(
            palette=custom_palette("#2255AA", "#EEF4FF", "#173263"),
            palette_source="brand",
        )
        authoring = render(data, authoring=True, editor_token="token", editor_recovery_id="recovery")
        self.assertIn("自定义细调", authoring)
        self.assertIn("品牌配色", authoring)
        self.assertNotIn("data-custom-palette-lock", authoring)
        self.assertNotIn('data-design-setting="', authoring)


if __name__ == "__main__":
    unittest.main()
