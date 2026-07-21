from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1] / "oil-ppt"
CLI = SKILL_ROOT / "scripts" / "oil-ppt"


class VersionCliTests(unittest.TestCase):
    def test_version_reports_verified_package_provenance(self) -> None:
        result = subprocess.run(
            [str(CLI), "version", "--json"],
            cwd=SKILL_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "oil-ppt.version/v1")
        self.assertEqual(payload["version"], "1.0.0")
        self.assertTrue(payload["ok"])
        self.assertRegex(payload["tree_sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
