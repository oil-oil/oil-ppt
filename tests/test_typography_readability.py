"""Browser regression coverage for projected-slide typography floors."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "oil-ppt"
sys.path.insert(0, str(ROOT / "scripts"))

from build_deck import chrome_binary  # noqa: E402
from cdp_validate import validate_file  # noqa: E402


class TypographyReadabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chrome = chrome_binary()
        if not self.chrome:
            self.skipTest("Chrome/Chromium unavailable")
        self.temporary = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        if hasattr(self, "temporary"):
            self.temporary.cleanup()

    def write_deck(self, second_content: str) -> Path:
        runtime = (ROOT / "assets" / "runtime" / "deck.css").read_text(encoding="utf-8")
        path = Path(self.temporary.name) / "typography.html"
        path.write_text(
            f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>{runtime}</style></head>
<body><div class="deck-viewport"><div class="deck-stage-shell"><div class="deck-stage">
<section class="oil-slide active" data-slide-id="first"><div class="slide-safe"><div data-layout style="position:absolute;inset:0"><h1 style="font-size:64px">First slide</h1><span style="font-size:28px">Readable opening copy.</span></div></div></section>
<section class="oil-slide" data-slide-id="second"><div class="slide-safe"><div data-layout style="position:absolute;inset:0">{second_content}</div></div></section>
</div></div></div></body></html>''',
            encoding="utf-8",
        )
        return path

    def test_hidden_later_slide_and_span_body_below_24px_are_blocked(self) -> None:
        report = validate_file(
            self.chrome,
            self.write_deck('<h1 style="font-size:64px">Second slide</h1><span class="body" style="font-size:20px">This explanatory sentence is too small.</span>'),
        )
        findings = [
            item for item in report["visualFindings"]
            if item.get("category") == "readability"
        ]
        self.assertEqual(report["status"], "error")
        self.assertTrue(any(
            item.get("slide") == "second"
            and item.get("fontSize") == 20
            and item.get("minimumFontSize") == 24
            and "too small" in item.get("text", "")
            for item in findings
        ), findings)

    def test_body_code_caption_and_explicit_microcopy_floors_pass(self) -> None:
        report = validate_file(
            self.chrome,
            self.write_deck('''<h1 style="font-size:48px">Second slide</h1>
<h2 style="font-size:32px">Readable section</h2>
<span style="font-size:24px">Body copy at the hard floor.</span>
<pre style="font-size:20px">code at compact floor</pre>
<figcaption style="font-size:20px">Source note</figcaption>
<span data-microcopy="index" style="font-size:18px">01</span>'''),
        )
        self.assertEqual(report["status"], "ok", report)
        self.assertEqual(
            [item for item in report["visualFindings"] if item.get("category") == "readability"],
            [],
        )

    def test_microcopy_cannot_lower_heading_sentence_or_descendant_floors(self) -> None:
        report = validate_file(
            self.chrome,
            self.write_deck('''<div data-microcopy="meta">
<h1 data-microcopy="index" style="font-size:18px">Tiny heading</h1>
<span style="font-size:18px">A descendant sentence stays audience copy.</span>
</div>
<span data-microcopy="meta" style="font-size:18px">Explain why this change is important.</span>'''),
        )
        findings = [
            item for item in report["visualFindings"]
            if item.get("category") == "readability" and item.get("slide") == "second"
        ]
        self.assertEqual(report["status"], "error")
        self.assertTrue(any(item.get("minimumFontSize") == 48 for item in findings), findings)
        self.assertGreaterEqual(
            sum(item.get("minimumFontSize") == 24 for item in findings),
            2,
            findings,
        )

    def test_white_on_white_html_and_svg_text_are_blocked(self) -> None:
        report = validate_file(
            self.chrome,
            self.write_deck('''<h1 style="font-size:64px">Contrast gate</h1>
<div style="font-size:28px;color:#fff;background:#fff">Invisible HTML label</div>
<svg width="600" height="180" viewBox="0 0 600 180">
  <rect x="0" y="0" width="600" height="180" fill="#fff"/>
  <text x="300" y="100" text-anchor="middle" style="font-size:28px;fill:#fff">Invisible SVG label</text>
</svg>'''),
        )
        findings = [
            item for item in report["visualFindings"]
            if item.get("category") == "contrast" and item.get("slide") == "second"
        ]
        self.assertEqual(report["status"], "error")
        self.assertEqual(
            {item.get("text") for item in findings},
            {"Invisible HTML label", "Invisible SVG label"},
            findings,
        )
        self.assertTrue(all(item.get("contrastRatio") == 1 for item in findings), findings)
        self.assertTrue(all(item.get("minimumContrastRatio") == 2.5 for item in findings), findings)

    def test_dark_text_on_light_html_and_svg_backgrounds_passes_contrast(self) -> None:
        report = validate_file(
            self.chrome,
            self.write_deck('''<h1 style="font-size:64px">Contrast gate</h1>
<div style="font-size:28px;color:#292929;background:#fff">Readable HTML label</div>
<svg width="600" height="180" viewBox="0 0 600 180">
  <rect x="0" y="0" width="600" height="180" fill="#fff"/>
  <text x="300" y="100" text-anchor="middle" style="font-size:28px;fill:#292929">Readable SVG label</text>
</svg>'''),
        )
        self.assertEqual(report["status"], "ok", report)
        self.assertEqual(
            [item for item in report["visualFindings"] if item.get("category") == "contrast"],
            [],
        )


if __name__ == "__main__":
    unittest.main()
