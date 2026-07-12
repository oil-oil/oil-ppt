#!/usr/bin/env python3
"""Render real template thumbnails for confirmation before scaffold."""
from __future__ import annotations

import argparse
import html
import json
import re
import webbrowser
from pathlib import Path

from fill_slots import FILLERS
from outline_schema import validate_outline
from palette_tokens import PALETTES, canonical_name, normalize_palette
from profile_tokens import SHAPE_META, SHAPE_PROFILES, TYPE_META, TYPE_PROFILES


ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "assets" / "templates"
RUNTIME_CSS = (ROOT / "assets" / "runtime" / "deck.css").read_text(encoding="utf-8")
RUNTIME_JS = (ROOT / "assets" / "runtime" / "deck.js").read_text(encoding="utf-8")
CSS_BLOCK = re.compile(r"/\*\s*OIL-SLIDE-CSS:START\s*\*/(.*?)/\*\s*OIL-SLIDE-CSS:END\s*\*/", re.S)
HTML_BLOCK = re.compile(r"<!--\s*OIL-SLIDE:START\s*-->(.*?)<!--\s*OIL-SLIDE:END\s*-->", re.S)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outline", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--no-open", action="store_true")
    return parser.parse_args()


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def palette_for(data: dict) -> dict[str, str]:
    raw = data["palette"]
    if isinstance(raw, str):
        return {"name": canonical_name(raw), **PALETTES[canonical_name(raw)]}
    return normalize_palette(raw)


def theme_css(data: dict) -> str:
    palette = palette_for(data)
    typography = TYPE_PROFILES[data["typography"]]
    shape = SHAPE_PROFILES[data["shape"]]
    return ":root{" + "".join((
        f"--slide-bg:{palette['canvas']};--stage-bg:{palette['canvas']};",
        f"--ink:{palette['ink']};--ink-2:{palette['ink_2']};--ink-3:{palette['ink_3']};",
        f"--border:{palette['border']};--surface:{palette['surface']};--surface-2:{palette['surface_2']};",
        f"--accent:{palette['accent']};--accent-mark:{palette['accent']};--accent-fill:{palette['accent_fill']};",
        f"--accent-soft:{palette['accent_soft']};--accent-wash:{palette['accent_soft']};--accent-strong:{palette['accent_strong']};",
        f"--font-zh:{typography['zh']};--font-ui:{typography['ui']};",
        f"--surface-radius:{shape['radius']};--surface-shadow:{shape['shadow']};",
    )) + "}"


def prepared_slide(slide: dict, index: int) -> tuple[str, str]:
    raw = (TEMPLATES / f"{slide['template']}.html").read_text(encoding="utf-8")
    title = html.escape(slide["title"], quote=True)
    raw = (raw.replace("__ID__", slide["id"])
              .replace("__TITLE__", title)
              .replace("__INDEX__", f"{index:02d}")
              .replace("__VARIANT__", html.escape(slide["variant"], quote=True))
              .replace("__DECOR__", html.escape(slide["decor"], quote=True)))
    css = CSS_BLOCK.search(raw).group(1)
    fragment = HTML_BLOCK.search(raw).group(1).strip()
    section = re.compile(r"<section\b(?P<attrs>[^>]*)>", re.I)
    match = section.search(fragment)
    attrs = match.group("attrs")
    additions = []
    if not re.search(r"\bdata-variant\s*=", attrs, re.I):
        additions.append(f' data-variant="{html.escape(slide["variant"], quote=True)}"')
    if not re.search(r"\bdata-component-decor\s*=", attrs, re.I):
        additions.append(f' data-component-decor="{html.escape(slide["decor"], quote=True)}"')
    if additions:
        fragment = fragment[:match.end() - 1] + "".join(additions) + fragment[match.end() - 1:]
    filler = FILLERS[slide["template"]]
    fragment = filler(fragment, slide)
    fragment = fragment.replace('src="../', 'src="')
    if slide.get("highlight"):
        phrase = html.escape(slide["highlight"], quote=True)
        marked = title.replace(phrase, f'<span class="hl">{phrase}</span>', 1)
        fragment = fragment.replace(f">{title}</h1>", f">{marked}</h1>", 1)
    return css, fragment


def iframe_document(data: dict, slide: dict, index: int) -> str:
    css, fragment = prepared_slide(slide, index)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{theme_css(data)}{RUNTIME_CSS}{css}</style></head>
<body data-oil-mode="preview" data-type-profile="{esc(data['typography'])}" data-shape-profile="{esc(data['shape'])}">
<div class="slide-preview-viewport"><div class="slide-preview-shell"><div class="slide-preview-stage">{fragment}</div></div></div>
<script>{RUNTIME_JS}</script></body></html>"""


def visual_label(slide: dict) -> str:
    image = slide.get("image") or slide.get("media") or slide.get("artifact_image")
    if image:
        return f"素材：{Path(str(image)).name}"
    task = str(slide.get("visual_task") or "").strip()
    return f"视觉计划：{task}" if task else "纯排版 / 程序化结构"


def palette_controls(data: dict) -> str:
    raw = data["palette"]
    if not isinstance(raw, str):
        palette = palette_for(data)
        return f'<span class="swatch" style="--swatch:{esc(palette["accent"])}">品牌配色 {esc(palette["name"])}</span>'
    selected = canonical_name(raw)
    buttons = []
    for name, tokens in PALETTES.items():
        state = " is-selected" if name == selected else ""
        buttons.append(
            f'<button type="button" class="palette-option{state}" data-palette="{esc(name)}" '
            f'style="--swatch:{esc(tokens["accent"])}" aria-pressed="{str(name == selected).lower()}">{esc(name)}</button>'
        )
    return (
        '<div class="palette-picker" aria-label="选择配色">'
        '<span class="setting-label">配色</span>'
        f'{"".join(buttons)}'
        '</div>'
    )


def validate_asset_paths(data: dict, base: Path) -> None:
    root = base.resolve()
    for index, slide in enumerate(data.get("slides") or [], start=1):
        value = slide.get("image") or slide.get("media") or slide.get("artifact_image")
        if not value:
            continue
        path = (root / str(value)).resolve()
        if root not in path.parents:
            raise SystemExit(f"Outline slide {index} asset must stay inside the project: {value}")
        if not path.is_file():
            raise SystemExit(f"Outline slide {index} asset is missing: {value}")


def render(data: dict) -> str:
    slides = validate_outline(data, TEMPLATES)
    palette = palette_for(data)
    cards = []
    for index, slide in enumerate(slides, start=1):
        document = html.escape(iframe_document(data, slide, index), quote=True)
        cards.append(f"""<article><div class="meta"><b>{index:02d}</b><span>{esc(slide['template'])}</span><span>{esc(slide['variant'])}</span><span>{esc(slide['decor'])}</span></div>
<iframe title="{esc(slide['title'])}" srcdoc="{document}"></iframe><p>{esc(visual_label(slide))}</p></article>""")
    palette_json = json.dumps(PALETTES, ensure_ascii=False).replace("</", "<\\/")
    selected_palette = palette["name"]
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(data['title'])} · 预览</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#f5f5f4;color:#292929;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{width:min(1500px,calc(100% - 40px));margin:auto;padding:44px 0 90px}}header{{margin-bottom:24px}}h1{{margin:0;font-size:40px}}.settings{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 28px}}.settings>span,.meta span{{padding:7px 10px;border-radius:999px;background:#fff;border:1px solid #e5e5e5;font-size:12px}}.swatch{{display:inline-flex!important;align-items:center;gap:7px}}.swatch::before,.palette-option::before{{content:"";width:12px;height:12px;border-radius:50%;background:var(--swatch);box-shadow:inset 0 0 0 1px rgba(0,0,0,.06)}}.palette-picker{{display:flex;align-items:center;gap:7px;flex-wrap:wrap;padding:7px;border:1px solid #dedede;border-radius:14px;background:#fff}}.setting-label{{padding:0 5px;font-size:12px;color:#777}}.palette-option{{display:inline-flex;align-items:center;gap:7px;padding:7px 10px;border:1px solid #e5e5e5;border-radius:999px;background:#fff;color:#555;font:600 12px/1 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;cursor:pointer}}.palette-option:hover{{border-color:#aaa}}.palette-option.is-selected{{border-color:#292929;background:#292929;color:#fff}}.pages{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}}article{{padding:14px;border-radius:18px;background:#fff;border:1px solid #e5e5e5}}.meta{{display:flex;align-items:center;gap:7px;margin-bottom:11px}}.meta b{{margin-right:auto}}iframe{{display:block;width:100%;aspect-ratio:16/9;border:1px solid #eee;border-radius:11px;background:#fff}}article p{{margin:10px 2px 0;color:#777;font-size:12px}}@media(max-width:900px){{.pages{{grid-template-columns:1fr}}}}</style></head><body><main>
<header><h1>{esc(data['title'])}</h1></header>
<div class="settings">{palette_controls(data)}<span>字体 {esc(TYPE_META[data['typography']]['label'])}</span><span>圆角 {esc(SHAPE_META[data['shape']]['label'])}</span></div>
<section class="pages">{''.join(cards)}</section></main>
<script>
const palettes={palette_json};
const tokenMap={{canvas:"--slide-bg",ink:"--ink",ink_2:"--ink-2",ink_3:"--ink-3",border:"--border",surface:"--surface",surface_2:"--surface-2",accent:"--accent",accent_fill:"--accent-fill",accent_soft:"--accent-soft",accent_strong:"--accent-strong"}};
let activePalette={json.dumps(selected_palette)};
function applyPalette(name){{
  const values=palettes[name];
  if(!values)return;
  activePalette=name;
  document.querySelectorAll('.palette-option').forEach(button=>{{const selected=button.dataset.palette===name;button.classList.toggle('is-selected',selected);button.setAttribute('aria-pressed',String(selected));}});
  document.querySelectorAll('iframe').forEach(frame=>{{
    const update=()=>{{const root=frame.contentDocument?.documentElement;if(!root)return;Object.entries(tokenMap).forEach(([key,variable])=>root.style.setProperty(variable,values[key]));root.style.setProperty('--accent-mark',values.accent);root.style.setProperty('--accent-wash',values.accent_soft);root.style.setProperty('--accent-ink',values.accent_strong);root.style.setProperty('--ambient',values.surface);frame.contentWindow?.dispatchEvent(new Event('resize'));}};
    if(frame.contentDocument?.readyState==='complete')update();else frame.addEventListener('load',update,{{once:true}});
  }});
}}
document.querySelectorAll('.palette-option').forEach(button=>button.addEventListener('click',()=>applyPalette(button.dataset.palette)));
document.querySelectorAll('iframe').forEach(frame=>frame.addEventListener('load',()=>applyPalette(activePalette)));
applyPalette(activePalette);
</script></body></html>"""


def main() -> None:
    args = parse_args()
    outline = args.outline.expanduser().resolve()
    if not outline.is_file():
        raise SystemExit(f"Outline file not found: {outline}")
    data = json.loads(outline.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Outline JSON must be an object.")
    validate_asset_paths(data, outline.parent)
    target = (args.out or outline.parent / "预览.html").expanduser().resolve()
    target.write_text(render(data), encoding="utf-8")
    print(f"Created preview: {target}")
    if not args.no_open and not webbrowser.open(target.as_uri()):
        print("Browser did not open automatically. Open the preview HTML manually.")


if __name__ == "__main__":
    main()
