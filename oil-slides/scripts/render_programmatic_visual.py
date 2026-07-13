#!/usr/bin/env python3
"""Render a local HTML/CSS authoring file into a verified static PNG."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from build_deck import chrome_binary
from media_assets import inspect_image


RESOURCE = re.compile(r'''(?:src|href)\s*=\s*["']([^"']+)["']|url\(\s*["']?([^)'"\s]+)''', re.I)


def _playwright_runtime() -> tuple[str, str]:
    package_candidates: list[Path] = []
    for value in os.environ.get("NODE_PATH", "").split(os.pathsep):
        if value:
            package_candidates.append(Path(value).expanduser() / "playwright" / "package.json")
    package_candidates.extend(Path.home().glob(".cache/codex-runtimes/**/node_modules/playwright/package.json"))
    package = next((path.resolve() for path in package_candidates if path.is_file()), None)
    if package is None:
        raise SystemExit("media render-html requires the bundled Playwright runtime; run it inside Codex or provide NODE_PATH with playwright.")
    module_root = package.parent.parent
    node_candidates = [
        os.environ.get("NODE_BINARY") or "",
        shutil.which("node") or "",
        str(module_root.parent / "bin" / ("node.exe" if os.name == "nt" else "node")),
    ]
    node = next((value for value in node_candidates if value and Path(value).is_file()), None)
    if node is None:
        raise SystemExit("media render-html could not find Node.js for the bundled Playwright runtime.")
    return node, str(module_root)


def _validate_local_document(source: Path) -> None:
    text = source.read_text(encoding="utf-8")
    if re.search(r'''(?:src|href)\s*=\s*["'](?:https?:)?//|url\(\s*["']?(?:https?:)?//|@import\s+(?:url\()?\s*["']?(?:https?:)?//''', text, re.I):
        raise ValueError("Programmatic visual HTML must not load remote resources or CDNs.")
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
    browser = chrome_binary()
    if not browser:
        raise SystemExit("No Chromium browser found; media render-html requires the same browser used by build validation.")
    node, module_root = _playwright_runtime()
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".oil-slides-render-", suffix=".png", dir=output.parent)
    os.close(descriptor)
    temporary_output = Path(temporary_name)
    temporary_output.unlink(missing_ok=True)
    script = r'''
const { chromium } = require('playwright');
(async () => {
  const [source, output, executablePath, widthText, heightText] = process.argv.slice(2);
  const browser = await chromium.launch({ headless: true, executablePath });
  try {
    const page = await browser.newPage({ viewport: { width: Number(widthText), height: Number(heightText) }, deviceScaleFactor: 1 });
    const remoteRequests = [];
    page.on('request', request => { if (/^https?:/i.test(request.url())) remoteRequests.push(request.url()); });
    await page.route('**/*', route => /^https?:/i.test(route.request().url()) ? route.abort('blockedbyclient') : route.continue());
    await page.context().setOffline(true);
    await page.goto(source, { waitUntil: 'load' });
    await page.evaluate(async () => {
      if (document.fonts) await document.fonts.ready;
      await Promise.all([...document.images].map(image => image.complete && image.naturalWidth ? null : new Promise((resolve, reject) => {
        image.addEventListener('load', resolve, { once: true });
        image.addEventListener('error', reject, { once: true });
      })));
    });
    if (remoteRequests.length) throw new Error(`Remote resource blocked: ${remoteRequests[0]}`);
    await page.screenshot({ path: output, type: 'png', animations: 'disabled', caret: 'hide', scale: 'css' });
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.stack || String(error)); process.exit(1); });
'''
    try:
        with tempfile.TemporaryDirectory(prefix="oil-slides-render-") as temp_dir:
            runner = Path(temp_dir) / "render.js"
            runner.write_text(script, encoding="utf-8")
            env = dict(os.environ)
            env["NODE_PATH"] = module_root + (os.pathsep + env["NODE_PATH"] if env.get("NODE_PATH") else "")
            try:
                result = subprocess.run(
                    [node, str(runner), source.as_uri(), str(temporary_output), browser, str(width), str(height)],
                    capture_output=True, text=True, check=False, timeout=45, env=env,
                )
            except subprocess.TimeoutExpired as error:
                raise SystemExit("Programmatic visual render timed out in Playwright.") from error
        if result.returncode or not temporary_output.is_file():
            detail = (result.stderr or result.stdout or "Playwright wrote no screenshot").strip()
            raise SystemExit(f"Programmatic visual render failed: {detail}")
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
