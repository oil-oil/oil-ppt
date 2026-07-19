from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
CLI = SCRIPTS / "oil-ppt"
sys.path.insert(0, str(SCRIPTS))

import oil_ppt  # noqa: E402
from design_directions import DESIGN_DIRECTIONS  # noqa: E402
from palette_tokens import custom_palette  # noqa: E402


def outline_data(*, palette: object = "oil-yellow", palette_source: str | None = None) -> dict:
    data = {
        "title": "Agent 设计调整测试",
        "palette": palette,
        "typography": "clean",
        "shape": "soft",
        "media_policy": "text-only",
        "click_navigation": False,
        "slides": [{
            "id": "section",
            "title": "一个清楚的章节",
            "content": "用真实 outline 验证设计事务。",
            "template": "section",
            "variant": "default",
            "decor": "none",
        }],
    }
    if palette_source:
        data["palette_source"] = palette_source
    return data


class DesignCliTests(unittest.TestCase):
    def initialized_project(self, root: Path, *, data: dict | None = None) -> Path:
        project = root / "deck"
        with contextlib.redirect_stdout(io.StringIO()):
            oil_ppt.init_project(project)
        markdown = project / "outline.md"
        markdown.write_text("# 已确认大纲\n\n- 目标：验证 Agent 视觉调整。\n", encoding="utf-8")
        outline = project / "outline.json"
        oil_ppt.atomic_write_json(outline, data or outline_data())
        outline_sha = oil_ppt.json_digest(outline)
        oil_ppt.atomic_write_json(oil_ppt.project_state_path(project), {
            "schema_version": "oil-ppt.project-state/v1",
            "history": [],
            "outline_confirmation": {
                "sha256": oil_ppt.outline_digest(markdown),
                "user_confirmed": True,
            },
            "visual_plan": {
                "markdown_sha256": oil_ppt.outline_digest(markdown),
                "outline_sha256": outline_sha,
            },
            "media_policy_confirmation": {
                "policy": "text-only",
                "outline_sha256": outline_sha,
                "user_confirmed": True,
            },
        })
        oil_ppt.atomic_write_json(oil_ppt.preview_state_path(outline), {
            "schema_version": "oil-ppt.preview/v1",
            "outline_sha256": outline_sha,
            "preview": str(project / "预览.html"),
            "confirmed": True,
        })
        oil_ppt.atomic_write_json(project / oil_ppt.BUILD_STATE_NAME, {"confirmed": True})
        oil_ppt.atomic_write_json(oil_ppt.validation_state_path(project), {"status": "ok"})
        return project

    def project_files(self, project: Path) -> dict[str, bytes]:
        names = (
            "outline.json", oil_ppt.PROJECT_STATE_NAME,
            oil_ppt.preview_state_path(project / "outline.json").name,
            oil_ppt.BUILD_STATE_NAME, oil_ppt.validation_state_path(project).name,
        )
        return {name: (project / name).read_bytes() for name in names if (project / name).is_file()}

    def test_discovery_is_machine_readable_and_registry_backed(self) -> None:
        result = subprocess.run(
            [str(CLI), "design", "list", "--compact"],
            cwd=SKILL_ROOT, capture_output=True, text=True, timeout=30, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "oil-ppt.design-list/v1")
        self.assertEqual(
            [item["id"] for item in payload["directions"]],
            [item.id for item in DESIGN_DIRECTIONS],
        )
        self.assertEqual(
            {item["id"] for item in payload["settings"]["palette"]},
            set(oil_ppt.PALETTES),
        )
        self.assertFalse(payload["application"]["mixed_modes_allowed"])

    def test_project_discovery_returns_current_digest_and_apply_prefix(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oil-ppt-design-cli-") as temporary:
            project = self.initialized_project(Path(temporary))
            payload = oil_ppt.design_catalog(project)
            self.assertEqual(
                payload["project"]["outline_sha256"],
                oil_ppt.outline_digest(project / "outline.json"),
            )
            self.assertIn("design apply", payload["project"]["apply_command_prefix"])
            self.assertIn("--expected-sha256", payload["project"]["apply_command_prefix"])

    def test_complete_direction_applies_and_returns_before_after_json(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oil-ppt-design-cli-") as temporary:
            project = self.initialized_project(Path(temporary))
            digest = oil_ppt.outline_digest(project / "outline.json")
            payload = oil_ppt.apply_project_design(
                project, expected_sha256=digest, direction="technical-system",
            )
            saved = json.loads((project / "outline.json").read_text(encoding="utf-8"))
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["changed"])
            self.assertEqual(payload["before"]["direction"], "fresh-default")
            self.assertEqual(payload["after"]["direction"], "technical-system")
            self.assertEqual(saved["palette"], "ocean-cobalt")
            self.assertEqual(saved["typography"], "technical")
            self.assertEqual(saved["shape"], "crisp")
            self.assertEqual(
                payload["next"]["command"], oil_ppt.cli_command("status", project.resolve(), "--json"),
            )

    def test_apply_cli_emits_one_machine_readable_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oil-ppt-design-cli-") as temporary:
            project = self.initialized_project(Path(temporary))
            digest = oil_ppt.outline_digest(project / "outline.json")
            result = subprocess.run(
                [
                    str(CLI), "design", "apply", str(project),
                    "--expected-sha256", digest,
                    "--typography", "editorial", "--shape", "crisp",
                    "--json", "--compact",
                ],
                cwd=SKILL_ROOT, capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(result.stdout.splitlines()), 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], "oil-ppt.design-apply/v1")
            self.assertEqual(payload["after"]["typography"], "editorial")
            self.assertEqual(payload["after"]["shape"], "crisp")
            self.assertEqual(payload["next"]["command"], oil_ppt.cli_command("status", project.resolve(), "--json"))

    def test_multiple_fine_tuning_settings_preserve_custom_palette(self) -> None:
        brand = custom_palette("#2255AA", "#EEF4FF", "#173263")
        with tempfile.TemporaryDirectory(prefix="oil-ppt-design-cli-") as temporary:
            project = self.initialized_project(
                Path(temporary), data=outline_data(palette=brand, palette_source="brand"),
            )
            original = json.loads(json.dumps(brand))
            digest = oil_ppt.outline_digest(project / "outline.json")
            payload = oil_ppt.apply_project_design(
                project, expected_sha256=digest, typography="editorial", shape="crisp",
            )
            saved = json.loads((project / "outline.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["palette"], original)
            self.assertEqual(saved["palette_source"], "brand")
            self.assertEqual(saved["typography"], "editorial")
            self.assertEqual(saved["shape"], "crisp")
            self.assertNotIn("palette", payload["changed_settings"])

    def test_stale_mixed_unknown_and_empty_input_leave_all_files_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oil-ppt-design-cli-") as temporary:
            project = self.initialized_project(Path(temporary))
            current = oil_ppt.outline_digest(project / "outline.json")
            cases = (
                {"expected_sha256": "0" * 64, "shape": "crisp"},
                {"expected_sha256": current, "direction": "warm-friendly", "shape": "crisp"},
                {"expected_sha256": current, "direction": "unknown"},
                {"expected_sha256": current},
            )
            for arguments in cases:
                before = self.project_files(project)
                with self.subTest(arguments=arguments), self.assertRaises(SystemExit):
                    oil_ppt.apply_project_design(project, **arguments)
                self.assertEqual(self.project_files(project), before)

    def test_active_draft_and_live_lock_are_rejected_without_changes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oil-ppt-design-cli-") as temporary:
            project = self.initialized_project(Path(temporary))
            digest = oil_ppt.outline_digest(project / "outline.json")
            draft = oil_ppt.edit_draft_path(project)
            draft.write_text("{}\n", encoding="utf-8")
            before = self.project_files(project)
            with self.assertRaisesRegex(SystemExit, "draft exists"):
                oil_ppt.apply_project_design(project, expected_sha256=digest, shape="crisp")
            self.assertEqual(self.project_files(project), before)
            draft.unlink()

            sleeper = subprocess.Popen(["sleep", "30"])
            try:
                oil_ppt.atomic_write_json(
                    oil_ppt.edit_lock_path(project), oil_ppt.editor_lock_payload(project, sleeper.pid),
                )
                before = self.project_files(project)
                with self.assertRaisesRegex(SystemExit, "editor is open"):
                    oil_ppt.apply_project_design(project, expected_sha256=digest, shape="crisp")
                self.assertEqual(self.project_files(project), before)
            finally:
                sleeper.terminate()
                sleeper.wait(timeout=5)
                oil_ppt.edit_lock_path(project).unlink(missing_ok=True)

    def test_success_invalidates_confirmations_and_keeps_plan_bound(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oil-ppt-design-cli-") as temporary:
            project = self.initialized_project(Path(temporary))
            outline = project / "outline.json"
            payload = oil_ppt.apply_project_design(
                project, expected_sha256=oil_ppt.outline_digest(outline), palette="quiet-moss",
            )
            preview = json.loads(oil_ppt.preview_state_path(outline).read_text(encoding="utf-8"))
            state = json.loads(oil_ppt.project_state_path(project).read_text(encoding="utf-8"))
            self.assertFalse(preview["confirmed"])
            self.assertFalse((project / oil_ppt.BUILD_STATE_NAME).exists())
            self.assertFalse(oil_ppt.validation_state_path(project).exists())
            self.assertEqual(state["visual_plan"]["outline_sha256"], oil_ppt.json_digest(outline))
            self.assertEqual(
                state["media_policy_confirmation"]["outline_sha256"], oil_ppt.json_digest(outline),
            )
            self.assertEqual(oil_ppt.status_payload(project)["phase"], "needs_preview")
            self.assertTrue(payload["invalidated"]["preview_confirmation"])
            self.assertTrue(payload["invalidated"]["build_confirmation"])

    def test_write_failure_rolls_back_every_transaction_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oil-ppt-design-cli-") as temporary:
            project = self.initialized_project(Path(temporary))
            digest = oil_ppt.outline_digest(project / "outline.json")
            before = self.project_files(project)
            original = oil_ppt.atomic_write_json
            calls = 0

            def fail_second(path: Path, data: dict) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected transaction failure")
                original(path, data)

            with mock.patch.object(oil_ppt, "atomic_write_json", side_effect=fail_second):
                with self.assertRaisesRegex(SystemExit, "atomically"):
                    oil_ppt.apply_project_design(
                        project, expected_sha256=digest, typography="editorial",
                    )
            self.assertEqual(self.project_files(project), before)


if __name__ == "__main__":
    unittest.main()
