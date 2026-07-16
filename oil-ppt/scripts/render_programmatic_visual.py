#!/usr/bin/env python3
"""Render a local HTML/CSS authoring file into a verified static PNG."""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse

from build_deck import chrome_binary
from cdp_validate import WebSocket, _stop_browser
from media_assets import inspect_image


RESOURCE = re.compile(r'''(?:src|href)\s*=\s*["']([^"']+)["']|url\(\s*["']?([^)'"\s]+)''', re.I)


def _screenshot_browser() -> str | None:
    """Find the same local Chromium family used by build validation."""
    candidates = [
        os.environ.get("CHROME_BIN") or "",
        chrome_binary() or "",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
        shutil.which("msedge") or "",
    ]
    return next((value for value in candidates if value and Path(value).is_file()), None)


def _capture_with_cdp(browser: str, source: Path, output: Path, width: int, height: int) -> None:
    profile_ctx = tempfile.TemporaryDirectory(prefix="oil-ppt-render-cdp-")
    profile = Path(profile_ctx.name)
    command = [
        browser, "--headless", "--no-sandbox", "--allow-file-access-from-files",
        "--disable-background-networking", "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows", "--disable-component-update", "--disable-default-apps",
        "--disable-renderer-backgrounding", "--disable-sync", "--disable-features=PaintHolding,RenderDocument",
        "--enable-features=CDPScreenshotNewSurface", "--enable-unsafe-swiftshader", "--force-color-profile=srgb",
        "--hide-scrollbars", "--metrics-recording-only", "--no-first-run", f"--user-data-dir={profile}",
        "--remote-debugging-port=0", f"--window-size={width},{height}", source.as_uri(),
    ]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    websocket: WebSocket | None = None
    try:
        deadline = time.monotonic() + 30
        port_file = profile / "DevToolsActivePort"
        while time.monotonic() < deadline and not port_file.exists():
            time.sleep(.05)
        if not port_file.exists():
            raise RuntimeError("Chromium did not expose a DevTools port for programmatic rendering.")
        port = int(port_file.read_text(encoding="utf-8").splitlines()[0])
        pages: list[dict] = []
        while time.monotonic() < deadline and not pages:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as response:
                    pages = [item for item in json.load(response) if item.get("type") == "page"]
            except OSError:
                time.sleep(.05)
        if not pages:
            raise RuntimeError("Chromium opened no inspectable page for programmatic rendering.")
        target_uri = source.as_uri()
        page = next((item for item in pages if item.get("url", "").startswith(target_uri)), pages[0])
        websocket = WebSocket(page["webSocketDebuggerUrl"])
        websocket.sock.settimeout(30)
        request_id = 0

        def request(method: str, params: dict | None = None) -> dict:
            nonlocal request_id
            request_id += 1
            websocket.send_json({"id": request_id, "method": method, "params": params or {}})
            while True:
                message = websocket.recv_json()
                if message.get("id") == request_id:
                    if message.get("error"):
                        raise RuntimeError(f"Chromium {method} failed: {message['error']}")
                    return message.get("result") or {}

        request("Emulation.setDeviceMetricsOverride", {
            "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
        })
        request("Page.navigate", {"url": target_uri})
        ready_expression = "document.readyState==='complete'&&(!document.fonts||document.fonts.status==='loaded')&&[...document.images].every(i=>i.complete)"
        while time.monotonic() < deadline:
            result = request("Runtime.evaluate", {"expression": ready_expression, "returnByValue": True})
            if ((result.get("result") or {}).get("value")) is True:
                break
            time.sleep(.1)
        else:
            raise RuntimeError("Programmatic visual page did not become ready before capture.")
        screenshot = request("Page.captureScreenshot", {
            "format": "png", "fromSurface": True, "captureBeyondViewport": False,
        })
        encoded = screenshot.get("data")
        if not isinstance(encoded, str) or not encoded:
            raise RuntimeError("Chromium returned no screenshot data.")
        output.write_bytes(base64.b64decode(encoded))
    finally:
        if websocket:
            websocket.close()
        _stop_browser(process, profile)
        try:
            profile_ctx.cleanup()
        except OSError:
            pass


def _validate_local_document(source: Path) -> None:
    text = source.read_text(encoding="utf-8")
    if re.search(r'''(?:src|href)\s*=\s*["'](?:https?:)?//|url\(\s*["']?(?:https?:)?//|@import\s+(?:url\()?\s*["']?(?:https?:)?//''', text, re.I):
        raise ValueError("Programmatic visual HTML must not load remote resources or CDNs.")
    if re.search(r'''(?:fetch|WebSocket|EventSource)\s*\(\s*["'](?:https?:)?//|\.open\s*\([^,]+,\s*["'](?:https?:)?//''', text, re.I):
        raise ValueError("Programmatic visual HTML must not request remote resources at runtime.")
    root = source.parent.resolve()
    for match in RESOURCE.finditer(text):
        value = (match.group(1) or match.group(2) or "").strip()
        if not value or value.startswith(("data:", "#", "about:")):
            continue
        parsed = urlparse(value)
        if parsed.scheme and parsed.scheme != "file":
            raise ValueError(f"Unsupported resource scheme in programmatic visual: {parsed.scheme}")
        candidate = Path(unquote(parsed.path)) if parsed.scheme == "file" else source.parent / unquote(parsed.path)
        resolved = candidate.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError(f"Programmatic visual resource must stay beside the source HTML: {value}")
        if not resolved.is_file():
            raise ValueError(f"Programmatic visual resource is missing: {value}")


def render_html_visual(source_arg: Path, output_arg: Path, *, width: int = 1600, height: int = 900) -> dict:
    source = source_arg.expanduser().resolve()
    output = output_arg.expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in {".html", ".htm"}:
        raise SystemExit(f"Programmatic visual source must be a local HTML file: {source}")
    if output.suffix.lower() != ".png":
        raise SystemExit("Programmatic visual output must use the .png extension.")
    if not 320 <= width <= 4096 or not 240 <= height <= 4096:
        raise SystemExit("Programmatic visual dimensions must stay within 320–4096 × 240–4096.")
    try:
        _validate_local_document(source)
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise SystemExit(f"Invalid programmatic visual HTML: {error}") from error
    browser = _screenshot_browser()
    if not browser:
        raise SystemExit("No Chromium browser found; media render-html requires the same browser used by build validation.")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".oil-ppt-render-", suffix=".png", dir=output.parent)
    os.close(descriptor)
    temporary_output = Path(temporary_name)
    temporary_output.unlink(missing_ok=True)
    try:
        try:
            _capture_with_cdp(browser, source, temporary_output, width, height)
        except (OSError, RuntimeError, ValueError) as error:
            raise SystemExit(f"Programmatic visual render failed: {error}") from error
        try:
            details = inspect_image(temporary_output)
        except ValueError as error:
            raise SystemExit(f"Programmatic visual render produced an invalid PNG: {error}") from error
        if details["width"] != width or details["height"] != height:
            raise SystemExit(
                f"Programmatic visual render size mismatch: expected {width}×{height}, got {details['width']}×{details['height']}"
            )
        os.replace(temporary_output, output)
    finally:
        temporary_output.unlink(missing_ok=True)
    return {"source": str(source), "output": str(output), "width": width, "height": height, "sha256": details["sha256"]}
