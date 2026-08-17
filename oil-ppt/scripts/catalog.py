"""Deterministic, offline visual catalogs for oil-ppt's HTML-first surface."""
from __future__ import annotations

import html
import os
import re
import tempfile
from pathlib import Path

from theme import DIRECTIONS, PALETTES, SHAPES, TYPOGRAPHY


ROOT = Path(__file__).resolve().parent.parent

STARTER_GUIDANCE = {
    "blank": "从零开始的留白画布，适合独特构图。",
    "statement": "用一句核心主张建立开场或章节判断。",
    "title-media": "让一项证据或视觉与标题并置。",
    "comparison": "用开放中轴对照现状与方向，只有推荐一侧使用色调面。",
    "sequence": "说明 2–4 个连续行动；三步可展开，四步时每步只保留一段解释。",
    "data": "突出一个指标和它的简短解释。",
    "evidence": "把结论与可核验材料放在同一页。",
    "section": "用短标题和节奏切换叙事段落。",
    "ending": "收束判断并留下清晰下一步。",
    "problem-canvas": "把问题、影响与机会组织成不等权的画布。",
    "converge": "展示多路输入如何汇聚为一个选择。",
    "process-rail": "四阶段总览；每个节点只放时间或编号、标题和一句短解释，第二层信息移到共享区或下一页。",
    "feature-grid": "用一项主特征和少量辅助特征建立层级。",
    "annotated-showcase": "用注释指向一项关键证据或界面细节。",
    "browser-showcase": "让本地产品或网页证据占据页面主体；标题保持简短，只有来源或限制确实必要时再补一行说明。",
    "editorial-feature": "以大标题和一项主表面讲述编辑式判断。",
    "relationship-map": "用真实 DOM 节点和连接线表达对象关系。",
    "hierarchy-tree": "以三层层级展示归属、职责或组织结构。",
    "cycle": "用四步循环解释持续反馈或迭代。",
    "metric-spotlight": "让一个关键数字占据主要视觉面积。",
    "quote-focus": "把一段可核验引用作为整页的主角。",
    "step-focus": "展开总览中的一个关键行动，而不是缩小全部步骤。",
    "bleed-split": "让本地媒体拥有一侧舞台，文字保持清晰安全区。",
    "media-collage": "组织三项本地材料为主辅关系，而非平均相册。",
}

COMPOSITION_FAMILIES = {
    "focus": ("blank", "statement", "section", "ending", "metric-spotlight", "quote-focus", "step-focus"),
    "comparison": ("comparison", "bleed-split"),
    "sequence": ("sequence", "process-rail", "cycle"),
    "hierarchy": ("feature-grid", "editorial-feature", "problem-canvas"),
    "relationship": ("converge", "relationship-map", "hierarchy-tree"),
    "evidence": ("title-media", "evidence", "annotated-showcase", "browser-showcase", "media-collage"),
    "data": ("data",),
}


def _write(output: Path, contents: str) -> Path:
    """Atomically write a catalog without depending on a project directory."""
    target = output.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".oil-ppt-catalog-", suffix=".html", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def _page(title: str, body: str) -> str:
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>
:root{{--ink:#292929;--ink-2:#666;--border:#e8e8e8;--surface:#f7f7f8;--accent:#ffd54a;--font:Inter,"Noto Sans SC","PingFang SC",sans-serif}}*{{box-sizing:border-box}}body{{margin:0;background:#fafafa;color:var(--ink);font-family:var(--font)}}main{{max-width:1440px;margin:auto;padding:48px 28px 80px}}h1{{margin:0;font-size:42px;letter-spacing:-.04em}}h2{{margin:52px 0 18px;font-size:22px}}p{{color:var(--ink-2);line-height:1.6}}.eyebrow{{margin:0 0 10px;font:700 12px/1 var(--font);letter-spacing:.12em;color:var(--ink-2)}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px}}.card{{overflow:hidden;border:1px solid var(--border);border-radius:18px;background:#fff}}.card.wide{{grid-column:span 2}}.card-body{{padding:18px}}.name{{margin:0 0 6px;font-size:18px}}.token{{margin:0;font:12px/1.55 ui-monospace,SFMono-Regular,monospace;color:var(--ink-2);white-space:pre-wrap}}.swatches{{display:grid;grid-template-columns:repeat(4,1fr);height:100px}}.swatch{{display:flex;align-items:end;padding:7px;color:#333;font:700 10px/1 var(--font)}}.type-sample{{padding:28px;font-size:28px;line-height:1.2;min-height:106px}}.shape-sample{{display:grid;place-items:center;min-height:106px;background:var(--surface)}}.shape-sample i{{display:block;width:130px;height:62px;background:#fff;border:1px solid var(--border)}}.preview{{position:relative;aspect-ratio:16/9;background:#f2f2f2;overflow:hidden}}iframe{{position:absolute;left:0;top:0;width:1920px;height:1080px;border:0;transform:scale(.13);transform-origin:top left;pointer-events:none}}.component-demo{{padding:22px;min-height:190px;background:#fff}}.component-demo .oil-panel{{margin-bottom:12px}}.component-demo .oil-metric-value{{font-size:38px}}.component-demo .oil-quote{{font-size:17px;padding:16px}}@media(max-width:600px){{main{{padding:32px 16px 60px}}h1{{font-size:32px}}.card.wide{{grid-column:auto}}}}
</style></head><body><main>{body}</main><script>(() => {{
  const fit = preview => {{
    const frame = preview.querySelector("iframe");
    if (frame && preview.clientWidth) frame.style.transform = `scale(${{preview.clientWidth / 1920}})`;
  }};
  const previews = [...document.querySelectorAll(".preview")];
  previews.forEach(fit);
  if ("ResizeObserver" in window) {{ const observer = new ResizeObserver(items => items.forEach(item => fit(item.target))); previews.forEach(item => observer.observe(item)); }}
}})();</script></body></html>\n'''


def render_theme_catalog(output: Path | None = None) -> Path:
    """Render the registry itself: five palettes, three type sets, three shapes."""
    palette_cards = []
    for name in sorted(PALETTES):
        tokens = PALETTES[name]
        selected = ("slide-bg", "accent", "accent-fill", "accent-alt", "accent-warm", "ink")
        swatches = "".join(
            f'<div class="swatch" style="background:{tokens[key]}">{html.escape(key)}</div>' for key in selected
        )
        palette_cards.append(f'<article class="card"><div class="swatches">{swatches}</div><div class="card-body"><h3 class="name">{html.escape(name)}</h3><p class="token">accent {html.escape(tokens["accent"])}\nalt    {html.escape(tokens["accent-alt"])}</p></div></article>')
    type_cards = []
    for name in sorted(TYPOGRAPHY):
        tokens = TYPOGRAPHY[name]
        type_cards.append(f'<article class="card"><div class="type-sample" style="font-family:{html.escape(tokens["font-zh"], quote=True)}">中文排版 Aa 123</div><div class="card-body"><h3 class="name">{html.escape(name)}</h3><p class="token">{html.escape(tokens["font-ui"])}</p></div></article>')
    shape_cards = []
    for name in sorted(SHAPES):
        tokens = SHAPES[name]
        shape_cards.append(f'<article class="card"><div class="shape-sample"><i style="border-radius:{html.escape(tokens["surface-radius"])}"></i></div><div class="card-body"><h3 class="name">{html.escape(name)}</h3><p class="token">surface {html.escape(tokens["surface-radius"])} · media {html.escape(tokens["media-radius"])}</p></div></article>')
    direction_cards = []
    for name in sorted(DIRECTIONS):
        direction = DIRECTIONS[name]
        recommended = direction["recommended"]
        direction_cards.append(
            f'<article class="card"><div class="component-demo"><p class="eyebrow">{html.escape(name)}</p>'
            f'<h3 class="name">{html.escape(direction["label"])}</h3><p>{html.escape(direction["description"])}</p>'
            f'<p class="token">{html.escape(recommended["palette"])} · {html.escape(recommended["typography"])} · {html.escape(recommended["shape"])}</p>'
            f'<p class="token">{" / ".join(html.escape(item) for item in direction["principles"])}</p></div></article>'
        )
    body = f'''<p class="eyebrow">OIL-PPT / THEME REGISTRY</p><h1>配色与主题总览</h1><p>方向是语义简报与起始 preset；运行时仍只由 palette、typography 和 shape 生成 token。</p><h2>Directions · {len(DIRECTIONS)}</h2><div class="grid">{"".join(direction_cards)}</div><h2>Palette · {len(PALETTES)}</h2><div class="grid">{"".join(palette_cards)}</div><h2>Typography · {len(TYPOGRAPHY)}</h2><div class="grid">{"".join(type_cards)}</div><h2>Shape · {len(SHAPES)}</h2><div class="grid">{"".join(shape_cards)}</div>'''
    return _write(output or Path("~/oil-ppt-theme-catalog.html"), _page("oil-ppt theme catalog", body))


def _starter_srcdoc(path: Path) -> str:
    """Use the real starter's parsed CSS and section in a self-contained iframe."""
    source = path.read_text(encoding="utf-8").replace("__ID__", "catalog").replace("__TITLE__", path.stem.replace("-", " ").title())
    css = source.split("/* OIL-SLIDE-CSS:START */", 1)[1].split("/* OIL-SLIDE-CSS:END */", 1)[0]
    section = re.search(r"<!-- OIL-SLIDE:START -->(.*?)<!-- OIL-SLIDE:END -->", source, re.S)
    if not section:
        raise SystemExit(f"Starter does not contain an OIL-SLIDE section: {path}")
    runtime = (ROOT / "assets" / "runtime" / "deck.css").read_text(encoding="utf-8")
    theme = (ROOT / "assets" / "runtime" / "theme.css").read_text(encoding="utf-8")
    return f'<!doctype html><html><head><style>{runtime}\n{theme}\n{css}</style></head><body data-oil-mode="preview"><div class="slide-preview-viewport"><div class="slide-preview-shell"><div class="slide-preview-stage">{section.group(1)}</div></div></div></body></html>'


def _component_examples() -> str:
    runtime = (ROOT / "assets" / "runtime" / "deck.css").read_text(encoding="utf-8")
    theme = (ROOT / "assets" / "runtime" / "theme.css").read_text(encoding="utf-8")
    demo = '''<div class="component-demo"><div class="oil-panel" data-tone="accent"><span class="oil-label">signal</span><div class="oil-metric"><strong class="oil-metric-value">72%</strong><span class="oil-metric-label">关键指标</span></div></div><blockquote class="oil-quote">共享 primitives 负责几何与表现。</blockquote></div>'''
    backgrounds = ''.join(
        f'<div class="catalog-bg"><section class="oil-slide s-catalog" data-bg="{name}"><span>{name}</span>'
        f'{"<i class=\"catalog-media-owned-sample\" aria-hidden=\"true\"></i>" if name == "media-owned" else ""}</section></div>'
        for name in ("grid-fade", "grid-wide", "soft-spotlight", "block-field", "media-owned", "grid-full", "plain")
    )
    cards = [
        ("layout", "oil-stack · oil-grid · oil-head · oil-notes · oil-surface", '<div class="component-demo"><div class="oil-grid" style="--grid-columns:3"><div class="oil-panel">A</div><div class="oil-panel">B</div><div class="oil-panel">C</div></div></div>'),
        ("content", "oil-panel · oil-metric · oil-quote · oil-label", demo),
        ("backgrounds", "grid-fade (default) · grid-wide · soft-spotlight · block-field · media-owned · grid-full · plain", f'<div class="component-demo catalog-backgrounds">{backgrounds}</div>'),
        ("media treatments", "natural · muted · mono · overlays · masks · oil-bleed", '<div class="component-demo catalog-media"><div class="oil-media" data-media-treatment="natural"><div class="oil-media-placeholder">NATURAL</div></div><div class="oil-media" data-media-treatment="muted" data-overlay="accent-wash"><div class="oil-media-placeholder">MUTED</div></div><div class="oil-media" data-media-treatment="mono" data-mask="fade-bottom"><div class="oil-media-placeholder">MONO</div></div><div class="oil-bleed" data-side="right"><span>BLEED</span></div></div>'),
        ("data", "oil-timeline · oil-chart · oil-table · oil-connector", '<div class="component-demo"><div class="oil-chart"><i class="oil-chart-bar" style="--bar-level:42%"></i><i class="oil-chart-bar" style="--bar-level:72%" data-focus="true"></i><i class="oil-chart-bar" style="--bar-level:56%"></i></div></div>'),
        ("surface craft", "dots · ring · triangle · slash (one craft layer per surface)", '<div class="component-demo catalog-surfaces"><div class="oil-surface" data-decor="dots">DOTS</div><div class="oil-surface" data-motif="ring"><span class="oil-shape-window" aria-hidden="true"></span>RING</div><div class="oil-surface" data-motif="triangle">TRIANGLE</div><div class="oil-surface" data-motif="slash">SLASH</div></div>'),
        ("relationship", "oil-relationship · oil-relationship-node · oil-relationship-link", '<div class="component-demo catalog-relationship"><div class="oil-relationship"><i class="oil-relationship-link" data-direction="arrow"></i><strong class="oil-relationship-node oil-surface" data-tone="accent">CENTER</strong><span class="oil-relationship-node oil-surface">INPUT</span></div></div>'),
    ]
    rendered = []
    for name, label, markup in cards:
        srcdoc = f'<!doctype html><html><head><style>{runtime}\n{theme}\nhtml,body{{overflow:hidden!important;background:#fff}}.component-demo{{position:relative;width:1920px;min-height:1080px;padding:128px;font-size:52px}}.component-demo .oil-panel{{padding:64px}}.component-demo .oil-grid{{gap:36px}}.component-demo .oil-metric-value{{font-size:112px}}.component-demo .oil-metric-label{{font-size:34px}}.component-demo .oil-quote{{margin-top:34px;padding:34px 44px;font-size:46px}}.component-demo .oil-chart{{height:760px;gap:34px;padding:80px 0}}.catalog-backgrounds{{display:grid;grid-template-columns:repeat(4,1fr);gap:24px;padding:72px}}.catalog-bg{{height:420px;overflow:hidden;border-radius:24px}}.catalog-bg .oil-slide{{position:relative!important;display:block!important;visibility:visible!important;opacity:1!important;width:100%!important;height:420px!important;padding:34px;color:var(--ink-2);font:700 28px/1 var(--font-ui)}}.catalog-bg .catalog-media-owned-sample{{position:absolute;right:0;top:0;width:58%;height:100%;background:linear-gradient(135deg,var(--accent-soft),var(--surface));clip-path:polygon(20% 0,100% 0,100% 100%,0 100%)}}.catalog-media{{display:grid;grid-template-columns:repeat(3,1fr);gap:28px;overflow:hidden}}.catalog-media .oil-media{{min-height:650px;border-radius:28px}}.catalog-media .oil-media-placeholder{{font-size:34px}}.catalog-media .oil-bleed{{position:relative;grid-column:1/-1;width:100%;height:104px;display:grid;place-items:center;color:var(--ink-2);font:700 30px/1 var(--font-ui)}}.catalog-surfaces{{display:grid;grid-template-columns:repeat(4,1fr);gap:28px}}.catalog-surfaces .oil-surface{{display:grid;place-items:center;min-height:710px;padding:28px;border-radius:32px;color:var(--ink-2);font:700 34px/1 var(--font-ui)}}.catalog-relationship .oil-relationship{{height:824px}}.catalog-relationship .oil-relationship-link{{left:430px;top:405px;width:1000px;height:5px}}.catalog-relationship .oil-relationship-node{{display:grid;place-items:center;padding:38px;min-width:300px;min-height:150px;border-radius:28px;font:700 34px/1 var(--font-ui)}}.catalog-relationship strong{{left:90px;top:330px}}.catalog-relationship span{{right:90px;top:330px}}</style></head><body data-oil-mode="preview">{markup}</body></html>'
        card_class = "card wide" if name in {"backgrounds", "media treatments", "surface craft", "relationship"} else "card"
        rendered.append(f'<article class="{card_class}"><div class="preview"><iframe title="{name}" srcdoc="{html.escape(srcdoc, quote=True)}"></iframe></div><div class="card-body"><h3 class="name">{name}</h3><p class="token">{label}</p></div></article>')
    return "".join(rendered)


def render_starter_catalog(output: Path | None = None) -> Path:
    starters = sorted((ROOT / "assets" / "starters").glob("*.html"))
    cards = []
    for path in starters:
        srcdoc = _starter_srcdoc(path)
        cards.append(f'<article class="card"><div class="preview"><iframe title="{html.escape(path.stem)} starter" srcdoc="{html.escape(srcdoc, quote=True)}"></iframe></div><div class="card-body"><h3 class="name">{html.escape(path.stem)}</h3><p>{html.escape(STARTER_GUIDANCE.get(path.stem, "Copy-once standalone HTML starter."))}</p><p class="token">assets/starters/{html.escape(path.name)}</p></div></article>')
    family_list = "".join(f"<li><strong>{html.escape(name)}</strong> · {html.escape(' · '.join(items))}</li>" for name, items in COMPOSITION_FAMILIES.items())
    body = f'''<p class="eyebrow">OIL-PPT / HTML-FIRST</p><h1>Starter 与通用组件总览</h1><p>每个 starter 预览都由真实独立 HTML source 的 section 和 page-scoped CSS 生成；无需页面 JSON schema。</p><h2>Composition families</h2><p>正常 8–10 页叙事至少混用四类构图，避免连续重复同一种卡片墙。</p><ul>{family_list}</ul><h2>Starters · {len(starters)}</h2><div class="grid">{"".join(cards)}</div><h2>Generic .oil-* primitives</h2><p>固定示例来自当前 deck.css，可组合进任意独立页面。</p><div class="grid">{_component_examples()}</div>'''
    return _write(output or Path("~/oil-ppt-starter-catalog.html"), _page("oil-ppt starter catalog", body))
