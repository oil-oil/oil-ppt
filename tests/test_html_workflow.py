"""HTML-first workflow regression coverage."""
from __future__ import annotations

import hashlib
import base64
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "oil-ppt"
sys.path.insert(0, str(ROOT / "scripts"))

from build_deck import build_project  # noqa: E402
from preview_deck import render_preview  # noqa: E402
from project import RUNTIME_SOURCE, init_project  # noqa: E402
from slide_html import parse_slide  # noqa: E402
from workflow import confirm_preview  # noqa: E402
import oil_ppt  # noqa: E402


class HtmlWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = init_project(Path(self.temporary.name) / "deck", "HTML deck")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_init_creates_reference_outline_and_html_project_shell(self) -> None:
        self.assertTrue((self.project / "outline.md").is_file())
        self.assertTrue((self.project / "deck.json").is_file())
        self.assertTrue((self.project / "slides").is_dir())
        self.assertTrue((self.project / ".oil-ppt" / "state.json").is_file())
        self.assertEqual(oil_ppt.status_payload(self.project)["next"]["action"], "edit_outline")
        self.assertTrue((self.project / "assets" / "icons" / "arrow-right.svg").is_file())

    def test_confirmed_outline_is_a_non_binding_reference(self) -> None:
        from workflow import confirm_outline
        (self.project / "outline.md").write_text("# HTML deck\n\nAudience and core claim.\n", encoding="utf-8")
        self.assertEqual(oil_ppt.status_payload(self.project)["next"]["action"], "ask_user_to_confirm_outline")
        confirm_outline(self.project)
        self.assertEqual(oil_ppt.status_payload(self.project)["next"]["action"], "author_slides")
        self.assertNotIn("outline.md", __import__("state").input_manifest(self.project))

    def test_slide_lifecycle_is_direct_html(self) -> None:
        oil_ppt.slide_add(self.project, "cover", "Cover", None, None)
        oil_ppt.slide_add(self.project, "problem", "Problem", None, "cover")
        oil_ppt.slide_duplicate(self.project, "problem", "solution", "Solution")
        oil_ppt.slide_move(self.project, "solution", 2)
        result = oil_ppt.slide_check(self.project)
        self.assertEqual([item["id"] for item in result["slides"]], ["cover", "solution", "problem"])
        oil_ppt.slide_remove(self.project, "problem")
        self.assertFalse((self.project / "slides" / "problem.html").exists())

    def test_starter_lookup_stays_inside_the_starter_directory(self) -> None:
        with self.assertRaisesRegex(SystemExit, "Starter name"):
            oil_ppt.starter_show("../slides/secret")

    def test_preview_and_build_do_not_mutate_slide_sources(self) -> None:
        oil_ppt.slide_add(self.project, "cover", "Cover", None, None)
        source = self.project / "slides" / "cover.html"
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        preview = render_preview(self.project)
        self.assertTrue(preview.is_file())
        self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())
        confirm_preview(self.project)
        output = build_project(self.project)
        self.assertTrue(output.is_file())
        self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())

    def test_confirmation_is_bound_to_real_sources(self) -> None:
        oil_ppt.slide_add(self.project, "cover", "Cover", None, None)
        render_preview(self.project)
        source = self.project / "slides" / "cover.html"
        source.write_text(source.read_text(encoding="utf-8").replace("Cover", "Changed", 1), encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "stale"):
            confirm_preview(self.project)

    def test_read_deck_refreshes_only_package_owned_runtime_and_invalidates_preview(self) -> None:
        oil_ppt.slide_add(self.project, "cover", "Cover", "statement", None)
        source = self.project / "slides" / "cover.html"
        theme = self.project / "runtime" / "theme.css"
        icon = self.project / "assets" / "icons" / "arrow-right.svg"
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        theme_bytes = theme.read_bytes()
        icon_bytes = icon.read_bytes()
        render_preview(self.project)
        confirm_preview(self.project)
        runtime = self.project / "runtime"
        (runtime / "deck.js").write_text("// old runtime sentinel\n", encoding="utf-8")
        (runtime / "deck.css").write_text("/* old runtime sentinel */\n", encoding="utf-8")
        state = __import__("state")
        old_manifest = state.input_manifest(self.project)
        state.write_state(self.project, preview_manifest=old_manifest, preview_confirmed=True, phase="complete")

        project, _ = oil_ppt.read_deck(self.project)

        self.assertEqual((runtime / "deck.js").read_bytes(), (RUNTIME_SOURCE / "deck.js").read_bytes())
        self.assertEqual((runtime / "deck.css").read_bytes(), (RUNTIME_SOURCE / "deck.css").read_bytes())
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hash)
        self.assertEqual(theme.read_bytes(), theme_bytes)
        self.assertEqual(icon.read_bytes(), icon_bytes)
        manifest = state.input_manifest(project)
        self.assertIn("@renderer/project.py", manifest)
        self.assertIn("@runtime-source/deck.css", manifest)
        self.assertIn("@runtime-source/deck.js", manifest)
        self.assertNotEqual(manifest, old_manifest)
        with self.assertRaisesRegex(SystemExit, "stale"):
            confirm_preview(project)
        with self.assertRaisesRegex(SystemExit, "stale"):
            build_project(project)
        refreshed_preview = render_preview(project).read_text(encoding="utf-8")
        self.assertIn("deck-overview-toggle", refreshed_preview)
        self.assertIn("restoreSlides", refreshed_preview)

        before_mtime = {name: (runtime / name).stat().st_mtime_ns for name in ("deck.js", "deck.css")}
        oil_ppt.read_deck(project)
        self.assertEqual(before_mtime, {name: (runtime / name).stat().st_mtime_ns for name in before_mtime})

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are required for runtime ownership coverage")
    def test_read_deck_rejects_runtime_directory_symlink_without_touching_external_files(self) -> None:
        external = Path(self.temporary.name) / "external-runtime"
        shutil.copytree(self.project / "runtime", external)
        before = {path.name: path.read_bytes() for path in external.iterdir() if path.is_file()}
        runtime = self.project / "runtime"
        shutil.rmtree(runtime)
        os.symlink(external, runtime, target_is_directory=True)

        with self.assertRaisesRegex(SystemExit, "runtime directory.*not a symlink"):
            oil_ppt.read_deck(self.project)

        self.assertEqual(before, {path.name: path.read_bytes() for path in external.iterdir() if path.is_file()})

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are required for runtime ownership coverage")
    def test_read_deck_rejects_runtime_file_symlinks_without_touching_external_files(self) -> None:
        runtime = self.project / "runtime"
        for name in ("deck.js", "deck.css"):
            with self.subTest(name=name):
                external = Path(self.temporary.name) / f"external-{name}"
                external.write_bytes(f"outside {name}".encode("utf-8"))
                destination = runtime / name
                destination.unlink()
                os.symlink(external, destination)
                before = external.read_bytes()

                with self.assertRaisesRegex(SystemExit, "runtime file must not be a symlink"):
                    oil_ppt.read_deck(self.project)

                self.assertEqual(external.read_bytes(), before)
                destination.unlink()
                shutil.copy2(RUNTIME_SOURCE / name, destination)

    def test_package_runtime_source_hashes_invalidate_confirmation_before_project_sync(self) -> None:
        oil_ppt.slide_add(self.project, "cover", "Cover", "statement", None)
        render_preview(self.project)
        state = __import__("state")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "runtime"
            shutil.copytree(RUNTIME_SOURCE, source)
            with mock.patch.object(state, "RUNTIME_SOURCE", source):
                old_manifest = state.input_manifest(self.project)
                self.assertIn("@runtime-source/deck.js", old_manifest)
                state.write_state(self.project, preview_manifest=old_manifest, preview_confirmed=True)
                (source / "deck.js").write_bytes((source / "deck.js").read_bytes() + b"\n// future runtime\n")
                self.assertNotEqual(old_manifest, state.input_manifest(self.project))
                with self.assertRaisesRegex(SystemExit, "stale"):
                    confirm_preview(self.project)

    def test_parser_rejects_custom_script_global_css_and_remote_asset(self) -> None:
        oil_ppt.slide_add(self.project, "cover", "Cover", None, None)
        source = self.project / "slides" / "cover.html"
        for needle, replacement, expected in (
            (".s-cover .slide-title", "body .slide-title", "leaks outside"),
            ("</body>", "<script>alert(1)</script></body>", "only the ../runtime/deck.js"),
            ("Edit this slide directly in HTML.", '<img src="https://example.test/image.png">', "remote or file URL"),
        ):
            original = source.read_text(encoding="utf-8")
            source.write_text(original.replace(needle, replacement, 1), encoding="utf-8")
            with self.subTest(expected=expected), self.assertRaisesRegex(SystemExit, expected):
                parse_slide(source, "cover")
            source.write_text(original, encoding="utf-8")

    def test_parser_allows_scoped_modern_css(self) -> None:
        oil_ppt.slide_add(self.project, "cover", "Cover", None, None)
        source = self.project / "slides" / "cover.html"
        text = source.read_text(encoding="utf-8")
        text = text.replace(
            "/* OIL-SLIDE-CSS:END */",
            """@media (max-width: 1200px) { .s-cover .slide-title:is(h1, h2) { letter-spacing: -.02em; } }
@keyframes s-cover-arrive { from { opacity: 0; } to { opacity: 1; } }
/* OIL-SLIDE-CSS:END */""",
        )
        source.write_text(text, encoding="utf-8")
        parse_slide(source, "cover")

    def test_literal_css_url_in_code_is_not_treated_as_a_resource(self) -> None:
        oil_ppt.slide_add(self.project, "cover", "Cover", None, None)
        source = self.project / "slides" / "cover.html"
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "Edit this slide directly in HTML.",
                '<code>background:url("https://example.test/demo.png")</code>',
            ),
            encoding="utf-8",
        )
        parse_slide(source, "cover")
        from media_assets import scan_slide_media
        self.assertEqual(scan_slide_media(self.project, source)["errors"], [])

    def test_css_url_text_inside_a_string_is_not_treated_as_a_resource(self) -> None:
        oil_ppt.slide_add(self.project, "cover", "Cover", None, None)
        source = self.project / "slides" / "cover.html"
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "/* OIL-SLIDE-CSS:END */",
                ".s-cover .slide-subtitle::after { content: 'url(https://example.test/not-a-resource.png)'; }\n/* OIL-SLIDE-CSS:END */",
            ),
            encoding="utf-8",
        )
        parse_slide(source, "cover")
        from media_assets import scan_slide_media
        self.assertEqual(scan_slide_media(self.project, source)["errors"], [])

    def test_status_points_to_the_single_page_that_needs_repair(self) -> None:
        from workflow import confirm_outline
        confirm_outline(self.project)
        oil_ppt.slide_add(self.project, "cover", "Cover", None, None)
        source = self.project / "slides" / "cover.html"
        original = source.read_text(encoding="utf-8")
        source.write_text(original.replace(".s-cover .slide-title", "body .slide-title", 1), encoding="utf-8")
        next_step = oil_ppt.status_payload(self.project)["next"]
        self.assertEqual(next_step["action"], "edit_slide")
        self.assertEqual(Path(next_step["path"]), source)
        source.write_text(original.replace("Edit this slide directly in HTML.", '<img src="../assets/missing.png" alt="Missing">'), encoding="utf-8")
        next_step = oil_ppt.status_payload(self.project)["next"]
        self.assertEqual(next_step["action"], "fix_media")
        self.assertEqual(Path(next_step["path"]), source)

    def test_titles_are_escaped_when_copying_and_duplicating(self) -> None:
        dangerous = 'A\"><img src=x onerror=alert(1)>'
        oil_ppt.slide_add(self.project, "cover", dangerous, "blank", None)
        source = self.project / "slides" / "cover.html"
        self.assertIn('data-title="A&quot;', source.read_text(encoding="utf-8"))
        parse_slide(source, "cover")
        oil_ppt.slide_duplicate(self.project, "cover", "copy", dangerous)
        copied = (self.project / "slides" / "copy.html").read_text(encoding="utf-8")
        self.assertIn('data-title="A&quot;', copied)
        self.assertNotIn('data-title="A\"><img', copied)
        parse_slide(self.project / "slides" / "copy.html", "copy")

    def test_duplicate_handles_numeric_ids_without_touching_longer_class_names(self) -> None:
        oil_ppt.slide_add(self.project, "a", "A", None, None)
        source = self.project / "slides" / "a.html"
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                ".s-a .slide-title {",
                ".s-a .s-audience { color: var(--ink); }\n.s-a .slide-title {",
            ),
            encoding="utf-8",
        )
        oil_ppt.slide_duplicate(self.project, "a", "1copy", None)
        copied = (self.project / "slides" / "1copy.html").read_text(encoding="utf-8")
        self.assertIn(".s-1copy .s-audience", copied)
        self.assertIn('class="oil-slide s-1copy"', copied)
        parse_slide(self.project / "slides" / "1copy.html", "1copy")

    def test_theme_is_metadata_only_and_reaches_generated_outputs(self) -> None:
        from workflow import confirm_outline
        confirm_outline(self.project)
        oil_ppt.slide_add(self.project, "cover", "Cover", None, None)
        project, deck = oil_ppt.read_deck(self.project)
        deck["theme"] = {"palette": "ink-slate", "typography": "technical", "shape": "crisp"}
        oil_ppt.save_deck(project, deck)
        before = (self.project / "slides" / "cover.html").read_bytes()
        self.assertIn("--accent:#9ED0FF", (self.project / "runtime" / "theme.css").read_text(encoding="utf-8"))
        self.assertIn('../runtime/theme.css', before.decode("utf-8"))
        preview = render_preview(self.project)
        self.assertIn("--accent:#9ED0FF", preview.read_text(encoding="utf-8"))
        confirm_preview(self.project)
        built = build_project(self.project)
        self.assertIn("--accent:#9ED0FF", built.read_text(encoding="utf-8"))
        self.assertEqual(before, (self.project / "slides" / "cover.html").read_bytes())

    def test_preview_rebases_and_build_inlines_real_media_references(self) -> None:
        pixel = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        asset = self.project / "assets" / "pixel.png"
        asset.write_bytes(pixel)
        oil_ppt.slide_add(self.project, "cover", "Cover", None, None)
        source = self.project / "slides" / "cover.html"
        text = source.read_text(encoding="utf-8")
        text = text.replace(
            ".s-cover .slide-subtitle {",
            '.s-cover .media-proof { background-image: url("../assets/pixel.png"); }\n.s-cover .slide-subtitle {',
        ).replace(
            "</div></section>",
            '<picture class="media-proof"><source srcset="../assets/pixel.png 1x"><img src="../assets/pixel.png" alt="One verification pixel"></picture></div></section>',
        )
        source.write_text(text, encoding="utf-8")
        preview = render_preview(self.project)
        preview_text = preview.read_text(encoding="utf-8")
        self.assertIn('src="assets/pixel.png"', preview_text)
        self.assertIn('url("assets/pixel.png")', preview_text)
        confirm_preview(self.project)
        built = build_project(self.project)
        built_text = built.read_text(encoding="utf-8")
        self.assertIn("data:image/png;base64,", built_text)
        self.assertNotIn("../assets/pixel.png", built_text)

    def test_preview_rebases_only_url_syntax_not_visible_copy(self) -> None:
        oil_ppt.slide_add(self.project, "cover", "Cover", None, None)
        source = self.project / "slides" / "cover.html"
        text = source.read_text(encoding="utf-8").replace(
            "Edit this slide directly in HTML.",
            "Use <code>../assets/example.png</code> in your page.",
        )
        source.write_text(text, encoding="utf-8")
        preview = render_preview(self.project).read_text(encoding="utf-8")
        self.assertIn("<code>../assets/example.png</code>", preview)

    def test_preview_and_build_preserve_escaped_markup_examples(self) -> None:
        oil_ppt.slide_add(self.project, "cover", "Cover", None, None)
        source = self.project / "slides" / "cover.html"
        example = '&lt;img src="../assets/example.png" alt="Example"&gt;'
        source.write_text(
            source.read_text(encoding="utf-8").replace("Edit this slide directly in HTML.", f"<code>{example}</code>"),
            encoding="utf-8",
        )
        preview = render_preview(self.project)
        self.assertIn(example, preview.read_text(encoding="utf-8"))
        confirm_preview(self.project)
        built = build_project(self.project)
        self.assertIn(example, built.read_text(encoding="utf-8"))

    def test_pptx_export_rebuilds_a_stale_prior_final(self) -> None:
        oil_ppt.slide_add(self.project, "first", "First", "statement", None)
        render_preview(self.project)
        confirm_preview(self.project)
        first_final = build_project(self.project)
        self.assertEqual(first_final.read_text(encoding="utf-8").count('<section class="oil-slide'), 1)
        oil_ppt.slide_add(self.project, "second", "Second", "comparison", None)
        render_preview(self.project)
        confirm_preview(self.project)

        def fake_export(**values: object) -> dict:
            html_path = Path(values["html_path"])
            self.assertEqual(html_path.read_text(encoding="utf-8").count('<section class="oil-slide'), 2)
            return {"ok": True, "slide_count": 2}

        with mock.patch.object(oil_ppt, "chrome_binary", return_value="/mock/chrome"), mock.patch(
            "pptx_export.export_hybrid_pptx", side_effect=fake_export
        ):
            report = oil_ppt.export_pptx_project(self.project)
        self.assertEqual(report["slide_count"], 2)


if __name__ == "__main__":
    unittest.main()
