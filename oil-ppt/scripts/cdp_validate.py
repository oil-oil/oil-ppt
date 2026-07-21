#!/usr/bin/env python3
"""Stdlib-only Chrome DevTools client for generic slide DOM validation."""
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


VISUAL_FINDING_CATEGORIES = frozenset({"content-bounds", "readability", "contrast", "page-scroll"})


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
        self.sock = socket.create_connection(
            (parsed.hostname or "127.0.0.1", parsed.port or 80), timeout=5
        )
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
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
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
                payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
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


def _wait_for_devtools_port(port_file: Path, deadline: float, message: str = "Chrome did not expose a DevTools port.") -> int:
    """Wait through Chrome's transient empty/partial port-file creation."""
    while time.monotonic() < deadline:
        try:
            lines = port_file.read_text(encoding="utf-8").splitlines()
            port = int(lines[0].strip()) if lines and lines[0].strip() else 0
            if 0 < port < 65536:
                return port
        except (OSError, UnicodeError, ValueError):
            pass
        time.sleep(0.05)
    raise RuntimeError(message)


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
            subprocess.run(
                [pkill, "-TERM", "-f", f"--user-data-dir={profile}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    elif process.poll() is None:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
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
    """Render an HTML deck and return generic geometry and media findings.

    The validator understands only the public slide contract, so custom page DOM
    remains a first-class authoring option.
    """
    profile_ctx = tempfile.TemporaryDirectory(prefix="oil-ppt-cdp-")
    profile = Path(profile_ctx.name)
    command = [
        chrome,
        "--headless",
        "--no-sandbox",
        "--allow-file-access-from-files",
        "--disable-background-networking",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-renderer-backgrounding",
        "--disable-sync",
        "--disable-features=PaintHolding,RenderDocument",
        "--enable-features=CDPScreenshotNewSurface",
        "--enable-unsafe-swiftshader",
        "--force-color-profile=srgb",
        "--hide-scrollbars",
        "--metrics-recording-only",
        "--no-first-run",
        f"--user-data-dir={profile}",
        "--remote-debugging-port=0",
        *([f"--window-size={viewport[0]},{viewport[1]}"] if viewport else []),
        html_file.resolve().as_uri(),
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    websocket: WebSocket | None = None
    try:
        deadline = time.monotonic() + timeout
        port_file = profile / "DevToolsActivePort"
        port = _wait_for_devtools_port(port_file, deadline)
        pages: list[dict] = []
        while time.monotonic() < deadline and not pages:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/json/list", timeout=2
                ) as response:
                    pages = [item for item in json.load(response) if item.get("type") == "page"]
            except OSError:
                time.sleep(0.05)
        if not pages:
            raise RuntimeError("Chrome opened no inspectable page.")
        target_uri = html_file.resolve().as_uri()
        page = next(
            (item for item in pages if item.get("url", "").startswith(target_uri)), pages[0]
        )
        websocket = WebSocket(page["webSocketDebuggerUrl"])
        websocket.sock.settimeout(timeout)
        expression = r"""(() => {
          const documents = [document, ...[...document.querySelectorAll('iframe')]
            .map(frame => { try { return frame.contentDocument; } catch (_) { return null; } })
            .filter(Boolean)];
          const all = selector => documents.flatMap(doc => [...doc.querySelectorAll(selector)]);
          const styleOf = node => node.ownerDocument.defaultView.getComputedStyle(node);
          const visible = node => {
            const style = styleOf(node);
            return node.getClientRects().length > 0 && style.display !== 'none'
              && style.visibility !== 'hidden' && Number(style.opacity || 1) > 0;
          };
          const slideId = node => node.closest('.oil-slide')?.dataset.slideId || 'unknown';
          const describe = node => {
            if (node.id) return `#${node.id}`;
            const classes = [...node.classList].slice(0, 3).join('.');
            return `${node.tagName.toLowerCase()}${classes ? '.' + classes : ''}`;
          };
          const inside = (box, bounds, tolerance=3) => box.left >= bounds.left - tolerance
            && box.right <= bounds.right + tolerance && box.top >= bounds.top - tolerance
            && box.bottom <= bounds.bottom + tolerance;
          const slides = all('.oil-slide');
          // Aggregated decks normally hide every slide except the active one.
          // Browser QA must still measure the whole deck, so expose every slide
          // inside this disposable validation process only.
          slides.forEach(slide => {
            slide.style.setProperty('visibility', 'visible', 'important');
            slide.style.setProperty('opacity', '1', 'important');
            slide.style.setProperty('pointer-events', 'auto', 'important');
            slide.setAttribute('aria-hidden', 'false');
          });
          const stages = all('.deck-stage, .slide-preview-stage');
          const images = documents.flatMap(doc => [...doc.images]);
          const brokenImages = images.filter(image => image.complete
            && (!image.naturalWidth || !image.naturalHeight));
          const missingSafeArea = slides.filter(slide => !slide.querySelector(':scope > .slide-safe'))
            .map(slide => ({slide: slide.dataset.slideId || 'unknown', reason: 'missing-slide-safe'}));

          const invalidLayouts = all('[data-layout]').flatMap(layout => {
            if (!visible(layout)) return [];
            const safe = layout.closest('.slide-safe');
            const slide = layout.closest('.oil-slide');
            if (!safe || !slide) return [{slide: slideId(layout), node: describe(layout), reason: 'layout-missing-safe-area'}];
            return inside(layout.getBoundingClientRect(), safe.getBoundingClientRect()) ? []
              : [{slide: slideId(layout), node: describe(layout), reason: 'layout-outside-safe-area'}];
          });

          const invalidBleeds = all('[data-bleed]').flatMap(node => {
            if (!visible(node)) return [];
            const slide = node.closest('.oil-slide');
            if (!slide) return [{slide: 'unknown', node: describe(node), reason: 'bleed-missing-slide'}];
            const box = node.getBoundingClientRect();
            const bounds = slide.getBoundingClientRect();
            const side = node.dataset.bleed || node.dataset.side || 'full';
            const touches = side === 'left' ? Math.abs(box.left - bounds.left) <= 3
              : side === 'right' ? Math.abs(box.right - bounds.right) <= 3
              : side === 'top' ? Math.abs(box.top - bounds.top) <= 3
              : side === 'bottom' ? Math.abs(box.bottom - bounds.bottom) <= 3
              : Math.abs(box.left - bounds.left) <= 3 && Math.abs(box.right - bounds.right) <= 3
                && Math.abs(box.top - bounds.top) <= 3 && Math.abs(box.bottom - bounds.bottom) <= 3;
            return touches ? [] : [{slide: slideId(node), node: describe(node), reason: `bleed-does-not-touch-${side}`}];
          });

          const ignoredTextTags = new Set(['script', 'style', 'svg', 'path', 'defs', 'title']);
          const ownText = node => [...node.childNodes]
            .filter(child => child.nodeType === Node.TEXT_NODE)
            .map(child => child.nodeValue || '')
            .join(' ')
            .replace(/\s+/g, ' ')
            .trim();
          const parseColor = value => {
            if (!value || value === 'none' || value === 'transparent') return null;
            const match = value.match(/^rgba?\(([^)]+)\)$/i);
            if (!match) return null;
            const parts = match[1].replace(/\//g, ' ').split(/[\s,]+/).filter(Boolean).map(Number);
            if (parts.length < 3 || parts.slice(0, 3).some(part => !Number.isFinite(part))) return null;
            const alpha = parts.length > 3 && Number.isFinite(parts[3]) ? parts[3] : 1;
            return {r: parts[0], g: parts[1], b: parts[2], a: Math.max(0, Math.min(1, alpha))};
          };
          const composite = (top, bottom) => {
            const alpha = top.a + bottom.a * (1 - top.a);
            if (alpha <= 0) return {r: 0, g: 0, b: 0, a: 0};
            return {
              r: (top.r * top.a + bottom.r * bottom.a * (1 - top.a)) / alpha,
              g: (top.g * top.a + bottom.g * bottom.a * (1 - top.a)) / alpha,
              b: (top.b * top.a + bottom.b * bottom.a * (1 - top.a)) / alpha,
              a: alpha,
            };
          };
          const channelLuminance = value => {
            const normalized = value / 255;
            return normalized <= .04045 ? normalized / 12.92 : Math.pow((normalized + .055) / 1.055, 2.4);
          };
          const luminance = color => .2126 * channelLuminance(color.r)
            + .7152 * channelLuminance(color.g) + .0722 * channelLuminance(color.b);
          const contrastRatio = (first, second) => {
            const a = luminance(first);
            const b = luminance(second);
            return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
          };
          const cssBackground = node => {
            const layers = [];
            let current = node;
            while (current?.nodeType === 1) {
              const style = styleOf(current);
              if (style.backgroundImage && style.backgroundImage !== 'none') return null;
              const color = parseColor(style.backgroundColor);
              if (color?.a > 0) {
                layers.push(color);
                if (color.a >= .999) break;
              }
              current = current.parentElement;
            }
            if (!layers.length || layers[layers.length - 1].a < .999) return null;
            let result = layers.pop();
            while (layers.length) result = composite(layers.pop(), result);
            return result;
          };
          const svgBackground = node => {
            const target = node.tagName.toLowerCase() === 'tspan' ? node.closest('text') : node;
            const svg = target?.closest('svg');
            if (!svg) return null;
            const ordered = [...svg.querySelectorAll('*')];
            const targetIndex = ordered.indexOf(target);
            const box = target.getBoundingClientRect();
            const x = box.left + box.width / 2;
            const y = box.top + box.height / 2;
            const backgroundTags = new Set(['rect', 'circle', 'ellipse', 'polygon']);
            for (let index = targetIndex - 1; index >= 0; index -= 1) {
              const candidate = ordered[index];
              if (!backgroundTags.has(candidate.tagName.toLowerCase()) || !visible(candidate)) continue;
              const candidateBox = candidate.getBoundingClientRect();
              if (x < candidateBox.left || x > candidateBox.right || y < candidateBox.top || y > candidateBox.bottom) continue;
              const style = styleOf(candidate);
              const fill = parseColor(style.fill);
              if (!fill?.a) continue;
              fill.a *= Number(style.fillOpacity || 1) * Number(style.opacity || 1);
              if (fill.a >= .999) return fill;
              const base = cssBackground(svg);
              return base ? composite(fill, base) : null;
            }
            return cssBackground(svg);
          };
          const textColors = node => {
            const style = styleOf(node);
            const isSvg = node.namespaceURI === 'http://www.w3.org/2000/svg';
            const foreground = parseColor(isSvg ? style.fill : style.color);
            const background = isSvg ? svgBackground(node) : cssBackground(node);
            if (!foreground || !background) return null;
            foreground.a *= Number(style.opacity || 1);
            if (isSvg) foreground.a *= Number(style.fillOpacity || 1);
            return {
              foreground: foreground.a >= .999 ? foreground : composite(foreground, background),
              background,
            };
          };
          const textElements = slides.flatMap(slide => [...slide.querySelectorAll('*')]).filter(node => {
            if (!visible(node) || ignoredTextTags.has(node.tagName.toLowerCase())) return false;
            if (node.closest('[aria-hidden="true"], [data-decoration]')) return false;
            return Boolean(ownText(node));
          });
          const semanticTextSelector = 'h1,h2,h3,h4,h5,h6,p,li,blockquote,figcaption,td,th,[data-fit]';
          const overflowTextElements = [...new Set([
            ...all(semanticTextSelector).filter(node => node.closest('.oil-slide')),
            ...textElements,
          ])];
          const isMicrocopy = node => {
            const kind = node.getAttribute('data-microcopy');
            if (!['index', 'meta'].includes(kind)) return false;
            if (node.closest('h1,h2,h3,h4,h5,h6,p,li,blockquote,figcaption,td,th,pre,code')) return false;
            const text = ownText(node);
            if (!text || /[。！？；.!?;]/.test(text)) return false;
            return kind === 'index' ? text.length <= 12 : text.length <= 32;
          };
          const minimumTextSize = node => {
            if (node.closest('h1')) return 48;
            if (node.closest('h2')) return 32;
            if (node.closest('h3,h4,h5,h6')) return 28;
            if (isMicrocopy(node)) return 18;
            if (node.closest('pre,code,.oil-code,figcaption,cite,th,small,.oil-label,.tag,.oil-browser-bar,.oil-media-placeholder')) return 20;
            return 24;
          };
          const invalidText = overflowTextElements.flatMap(node => {
            if (!visible(node) || !node.textContent.trim()) return [];
            const style = styleOf(node);
            const overflow = node.scrollWidth > node.clientWidth + 2 || node.scrollHeight > node.clientHeight + 2;
            const clipped = ['hidden', 'clip'].includes(style.overflow)
              || ['hidden', 'clip'].includes(style.overflowX)
              || ['hidden', 'clip'].includes(style.overflowY);
            return overflow && clipped
              ? [{
                  slide: slideId(node), node: describe(node), reason: 'clipped-text',
                  clientWidth: node.clientWidth, scrollWidth: node.scrollWidth,
                  clientHeight: node.clientHeight, scrollHeight: node.scrollHeight,
                  fontSize: style.fontSize
                }] : [];
          });

          const contentBounds = slides.flatMap(slide => {
            const safe = slide.querySelector(':scope > .slide-safe');
            if (!safe) return [];
            const bounds = safe.getBoundingClientRect();
            return [...safe.children].flatMap(node => {
              if (!visible(node) || node.hasAttribute('data-bleed') || node.hasAttribute('data-decoration')) return [];
              const style = styleOf(node);
              if (style.position === 'fixed') return [];
              return inside(node.getBoundingClientRect(), bounds) ? [] : [{
                slide: slide.dataset.slideId || 'unknown', node: describe(node), reason: 'safe-area-child-outside-bounds'
              }];
            });
          });

          const readability = textElements.flatMap(node => {
            const size = parseFloat(styleOf(node).fontSize || '0');
            const minimum = minimumTextSize(node);
            return size > 0 && size + .1 < minimum ? [{
              slide: slideId(node), node: describe(node), reason: 'small-text',
              fontSize: size, minimumFontSize: minimum, text: ownText(node).slice(0, 120)
            }] : [];
          });

          const minimumContrastRatio = 2.5;
          const contrast = textElements.flatMap(node => {
            const colors = textColors(node);
            if (!colors) return [];
            const ratio = contrastRatio(colors.foreground, colors.background);
            return ratio + .01 < minimumContrastRatio ? [{
              slide: slideId(node), node: describe(node), reason: 'low-text-contrast',
              contrastRatio: Number(ratio.toFixed(2)), minimumContrastRatio,
              foreground: styleOf(node).fill !== 'none' && node.namespaceURI === 'http://www.w3.org/2000/svg'
                ? styleOf(node).fill : styleOf(node).color,
              background: `rgb(${Math.round(colors.background.r)}, ${Math.round(colors.background.g)}, ${Math.round(colors.background.b)})`,
              text: ownText(node).slice(0, 120)
            }] : [];
          });

          const pageScroll = documents.flatMap(doc => {
            const root = doc.documentElement;
            const body = doc.body;
            if (!root || !body) return [];
            const extraX = Math.max(root.scrollWidth, body.scrollWidth) - root.clientWidth;
            const extraY = Math.max(root.scrollHeight, body.scrollHeight) - root.clientHeight;
            return extraX > 3 || extraY > 3 ? [{reason: 'document-scroll', extraX, extraY}] : [];
          });
          const documentsReady = documents.every(doc => doc.readyState === 'complete'
            && (!doc.fonts || doc.fonts.status === 'loaded'));
          const stageRect = stages[0]?.getBoundingClientRect();
          const blockingCount = brokenImages.length + missingSafeArea.length + invalidLayouts.length
            + invalidBleeds.length + invalidText.length + contentBounds.length + readability.length + contrast.length;
          return {
            ready: documentsReady && images.every(image => image.complete),
            status: slides.length && stages.length ? (blockingCount ? 'error' : 'ok') : 'pending',
            slides: slides.length,
            images: images.length,
            brokenImages: brokenImages.map(image => image.currentSrc || image.getAttribute('src') || ''),
            missingSafeArea,
            invalidLayouts,
            invalidBleeds,
            invalidText,
            visualFindings: [
              ...contentBounds.map(item => ({...item, category: 'content-bounds'})),
              ...readability.map(item => ({...item, category: 'readability'})),
              ...contrast.map(item => ({...item, category: 'contrast'})),
              ...pageScroll.map(item => ({...item, category: 'page-scroll'}))
            ],
            viewport: {width: innerWidth, height: innerHeight},
            stage: stageRect ? {
              left: stageRect.left, top: stageRect.top, right: stageRect.right, bottom: stageRect.bottom,
              width: stageRect.width, height: stageRect.height,
              scale: Number(stages[0].dataset.scale || 0)
            } : null
          };
        })()"""
        request_id = 0
        while time.monotonic() < deadline:
            request_id += 1
            websocket.send_json(
                {
                    "id": request_id,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expression, "returnByValue": True},
                }
            )
            while True:
                message = websocket.recv_json()
                if message.get("id") == request_id:
                    break
            if "exceptionDetails" in message.get("result", {}):
                details = message["result"]["exceptionDetails"]
                description = (
                    details.get("exception", {}).get("description")
                    or details.get("text")
                    or "unknown error"
                )
                raise RuntimeError(
                    f"Page validation JavaScript raised an exception: {description}"
                )
            report = message["result"]["result"].get("value", {})
            if report.get("ready") and report.get("status") in {"ok", "error"}:
                return report
            time.sleep(0.1)
        raise RuntimeError("Page never reached a validated DOM state.")
    finally:
        if websocket:
            websocket.close()
        _stop_browser(process, profile)
        try:
            profile_ctx.cleanup()
        except OSError:
            pass
