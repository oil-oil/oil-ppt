#!/usr/bin/env python3
"""Render the real oil-ppt component matrix as a human review catalog."""
from __future__ import annotations

import argparse
import copy
import html
import json
from pathlib import Path

from capability_catalog import decor_ui_label, template_ui_label, variant_ui_label
from component_contracts import COMPONENT_CONTRACTS, normalize_component_choices
from doctor import smoke_slides
from outline_schema import TEMPLATE_FAMILIES, validate_outline
from render_outline_review import iframe_document


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = Path.home() / "oil-ppt-component-catalog.html"
PLACEHOLDER = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 800'%3E"
    "%3Crect width='1200' height='800' fill='%23f2f1ed'/%3E"
    "%3Ccircle cx='870' cy='180' r='250' fill='%23ebe8df'/%3E"
    "%3Cpath d='M0 650L410 310l230 190 230-270 330 420v150H0z' fill='%23d8d6cf'/%3E"
    "%3Cpath d='M0 720L360 430l250 210 190-150 400 310H0z' fill='%23c9c6bc'/%3E%3C/svg%3E"
)

FAMILY_ORDER = ("focal", "data", "sequence", "cards", "comparison", "canvas", "split", "bleed", "compound")
FAMILY_LABELS = {
    "focal": "单焦点",
    "data": "数据关系",
    "sequence": "顺序推进",
    "cards": "主次聚合",
    "comparison": "对照判断",
    "canvas": "空间关系",
    "split": "图文并置",
    "bleed": "全屏视觉",
    "compound": "复合编辑",
}


def _plain_points(side: dict) -> list[str]:
    points = []
    for item in side.get("points") or []:
        if isinstance(item, dict):
            points.append(str(item.get("body") or item.get("title") or ""))
        else:
            points.append(str(item))
    return points


def catalog_slide(seed: dict, template: str, variant: str, decor: str, index: int) -> dict:
    """Adapt the doctor seed to the exact public variant without example-only extras."""
    slide = copy.deepcopy(seed)
    slide.update({"id": f"catalog-{index:02d}", "variant": variant, "decor": decor})

    if template == "cover":
        slide.pop("image", None)
        slide.pop("media_frame", None)
        if variant == "media":
            slide.update({"image": "assets/smoke.svg", "media_frame": "content", "image_alt": "示例视觉"})
    elif template == "end":
        for key in ("aside", "aside_label", "image", "artifact_title", "artifact_body", "content", "media_frame"):
            slide.pop(key, None)
        if variant == "line-note":
            slide.update({"aside": "保留一句克制的余韵", "aside_label": "NOTE"})
        elif variant == "line-artifact":
            slide.update({
                "image": "assets/smoke.svg", "media_frame": "content", "image_alt": "示例交付物",
                "artifact_title": "最终交付", "artifact_body": "把重要内容带离现场", "content": "交付仍然保持清楚",
            })
    elif template == "process-rail" and variant == "steps-8":
        slide["steps"] = [{"label": f"动作{i}"} for i in range(1, 9)]
    elif template == "card-trio" and variant != "media-evidence":
        slide.pop("content", None)
        slide.pop("media_frame", None)
        for card in slide.get("cards") or []:
            card.pop("images", None)
    elif template == "comparison" and variant == "default":
        slide.pop("content", None)
        slide.pop("media_frame", None)
        for side in slide.get("sides") or []:
            side.pop("evidence", None)
            side.pop("lead", None)
            side["points"] = _plain_points(side)[:2]
    elif template == "editorial-feature" and variant == "default":
        for key in ("secondary_image", "badge", "media_note"):
            slide.pop(key, None)
    elif template == "case-study-board" and variant == "chart":
        slide.pop("image", None)
        slide.pop("media_frame", None)
        slide["chart"] = {"label": "真实变化", "values": [42, 58, 53, 76, 69]}
    elif template == "data-story":
        if variant == "trend":
            slide["content"] = "变化发生在连续时间点之间"
            slide["data"] = {
                "unit": "k",
                "items": [
                    {"label": "Q1", "value": 18}, {"label": "Q2", "value": 24},
                    {"label": "Q3", "value": 31}, {"label": "Q4", "value": 29},
                    {"label": "Q5", "value": 42},
                ],
            }
        elif variant == "composition":
            slide["content"] = "少数部分构成了整体的大部分"
            slide["data"] = {
                "items": [
                    {"label": "组成 A", "value": 48}, {"label": "组成 B", "value": 27},
                    {"label": "组成 C", "value": 16}, {"label": "组成 D", "value": 9},
                ],
            }
        elif variant == "relationship":
            slide["content"] = "两个指标在样本中呈现共同变化"
            slide["data"] = {
                "x_label": "投入", "y_label": "产出", "x_unit": "h", "y_unit": "pt",
                "items": [
                    {"label": "样本 A", "x": 12, "y": 34}, {"label": "样本 B", "x": 18, "y": 45},
                    {"label": "样本 C", "x": 25, "y": 52}, {"label": "样本 D", "x": 31, "y": 67},
                    {"label": "样本 E", "x": 38, "y": 71}, {"label": "样本 F", "x": 44, "y": 83},
                ],
            }
    elif template == "metric" and variant == "delta":
        slide["metric"].update({"change": "+12", "change_label": "较上月"})
    elif template == "metric" and variant == "progress":
        slide["metric"] = {
            "value": 86,
            "target": 100,
            "unit": "%",
            "caption": "当前值与目标值使用同一统计口径",
        }

    normalize_component_choices(slide, index)
    return slide


def build_slides() -> list[dict]:
    seeds = {slide["template"]: slide for slide in smoke_slides()}
    slides = []
    for template, contract in COMPONENT_CONTRACTS.items():
        for variant in contract["variants"]:
            for decor in contract["decorations"]:
                slides.append(catalog_slide(seeds[template], template, variant, decor, len(slides) + 1))
    return slides


def render_card(deck: dict, slide: dict, index: int) -> str:
    document = iframe_document(deck, slide, index).replace("assets/smoke.svg", PLACEHOLDER).replace("assets/secondary.svg", PLACEHOLDER)
    template = slide["template"]
    family = TEMPLATE_FAMILIES[template]
    decor_pill = f"<span>{html.escape(decor_ui_label(slide['decor']))}</span>" if slide["decor"] != "none" else ""
    return f"""
    <article class="component-card" data-family="{html.escape(family)}">
      <div class="card-meta">
        <div><span class="eyebrow">{index:02d}</span><h3>{html.escape(template_ui_label(template))}</h3></div>
        <div class="pills"><span>{html.escape(variant_ui_label(slide['variant']))}</span>{decor_pill}</div>
      </div>
      <div class="preview"><iframe title="{html.escape(template)} · {html.escape(slide['variant'])}" srcdoc="{html.escape(document, quote=True)}" loading="lazy"></iframe></div>
      <footer><code>{html.escape(template)}</code><span>{html.escape(FAMILY_LABELS[family])}</span></footer>
    </article>"""


def render_catalog(output: Path) -> int:
    slides = build_slides()
    deck = {
        "title": "oil-ppt component catalog",
        "palette": "oil-yellow",
        "typography": "clean",
        "shape": "soft",
        "click_navigation": False,
        "media_policy": "required",
        "slides": slides,
    }
    validate_outline(deck, ROOT / "assets" / "templates")
    grouped = {family: [] for family in FAMILY_ORDER}
    for index, slide in enumerate(slides, start=1):
        grouped[TEMPLATE_FAMILIES[slide["template"]]].append(render_card(deck, slide, index))

    sections = []
    for family in FAMILY_ORDER:
        if not grouped[family]:
            continue
        sections.append(f"""
        <section class="family-section" data-family-section="{family}">
          <header class="section-head"><span>{html.escape(FAMILY_LABELS[family])}</span><b>{len(grouped[family])} 种组合</b></header>
          <div class="component-grid">{''.join(grouped[family])}</div>
        </section>""")

    buttons = ''.join(
        f'<button type="button" data-filter="{family}">{html.escape(FAMILY_LABELS[family])}</button>'
        for family in FAMILY_ORDER if grouped[family]
    )
    page = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>oil-ppt 组件目录</title><style>
    :root{{--ink:#2d2d2b;--muted:#777773;--line:#e4e3df;--paper:#f5f5f2;--surface:#fff;--accent:#f0bf4d;--accent-soft:#fff4d5;--radius:34px}}
    *{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:"PingFang SC","Noto Sans SC",system-ui,sans-serif}}button{{font:inherit}}
    .page{{width:min(1500px,calc(100% - 40px));margin:20px auto 80px}}
    .hero{{position:relative;min-height:520px;padding:76px 80px;border:0;border-radius:44px;background:var(--surface);overflow:visible}}
    .shape-window{{position:absolute;inset:0;z-index:0;overflow:hidden;border-radius:inherit;pointer-events:none}}.shape-window::after{{content:"";position:absolute;border-radius:50%}}
    .hero>.shape-window::after{{right:-132px;top:-132px;width:420px;height:420px;border:48px solid #f1f1ef}}
    .kicker{{display:flex;align-items:center;gap:14px;font-weight:800;letter-spacing:.08em}}.kicker::before{{content:"";width:42px;height:14px;border-radius:99px;background:var(--accent)}}
    h1{{position:relative;z-index:1;max-width:1080px;margin:40px 0 24px;font-size:78px;line-height:1.05;letter-spacing:-.055em}}.lead{{position:relative;z-index:1;max-width:980px;margin:0;color:var(--muted);font-size:25px;line-height:1.65}}
    .stats{{position:relative;z-index:1;display:flex;gap:14px;margin-top:44px}}.stat{{min-width:210px;padding:22px 26px;border-radius:24px;background:#f1f1ee}}.stat:first-child{{background:var(--accent-soft)}}.stat strong{{display:block;font-size:38px}}.stat span{{color:var(--muted)}}
    .system{{margin-top:22px;padding:42px 48px;border:0;border-radius:36px;background:var(--surface)}}.system h2{{margin:0;font-size:38px}}.system p{{max-width:990px;color:var(--muted);font-size:20px;line-height:1.65}}
    .primitives{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:30px}}.primitive{{position:relative;min-height:180px;padding:28px;border-radius:28px;background:#f2f2ef;overflow:visible;isolation:isolate}}.primitive.accent{{background:var(--accent-soft)}}.primitive.ink{{background:var(--ink);color:#fff}}.primitive b{{position:relative;z-index:1;font-size:24px}}.primitive>span:not(.shape-window){{position:absolute;z-index:1;left:28px;bottom:26px;color:var(--muted)}}.primitive.ink>span:not(.shape-window){{color:#bbb}}
    .primitive.ring>.shape-window::after{{right:-60px;top:-60px;width:200px;height:200px;border:28px solid rgba(45,45,43,.07)}}.dots::after{{content:"";position:absolute;right:20px;bottom:18px;width:126px;height:92px;background:radial-gradient(circle,rgba(45,45,43,.12) 2px,transparent 2.5px);background-size:18px 18px}}
    .filters{{position:sticky;top:12px;z-index:20;display:flex;gap:10px;flex-wrap:wrap;margin:22px 0;padding:14px;border:0;border-radius:26px;background:rgba(255,255,255,.9);backdrop-filter:blur(16px)}}.filters button{{padding:12px 18px;border:0;border-radius:16px;background:#efefec;color:var(--ink);cursor:pointer}}.filters button.is-active{{background:var(--ink);color:#fff}}
    .family-section{{margin-top:26px;padding:34px;border:0;border-radius:36px;background:var(--surface)}}.section-head{{display:flex;justify-content:space-between;align-items:center;margin:0 0 24px}}.section-head span{{font-size:34px;font-weight:800}}.section-head b{{color:var(--muted);font-size:17px}}
    .component-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}}.component-card{{min-width:0;padding:18px;border-radius:28px;background:#f4f4f1}}.card-meta{{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:4px 6px 16px}}.card-meta>div:first-child{{display:flex;align-items:center;gap:12px}}.eyebrow{{display:grid;place-items:center;width:38px;height:38px;border-radius:13px;background:var(--accent-soft);font-size:13px;font-weight:800}}h3{{margin:0;font-size:22px}}.pills{{display:flex;gap:8px}}.pills span{{padding:7px 10px;border-radius:11px;background:#fff;color:var(--muted);font-size:13px}}
    .preview{{position:relative;aspect-ratio:16/9;border-radius:22px;background:#fff;overflow:hidden}}iframe{{position:absolute;inset:0;width:100%;height:100%;border:0;pointer-events:none}}.component-card footer{{display:flex;justify-content:space-between;padding:15px 6px 3px;color:var(--muted)}}code{{font-size:13px}}
    body[data-filter]:not([data-filter="all"]) .family-section{{display:none}}body[data-filter="focal"] [data-family-section="focal"],body[data-filter="data"] [data-family-section="data"],body[data-filter="sequence"] [data-family-section="sequence"],body[data-filter="cards"] [data-family-section="cards"],body[data-filter="comparison"] [data-family-section="comparison"],body[data-filter="canvas"] [data-family-section="canvas"],body[data-filter="split"] [data-family-section="split"],body[data-filter="bleed"] [data-family-section="bleed"],body[data-filter="compound"] [data-family-section="compound"]{{display:block!important}}
    @media(max-width:980px){{.page{{width:calc(100% - 20px);margin-top:10px}}.hero{{padding:48px 32px;min-height:auto}}h1{{font-size:52px}}.primitives,.component-grid{{grid-template-columns:1fr}}.stats{{flex-wrap:wrap}}}}
    </style></head><body data-filter="all"><main class="page">
      <header class="hero"><span class="shape-window" aria-hidden="true"></span><div class="kicker">OIL-PPT COMPONENT CATALOG</div><h1>把真实可用的组件，放进同一个设计系统里。</h1><p class="lead">目录完全来自当前 CLI 契约。配色收束为一个主题色系、中性灰与可选深色锚点；圆环、点阵和块面由程序自动承担。</p><div class="stats"><div class="stat"><strong>{len(COMPONENT_CONTRACTS)}</strong><span>注册组件</span></div><div class="stat"><strong>{len(slides)}</strong><span>可调用组合</span></div><div class="stat"><strong>1 + N</strong><span>主题色与中性色层级</span></div></div></header>
      <section class="system"><h2>先看程序自动承担的视觉原语</h2><p>模型只选择内容关系。容器底色、低对比几何、点阵、圆角与图标框架由模板和 runtime 统一生成，因此不会因为模型能力不同而变成彩色卡片拼盘。</p><div class="primitives"><article class="primitive accent"><b>主题色浅层</b><span>重点容器</span></article><article class="primitive ring"><span class="shape-window" aria-hidden="true"></span><b>中性圆环</b><span>低对比几何</span></article><article class="primitive dots"><b>局部点阵</b><span>只落一个重点</span></article><article class="primitive ink"><b>深色锚点</b><span>每页最多一个</span></article></div></section>
      <nav class="filters"><button type="button" class="is-active" data-filter="all">全部</button>{buttons}</nav>{''.join(sections)}
    </main><script>document.querySelector('.filters').addEventListener('click',event=>{{const button=event.target.closest('button[data-filter]');if(!button)return;document.body.dataset.filter=button.dataset.filter;document.querySelectorAll('.filters button').forEach(item=>item.classList.toggle('is-active',item===button));}})</script></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    return len(slides)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    count = render_catalog(args.output.expanduser().resolve())
    print(f"Rendered {count} callable component combinations: {args.output.expanduser().resolve()}")


if __name__ == "__main__":
    main()
