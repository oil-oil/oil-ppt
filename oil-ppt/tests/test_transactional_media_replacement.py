from __future__ import annotations

import io
import http.client
import json
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest import mock
from urllib.parse import quote


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import media_assets  # noqa: E402
import render_outline_review  # noqa: E402
import text_editor  # noqa: E402
from oil_ppt import atomic_write_json, preview_state_path, project_state_path  # noqa: E402


def png(width: int = 2, height: int = 2) -> bytes:
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big")


def jpeg(width: int = 2, height: int = 2) -> bytes:
    return b"\xff\xd8\xff\xc0\x00\x07\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\xff\xd9"


def webp(width: int = 2, height: int = 2) -> bytes:
    return (
        b"RIFF\x16\x00\x00\x00WEBPVP8X" + b"\x00" * 8
        + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
    )


def svg(width: int = 2, height: int = 2) -> bytes:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"/>'.encode()


def deck() -> dict:
    return {
        "title": "媒体事务测试",
        "palette": "oil-yellow",
        "typography": "clean",
        "shape": "soft",
        "media_policy": "required",
        "click_navigation": False,
        "slides": [
            {
                "id": "cover", "title": "封面", "template": "cover", "variant": "default",
                "decor": "none", "image": "assets/original.svg", "media_frame": "content",
            },
            {
                "id": "gallery", "title": "过程", "template": "sequence-gallery", "variant": "default",
                "decor": "none", "content": "过程证据", "media_frame": "content",
                "steps": [
                    {"title": "一步", "body": "说明", "image": "assets/nested.svg"},
                    {"title": "二步", "body": "说明", "image": "assets/nested-2.svg"},
                    {"title": "三步", "body": "说明", "image": "assets/nested-3.svg"},
                ],
            },
        ],
    }


class MediaUploadValidationTests(unittest.TestCase):
    def test_png_jpeg_webp_and_svg_are_content_checked(self) -> None:
        cases = (
            ("image.png", "image/png", png()),
            ("image.jpg", "image/jpeg", jpeg()),
            ("image.webp", "image/webp", webp()),
            ("image.svg", "image/svg+xml", svg()),
        )
        for filename, content_type, payload in cases:
            with self.subTest(filename=filename):
                details = media_assets.validate_editor_upload(filename, content_type, payload)
                self.assertEqual((details["width"], details["height"]), (2, 2))

    def test_traversal_malformed_oversized_unsupported_and_dimensions_are_rejected(self) -> None:
        invalid = (
            ("../image.png", "image/png", png(), "must not contain a path"),
            ("image.png", "image/png", b"not a png", "invalid PNG"),
            ("image.png", "image/jpeg", png(), "does not match"),
            ("image.gif", "image/gif", b"GIF89a", "must be a PNG"),
            ("huge.png", "image/png", png(media_assets.MAX_EDITOR_IMAGE_DIMENSION + 1, 1), "must not exceed"),
            ("large.svg", "image/svg+xml", b" " * (media_assets.MAX_EDITOR_UPLOAD_BYTES + 1), "exceeds"),
            ("active.svg", "image/svg+xml", b'<svg width="2" height="2" onload="alert(1)"/>', "event handlers"),
        )
        for filename, content_type, payload, message in invalid:
            with self.subTest(filename=filename, message=message), self.assertRaisesRegex(ValueError, message):
                media_assets.validate_editor_upload(filename, content_type, payload)

    def test_binary_request_reader_enforces_headers_and_size(self) -> None:
        handler = text_editor.EditorHandler.__new__(text_editor.EditorHandler)
        handler.headers = {
            "Content-Length": str(len(png())),
            "Content-Type": "image/png",
            "X-Oil-Ppt-Media-Path": quote("/slides/0/image", safe=""),
            "X-Oil-Ppt-Filename": quote("封面.png", safe=""),
        }
        handler.rfile = io.BytesIO(png())
        self.assertEqual(handler._read_upload()[:3], ("/slides/0/image", "封面.png", "image/png"))

        handler.headers["Content-Length"] = str(media_assets.MAX_EDITOR_UPLOAD_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            handler._read_upload()

        handler.headers["Content-Length"] = str(len(png()) + 1)
        handler.rfile = io.BytesIO(png())
        with self.assertRaisesRegex(ValueError, "ended before"):
            handler._read_upload()


class MediaBindingRenderTests(unittest.TestCase):
    def test_top_level_and_nested_bindings_receive_picker_paths_only_in_authoring(self) -> None:
        data = deck()
        bindings = media_assets.editable_outline_media(data)
        self.assertEqual(bindings["/slides/0/image"], "assets/original.svg")
        self.assertEqual(bindings["/slides/1/steps/2/image"], "assets/nested-3.svg")

        fragment = "".join(
            f'<img src="{value}" alt="">' for value in bindings.values()
        )
        annotated = render_outline_review.annotate_media_fragment(fragment, data["slides"][0], 0)
        self.assertIn('data-media-path="/slides/0/image"', annotated)

        with mock.patch.object(render_outline_review, "validate_outline", return_value=data["slides"]):
            authoring = render_outline_review.render(data, authoring=True, editor_token="token", editor_recovery_id="id")
            formal = render_outline_review.render(data)
        for path in bindings:
            self.assertIn(path, authoring)
        self.assertIn("/api/media", authoring)
        self.assertIn("替换这张图片", authoring)
        self.assertNotIn("/api/media", formal)
        self.assertNotIn("替换这张图片", formal)


class MediaEditorTransactionTests(unittest.TestCase):
    @contextmanager
    def editor(self):
        with tempfile.TemporaryDirectory(prefix="oil-ppt-media-editor-") as temporary:
            project = Path(temporary)
            (project / "assets").mkdir()
            for name in ("original.svg", "nested.svg", "nested-2.svg", "nested-3.svg"):
                (project / "assets" / name).write_bytes(svg())
            outline = project / "outline.json"
            atomic_write_json(outline, deck())
            atomic_write_json(project_state_path(project), {"visual_plan": {"outline_sha256": "initial"}})

            def fake_preview(_project: Path, target: Path, *_args: object, **_kwargs: object) -> None:
                target.write_text("<!doctype html><title>preview</title>", encoding="utf-8")
                atomic_write_json(preview_state_path(outline), {"preview": str(target), "confirmed": False})

            with (
                mock.patch.object(text_editor, "outline_confirmation_valid", return_value=True),
                mock.patch.object(text_editor, "visual_plan_valid", return_value=True),
                mock.patch.object(text_editor, "preview_state_status", return_value=("awaiting-confirmation", {}, None)),
                mock.patch.object(text_editor, "validate_outline", side_effect=lambda data, _templates: data["slides"]),
                mock.patch.object(text_editor, "enforce_outline_quality"),
                mock.patch.object(text_editor, "generate_preview", side_effect=fake_preview),
            ):
                session = text_editor.EditorSession(project)
                try:
                    yield session, project, outline
                finally:
                    session.close()

    def test_nested_replacement_duplicate_names_and_undo_redo_share_one_history(self) -> None:
        with self.editor() as (session, project, _outline):
            path = "/slides/1/steps/0/image"
            first = session.replace_media(path, "capture.png", "image/png", png(3, 2))
            self.assertEqual(first["revision"], 1)
            first_asset = first["media_values"][path]
            second = session.replace_media(path, "capture.png", "image/png", png(3, 2))
            self.assertEqual(second["revision"], 2)
            second_asset = second["media_values"][path]

            self.assertNotEqual(first_asset, second_asset)
            self.assertTrue((project / first_asset).is_file())
            self.assertTrue((project / second_asset).is_file())
            self.assertEqual(session.data["slides"][1]["media_frame"], "content")
            self.assertEqual(session.undo()["media_values"][path], first_asset)
            self.assertEqual(session.redo()["media_values"][path], second_asset)
            self.assertTrue(session.draft_path.is_file())

    def test_text_media_design_and_structure_share_one_revision_and_history(self) -> None:
        with self.editor() as (session, project, _outline):
            media_path = "/slides/1/steps/0/image"
            session.apply_edit("/slides/1/title", "更新后的过程", expected_revision=0)
            replaced = session.replace_media(media_path, "evidence.png", "image/png", png(4, 3))
            session.apply_settings({"shape": "crisp"})
            session.apply_slide_operation("duplicate", {
                "action": "duplicate",
                "slide_id": "gallery",
                "expected_revision": 3,
                "operation_id": "operation-unified-editor-history",
            })

            self.assertEqual(session.revision, 4)
            self.assertEqual([slide["id"] for slide in session.data["slides"]], [
                "cover", "gallery", "gallery-copy",
            ])
            self.assertEqual(session.data["shape"], "crisp")
            self.assertEqual(session.data["slides"][1]["steps"][0]["image"], replaced["media_values"][media_path])

            session.undo()
            self.assertEqual(len(session.data["slides"]), 2)
            session.undo()
            self.assertEqual(session.data["shape"], "soft")
            session.undo()
            self.assertEqual(session.data["slides"][1]["steps"][0]["image"], "assets/nested.svg")
            session.undo()
            self.assertEqual(session.data["slides"][1]["title"], "过程")
            self.assertEqual(session.revision, 8)

            session.discard()
            self.assertFalse((project / replaced["media_values"][media_path]).exists())

    def test_authenticated_binary_upload_endpoint_updates_the_binding(self) -> None:
        with self.editor() as (session, project, _outline):
            token = "test-token"
            handler = type("TestEditorHandler", (text_editor.EditorHandler,), {"session": session, "token": token})
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            server.daemon_threads = True
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            try:
                payload = png(6, 4)
                connection.request("POST", "/api/media", body=payload, headers={
                    "Content-Type": "image/png",
                    "Content-Length": str(len(payload)),
                    "X-Oil-Ppt-Token": token,
                    "X-Oil-Ppt-Media-Path": quote("/slides/0/image", safe=""),
                    "X-Oil-Ppt-Filename": quote("endpoint.png", safe=""),
                })
                response = connection.getresponse()
                result = json.loads(response.read())
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
            self.assertEqual(response.status, 200)
            relative = result["media_values"]["/slides/0/image"]
            self.assertTrue((project / relative).is_file())

    def test_discard_removes_all_staged_assets_and_restores_binding(self) -> None:
        with self.editor() as (session, project, _outline):
            state = session.replace_media("/slides/0/image", "new.svg", "image/svg+xml", svg(4, 3))
            relative = state["media_values"]["/slides/0/image"]
            self.assertTrue((project / relative).is_file())

            discarded = session.discard()
            self.assertEqual(discarded["media_values"]["/slides/0/image"], "assets/original.svg")
            self.assertFalse((project / relative).exists())
            self.assertFalse(session.draft_path.exists())

    def test_finish_persists_asset_and_outline_and_removes_superseded_upload(self) -> None:
        with self.editor() as (session, project, outline):
            first = session.replace_media("/slides/0/image", "same.png", "image/png", png(3, 2))
            old_asset = first["media_values"]["/slides/0/image"]
            second = session.replace_media("/slides/0/image", "same.png", "image/png", png(5, 4))
            final_asset = second["media_values"]["/slides/0/image"]

            result = session.finish([], report_complete=True)
            saved = json.loads(outline.read_text(encoding="utf-8"))
            self.assertTrue(result["changed"])
            self.assertEqual(saved["slides"][0]["image"], final_asset)
            self.assertTrue((project / final_asset).is_file())
            self.assertFalse((project / old_asset).exists())
            self.assertFalse(session.draft_path.exists())

    def test_finish_failure_rolls_back_outline_state_preview_and_staged_assets(self) -> None:
        with self.editor() as (session, project, outline):
            original_outline = outline.read_bytes()
            original_state = project_state_path(project).read_bytes()
            state = session.replace_media("/slides/0/image", "new.webp", "image/webp", webp())
            staged = state["media_values"]["/slides/0/image"]
            draft_before = session.draft_path.read_bytes()

            with mock.patch.object(text_editor, "generate_preview", side_effect=OSError("render failed")):
                with self.assertRaisesRegex(ValueError, "render failed"):
                    session.finish([], report_complete=True)

            self.assertEqual(outline.read_bytes(), original_outline)
            self.assertEqual(project_state_path(project).read_bytes(), original_state)
            self.assertEqual(session.draft_path.read_bytes(), draft_before)
            self.assertTrue((project / staged).is_file())
            self.assertEqual(session.data["slides"][0]["image"], staged)

    def test_draft_recovery_retains_staged_asset_until_explicit_discard(self) -> None:
        with self.editor() as (session, project, _outline):
            state = session.replace_media("/slides/0/image", "recover.svg", "image/svg+xml", svg(7, 5))
            staged = state["media_values"]["/slides/0/image"]
            session.close()

            recovered = text_editor.EditorSession(project)
            try:
                self.assertEqual(recovered.data["slides"][0]["image"], staged)
                self.assertIn(staged, recovered.staged_assets)
                recovered.discard()
                self.assertFalse((project / staged).exists())
            finally:
                recovered.close()


if __name__ == "__main__":
    unittest.main()
