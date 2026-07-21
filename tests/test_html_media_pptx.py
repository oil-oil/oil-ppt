from __future__ import annotations

import sys
import base64
import tempfile
import threading
import time
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "oil-ppt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import media_assets  # noqa: E402
import pptx_export  # noqa: E402
import oil_ppt  # noqa: E402
from cdp_validate import _wait_for_devtools_port  # noqa: E402
from build_deck import chrome_binary  # noqa: E402
from preview_deck import render_preview  # noqa: E402
from project import init_project, read_deck  # noqa: E402


def png(width: int = 4, height: int = 3) -> bytes:
    """Enough bytes for the stdlib PNG inspector; no decoder is needed here."""
    return b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big")


class HtmlMediaScannerTests(unittest.TestCase):
    def test_scans_img_source_and_svg_references_with_file_and_selector(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "slides").mkdir(); (project / "assets").mkdir()
            (project / "assets" / "a.png").write_bytes(png())
            (project / "assets" / "b.png").write_bytes(png(7, 2))
            slide = project / "slides" / "one.html"
            slide.write_text('''<picture><source srcset="../assets/a.png 1x, ../assets/b.png 2x"><img src="../assets/a.png" alt="A"></picture><svg><image href="../assets/b.png"/></svg>''', encoding="utf-8")

            report = media_assets.scan_slide_media(project, slide, slide_id="one")

            self.assertEqual(report["count"], 4)
            self.assertEqual(report["errors"], [])
            self.assertEqual({item["file"] for item in report["items"]}, {"slides/one.html"})
            self.assertEqual({item["relative_path"] for item in report["items"]}, {"assets/a.png", "assets/b.png"})
            self.assertTrue(all(item["selector"] and item["path"] for item in report["items"]))

    def test_rejects_remote_absolute_escape_missing_and_broken_media(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "slides").mkdir(); (project / "assets").mkdir()
            (project / "assets" / "broken.png").write_bytes(b"not-png")
            slide = project / "slides" / "bad.html"
            slide.write_text('''<img src="https://invalid.test/photo.png" alt=""><img src="/tmp/photo.png" alt=""><img src="../../escape.png" alt=""><img src="../assets/missing.png" alt=""><img src="../assets/broken.png" alt="">''', encoding="utf-8")

            errors = media_assets.scan_deck_media(project, {"slides": ["slides/bad.html"]})["errors"]

            self.assertEqual(len(errors), 5)
            self.assertTrue(all(error["file"] == "slides/bad.html" and error["selector"] for error in errors))
            reasons = "\n".join(error["reason"] for error in errors)
            self.assertIn("remote", reasons)
            self.assertIn("project-relative", reasons)
            self.assertIn("stay inside", reasons)
            self.assertIn("missing", reasons)
            self.assertIn("invalid PNG", reasons)

    def test_img_requires_alt_but_allows_empty_alt_for_decoration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "slides").mkdir(); (project / "assets").mkdir()
            (project / "assets" / "a.png").write_bytes(png())
            slide = project / "slides" / "one.html"
            slide.write_text('<img src="../assets/a.png"><img src="../assets/a.png" alt="">', encoding="utf-8")
            report = media_assets.scan_slide_media(project, slide, slide_id="one")
            self.assertEqual(len(report["errors"]), 1)
            self.assertEqual(report["errors"][0]["attribute"], "alt")


class RenderedDomCoverageTests(unittest.TestCase):
    def test_devtools_port_wait_tolerates_an_existing_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            port_file = Path(temporary) / "DevToolsActivePort"
            port_file.touch()
            writer = threading.Thread(target=lambda: (time.sleep(0.05), port_file.write_text("9222\n/browser\n", encoding="utf-8")))
            writer.start()
            try:
                self.assertEqual(_wait_for_devtools_port(port_file, time.monotonic() + 1), 9222)
            finally:
                writer.join()

    def test_classification_counts_only_safe_final_dom_layers_as_editable(self) -> None:
        layout = {
            "slideId": "one", "title": "One",
            "text": [
                {"selector": "h1:nth-leaf(1)", "text": "Native", "native": True},
                {"selector": "span:nth-leaf(2)", "text": "Shadow", "native": False, "reason": "text shadow"},
            ],
            "images": [
                {"selector": "img:nth-of-type(1)", "src": "data:image/png;base64,AA==", "native": True},
                {"selector": "img:nth-of-type(2)", "src": "data:image/svg+xml;base64,AA==", "native": False, "reason": "clip path"},
            ],
        }

        coverage = pptx_export.classify_rendered_slide(layout)

        self.assertEqual([item["text"] for item in coverage["native_text"]], ["Native"])
        self.assertEqual([item["selector"] for item in coverage["native_images"]], ["img:nth-of-type(1)"])
        self.assertEqual([item["kind"] for item in coverage["unsupported"]], ["rendered-text", "rendered-image"])
        self.assertTrue(all(item["preserved_in"] == "background" for item in coverage["unsupported"]))

    def test_embedded_image_resolution_rejects_nonportable_svg(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); work = root / "work"; work.mkdir()
            image, error = pptx_export._source_to_file("data:image/svg+xml;base64,PHN2Zy8+", root, work, 1)
            self.assertEqual(image, Path())
            self.assertIn("cannot be embedded", error or "")

    @unittest.skipUnless(chrome_binary(), "Chrome/Chromium is required for rendered-layer regression")
    def test_bundled_list_markers_and_rounded_media_stay_in_background(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = init_project(root / "deck", "PPTX fidelity")
            oil_ppt.slide_add(project, "comparison", "Comparison", "comparison", None)
            oil_ppt.slide_add(project, "media", "Media", "title-media", None)
            pixel = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            )
            (project / "assets" / "pixel.png").write_bytes(pixel)
            media = project / "slides" / "media.html"
            media.write_text(
                media.read_text(encoding="utf-8").replace(
                    '<div class="oil-media-placeholder">MEDIA</div>',
                    '<img src="../assets/pixel.png" alt="Verification pixel">',
                ),
                encoding="utf-8",
            )
            preview = render_preview(project)
            _, deck = read_deck(project)
            backgrounds = root / "backgrounds"
            backgrounds.mkdir()
            layouts = pptx_export.collect_render_layers(chrome_binary() or "", preview, deck, backgrounds)
            self.assertTrue(all(item.get("chromeHidden") is True for item in layouts))
            list_items = [item for item in layouts[0]["text"] if item.get("tag") == "li"]
            self.assertTrue(list_items)
            self.assertTrue(all(not item["native"] for item in list_items))
            self.assertEqual(len(layouts[1]["images"]), 1)
            self.assertFalse(layouts[1]["images"][0]["native"])

    def test_pptx_layout_closes_and_hides_overview_chrome_before_capture(self) -> None:
        expression = pptx_export._layout_expression(0)
        self.assertIn("[data-deck-overview-close]", expression)
        self.assertIn("overview must be closed before PPTX capture", expression)
        self.assertIn("all slides must be restored to stage before PPTX capture", expression)
        self.assertIn(".deck-overview-toggle,.deck-overview", expression)
        self.assertIn("chromeHidden:exportChrome.every", expression)


if __name__ == "__main__":
    unittest.main()
