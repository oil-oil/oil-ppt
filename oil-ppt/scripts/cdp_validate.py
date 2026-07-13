#!/usr/bin/env python3
"""Stdlib-only Chrome DevTools client for oil-ppt DOM validation."""
from __future__ import annotations

import base64
import json
import os
import secrets
import signal
import socket
import struct
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    while size:
        chunk = sock.recv(size)
        if not chunk:
            raise RuntimeError("Chrome DevTools websocket closed unexpectedly.")
        chunks.append(chunk)
        size -= len(chunk)
    return b"".join(chunks)


class WebSocket:
    def __init__(self, url: str):
        parsed = urllib.parse.urlparse(url)
        self.sock = socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 80), timeout=5)
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        request = (
            f"GET {path} HTTP/1.1\r\nHost: {parsed.hostname}:{parsed.port}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            response += self.sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError("Chrome DevTools websocket handshake failed.")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def send_json(self, value: dict) -> None:
        payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
        mask = secrets.token_bytes(4)
        header = bytearray([0x81])
        if len(payload) < 126:
            header.append(0x80 | len(payload))
        elif len(payload) < 65536:
            header.extend([0x80 | 126])
            header.extend(struct.pack("!H", len(payload)))
        else:
            header.extend([0x80 | 127])
            header.extend(struct.pack("!Q", len(payload)))
        header.extend(mask)
        masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        self.sock.sendall(header + masked)

    def recv_json(self) -> dict:
        message_opcode: int | None = None
        chunks: list[bytes] = []
        while True:
            first, second = _recv_exact(self.sock, 2)
            finished = bool(first & 0x80)
            opcode = first & 0x0F
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", _recv_exact(self.sock, 2))[0]
            elif length == 127:
                length = struct.unpack("!Q", _recv_exact(self.sock, 8))[0]
            mask = _recv_exact(self.sock, 4) if second & 0x80 else b""
            payload = _recv_exact(self.sock, length)
            if mask:
                payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
            if opcode == 0x8:
                raise RuntimeError("Chrome DevTools websocket closed before validation completed.")
            if opcode in {0x1, 0x2}:
                message_opcode = opcode
                chunks = [payload]
            elif opcode == 0x0 and message_opcode is not None:
                chunks.append(payload)
            else:
                continue
            if finished:
                return json.loads(b"".join(chunks).decode("utf-8"))


def _which(name: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _stop_browser(process: subprocess.Popen, profile: Path) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if pkill := _which("pkill"):
            subprocess.run([pkill, "-TERM", "-f", f"--user-data-dir={profile}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif process.poll() is None:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()


def validate_file(
    chrome: str,
    html_file: Path,
    timeout: float = 15,
    viewport: tuple[int, int] | None = None,
) -> dict:
    profile_ctx = tempfile.TemporaryDirectory(prefix="oil-ppt-cdp-")
    profile = Path(profile_ctx.name)
    command = [
        chrome, "--headless", "--no-sandbox", "--allow-file-access-from-files",
        "--disable-background-networking", "--disable-background-timer-throttling", "--disable-backgrounding-occluded-windows",
        "--disable-component-update", "--disable-default-apps", "--disable-renderer-backgrounding", "--disable-sync",
        "--disable-features=PaintHolding,RenderDocument", "--enable-features=CDPScreenshotNewSurface",
        "--enable-unsafe-swiftshader", "--force-color-profile=srgb", "--hide-scrollbars",
        "--metrics-recording-only", "--no-first-run", f"--user-data-dir={profile}", "--remote-debugging-port=0",
        *([f"--window-size={viewport[0]},{viewport[1]}"] if viewport else []),
        html_file.resolve().as_uri(),
    ]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    websocket: WebSocket | None = None
    try:
        deadline = time.monotonic() + timeout
        port_file = profile / "DevToolsActivePort"
        while time.monotonic() < deadline and not port_file.exists():
            time.sleep(.05)
        if not port_file.exists():
            raise RuntimeError("Chrome did not expose a DevTools port.")
        port = int(port_file.read_text(encoding="utf-8").splitlines()[0])
        pages: list[dict] = []
        while time.monotonic() < deadline and not pages:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as response:
                    pages = [item for item in json.load(response) if item.get("type") == "page"]
            except OSError:
                time.sleep(.05)
        if not pages:
            raise RuntimeError("Chrome opened no inspectable page.")
        target_uri = html_file.resolve().as_uri()
        page = next((item for item in pages if item.get("url", "").startswith(target_uri)), pages[0])
        websocket = WebSocket(page["webSocketDebuggerUrl"])
        websocket.sock.settimeout(timeout)
        expression = """(() => {
          const root = document.documentElement;
          if (!root) return {ready:false, status:'pending', slides:0};
          const slides = document.querySelectorAll('.oil-slide').length;
          const stage = document.querySelector('.deck-stage, .slide-preview-stage');
          const images = [...document.images];
          const imagesReady = images.every(image => image.complete);
          const brokenImages = images.filter(image => image.complete && (!image.naturalWidth || !image.naturalHeight));
          const invalidBleeds = [...document.querySelectorAll('[data-bleed]')].flatMap(bleed => {
            const slide = bleed.closest('.oil-slide');
            if (!slide) return [{slide:'unknown', reason:'missing-slide'}];
            const style = getComputedStyle(bleed);
            const side = bleed.dataset.side || 'right';
            const bleedRect = bleed.getBoundingClientRect();
            const slideRect = slide.getBoundingClientRect();
            const touchesEdge = side === 'full'
              ? Math.abs(bleedRect.left - slideRect.left) <= 2
                && Math.abs(bleedRect.right - slideRect.right) <= 2
                && Math.abs(bleedRect.top - slideRect.top) <= 2
                && Math.abs(bleedRect.bottom - slideRect.bottom) <= 2
              : side === 'left'
                ? Math.abs(bleedRect.left - slideRect.left) <= 2
                : Math.abs(bleedRect.right - slideRect.right) <= 2;
            return style.position === 'absolute' && touchesEdge
              ? []
              : [{slide:slide.dataset.slideId || 'unknown', reason:`position=${style.position},side=${side},touches=${touchesEdge}`}];
          });
          const invalidLayouts = [...document.querySelectorAll('.slide-safe [data-layout]')].flatMap(layout => {
            if (!layout.getClientRects().length || getComputedStyle(layout).display === 'none') return [];
            const safe = layout.closest('.slide-safe');
            const slide = layout.closest('.oil-slide');
            if (!safe || !slide) return [{slide:'unknown', reason:'layout-missing-safe-area'}];
            const box = layout.getBoundingClientRect();
            const bounds = safe.getBoundingClientRect();
            const inside = box.left >= bounds.left - 3 && box.right <= bounds.right + 3
              && box.top >= bounds.top - 3 && box.bottom <= bounds.bottom + 3;
            if (!inside) return [{slide:slide.dataset.slideId || 'unknown', reason:'layout-outside-safe-area'}];
            const outsideChild = [...layout.children].find(child => {
              if (!child.getClientRects().length) return false;
              const childStyle = getComputedStyle(child);
              if (childStyle.display === 'none' || childStyle.visibility === 'hidden'
                || childStyle.position === 'absolute' || childStyle.position === 'fixed') return false;
              const childBox = child.getBoundingClientRect();
              return childBox.left < box.left - 3 || childBox.right > box.right + 3
                || childBox.top < box.top - 3 || childBox.bottom > box.bottom + 3;
            });
            return outsideChild ? [{
              slide:slide.dataset.slideId || 'unknown',
              reason:'layout-child-outside-container',
              child:outsideChild.className || outsideChild.tagName.toLowerCase()
            }] : [];
          });
          const invalidText = [...document.querySelectorAll('[data-fit]')].flatMap(text => {
            if (!text.getClientRects().length || getComputedStyle(text).display === 'none') return [];
            const slide = text.closest('.oil-slide');
            const overflow = text.scrollWidth > text.clientWidth + 1 || text.scrollHeight > text.clientHeight + 1;
            return overflow ? [{slide:slide?.dataset.slideId || 'unknown', reason:'text-overflow'}] : [];
          });
          const invalidBounds = [...document.querySelectorAll('.slide-safe [data-bound]')].flatMap(node => {
            if (!node.getClientRects().length) return [];
            const style = getComputedStyle(node);
            if (style.display === 'none' || style.visibility === 'hidden') return [];
            const parent = node.parentElement?.closest('[data-bound], .slide-safe');
            const slide = node.closest('.oil-slide');
            if (!parent || !slide) return [{slide:slide?.dataset.slideId || 'unknown', reason:'bound-missing-parent'}];
            const box = node.getBoundingClientRect();
            const bounds = parent.getBoundingClientRect();
            const inside = box.left >= bounds.left - 3 && box.right <= bounds.right + 3
              && box.top >= bounds.top - 3 && box.bottom <= bounds.bottom + 3;
            return inside ? [] : [{
              slide:slide.dataset.slideId || 'unknown',
              reason:'bound-outside-parent',
              node:node.className || node.tagName.toLowerCase()
            }];
          });
          const invalidOptionalRegions = [...document.querySelectorAll('[data-optional-region]')].flatMap(region => {
            if (!region.getClientRects().length) return [];
            const style = getComputedStyle(region);
            if (region.hidden || region.getAttribute('aria-hidden') === 'true' || style.display === 'none') return [];
            const hasText = (region.textContent || '').trim().length > 0;
            const hasVisual = [...region.querySelectorAll('img,svg,canvas,video')].some(node => {
              if (!node.getClientRects().length) return false;
              if (node instanceof HTMLImageElement) return node.complete && node.naturalWidth > 0 && node.naturalHeight > 0;
              const box = node.getBoundingClientRect();
              return box.width > 1 && box.height > 1;
            });
            if (hasText || hasVisual) return [];
            const slide = region.closest('.oil-slide');
            return [{
              slide:slide?.dataset.slideId || 'unknown',
              reason:'empty-optional-region',
              region:region.dataset.optionalRegion || region.className || region.tagName.toLowerCase()
            }];
          });
          const rootStyle = getComputedStyle(root);
          const stageRect = stage?.getBoundingClientRect();
          return {
          ready: document.readyState === 'complete' && (!document.fonts || document.fonts.status === 'loaded') && imagesReady,
          status: brokenImages.length || invalidBleeds.length || invalidLayouts.length || invalidText.length || invalidBounds.length || invalidOptionalRegions.length ? 'error' : (root.dataset.oilValidated === 'ok' && slides > 0 && !!stage ? 'ok' : 'pending'),
          slides,
          images: images.length,
          brokenImages: brokenImages.map(image => image.currentSrc || image.getAttribute('src') || ''),
          invalidBleeds,
          invalidLayouts,
          invalidText,
          invalidBounds,
          invalidOptionalRegions,
          viewport: {width:innerWidth, height:innerHeight},
          stage: stageRect ? {
            left:stageRect.left, top:stageRect.top, right:stageRect.right, bottom:stageRect.bottom,
            width:stageRect.width, height:stageRect.height,
            scale:Number(stage.dataset.scale || 0)
          } : null,
          tokens: {
            accent: rootStyle.getPropertyValue('--accent').trim(),
            surfaceRadius: rootStyle.getPropertyValue('--surface-radius').trim(),
            fontZh: rootStyle.getPropertyValue('--font-zh').trim()
          }
        };})()"""
        request_id = 0
        while time.monotonic() < deadline:
            request_id += 1
            websocket.send_json({"id": request_id, "method": "Runtime.evaluate", "params": {"expression": expression, "returnByValue": True}})
            while True:
                message = websocket.recv_json()
                if message.get("id") == request_id:
                    break
            if "exceptionDetails" in message.get("result", {}):
                details = message["result"]["exceptionDetails"]
                description = details.get("exception", {}).get("description") or details.get("text") or "unknown error"
                raise RuntimeError(f"Page validation JavaScript raised an exception: {description}")
            report = message["result"]["result"].get("value", {})
            if report.get("ready") and report.get("status") in {"ok", "error"}:
                return report
            time.sleep(.1)
        raise RuntimeError("Page never reached a validated DOM state.")
    finally:
        if websocket:
            websocket.close()
        _stop_browser(process, profile)
        try:
            profile_ctx.cleanup()
        except OSError:
            pass
