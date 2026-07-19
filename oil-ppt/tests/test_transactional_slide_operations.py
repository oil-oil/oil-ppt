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

from doctor import smoke_slides  # noqa: E402
import text_editor  # noqa: E402
from oil_ppt import atomic_write_json, preview_state_path, project_state_path  # noqa: E402
from render_outline_review import render  # noqa: E402


def slide(template: str, slide_id: str, title: str) -> dict:
    value = copy.deepcopy(next(item for item in smoke_slides() if item["template"] == template))
    value["id"] = slide_id
    value["title"] = title
    value.pop("highlight", None)
    return value


def deck_data() -> dict:
    return {
        "title": "事务式页面编辑测试",
        "palette": "oil-yellow",
        "typography": "clean",
        "shape": "soft",
        "media_policy": "text-only",
        "click_navigation": False,
        "slides": [
            slide("cover", "cover", "封面"),
            slide("section", "alpha", "甲页面"),
            slide("section", "beta", "乙页面"),
            slide("end", "end", "结束页"),
        ],
    }


def transaction(action: str, slide_id: str, revision: int, operation_id: str, **extra: str) -> dict:
    return {
        "action": action,
        "slide_id": slide_id,
        "expected_revision": revision,
        "operation_id": operation_id,
        **extra,
    }


class TransactionalSlideOperationTests(unittest.TestCase):
    @contextmanager
    def editor(self, data: dict | None = None):
        with tempfile.TemporaryDirectory(prefix="oil-ppt-transaction-editor-") as temporary:
            project = Path(temporary)
            outline = project / "outline.json"
            preview = project / "预览.html"
            atomic_write_json(outline, data or deck_data())
            preview.write_text("<!doctype html><title>old preview</title>", encoding="utf-8")
            atomic_write_json(project_state_path(project), {"visual_plan": {"outline_sha256": "initial"}})
            atomic_write_json(preview_state_path(outline), {
                "preview": str(preview),
                "preview_sha256": "old",
                "confirmed": True,
            })

            def fake_preview(_project: Path, target: Path, *_args: object, **_kwargs: object) -> None:
                target.write_text("<!doctype html><title>new preview</title>", encoding="utf-8")
                atomic_write_json(preview_state_path(outline), {
                    "preview": str(target),
                    "preview_sha256": "new",
                    "confirmed": False,
                })

            with (
                mock.patch.object(text_editor, "outline_confirmation_valid", return_value=True),
                mock.patch.object(text_editor, "visual_plan_valid", return_value=True),
                mock.patch.object(text_editor, "preview_state_status", return_value=("awaiting-confirmation", {}, None)),
                mock.patch.object(text_editor, "enforce_outline_quality"),
                mock.patch.object(text_editor, "verify_outline_media"),
                mock.patch.object(text_editor, "generate_preview", side_effect=fake_preview) as generate,
            ):
                session = text_editor.EditorSession(project)
                try:
                    yield session, project, outline, generate
                finally:
                    session.close()

    def test_text_and_structure_share_one_ordered_undo_redo_history(self) -> None:
        with self.editor() as (session, _project, _outline, _generate):
            session.apply_edit("/slides/1/title", "修改后的甲页面", expected_revision=0)
            session.apply_slide_operation("move", transaction(
                "move", "alpha", 1, "operation-move-alpha", direction="down",
            ))
            self.assertEqual([item["id"] for item in session.data["slides"]], ["cover", "beta", "alpha", "end"])
            self.assertEqual(session.data["slides"][2]["title"], "修改后的甲页面")

            session.undo()
            self.assertEqual([item["id"] for item in session.data["slides"]], ["cover", "alpha", "beta", "end"])
            self.assertEqual(session.data["slides"][1]["title"], "修改后的甲页面")
            session.undo()
            self.assertEqual(session.data["slides"][1]["title"], "甲页面")

            session.redo()
            session.redo()
            self.assertEqual([item["id"] for item in session.data["slides"]], ["cover", "beta", "alpha", "end"])
            self.assertEqual(session.data["slides"][2]["title"], "修改后的甲页面")

    def test_duplicate_ids_are_deterministic_unique_and_operation_replay_is_idempotent(self) -> None:
        with self.editor() as (session, _project, _outline, _generate):
            first = transaction("duplicate", "alpha", 0, "operation-duplicate-alpha-1")
            session.apply_slide_operation("duplicate", first)
            self.assertEqual([item["id"] for item in session.data["slides"]], [
                "cover", "alpha", "alpha-copy", "beta", "end",
            ])

            replay = session.apply_slide_operation("duplicate", first)
            self.assertEqual(len(session.data["slides"]), 5)
            self.assertIn("already applied", replay["notices"][-1])

            session.apply_slide_operation("duplicate", transaction(
                "duplicate", "alpha", 1, "operation-duplicate-alpha-2",
            ))
            self.assertEqual([item["id"] for item in session.data["slides"]], [
                "cover", "alpha", "alpha-copy-2", "alpha-copy", "beta", "end",
            ])

    def test_invalid_boundary_minimum_stale_and_unknown_operations_are_atomic(self) -> None:
        with self.editor() as (session, _project, _outline, _generate):
            cases = (
                ("move", transaction("move", "cover", 0, "operation-cover-move", direction="down"), "boundary"),
                ("duplicate", transaction("duplicate", "end", 0, "operation-end-copy"), "boundary"),
                ("delete", transaction("delete", "missing", 0, "operation-missing-delete"), "stale or invalid"),
                ("move", transaction("move", "alpha", 8, "operation-stale-move", direction="down"), "Stale"),
            )
            for action, payload, message in cases:
                before = copy.deepcopy(session.data)
                before_revision = session.revision
                with self.subTest(action=action, message=message), self.assertRaisesRegex(ValueError, message):
                    session.apply_slide_operation(action, payload)
                self.assertEqual(session.data, before)
                self.assertEqual(session.revision, before_revision)
                self.assertFalse(session.draft_path.exists())

            session.apply_slide_operation("delete", transaction(
                "delete", "alpha", 0, "operation-delete-alpha",
            ))
            before = copy.deepcopy(session.data)
            with self.assertRaisesRegex(ValueError, "retain at least one content slide"):
                session.apply_slide_operation("delete", transaction(
                    "delete", "beta", 1, "operation-delete-beta",
                ))
            self.assertEqual(session.data, before)
            self.assertEqual([item["id"] for item in session.data["slides"]], ["cover", "beta", "end"])

    def test_structural_draft_recovers_revision_and_does_not_replay_twice(self) -> None:
        with self.editor() as (session, project, _outline, _generate):
            payload = transaction("duplicate", "alpha", 0, "operation-browser-recovery")
            session.apply_slide_operation("duplicate", payload)
            draft = json.loads(session.draft_path.read_text(encoding="utf-8"))
            self.assertEqual(draft["revision"], 1)
            self.assertIn(payload["operation_id"], draft["applied_operations"])

            session.close()
            recovered = text_editor.EditorSession(project)
            try:
                self.assertEqual(recovered.revision, 1)
                self.assertEqual(len(recovered.data["slides"]), 5)
                recovered.apply_slide_operation("duplicate", payload)
                self.assertEqual(len(recovered.data["slides"]), 5)
                self.assertEqual(recovered.revision, 1)
            finally:
                recovered.close()

    def test_discard_restores_the_complete_base_deck(self) -> None:
        with self.editor() as (session, _project, _outline, _generate):
            original = copy.deepcopy(session.base_data)
            session.apply_edit("/slides/1/title", "临时标题", expected_revision=0)
            session.apply_slide_operation("duplicate", transaction(
                "duplicate", "alpha", 1, "operation-discard-copy",
            ))
            state = session.discard()
            self.assertEqual(session.data, original)
            self.assertFalse(state["draft"])
            self.assertFalse(state["can_undo"])
            self.assertFalse(state["can_redo"])

    def test_finish_persists_complete_deck_invalidates_confirmation_and_rebuilds_once(self) -> None:
        with self.editor() as (session, _project, outline, generate):
            session.apply_slide_operation("move", transaction(
                "move", "alpha", 0, "operation-finish-move", direction="down",
            ))
            invalidated = json.loads(preview_state_path(outline).read_text(encoding="utf-8"))
            self.assertFalse(invalidated["confirmed"])

            result = session.finish([], report_complete=True)
            saved = json.loads(outline.read_text(encoding="utf-8"))
            final_preview = json.loads(preview_state_path(outline).read_text(encoding="utf-8"))
            self.assertTrue(result["changed"])
            self.assertEqual([item["id"] for item in saved["slides"]], ["cover", "beta", "alpha", "end"])
            self.assertFalse(final_preview["confirmed"])
            self.assertEqual(generate.call_count, 1)
            self.assertFalse(session.draft_path.exists())

    def test_schema_failure_before_finish_leaves_outline_and_draft_unchanged(self) -> None:
        with self.editor() as (session, _project, outline, generate):
            session.apply_slide_operation("duplicate", transaction(
                "duplicate", "alpha", 0, "operation-schema-rollback",
            ))
            outline_before = outline.read_bytes()
            draft_before = session.draft_path.read_bytes()
            with mock.patch.object(text_editor, "validate_outline", side_effect=SystemExit("schema failure")):
                with self.assertRaisesRegex(ValueError, "schema failure"):
                    session.finish([], report_complete=True)
            self.assertEqual(outline.read_bytes(), outline_before)
            self.assertEqual(session.draft_path.read_bytes(), draft_before)
            self.assertEqual(generate.call_count, 0)
            self.assertFalse(session.editing_complete)


class StructuralAuthoringHtmlTests(unittest.TestCase):
    def test_controls_exist_only_in_authoring_preview(self) -> None:
        data = deck_data()
        authoring = render(data, authoring=True, editor_token="token", editor_recovery_id="recovery")
        formal = render(data)

        for action in ("move", "duplicate", "delete"):
            self.assertIn(f'data-slide-action="{action}"', authoring)
            self.assertNotIn(f'data-slide-action="{action}"', formal)
        self.assertIn("/api/slides/${transaction.action}", authoring)
        self.assertNotIn("/api/slides/${transaction.action}", formal)
        self.assertNotIn('class="slide-actions"', formal)
        self.assertIn('data-slide-id="cover"', authoring)
        self.assertIn('data-slide-action="move" data-direction="up" disabled', authoring)


if __name__ == "__main__":
    unittest.main()
