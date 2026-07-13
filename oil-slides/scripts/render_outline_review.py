#!/usr/bin/env python3
"""Render real template thumbnails for confirmation before scaffold."""
from __future__ import annotations

import argparse
import html
import json
import re
import webbrowser
from pathlib import Path

from background_presets import effective_background
from design_quality import audit_summary, has_media, slide_quality
from fill_slots import FILLERS, apply_media_attributes, inject_backdrop_text
from media_assets import verify_outline_media
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
        f"--accent-ink:{palette['accent_strong']};--ambient:{palette['surface']};",
        f"--grid-color:color-mix(in srgb,{palette['ink']} 3.2%,transparent);",
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
    background = effective_background(slide)
    fragment, count = re.subn(
        r'(data-bg=["\'])[^"\']+(["\'])',
        rf'\g<1>{html.escape(background, quote=True)}\g<2>',
        fragment,
        count=1,
    )
    if count != 1:
        raise SystemExit(f"Template {slide['template']} does not expose data-bg.")
    filler = FILLERS[slide["template"]]
    fragment = filler(fragment, slide)
    fragment = apply_media_attributes(fragment, slide)
    fragment = inject_backdrop_text(fragment, slide)
    fragment = fragment.replace('src="../', 'src="')
    if slide.get("highlight"):
        phrase = html.escape(slide["highlight"], quote=True)
        marked = title.replace(phrase, f'<span class="hl">{phrase}</span>', 1)
        fragment = fragment.replace(f">{title}</h1>", f">{marked}</h1>", 1)
    return css, fragment


def iframe_document(data: dict, slide: dict, index: int) -> str:
    css, fragment = prepared_slide(slide, index)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{RUNTIME_CSS}{theme_css(data)}{css}</style></head>
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


def rhythm_panel(data: dict, slides: list[dict]) -> str:
    background_codes = {
        "grid-fade": "GF", "grid-wide": "GW", "soft-spotlight": "SS",
        "block-field": "BF", "media-owned": "MO",
    }
    silhouette_codes = {
        "bleed": "BL", "browser": "BR", "canvas": "CV", "card-grid": "CG", "diagram": "DG",
        "editorial-list": "EL", "focal": "FC", "metric": "MT", "rail": "RL", "split": "SP",
        "matrix": "MX",
        "state-panel": "SW", "step-grid": "ST", "timeline": "TL", "two-panel": "TP",
    }

    def cells(kind: str) -> str:
        items = []
        for index, slide in enumerate(slides, start=1):
            background = effective_background(slide)
            silhouette = slide_quality(slide)["silhouette"]
            if kind == "background":
                value = background_codes[background]
                title = background
                class_name = f"bg-{background}"
            elif kind == "silhouette":
                value = silhouette_codes.get(silhouette, silhouette[:2].upper())
                title = silhouette
                class_name = ""
            elif kind == "backdrop":
                value = "Aa" if slide.get("backdrop_text") else "·"
                title = slide.get("backdrop_text") or "无背景大字"
                class_name = "is-highlight" if slide.get("backdrop_text") else ""
            elif kind == "media":
                if not has_media(slide):
                    value, title, class_name = "·", "无媒体", ""
                elif silhouette == "bleed":
                    value, title, class_name = "满", "全屏 / 出血媒体", "is-highlight"
                else:
                    value, title, class_name = "框", "安全区内媒体", ""
            else:
                value = "●" if slide.get("highlight") else "·"
                title = slide.get("highlight") or "无标题划线强调"
                class_name = "is-highlight" if slide.get("highlight") else ""
            items.append(
                f'<span class="rhythm-cell {class_name}" title="{index:02d} · {esc(slide["title"])} · {esc(title)}">'
                f'<small>{index:02d}</small><i>{esc(value)}</i></span>'
            )
        return "".join(items)

    def issue_hint(item: dict) -> str:
        suggestion = item.get("suggestion") or {}
        changes = suggestion.get("set_background") or {}
        if changes:
            return "建议：" + "，".join(f"{slide_id} → {background}" for slide_id, background in changes.items())
        candidates = suggestion.get("candidate_slides") or []
        templates = suggestion.get("templates") or []
        if templates and candidates:
            return "候选页：" + "、".join(candidates) + "；可选：" + " / ".join(templates)
        if templates:
            return "可选：" + " / ".join(templates)
        if candidates:
            return "候选页：" + "、".join(candidates)
        return str(suggestion.get("action") or "")

    summary = audit_summary(data)
    aesthetic_codes = {
        "background-monotony", "background-class-monotony", "background-run", "highlight-absence", "highlight-saturation",
        "backdrop-saturation", "component-dominance", "missing-focal-beat",
        "missing-cinematic-beat", "media-shape-monotony", "inset-media-run", "specialized-capability-missed",
    }
    issues = [item for item in summary["issues"] if item["code"] in aesthetic_codes]
    issue_html = "".join(
        f'<li><code>{esc(item["code"])}</code><span>{esc(item["message"])}</span>'
        f'<em>{esc(issue_hint(item))}</em></li>' for item in issues
    ) or '<li class="is-ok">背景、版式与强调节奏没有发现明显重复。</li>'
    return f'''<section class="rhythm-panel" aria-label="整套演示节奏检查">
<div class="rhythm-head"><div><strong>整套节奏</strong><span>程序根据 Outline 自动生成；提示只出现在预览壳层。</span></div><ul>{issue_html}</ul></div>
<div class="rhythm-row"><b>背景</b><div class="rhythm-cells">{cells("background")}</div></div>
<div class="rhythm-row"><b>版式</b><div class="rhythm-cells">{cells("silhouette")}</div></div>
<div class="rhythm-row"><b>媒体</b><div class="rhythm-cells">{cells("media")}</div></div>
<div class="rhythm-row"><b>强调</b><div class="rhythm-cells">{cells("highlight")}</div></div>
<div class="rhythm-row"><b>背景字</b><div class="rhythm-cells">{cells("backdrop")}</div></div>
</section>'''


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
    verify_outline_media(data, base)


def render(data: dict) -> str:
    slides = validate_outline(data, TEMPLATES)
    palette = palette_for(data)
    cards = []
    for index, slide in enumerate(slides, start=1):
        document = html.escape(iframe_document(data, slide, index), quote=True)
        cards.append(f"""<article><div class="meta"><b>{index:02d}</b><span>{esc(slide['template'])}</span><span>{esc(slide['variant'])}</span><span>{esc(slide['decor'])}</span><span>{esc(effective_background(slide))}</span></div>
<iframe title="{esc(slide['title'])}" srcdoc="{document}"></iframe><p>{esc(visual_label(slide))}</p></article>""")
    palette_json = json.dumps(PALETTES, ensure_ascii=False).replace("</", "<\\/")
    selected_palette = palette["name"]
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(data['title'])} · 预览</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#f5f5f4;color:#292929;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{width:min(1500px,calc(100% - 40px));margin:auto;padding:44px 0 90px}}header{{margin-bottom:24px}}h1{{margin:0;font-size:40px}}.settings{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 28px}}.settings>span,.meta span{{padding:7px 10px;border-radius:999px;background:#fff;border:1px solid #e5e5e5;font-size:12px}}.swatch{{display:inline-flex!important;align-items:center;gap:7px}}.swatch::before,.palette-option::before{{content:"";width:12px;height:12px;border-radius:3px;background:var(--swatch);border:1px solid rgba(0,0,0,.06)}}.palette-picker{{display:flex;align-items:center;gap:7px;flex-wrap:wrap;padding:7px;border:1px solid #dedede;border-radius:14px;background:#fff}}.setting-label{{padding:0 5px;font-size:12px;color:#777}}.palette-option{{display:inline-flex;align-items:center;gap:7px;padding:7px 10px;border:1px solid #e5e5e5;border-radius:999px;background:#fff;color:#555;font:600 12px/1 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;cursor:pointer}}.palette-option:hover{{border-color:#aaa}}.palette-option.is-selected{{border-color:#292929;background:#292929;color:#fff}}.rhythm-panel{{margin:0 0 28px;padding:18px;border:1px solid #dedede;border-radius:18px;background:#fff;box-shadow:0 10px 30px rgba(0,0,0,.035)}}.rhythm-head{{display:grid;grid-template-columns:minmax(220px,.7fr) minmax(0,1.3fr);gap:24px;margin-bottom:14px}}.rhythm-head>div{{display:flex;align-items:baseline;gap:10px}}.rhythm-head strong{{font-size:16px}}.rhythm-head span{{color:#888;font-size:12px}}.rhythm-head ul{{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end;margin:0;padding:0;list-style:none}}.rhythm-head li{{display:flex;gap:7px;align-items:center;flex-wrap:wrap;padding:6px 9px;border-radius:9px;background:#fff8df;color:#6d5a16;font-size:11px}}.rhythm-head li.is-ok{{background:#f4f6f2;color:#65705e}}.rhythm-head code{{font:700 10px/1 ui-monospace,SFMono-Regular,Menlo,monospace}}.rhythm-head em{{width:100%;padding-left:calc(7px + 10ch);color:#8c772c;font-style:normal}}.rhythm-row{{display:grid;grid-template-columns:52px minmax(0,1fr);gap:10px;align-items:center;margin-top:8px}}.rhythm-row>b{{color:#777;font-size:12px}}.rhythm-cells{{display:grid;grid-template-columns:repeat({len(slides)},minmax(24px,1fr));gap:5px}}.rhythm-cell{{min-width:0;height:34px;display:grid;grid-template-rows:11px 1fr;place-items:center;border:1px solid #ececec;border-radius:7px;background:#fafafa;color:#a3a3a3;overflow:hidden}}.rhythm-cell small{{font:600 8px/1 ui-monospace,SFMono-Regular,Menlo,monospace;color:#aaa}}.rhythm-cell i{{font:700 10px/1 ui-monospace,SFMono-Regular,Menlo,monospace;font-style:normal}}.rhythm-cell.is-highlight i{{color:#292929}}.rhythm-cell.bg-grid-fade{{background:linear-gradient(145deg,#fff,#f5f5f4)}}.rhythm-cell.bg-grid-wide{{background:repeating-linear-gradient(90deg,#fafafa 0 5px,#ededeb 5px 6px)}}.rhythm-cell.bg-soft-spotlight{{background:radial-gradient(circle at 30% 28%,#e4e4e1,#fff 58%)}}.rhythm-cell.bg-block-field{{background:linear-gradient(145deg,#fff 0 44%,#eee 44% 72%,#f7e9ae 72%)}}.rhythm-cell.bg-media-owned{{background:#fff}}.pages{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}}article{{padding:14px;border-radius:18px;background:#fff;border:1px solid #e5e5e5}}.meta{{display:flex;align-items:center;gap:7px;margin-bottom:11px}}.meta b{{margin-right:auto}}iframe{{display:block;width:100%;aspect-ratio:16/9;border:1px solid #eee;border-radius:11px;background:#fff}}article p{{margin:10px 2px 0;color:#777;font-size:12px}}@media(max-width:900px){{.rhythm-head{{grid-template-columns:1fr}}.rhythm-head ul{{justify-content:flex-start}}.rhythm-panel{{overflow-x:auto}}.rhythm-row{{min-width:720px}}.pages{{grid-template-columns:1fr}}}}</style></head><body><main>
<header><h1>{esc(data['title'])}</h1></header>
<div class="settings">{palette_controls(data)}<span>字体 {esc(TYPE_META[data['typography']]['label'])}</span><span>圆角 {esc(SHAPE_META[data['shape']]['label'])}</span><span>鼠标翻页 {'开启' if data['click_navigation'] else '关闭'}</span></div>
{rhythm_panel(data, slides)}
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
