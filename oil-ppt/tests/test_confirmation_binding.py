from __future__ import annotations

import contextlib
import io
import shlex
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import oil_ppt  # noqa: E402


class ConfirmationBindingTests(unittest.TestCase):
    def initialized_project(self, root: Path) -> Path:
        project = root / "deck"
        with contextlib.redirect_stdout(io.StringIO()):
            oil_ppt.init_project(project)
        (project / "outline.md").write_text(
            "# 已完成的大纲\n\n- 目标：验证确认摘要绑定。\n",
            encoding="utf-8",
        )
        return project

    def test_status_binds_outline_confirmation_to_current_digest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oil-ppt-confirm-test-") as temp_dir:
            project = self.initialized_project(Path(temp_dir))
            payload = oil_ppt.status_payload(project)
            next_step = payload["next"]
            expected = oil_ppt.outline_digest(project / "outline.md")

            self.assertEqual(next_step["artifact_sha256"], expected)
            command = shlex.split(next_step["command_on_confirm"])
            self.assertEqual(command[command.index("--expected-sha256") + 1], expected)

    def test_stale_outline_confirmation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oil-ppt-confirm-test-") as temp_dir:
            project = self.initialized_project(Path(temp_dir))
            expected = oil_ppt.outline_digest(project / "outline.md")
            (project / "outline.md").write_text(
                "# 已被修改的大纲\n\n- 目标：旧命令不能确认新内容。\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(SystemExit, "confirmation is stale"):
                oil_ppt.confirm_outline(project, True, expected)
            self.assertFalse(oil_ppt.outline_confirmation_valid(project))

    def test_expected_preview_bindings_are_path_normalized(self) -> None:
        digest = "a" * 64
        parsed = oil_ppt.parse_expected_previews([f"./relative-project::{digest}"])
        self.assertEqual(parsed[Path("relative-project").resolve()], digest)


if __name__ == "__main__":
    unittest.main()
