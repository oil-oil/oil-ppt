# HTML component guide

Use this reference while authoring a slide when the starter alone is not enough. Components are ordinary HTML classes backed by `runtime/deck.css`. They provide reliable geometry and visual language; they do not prescribe page content or DOM structure.

## Progressive freedom

1. Copy the nearest starter and replace its example content.
2. Rearrange or combine the generic components below.
3. Add page-specific DOM and CSS scoped below `.s-<id>`.
4. Replace the starter structure completely when the page needs a unique composition.

Never change another slide to make the current slide work. Reusable improvements belong in runtime only when at least several pages genuinely share the same primitive.

## Choose the relationship before the component

先写出这一页唯一要让观众看懂的关系，再选择构图。组件是关系的载体，不是内容容器的库存。

| 内容关系 | 优先构图 | 避免 |
| --- | --- | --- |
| 一个判断最重要 | statement、title-media、单一证据画布 | 为了填满而补三张小卡 |
| 两者差异或取舍 | comparison、开放对照轴 | 两边各堆多层面板 |
| 2–3 个连续动作 | sequence、宽松步骤 | 把每一步写成小文档 |
| 4 个阶段总览 | process-rail、timeline | 每列再嵌套护栏框、指标或引用 |
| 多路输入汇聚 | converge、关系图 | 把因果关系改写成卡片列表 |
| 一主多辅 | feature-grid | 等权卡片墙 |
| 截图或材料支撑判断 | evidence、annotated-showcase、browser-showcase | 用装饰图替代真实证据 |

### Repeated-unit load budget

- 2 个并列单元：每个可承载标题、一段解释和一个必要证据。
- 3 个并列单元：每个保留标题和一段解释；只有一个单元可以成为重点并增加证据。
- 4 个及以上等宽单元：每个只保留编号或时间、标题和一句短解释。不要在每个单元里再放说明框、护栏、指标、引用或第二段正文。
- 5–8 个步骤：只有标题级信息时可以使用两行路线；只要需要逐步解释，就拆成“总览页 + 重点页”，不能继续压缩字号。

第二层信息有三种去处：合并成页面底部一个共享结论；只展开一个当前重点，其余保持概览；拆到下一页。不要把同一类补充信息复制进每个重复节点。

### Use the stage, not just the top edge

清爽不等于把内容缩成页面上方的一条。标题之后的主要关系通常应占安全区约 55%–70% 的高度，并让视觉重心接近页面中部。若核心内容在页面高度约 60% 之前已经结束、页脚却贴在最底部，应先重新分配垂直空间、放大关系或改用聚焦构图，而不是继续添加小框填空。

## Design tokens

Prefer these variables over literal colors and radii:

```css
var(--slide-bg)
var(--ink)
var(--ink-2)
var(--ink-3)
var(--border)
var(--surface)
var(--surface-2)
var(--accent)
var(--accent-fill)
var(--accent-soft)
var(--accent-strong)
var(--accent-alt)
var(--accent-warm)
var(--surface-radius)
var(--surface-radius-sm)
var(--media-radius)
var(--font-zh)
var(--font-ui)
var(--oil-text-body)
var(--oil-text-compact)
var(--oil-text-caption)
```

The selected deck theme supplies the values. A page may define its own page-scoped custom properties when it needs different spacing or geometry.

## Readable type on the 1920×1080 stage

Treat a slide as projected content, not a desktop web page. Start ordinary body copy at 28–32px. The browser quality gate enforces these floors across every slide, including text placed in `span`, `div`, `strong`, `pre`, and custom DOM:

- `h1`: 48px minimum; most page titles should be 64–96px.
- `h2`: 32px minimum; `h3` through `h6`: 28px minimum.
- Ordinary explanatory copy: 24px hard minimum; prefer `var(--oil-text-body)` at 28px.
- Compact tables, code, captions, sources, and short labels: 20px minimum; prefer `var(--oil-text-compact)` or `var(--oil-text-caption)`.
- A short index may use `data-microcopy="index"`; short auxiliary metadata may use `data-microcopy="meta"`. Put the attribute on the text element itself, never on a container. These explicit roles may go down to 18px, but headings, sentences, card descriptions, takeaways, and instructions always keep their normal floors.
- Visible HTML and inline SVG text must keep at least 2.5:1 contrast against a determinable solid background. The browser quality gate checks CSS `color` and SVG text `fill`; white-on-white and similar failures block preview and build.

If content does not fit, shorten it, split the page, or change the composition. Do not shrink audience-facing copy below the floor. If a page has large unused areas, enlarge the main copy or visual before adding decoration.

## Layout primitives

`.oil-stack` is a vertical flex stack. Set `--stack-gap` locally; use `data-direction="row"`, `data-align="center"`, or `data-align="end"` for common variants.

`.oil-grid` is a responsive grid within the fixed stage. Set `--grid-columns` and `--grid-gap` in the page CSS, then assign item spans with page-specific classes.

`.oil-panel` and `.oil-surface` provide stable panels. `.oil-panel` 默认是无边框静面；可选 `data-tone` 为 `soft`、`accent`、`ink`，只有需要明确分界时才写 `data-stroke="hairline"` 或 `data-stroke="strong"`。

```html
<div class="oil-grid feature-grid" data-layout>
  <article class="oil-panel" data-tone="accent">…</article>
  <article class="oil-panel" data-stroke="hairline">…</article>
</div>
```

The `data-layout` attribute is only a geometry-check hint. It does not choose a page implementation or constrain the element's children.

## Background, surface craft and relationships

`.oil-slide` defaults to `grid-fade`: a warm/off-white canvas with a local fading grid. Choose `data-bg="grid-wide"` only when a system diagram needs a wider field; `soft-spotlight`, `block-field` and `media-owned` are deliberate alternatives. `grid-full` is an explicit uniform grid, never the default, and `plain` removes the background decoration.

`.oil-surface` and `.oil-panel` are quiet by default. Add one local craft layer to one primary surface when it helps hierarchy: `data-decor="dots"` with a corner `data-decor-pos`, or `data-motif="ring|triangle|slash"` with `data-motif-pos="top-right|top-left|bottom-right|bottom-left"`. Ring clipping uses a child `<span class="oil-shape-window" aria-hidden="true"></span>` and paints exactly one clipped ring. Decorative pseudo-elements never contain text; all meaning stays in the DOM. Do not combine dots and a motif on the same surface, and do not decorate every surface; the nonblocking advice flags this conflict.

`.oil-relationship`, `.oil-relationship-node`, and `.oil-relationship-link` provide only generic geometry. Put the real labels, explanations and any relationship-specific positioning in page-scoped HTML/CSS. The `relationship-map` starter uses a page-scoped CSS Grid to keep the core node centered and a decorative inline SVG only for connectors; text remains real DOM, and the copied page may change the grid, node count, connector paths or complete structure. Do not turn relationship diagrams into a hidden schema or canvas-only text.

## Sequences and process rails

`.oil-timeline` 或 `sequence` starter 适合 2–4 个连续动作。三步时可以给每一步更宽的解释空间；四步时必须切换到总览密度。

`process-rail` starter 是四阶段总览：轨道建立先后关系，每个节点只承担 meta、标题和一句说明。共享原则、共同护栏或统一衡量标准放在轨道之外，只出现一次。若每个阶段都有不同护栏或证据，这已经不是一张总览页，应保留轨道作为第一页，再为重点阶段制作下一页。

路线不是卡片墙。轨道节点默认不需要背景、描边、阴影或嵌套面板；节点之间的线、位置、留白和一处强调已经足够表达顺序。

## Airy house style

先用面积、位置、柔和底色和留白排出主次，再考虑框线。清脆感优先通过圆角几何表达，不通过加粗描边；2px 深色描边是明确的例外。技术内容保持冷静清楚，不需要黑黄工业感。默认只保留一个主深色面，避免嵌套/重复框和等权卡片墙；有多个要点时，优先改成开放轨道、关系图或一主多辅 feature hierarchy。内容过多就拆页或重组，不能缩小文字。

## Content primitives

- `.oil-metric`, `.oil-metric-value`, `.oil-metric-label`: one compact metric.
- `.oil-quote`: a quotation with an optional `<cite>`.
- `.oil-label`: a short kicker. Runtime components always stay in the `oil-*` namespace so page-specific class names remain free.
- `.oil-highlight`: a short inline marker highlight.
- `.oil-code`: a preformatted code panel.
- `.oil-table`: a legible compact table.
- `.oil-timeline` and `.oil-timeline-item`: a simple horizontal sequence. Set `--timeline-columns`.
- `.oil-chart`, `.oil-chart-bar`: a small bar chart. Set each bar's `--bar-level` in page CSS or use page-specific data attributes mapped by scoped CSS.
- `.oil-connector`: a simple directional connector between nearby elements.

Charts use real values and a visible source note. For analytical charts that need axes, scales, labels, or richer geometry, author inline SVG or semantic HTML/CSS directly rather than forcing the generic bar primitive.

## Media and evidence

`.oil-media` is the standard clipped media frame. Direct child images and videos fill it with `object-fit: cover`; add `data-media-fit="contain"` for diagrams, documents, and product screenshots that must not be cropped.

`.oil-browser` provides a browser shell with `.oil-browser-bar`, `.oil-browser-lights`, `.oil-browser-address`, and `.oil-browser-screen`. Use it only when the browser chrome helps the audience understand the evidence.

All sources are project-local and referenced from a slide as `../assets/...`. Add accurate `alt` text. Use `data-bleed="left|right|top|bottom|full"` only when an element intentionally reaches the slide edge. Decorative elements that may cross the safe area should carry `data-decoration` so geometry checks treat them as decoration rather than content.

For a side-owned visual, use `.oil-bleed` with `data-side="left|right"` and optional `data-cut="diagonal"`. `.oil-media` accepts `data-media-position` presets, natural/muted/mono treatments, `left-fade|right-fade|bottom-ink|accent-wash` overlays, and `soft-edges|fade-bottom` masks. These APIs only frame project-local media; they do not generate images, fetch remote sources, or add JavaScript.

## Icons

Bundled icons live in `assets/icons/` inside a project. Use them as local images or copy the SVG markup inline when color needs to follow `currentColor`:

```html
<span class="oil-icon-frame" aria-hidden="true">
  <img class="oil-icon" src="../assets/icons/lightbulb.svg" alt="">
</span>
```

Do not substitute emoji for interface or conceptual icons, and do not load an icon font or remote SVG package.

## Page-specific CSS

Every selector inside the slide marker must begin with the slide scope:

```css
.s-problem .feature-grid { --grid-columns: 12; align-items: stretch; }
.s-problem .feature-main { grid-column: span 7; }
.s-problem .feature-proof { grid-column: span 5; }
```

Use the component class for the shared behavior and the page class for the unique composition. This separation lets a model repair one page without knowing or changing every other page.
