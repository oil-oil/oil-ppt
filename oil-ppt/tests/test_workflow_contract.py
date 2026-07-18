"""Regression tests for model-facing workflow dispatch contracts."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
CLI = SCRIPTS / "oil-ppt"
sys.path.insert(0, str(SCRIPTS))

from workflow_contract import (  # noqa: E402
    BATCH_NEXT_ACTIONS,
    STATUS_NEXT_ACTIONS,
    validate_batch_payload,
    validate_status_payload,
)
import oil_ppt  # noqa: E402


class WorkflowContractTests(unittest.TestCase):
    def test_action_vocabulary_is_closed_and_batch_has_one_explicit_extension(self) -> None:
        self.assertEqual(BATCH_NEXT_ACTIONS - STATUS_NEXT_ACTIONS, {"ask_user_to_confirm_previews"})
        self.assertIn("fix_media", STATUS_NEXT_ACTIONS)
        self.assertNotIn("generate_external_media", BATCH_NEXT_ACTIONS)

    def test_status_rejects_an_unknown_next_action(self) -> None:
        with self.assertRaisesRegex(SystemExit, r"status contract violation: unsupported next\.action 'invent_step'"):
            validate_status_payload({"next": {"action": "invent_step", "command": None}})

        with mock.patch.object(
            oil_ppt,
            "_status_payload_unchecked",
            return_value={"next": {"action": "invent_step", "command": None}},
        ):
            with self.assertRaisesRegex(SystemExit, r"status contract violation: unsupported next\.action 'invent_step'"):
                oil_ppt.status_payload(Path("unused"))

    def test_batch_rejects_unknown_nested_and_top_level_actions(self) -> None:
        with self.assertRaisesRegex(SystemExit, r"batch\.projects\[0\].*unsupported next\.action 'invent_step'"):
            validate_batch_payload({
                "projects": [{"next": {"action": "invent_step", "command": None}}],
                "next": {"action": "complete", "command": None},
            })
        with self.assertRaisesRegex(SystemExit, r"batch contract violation: unsupported next\.action 'invent_step'"):
            validate_batch_payload({
                "projects": [{"next": {"action": "complete", "command": None}}],
                "next": {"action": "invent_step", "command": None},
            })

    def test_top_level_help_explains_hidden_callable_workflow_commands(self) -> None:
        result = subprocess.run(
            [str(CLI), "--help"],
            cwd=SKILL_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("callable workflow commands intentionally omitted", result.stdout)
        self.assertIn("Execute only the exact command string returned by status", result.stdout)
        self.assertNotIn("{init,batch,status,plan,", result.stdout)


if __name__ == "__main__":
    unittest.main()
