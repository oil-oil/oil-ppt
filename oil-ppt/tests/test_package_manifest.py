from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import package_manifest  # noqa: E402


class PackageManifestTests(unittest.TestCase):
    def test_generation_is_stable_and_excludes_development_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "nested").mkdir()
            (root / "nested" / "beta.txt").write_text("beta", encoding="utf-8")
            (root / "alpha.txt").write_text("alpha", encoding="utf-8")
            (root / "manifest.json").write_text("ignored", encoding="utf-8")
            (root / ".DS_Store").write_bytes(b"ignored")
            (root / "ignored.pyc").write_bytes(b"ignored")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "cached.py").write_text("ignored", encoding="utf-8")

            first = package_manifest.generate_manifest(root)
            second = package_manifest.generate_manifest(root)

            self.assertEqual(first, second)
            self.assertEqual(first["schema_version"], "oil-ppt.package/v1")
            self.assertEqual(first["package_version"], "0.3.0")
            self.assertEqual(
                [record["path"] for record in first["files"]],
                ["alpha.txt", "nested/beta.txt"],
            )
            self.assertEqual(
                first["tree_sha256"],
                package_manifest.compute_tree_sha256(first["files"]),
            )

    def test_verify_reports_changed_missing_and_unexpected_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "manifest.json"
            (root / "changed.txt").write_text("before", encoding="utf-8")
            (root / "missing.txt").write_text("remove me", encoding="utf-8")
            (root / "same.txt").write_text("same", encoding="utf-8")
            package_manifest.write_manifest(manifest_path, root=root)

            (root / "changed.txt").write_text("after", encoding="utf-8")
            (root / "missing.txt").unlink()
            (root / "unexpected.txt").write_text("new", encoding="utf-8")

            report = package_manifest.verify_manifest(manifest_path, root=root)

            self.assertFalse(report["ok"])
            self.assertEqual(report["changed"], ["changed.txt"])
            self.assertEqual(report["missing"], ["missing.txt"])
            self.assertEqual(report["unexpected"], ["unexpected.txt"])
            self.assertEqual(report["errors"], [])

    def test_nested_manifest_named_file_is_tracked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested_manifest = root / "assets" / "manifest.json"
            nested_manifest.parent.mkdir()
            nested_manifest.write_text('{"version": 1}', encoding="utf-8")
            package_manifest.write_manifest(root=root)

            nested_manifest.write_text('{"version": 2}', encoding="utf-8")
            report = package_manifest.verify_manifest(root=root)

            self.assertFalse(report["ok"])
            self.assertEqual(report["changed"], ["assets/manifest.json"])

    def test_verify_succeeds_without_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "manifest.json"
            (root / "SKILL.md").write_text("skill", encoding="utf-8")

            package_manifest.write_manifest(manifest_path, root=root)
            report = package_manifest.verify_manifest(manifest_path, root=root)

            self.assertTrue(report["ok"])
            self.assertEqual(report["missing"], [])
            self.assertEqual(report["changed"], [])
            self.assertEqual(report["unexpected"], [])

    def test_package_status_uses_declared_provenance_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tracked = root / "SKILL.md"
            tracked.write_text("before", encoding="utf-8")
            manifest = package_manifest.write_manifest(root=root)

            healthy = package_manifest.package_status(root)
            self.assertEqual(healthy["schema_version"], "oil-ppt.version/v1")
            self.assertTrue(healthy["ok"])
            self.assertEqual(healthy["version"], "0.3.0")
            self.assertEqual(healthy["tree_sha256"], manifest["tree_sha256"])
            self.assertEqual(healthy["file_count"], 1)
            self.assertEqual(healthy["root"], str(root.resolve()))
            self.assertEqual(healthy["manifest_path"], str((root / "manifest.json").resolve()))

            tracked.write_text("after", encoding="utf-8")
            changed = package_manifest.package_status(root)
            self.assertFalse(changed["ok"])
            self.assertEqual(changed["tree_sha256"], manifest["tree_sha256"])
            self.assertEqual(changed["changed"], ["SKILL.md"])

    def test_package_status_falls_back_to_current_digest_without_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "SKILL.md").write_text("skill", encoding="utf-8")
            current = package_manifest.generate_manifest(root)

            status = package_manifest.package_status(root)

            self.assertFalse(status["ok"])
            self.assertEqual(status["tree_sha256"], current["tree_sha256"])
            self.assertEqual(status["file_count"], 1)
            self.assertTrue(status["errors"])


if __name__ == "__main__":
    unittest.main()
