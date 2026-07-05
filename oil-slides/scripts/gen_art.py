#!/usr/bin/env python3
"""
oil-slides 墨水插画生图 + 抠图(一体,无 Codex 环境时的 fallback)

管线:zenmux gpt-image-2 在【纯绿幕】上生成插画 → 绿幕抠图去绿边 → 透明 PNG,
直接可落进幻灯片的蒙版色块容器。绝不在白底上生成(抠不干净)。

风格固定:漫画墨水 + 半调网点,火柴人主角 + 黄色边牧同伴,九成黑白灰,
与 oil-html 同一套画风,见 references/illustration.md。默认生成路径是
Codex image_gen(灰底 #808080 + cutout.py),本脚本只在没有 Codex 时用。

用法:
  python3 gen_art.py --subject "the character placing one card on a stack" --out art/card.png
  python3 gen_art.py --subject "..." --out x.png --no-key      # 只生成,不抠图(调试)
  python3 gen_art.py --subject "..." --out x.png --preview      # 额外输出白底合成预览
  python3 gen_art.py --subject "..." --out x.png --dry-run      # 只打印 prompt,不调 API

环境:zenmux key 取自 $ZENMUX_API_KEY 或 ~/.zenmux_api_key
"""
import argparse
import base64
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

API_BASE = "https://zenmux.ai/api/v1"
IMAGE_MODEL = "openai/gpt-image-2"
DEFAULT_KEY_FILE = Path.home() / ".zenmux_api_key"

# 抠图与预览参数
KEY_RGB = (0, 255, 0)          # 绿幕基准
T0, T1 = 90, 200               # 到绿幕距离 <T0 全透明; >T1 全不透明; 之间羽化
GYPSUM = (255, 255, 255)       # 白底,用于预览合成

# ── 固定风格前缀(与 oil-html 插画同一套画风,改这里 = 改全局画风)────────────
STYLE = (
    "Professional manga/comic ink illustration. Clean confident ink outlines "
    "with varying line weights (thick for contours, thin for details), NOT wobbly "
    "or sketchy. Heavy use of classic circular halftone screentone dot patterns for "
    "all grey/shadow areas — this is the signature visual element. Flat black fills "
    "for dark areas, white with screentone shading elsewhere. The main character, "
    "when present, is a cute stick figure with a round head, thin round glasses, dot "
    "eyes, simple smile, and thin line-drawn limbs — minimal and charming, not "
    "detailed. His companion is a chubby warm-yellow Border Collie dog with black "
    "ink outlines and a white chest. Color usage is extremely restrained — 90% of "
    "the image is black, white, and grey halftone screentone; warm yellow only on "
    "the Border Collie, small warm light patches, and sparse star decorations; no "
    "other colors. No text, no letters, no numbers, no watermark. Rich detail and "
    "visual complexity like a printed comic page or indie zine illustration, not a "
    "simple mascot icon. Background MUST be a perfectly flat, solid, uniform bright "
    "chroma-key green, evenly colored edge to edge, with ZERO screentone dots, ink "
    "marks, or any element bleeding into the background."
)


def build_prompt(subject: str) -> str:
    return f"{STYLE} Subject: {subject.strip()}"


def api_key(args) -> str:
    import os
    key = args.api_key or os.environ.get("ZENMUX_API_KEY", "")
    if not key and args.key_file.exists():
        key = args.key_file.read_text(encoding="utf-8").strip()
    if not key:
        sys.exit(f"No zenmux key. Set ZENMUX_API_KEY or put it in {args.key_file}.")
    return key


def _find(obj, k):
    if isinstance(obj, dict):
        if obj.get(k):
            return obj[k]
        for v in obj.values():
            r = _find(v, k)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find(v, k)
            if r:
                return r
    return None


def generate(prompt: str, size: str, key: str, timeout: int) -> bytes:
    payload = {"model": IMAGE_MODEL, "prompt": prompt, "n": 1, "size": size}
    req = urllib.request.Request(
        f"{API_BASE}/images/generations",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"zenmux HTTP {e.code}: {e.read().decode(errors='replace')[:800]}")
    b64 = _find(resp, "b64_json")
    if b64:
        return base64.b64decode(b64)
    url = _find(resp, "url")
    if url:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read()
    sys.exit("image response had neither b64_json nor url")


def key_out(raw_path: Path, out_path: Path, preview_path: Path | None):
    import numpy as np
    from PIL import Image

    a = np.asarray(Image.open(raw_path).convert("RGB")).astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    dist = np.sqrt((a[..., 0] - KEY_RGB[0]) ** 2 + (a[..., 1] - KEY_RGB[1]) ** 2 + (a[..., 2] - KEY_RGB[2]) ** 2)
    alpha = np.clip((dist - T0) / (T1 - T0), 0, 1)
    spill = g > (np.maximum(r, b) + 12)          # 去绿边:绿色明显高于红蓝处压回
    g = np.where(spill, np.maximum(r, b), g)
    out = np.dstack([r, g, b, alpha * 255]).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(out_path)
    print(f"keyed -> {out_path}  (opaque {float((alpha>0.5).mean())*100:.1f}%)")
    if preview_path:
        bg = Image.new("RGBA", Image.open(out_path).size, GYPSUM + (255,))
        comp = Image.alpha_composite(bg, Image.open(out_path))
        comp.convert("RGB").save(preview_path)
        print(f"preview -> {preview_path}")


def main():
    p = argparse.ArgumentParser(description="oil-slides line-art generator + green-screen keyer")
    p.add_argument("--subject", required=True, help="画面主体(英文,具体的概念,如 'a hand placing one card on a stack')")
    p.add_argument("--out", required=True, type=Path, help="输出透明 PNG 路径")
    p.add_argument("--size", default="1024x1024", help="须被 16 整除,默认 1024x1024")
    p.add_argument("--no-key", action="store_true", help="只生成绿幕原图,不抠图")
    p.add_argument("--preview", action="store_true", help="额外输出白底合成预览")
    p.add_argument("--dry-run", action="store_true", help="只打印 prompt,不调 API")
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--api-key", default="")
    p.add_argument("--key-file", type=Path, default=DEFAULT_KEY_FILE)
    args = p.parse_args()

    prompt = build_prompt(args.subject)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sidecar = args.out.with_suffix(args.out.suffix + ".prompt.txt")
    sidecar.write_text(prompt + "\n", encoding="utf-8")

    if args.dry_run:
        print(prompt)
        return

    raw_path = args.out.with_name(args.out.stem + ".raw.png")
    raw_path.write_bytes(generate(prompt, args.size, api_key(args), args.timeout))
    print(f"raw   -> {raw_path}")

    if args.no_key:
        return
    preview = args.out.with_name(args.out.stem + ".on-white.png") if args.preview else None
    key_out(raw_path, args.out, preview)


if __name__ == "__main__":
    main()
