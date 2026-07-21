"""Regression coverage for the closed model-facing workflow vocabulary."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1] / "oil-ppt"
SCRIPTS = SKILL_ROOT / "scripts"
CLI = SCRIPTS / "oil-ppt"
sys.path.insert(0, str(SCRIPTS))

from project import discover_projects, init_project  # noqa: E402
from workflow import batch  # noqa: E402
from workflow_contract import (  # noqa: E402
    BATCH_NEXT_ACTIONS,
    STATUS_NEXT_ACTIONS,
    validate_batch_payload,
    validate_status_payload,
)


class WorkflowContractTests(unittest.TestCase):
    def test_action_vocabulary_is_closed(self) -> None:
        self.assertEqual(BATCH_NEXT_ACTIONS, STATUS_NEXT_ACTIONS)
        self.assertEqual(
            STATUS_NEXT_ACTIONS,
            {
                "edit_outline", "ask_user_to_confirm_outline",
                "author_slides", "edit_slide", "fix_media", "run_command",
                "ask_user_to_confirm_preview", "complete",
            },
        )

    def test_contract_rejects_unknown_actions(self) -> None:
        with self.assertRaisesRegex(SystemExit, "unsupported next.action"):
            validate_status_payload({"next": {"action": "unknown"}})
        with self.assertRaisesRegex(SystemExit, "unsupported next.action"):
            validate_batch_payload({
                "projects": [{"next": {"action": "complete"}}],
                "next": {"action": "unknown"},
            })

    def test_batch_discovers_only_projects_inside_supplied_parents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = init_project(root / "group" / "first", "First")
            second = init_project(root / "group" / "nested" / "second", "Second")
            found = discover_projects([root / "group"])
            self.assertEqual(found, [first, second])
            payload = validate_batch_payload(batch(found, lambda *parts: " ".join(map(str, parts))))
            self.assertEqual(payload["next"]["action"], "edit_outline")

    def test_batch_returns_an_executable_single_preview_confirmation(self) -> None:
        payload = {
            "schema_version": "oil-ppt.status/v1", "ok": True, "project": "/deck",
            "phase": "needs_preview_confirmation", "slides": 1,
            "next": {"action": "ask_user_to_confirm_preview", "artifact": "/deck/预览.html", "command_on_confirm": "oil-ppt confirm /deck preview"},
        }
        import workflow
        original = workflow.status
        try:
            workflow.status = lambda project, command: payload
            result = validate_batch_payload(batch([Path("/deck")], lambda *parts: " ".join(map(str, parts))))
        finally:
            workflow.status = original
        self.assertEqual(result["next"], payload["next"])
        self.assertTrue(result["next"]["command_on_confirm"])

    def test_cli_help_exposes_html_authoring_commands(self) -> None:
        result = subprocess.run(
            [str(CLI), "--help"],
            cwd=SKILL_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("slide", "starter", "theme", "preview", "build", "export-pptx", "doctor"):
            self.assertIn(command, result.stdout)


if __name__ == "__main__":
    unittest.main()
