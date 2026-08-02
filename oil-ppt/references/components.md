# 页面设计与组件规范

本文件是 oil-ppt 的唯一设计规范。进入 `author_slides` 后完整读取一次；制作具体页面时按照当前关系选择相关部分。组件提供可靠几何和视觉语言，不规定页面字段或固定模板。

## 目录

1. 设计执行顺序
2. 关系与构图
3. 舞台和纵向占满
4. 字号与文字节奏
5. 布局和表面组件
6. 背景与局部装饰
7. 流程、关系和数据
8. 媒体与证据
9. 页面局部 CSS
10. 页面完成检查

## 设计执行顺序

每页按照以下顺序完成：

1. 写出观众需要看懂的唯一判断。
2. 判断内容关系：聚焦、比较、顺序、汇聚、关系、证据或数据。
3. 选择最接近的 starter，先排主要关系和视觉重心。
4. 让主要关系使用足够的舞台，再处理字号、间距和素材。
5. 最后添加一处必要的网格、点纹理或几何装饰。

渐进自由度固定为：

```text
starter → 组合组件 → 修改局部 DOM/CSS → 完全自定义页面
```

不要为了当前页修改其他页面。只有多页都需要的稳定能力才进入 runtime；单页表达留在自己的 `.s-<id>` 中。

## 关系与构图

| 内容关系 | 优先构图 | 避免 |
| --- | --- | --- |
| 一个判断最重要 | statement、title-media、单一证据画布 | 为了填满增加三张小卡 |
| 两者差异或取舍 | comparison、开放对照轴 | 两边继续嵌套多层面板 |
| 2–3 个连续动作 | sequence、宽松步骤 | 每一步都写成小文档 |
| 4 个阶段总览 | process-rail、timeline | 每列继续添加护栏、指标和引用 |
| 多路输入汇聚 | converge、关系图 | 将因果关系改写成卡片列表 |
| 一主多辅 | feature-grid | 等权卡片墙 |
| 截图或材料支撑判断 | evidence、annotated-showcase、browser-showcase | 使用装饰图替代真实证据 |

重复单元的承载量随数量下降：

- 2 个并列单元：每个可以包含标题、一段解释和一个必要证据。
- 3 个并列单元：每个保留标题和一段解释；只有一个重点单元可以增加证据。
- 4 个及以上等宽单元：每个只保留编号或时间、标题和一句短解释。
- 5–8 个步骤：只有标题级信息时可以使用两行路线；需要逐步解释时拆成“总览页 + 重点页”。

第二层信息只有三个去处：合并为材料已经支持的共享说明；只展开一个当前重点；拆到下一页。共享说明不能自动生成材料中不存在的总结或行动建议。

## 舞台和纵向占满

清爽不等于将内容缩在页面上方。标题之后的主要关系通常占安全区约 55%–70% 高度，视觉重心接近页面中部。

纵向页面优先使用：

```html
<div class="frame oil-stack">
  <header>…</header>
  <main class="oil-main-fill">…</main>
</div>
```

```css
.s-page .frame {
  position: absolute;
  inset: 0;
}
```

`.oil-main-fill` 提供 `flex:1; min-height:0`。不要用一组固定 `top` 坐标将卡片钉在上方。如果主要内容在页面约 60% 高度之前结束、页脚却贴在最底部，先重新分配高度、放大主要关系或改用聚焦构图。

左右分栏中，文字明显短于图片或主视觉时默认垂直居中：

```html
<div class="oil-copy-center">…</div>
```

只有时间线、长清单或明确从上向下阅读的内容才顶端对齐。

## 字号与文字节奏

1920×1080 舞台按照投影内容处理：

- `h1`：阻塞下限 48px；常规页面标题 64–96px。
- `h2`：阻塞下限 32px；`h3` 至 `h6`：阻塞下限 28px。
- 普通说明正文：阻塞下限 24px；默认 `var(--oil-text-body)`，即 28px。
- 图注、来源、表头、代码和短标签：阻塞下限 20px。
- 只有元素自身声明 `data-microcopy="index"` 或 `data-microcopy="meta"` 的短编号、辅助元数据可以低至 18px。
- 多行中文主标题使用 `var(--oil-leading-display)` 和 `var(--oil-tracking-display)`，默认约 1.14 行高、-0.02em 字距。
- 普通正文使用 `var(--oil-leading-body)`，默认约 1.5 行高。
- 可见文字与可确定纯色背景的对比度至少为 2.5:1。

内容放不下时，先删除冗余、拆页或改变构图，不能缩小观众文字。页面空白明显时，先放大主要文字或视觉，再考虑装饰。

优先使用以下 token：

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
var(--oil-leading-display)
var(--oil-leading-body)
var(--oil-tracking-display)
```

## 布局和表面组件

### 布局

- `.oil-stack`：纵向 flex；局部设置 `--stack-gap`。
- `.oil-stack[data-direction="row"]`：横向排列。
- `.oil-stack[data-align="center|end"]`：交叉轴对齐。
- `.oil-main-fill`：使用剩余纵向空间。
- `.oil-copy-center`：短文案列垂直居中。
- `.oil-grid`：12 列语义网格；通过 `--grid-columns` 和 `--grid-gap` 调整。

`data-layout` 只用于几何检查，不选择页面模板，也不限制子元素。

### 表面

`.oil-panel` 和 `.oil-surface` 默认是无边框静面。优先使用面积、位置、柔和底色和留白建立层级：

```html
<div class="oil-grid feature-grid" data-layout>
  <article class="oil-panel" data-tone="accent">…</article>
  <article class="oil-panel" data-stroke="hairline">…</article>
</div>
```

- `data-tone="soft|accent|ink"`：选择表面色调。
- `data-stroke="hairline|strong"`：只在确实需要边界时使用。
- 默认一页最多一个主深色面。

大卡片中的文字明显少于可用高度时，默认在卡片内部垂直居中；不要扩大卡片后仍将全部文字挤在左上角。时间线、表格和长清单除外。

浅色比较或特征卡之后不追加通栏深色结论条。将材料已经支持的结论放进标题、重点单元，或放进 hairline 分隔后的共享说明。不要将轻盈页面截断成“卡片 + 页脚通知”。

## 背景与局部装饰

### 页面背景

`.oil-slide` 默认使用 `grid-fade`：暖白画布和局部淡网格。网格在缩略图中应当可辨认，但不能与正文竞争。

- `data-bg="grid-fade"`：默认局部网格。
- `data-bg="grid-wide"`：系统图和关系图的宽网格。
- `data-bg="grid-full"`：明确需要统一坐标场时使用，不是默认值。
- `data-bg="soft-spotlight|block-field"`：有意选择的柔和背景。
- `data-bg="media-owned"`：媒体接管一侧或整页。
- `data-bg="plain"`：明确需要纯净底色。

普通内容页不能因为留白较多就关闭网格。

### 卡片点纹理和几何

只给一个主要表面添加一种局部装饰：

```html
<article
  class="oil-surface"
  data-decor="dots"
  data-decor-pos="bottom-right">
  …
</article>
```

`data-decor-pos` 支持 `top-left`、`top-right`、`bottom-left`、`bottom-right`。

几何 motif 使用：

```html
<article class="oil-surface" data-motif="ring" data-motif-pos="top-right">
  <span class="oil-shape-window" aria-hidden="true"></span>
  …
</article>
```

`data-motif` 支持 `ring`、`triangle`、`slash`。同一表面不能同时使用 dots 和 motif，也不要装饰所有表面。装饰伪元素不能承载文字或含义。

## 流程、关系和数据

### 流程

`.oil-timeline` 或 sequence starter 适合 2–4 个连续动作。`process-rail` 是四阶段总览：每个节点只承担编号或时间、标题和一句说明；共享规则放在轨道之外，只出现一次。

路线不是卡片墙。位置、连线、留白和一处强调已经可以表达顺序。

### 关系

`.oil-relationship`、`.oil-relationship-node` 和 `.oil-relationship-link` 只提供几何。真实标签和解释保留为 DOM 文字；连接线可以使用装饰性内联 SVG。不要将页面内容藏进 JSON schema 或 canvas。

### 数据

- `.oil-metric`、`.oil-metric-value`、`.oil-metric-label`：单个指标。
- `.oil-chart`、`.oil-chart-bar`：简单柱状关系。
- `.oil-table`：紧凑表格。
- `.oil-quote`：引文和可选 `<cite>`。
- `.oil-code`：代码面板。
- `.oil-highlight`：短行内标记。

图表必须使用真实数值和可见来源。需要坐标轴、刻度和复杂标注时，直接使用 HTML/CSS 或内联 SVG。

## 媒体与证据

`.oil-media` 是标准媒体框。图片和视频默认 `object-fit:cover`；文档、图表和产品截图需要完整显示时使用 `data-media-fit="contain"`。

`.oil-browser` 提供浏览器外壳。只有浏览器 chrome 能够帮助观众理解证据时才使用。

项目素材使用 `../assets/...` 相对路径，并添加准确的 `alt`。截图、数据、界面和文档保持保真。

媒体主动接管一侧时使用：

```html
<div class="oil-bleed oil-media" data-side="right">…</div>
```

`.oil-bleed` 支持 `data-side="left|right"` 和可选的 `data-cut="diagonal"`。`.oil-media` 支持自然、弱化、黑白处理，以及 `left-fade|right-fade|bottom-ink|accent-wash` overlay 和 `soft-edges|fade-bottom` mask。

`data-bleed="left|right|top|bottom|full"` 只用于有意触达页面边缘的内容。跨越安全区的纯装饰标记 `data-decoration`。

图标使用项目 `assets/icons/` 中的本地 SVG，不使用 emoji、远程图标字体或远程 SVG。

## 页面局部 CSS

页面 marker 内的每个 selector 都以自己的 slide scope 开始：

```css
.s-problem .feature-grid { --grid-columns: 12; align-items: stretch; }
.s-problem .feature-main { grid-column: span 7; }
.s-problem .feature-proof { grid-column: span 5; }
```

组件类负责共享行为，页面类负责当前构图。现有组件无法表达时可以直接改变 DOM 和局部 CSS。

## 页面完成检查

- 主要判断一眼可见，页面关系不是由多层容器代替。
- 标题后的主要关系使用足够纵向空间，没有上挤下空。
- 左右分栏中的短文案默认垂直居中。
- 标题和正文使用统一 token，没有极紧行高和字距。
- 页面保持默认局部网格，除非媒体或纯净底色明确接管。
- 点纹理或几何装饰只出现在一个主要表面。
- 没有等权卡片墙、重复深色面、厚重描边或深色结论页脚。
- 真实媒体、数据、引文和来源保持保真。
- 没有通过缩小字号解决内容过载。
