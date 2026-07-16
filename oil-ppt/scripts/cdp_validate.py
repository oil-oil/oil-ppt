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


VISUAL_FINDING_CATEGORIES = frozenset({
    "content-bounds", "surface-clipping", "decoration", "ring-geometry", "surface-paint", "line-density",
})


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
          const documents = [document, ...[...document.querySelectorAll('iframe')]
            .map(frame => { try { return frame.contentDocument; } catch (_) { return null; } })
            .filter(Boolean)];
          const slideDocuments = documents.filter(doc => doc.querySelector('.oil-slide'));
          const all = selector => documents.flatMap(doc => [...doc.querySelectorAll(selector)]);
          const styleOf = (node, pseudo=null) => node.ownerDocument.defaultView.getComputedStyle(node, pseudo);
          const slidesNodes = all('.oil-slide');
          const slides = slidesNodes.length;
          const stage = all('.deck-stage, .slide-preview-stage')[0] || null;
          const images = documents.flatMap(doc => [...doc.images]);
          const imagesReady = images.every(image => image.complete);
          const brokenImages = images.filter(image => image.complete && (!image.naturalWidth || !image.naturalHeight));
          const invalidBleeds = all('[data-bleed]').flatMap(bleed => {
            const slide = bleed.closest('.oil-slide');
            if (!slide) return [{slide:'unknown', reason:'missing-slide'}];
            const style = styleOf(bleed);
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
          const invalidLayouts = all('.slide-safe [data-layout]').flatMap(layout => {
            if (!layout.getClientRects().length || styleOf(layout).display === 'none') return [];
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
              const childStyle = styleOf(child);
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
          const textCandidates = all('[data-fit], [data-sentence], [data-slot], [data-copy-title], [data-copy-body]');
          const invalidText = textCandidates.flatMap(text => {
            if (!text.getClientRects().length || styleOf(text).display === 'none') return [];
            if (text.hasAttribute('data-overflow-ok') || !(text.textContent || '').replace(/\\s+/g, ' ').trim()) return [];
            const slide = text.closest('.oil-slide');
            const overflow = text.scrollWidth > text.clientWidth + 1 || text.scrollHeight > text.clientHeight + 1;
            return overflow ? [{
              slide:slide?.dataset.slideId || 'unknown', reason:'text-overflow',
              node:text.tagName.toLowerCase(), className:text.className || '',
              path:text.dataset.editPath || '',
              text:(text.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 120),
              client:`${text.clientWidth}x${text.clientHeight}`, scroll:`${text.scrollWidth}x${text.scrollHeight}`,
              overflowWidth:Math.max(0, text.scrollWidth - text.clientWidth),
              overflowHeight:Math.max(0, text.scrollHeight - text.clientHeight),
              fontSize:styleOf(text).fontSize, minSize:text.dataset.minSize || '', maxHeight:styleOf(text).maxHeight,
            }] : [];
          });
          const invalidCopyFlows = all('[data-copy-flow]').flatMap(flow => {
            const title = [...flow.children].find(node => node.matches?.('[data-copy-title]'));
            const body = [...flow.children].find(node => node.matches?.('[data-copy-body]'));
            if (!title || !body || body.previousElementSibling !== title) return [];
            if (!title.textContent.trim() || !body.textContent.trim()) return [];
            if (!title.getClientRects().length || !body.getClientRects().length) return [];
            const gap = body.getBoundingClientRect().top - title.getBoundingClientRect().bottom;
            if (gap <= 72) return [];
            return [{
              slide:flow.closest('.oil-slide')?.dataset.slideId || 'unknown',
              reason:'copy-gap', gap:Math.round(gap)
            }];
          });
          const invalidBounds = all('.slide-safe [data-bound]').flatMap(node => {
            if (!node.getClientRects().length) return [];
            const style = styleOf(node);
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
          const invalidOptionalRegions = all('[data-optional-region]').flatMap(region => {
            if (!region.getClientRects().length) return [];
            const style = styleOf(region);
            if (region.hidden || region.getAttribute('aria-hidden') === 'true' || style.display === 'none') return [];
            const hasText = (region.textContent || '').trim().length > 0;
            const hasVisual = [...region.querySelectorAll('img,svg,canvas,video')].some(node => {
              if (!node.getClientRects().length) return false;
              if (node.tagName === 'IMG') return node.complete && node.naturalWidth > 0 && node.naturalHeight > 0;
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
          const visible = node => {
            if (!node?.getClientRects().length) return false;
            const style = styleOf(node);
            return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) > .001;
          };
          const insideRect = (box, bounds, tolerance=3) => box.left >= bounds.left - tolerance
            && box.right <= bounds.right + tolerance && box.top >= bounds.top - tolerance
            && box.bottom <= bounds.bottom + tolerance;
          const invalidContentBounds = all('.slide-safe [data-fit], .slide-safe [data-sentence], .slide-safe [data-slot], .slide-safe [data-copy-title], .slide-safe [data-copy-body], .slide-safe img, .slide-safe video, .slide-safe canvas, .slide-safe svg, .slide-safe svg text').flatMap(node => {
            if (!visible(node) || node.closest('[data-bleed]')) return [];
            const owner = node.parentElement?.closest('[data-bound], [data-layout], .oil-surface, .oil-media, .oil-browser');
            if (!owner || owner === node || !visible(owner)) return [];
            const box = node.getBoundingClientRect();
            const bounds = owner.getBoundingClientRect();
            if (insideRect(box, bounds)) return [];
            return [{
              slide:node.closest('.oil-slide')?.dataset.slideId || 'unknown',
              reason:'content-outside-semantic-container',
              node:node.className?.baseVal || node.className || node.tagName.toLowerCase(),
              owner:owner.className || owner.tagName.toLowerCase()
            }];
          });
          const clipOwners = '.oil-media, .oil-browser, [data-clip="media"], [data-clip="browser"], [data-clip="shape"]';
          const invalidSurfaceClips = all('.oil-surface').flatMap(surface => {
            if (!visible(surface)) return [];
            const style = styleOf(surface);
            const clips = ['hidden', 'clip'].includes(style.overflowX) || ['hidden', 'clip'].includes(style.overflowY);
            if (!clips || surface.matches(clipOwners)) return [];
            return [{
              slide:surface.closest('.oil-slide')?.dataset.slideId || 'unknown',
              reason:'surface-clips-content',
              node:surface.className || surface.tagName.toLowerCase(),
              overflow:`${style.overflowX}/${style.overflowY}`
            }];
          });
          const px = value => {
            const parsed = Number.parseFloat(value);
            return Number.isFinite(parsed) ? parsed : null;
          };
          const pseudoRect = (owner, style) => {
            const bounds = owner.getBoundingClientRect();
            const scaleX = owner.offsetWidth ? bounds.width / owner.offsetWidth : 1;
            const scaleY = owner.offsetHeight ? bounds.height / owner.offsetHeight : 1;
            const rawWidth = px(style.width), rawHeight = px(style.height);
            const width = rawWidth === null ? null : rawWidth * scaleX;
            const height = rawHeight === null ? null : rawHeight * scaleY;
            if (width === null || height === null) return null;
            const left = px(style.left), right = px(style.right), top = px(style.top), bottom = px(style.bottom);
            const x = left !== null ? bounds.left + left * scaleX : right !== null ? bounds.right - right * scaleX - width : null;
            const y = top !== null ? bounds.top + top * scaleY : bottom !== null ? bounds.bottom - bottom * scaleY - height : null;
            return x === null || y === null ? null : {left:x, top:y, right:x + width, bottom:y + height, width, height};
          };
          const transformedRect = (box, style, scaleX, scaleY) => {
            if (!box || !style.transform || style.transform === 'none') return box;
            let matrix;
            try { matrix = new DOMMatrixReadOnly(style.transform); }
            catch (_) { return box; }
            const origin = String(style.transformOrigin || '0 0').split(/\\s+/).map(px);
            const ox = box.left + (origin[0] ?? 0) * scaleX;
            const oy = box.top + (origin[1] ?? 0) * scaleY;
            const points = [
              [box.left, box.top], [box.right, box.top],
              [box.right, box.bottom], [box.left, box.bottom],
            ].map(([x, y]) => ({
              x: ox + matrix.a * (x - ox) + matrix.c * (y - oy) + matrix.e * scaleX,
              y: oy + matrix.b * (x - ox) + matrix.d * (y - oy) + matrix.f * scaleY,
            }));
            const xs = points.map(point => point.x), ys = points.map(point => point.y);
            const left = Math.min(...xs), right = Math.max(...xs), top = Math.min(...ys), bottom = Math.max(...ys);
            return {left, right, top, bottom, width:right - left, height:bottom - top};
          };
          const pseudoVisible = style => style.content !== 'none' && style.display !== 'none'
            && style.visibility !== 'hidden' && Number(style.opacity || 1) > .001;
          const insetClipRect = (box, clipPath) => {
            const match = clipPath.match(/^inset\\(([^)]*)\\)/);
            if (!box || !match) return box;
            const values = [...match[1].split(/\\bround\\b/)[0].matchAll(/(-?[\\d.]+)(%)/g)]
              .map(item => Number(item[1]) / 100);
            if (!values.length) return box;
            const [top, right, bottom, left] = values.length === 1
              ? [values[0], values[0], values[0], values[0]]
              : values.length === 2 ? [values[0], values[1], values[0], values[1]]
              : values.length === 3 ? [values[0], values[1], values[2], values[1]] : values;
            return {
              left:box.left + box.width * left, right:box.right - box.width * right,
              top:box.top + box.height * top, bottom:box.bottom - box.height * bottom,
            };
          };
          const invalidDecorations = all('.oil-surface[data-decor]').flatMap(surface => {
            if (!visible(surface) || surface.dataset.decor === 'none' || surface.dataset.decor === '') return [];
            const style = styleOf(surface);
            if (style.getPropertyValue('--decor-opacity').trim() === '0') return [];
            const pseudo = styleOf(surface, '::after');
            if (!pseudoVisible(pseudo)) return [];
            const position = surface.dataset.decorPos || 'top-right';
            const [vertical, horizontal] = position.split('-');
            const box = pseudoRect(surface, pseudo);
            const bounds = surface.getBoundingClientRect();
            const scaleX = surface.offsetWidth ? bounds.width / surface.offsetWidth : 1;
            const scaleY = surface.offsetHeight ? bounds.height / surface.offsetHeight : 1;
            const paintedBox = transformedRect(box, pseudo, scaleX, scaleY);
            const horizontalInset = px(style.getPropertyValue(`--decor-${horizontal}`));
            const verticalInset = px(style.getPropertyValue(`--decor-${vertical}`));
            const expectedLeft = box && horizontalInset !== null
              ? (horizontal === 'left' ? bounds.left + horizontalInset * scaleX : bounds.right - horizontalInset * scaleX - box.width) : null;
            const expectedTop = box && verticalInset !== null
              ? (vertical === 'top' ? bounds.top + verticalInset * scaleY : bounds.bottom - verticalInset * scaleY - box.height) : null;
            const wrongAnchor = !box || expectedLeft === null || expectedTop === null
              || Math.abs(box.left - expectedLeft) > 3 || Math.abs(box.top - expectedTop) > 3;
            const slide = surface.closest('.oil-slide');
            const outsideSlide = paintedBox && slide && pseudo.clipPath === 'none'
              && !insideRect(paintedBox, slide.getBoundingClientRect(), 3);
            return [
              ...(wrongAnchor ? [{
                slide:slide?.dataset.slideId || 'unknown', reason:'decoration-anchor-mismatch',
                decoration:surface.dataset.motif || surface.dataset.decor || 'unknown', expected:position
              }] : []),
              ...(outsideSlide ? [{
                slide:slide?.dataset.slideId || 'unknown', reason:'decoration-outside-slide',
                decoration:surface.dataset.motif || surface.dataset.decor || 'unknown'
              }] : [])
            ];
          });
          const invalidMotifBounds = all('.oil-surface[data-motif]').flatMap(surface => {
            if (!visible(surface)) return [];
            const pseudo = styleOf(surface, '::after');
            if (!pseudoVisible(pseudo)) return [];
            const bounds = surface.getBoundingClientRect();
            const scaleX = surface.offsetWidth ? bounds.width / surface.offsetWidth : 1;
            const scaleY = surface.offsetHeight ? bounds.height / surface.offsetHeight : 1;
            const box = insetClipRect(transformedRect(pseudoRect(surface, pseudo), pseudo, scaleX, scaleY), pseudo.clipPath);
            const slide = surface.closest('.oil-slide');
            return box && slide && !insideRect(box, slide.getBoundingClientRect(), 3) ? [{
              slide:slide.dataset.slideId || 'unknown', reason:'decoration-outside-slide',
              decoration:surface.dataset.motif || 'unknown'
            }] : [];
          });
          const invalidRingGeometry = all('.oil-surface[data-motif="ring"]').flatMap(surface => {
            if (!visible(surface) || styleOf(surface).getPropertyValue('--decor-opacity').trim() === '0') return [];
            const pseudo = styleOf(surface, '::after');
            if (!pseudoVisible(pseudo)) return [];
            const box = pseudoRect(surface, pseudo);
            const borders = [pseudo.borderTopWidth, pseudo.borderRightWidth, pseudo.borderBottomWidth, pseudo.borderLeftWidth].map(px);
            const uniformBorder = borders.every(value => value !== null && value >= 3)
              && Math.max(...borders) - Math.min(...borders) <= 1;
            const radiusValue = pseudo.borderTopLeftRadius;
            const radius = box && radiusValue.endsWith('%')
              ? Math.min(box.width, box.height) * Number.parseFloat(radiusValue) / 100
              : px(radiusValue);
            const clipped = pseudo.clipPath && pseudo.clipPath !== 'none';
            const borderCircle = box && Math.abs(box.width - box.height) <= Math.max(2, box.width * .04)
              && uniformBorder && radius !== null && radius >= Math.min(box.width, box.height) * .45;
            const inner = px(pseudo.getPropertyValue('--oil-ring-inner'));
            const outer = px(pseudo.getPropertyValue('--oil-ring-outer'));
            const radialCircle = box && Math.abs(box.width - box.height) <= Math.max(2, box.width * .04)
              && pseudo.backgroundImage.includes('radial-gradient')
              && inner !== null && outer !== null && outer - inner >= 6;
            if (clipped) return [{
              slide:surface.closest('.oil-slide')?.dataset.slideId || 'unknown',
              reason:'ring-is-clipped', node:surface.className || surface.tagName.toLowerCase()
            }];
            if (borderCircle || radialCircle) return [];
            return [{
              slide:surface.closest('.oil-slide')?.dataset.slideId || 'unknown',
              reason:'ring-is-not-circular', node:surface.className || surface.tagName.toLowerCase()
            }];
          });
          const gradientCount = value => (value.match(/(?:repeating-)?(?:linear|radial|conic)-gradient\\(/g) || []).length;
          const invalidPaint = all('.oil-surface:not(.oil-media)').flatMap(surface => {
            if (!visible(surface)) return [];
            const layers = [styleOf(surface), styleOf(surface, '::before'), styleOf(surface, '::after')]
              .map(style => gradientCount(`${style.backgroundImage} ${style.maskImage}`));
            const excessive = layers.findIndex(count => count > 2);
            return excessive < 0 ? [] : [{
              slide:surface.closest('.oil-slide')?.dataset.slideId || 'unknown',
              reason:'excessive-gradient-layers', layer:['element', 'before', 'after'][excessive], count:layers[excessive]
            }];
          });
          const paintedLine = (style, width, height) => {
            const short = Math.min(width, height), long = Math.max(width, height);
            if (!(short > 0 && short <= 2.5 && long >= 48 && long / short >= 12)) return false;
            const hasBackground = style.backgroundColor !== 'transparent' && style.backgroundColor !== 'rgba(0, 0, 0, 0)';
            const border = [style.borderTopWidth, style.borderRightWidth, style.borderBottomWidth, style.borderLeftWidth]
              .map(px).some(value => value !== null && value > 0);
            return hasBackground || style.backgroundImage !== 'none' || border;
          };
          const excessiveHairlines = slidesNodes.flatMap(slide => {
            const lines = [];
            for (const node of [slide, ...slide.querySelectorAll('*')]) {
              if (!visible(node) || node.closest('[data-visual-edge]') || node.matches('.oil-browser, .oil-browser *')) continue;
              const box = node.getBoundingClientRect();
              if (paintedLine(styleOf(node), box.width, box.height)) lines.push(node.className || node.tagName.toLowerCase());
              for (const pseudoName of ['::before', '::after']) {
                const pseudo = styleOf(node, pseudoName);
                if (!pseudoVisible(pseudo)) continue;
                const bounds = node.getBoundingClientRect();
                const scaleX = node.offsetWidth ? bounds.width / node.offsetWidth : 1;
                const scaleY = node.offsetHeight ? bounds.height / node.offsetHeight : 1;
                const pseudoBox = transformedRect(pseudoRect(node, pseudo), pseudo, scaleX, scaleY);
                if (pseudoBox && paintedLine(pseudo, pseudoBox.width, pseudoBox.height)) {
                  lines.push(`${node.className || node.tagName.toLowerCase()}${pseudoName}`);
                }
              }
            }
            return lines.length <= 3 ? [] : [{
              slide:slide.dataset.slideId || 'unknown', reason:'excessive-unowned-hairlines',
              count:lines.length, nodes:lines.slice(0, 6)
            }];
          });
          const tokenRoot = slideDocuments[0]?.documentElement || document.documentElement;
          const rootStyle = tokenRoot ? tokenRoot.ownerDocument.defaultView.getComputedStyle(tokenRoot) : null;
          const stageRect = stage?.getBoundingClientRect();
          const documentsReady = documents.every(doc => doc.readyState === 'complete' && (!doc.fonts || doc.fonts.status === 'loaded'));
          const validated = slideDocuments.length > 0 && slideDocuments.every(doc => doc.documentElement?.dataset.oilValidated === 'ok');
          const blockingVisualCount = invalidContentBounds.length + invalidSurfaceClips.length
            + invalidDecorations.length + invalidMotifBounds.length + invalidRingGeometry.length;
          return {
          ready: documentsReady && imagesReady,
          status: brokenImages.length || invalidBleeds.length || invalidLayouts.length || invalidText.length
            || invalidCopyFlows.length || invalidBounds.length || invalidOptionalRegions.length || blockingVisualCount
            ? 'error' : (validated && slides > 0 && !!stage ? 'ok' : 'pending'),
          slides,
          images: images.length,
          brokenImages: brokenImages.map(image => image.currentSrc || image.getAttribute('src') || ''),
          invalidBleeds,
          invalidLayouts,
          invalidText,
          invalidCopyFlows,
          invalidBounds,
          invalidOptionalRegions,
          visualFindings: [
            ...invalidContentBounds.map(item => ({...item, category:'content-bounds'})),
            ...invalidSurfaceClips.map(item => ({...item, category:'surface-clipping'})),
            ...invalidDecorations.map(item => ({...item, category:'decoration'})),
            ...invalidMotifBounds.map(item => ({...item, category:'decoration'})),
            ...invalidRingGeometry.map(item => ({...item, category:'ring-geometry'})),
            ...invalidPaint.map(item => ({...item, category:'surface-paint'})),
            ...excessiveHairlines.map(item => ({...item, category:'line-density'}))
          ],
          viewport: {width:innerWidth, height:innerHeight},
          stage: stageRect ? {
            left:stageRect.left, top:stageRect.top, right:stageRect.right, bottom:stageRect.bottom,
            width:stageRect.width, height:stageRect.height,
            scale:Number(stage.dataset.scale || 0)
          } : null,
          tokens: {
            accent: rootStyle?.getPropertyValue('--accent').trim() || '',
            surfaceRadius: rootStyle?.getPropertyValue('--surface-radius').trim() || '',
            fontZh: rootStyle?.getPropertyValue('--font-zh').trim() || ''
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
