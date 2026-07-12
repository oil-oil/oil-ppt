#!/usr/bin/env python3
"""Stdlib-only Chrome DevTools client for oil-slides DOM validation."""
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
        while True:
            first, second = _recv_exact(self.sock, 2)
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
            if opcode == 0x1:
                return json.loads(payload.decode("utf-8"))


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


def validate_file(chrome: str, html_file: Path, timeout: float = 15) -> dict:
    profile_ctx = tempfile.TemporaryDirectory(prefix="oil-slides-cdp-")
    profile = Path(profile_ctx.name)
    command = [
        chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--allow-file-access-from-files",
        "--disable-background-networking", "--disable-component-update", "--disable-default-apps", "--disable-sync",
        "--metrics-recording-only", "--no-first-run", f"--user-data-dir={profile}", "--remote-debugging-port=0",
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
        expression = """(() => {
          const root = document.documentElement;
          if (!root) return {ready:false, status:'pending', slides:0};
          const slides = document.querySelectorAll('.oil-slide').length;
          const stage = document.querySelector('.deck-stage, .slide-preview-stage');
          return {
          ready: document.readyState === 'complete' && (!document.fonts || document.fonts.status === 'loaded'),
          status: root.dataset.oilValidated === 'ok' && slides > 0 && !!stage ? 'ok' : 'pending',
          slides
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
