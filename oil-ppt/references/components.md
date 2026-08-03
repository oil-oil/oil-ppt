# 页面设计与组件规范

本文件是 oil-ppt 的唯一设计规范。进入 `author_slides` 后完整读取一次；制作具体页面时按照当前构图家族选择相关部分。组件提供可靠几何和视觉语言，不规定页面字段或固定模板。

## 目录

1. 设计执行顺序
2. 视觉层级
3. 版式节奏
4. 构图家族
5. 字号与文字节奏
6. 布局和表面组件
7. 背景与局部装饰
8. 流程、关系和数据
9. 媒体与证据
10. 页面局部 CSS
11. 页面完成检查

## 设计执行顺序

每页按照以下顺序完成：

1. 写出观众需要看懂的唯一判断。
2. 判断内容关系，确定构图家族：聚焦、对照、顺序、主次、关系、证据或数据。
3. 选择最接近的 starter，先定视觉重心的位置和面积，再填内容。
4. 排纵向三段节奏：标题区、主关系区、可选收尾区。
5. 处理字号、间距和素材。
6. 最后添加一处网格、点纹理或几何装饰，位置跟随构图的空区。

渐进自由度固定为：

```text
starter → 组合组件 → 修改局部 DOM/CSS → 完全自定义页面
```

不要为了当前页修改其他页面。只有多页都需要的稳定能力才进入 runtime；单页表达留在自己的 `.s-<id>` 中。

## 视觉层级

每页只有三级，从强到弱：

- **判断层**：标题或页面唯一结论。最大字号，一页一处。
- **关系层**：主构图本身——对照轴、轨道、媒体、图表或主表面。占页面最大面积。
- **支撑层**：注释、来源、图注和辅助说明。小一级字号，`--ink-2` 或 `--ink-3`。

层级规则：

- 一页一个视觉重心。主单元与次单元的面积差至少约 1.6:1；分不出主次的等权排列就是卡片墙。
- 层级靠字号阶梯、面积、色调和留白建立，不靠多层描边、嵌套面板或加粗堆叠。
- 默认一页最多一个主深色面、一个 accent 色调面。
- 第二层信息只有三个去处：合并为材料已经支持的共享说明；只展开一个当前重点；拆到下一页。共享说明不能自动生成材料中不存在的总结或行动建议。

重复单元的承载量随数量下降：

- 2 个并列单元：每个可以包含标题、一段解释和一个必要证据。
- 3 个并列单元：每个保留标题和一段解释；只有一个重点单元可以增加证据。
- 4 个及以上等宽单元：每个只保留编号或时间、标题和一句短解释。
- 5–8 个步骤：只有标题级信息时可以使用两行路线；需要逐步解释时拆成“总览页 + 重点页”。

## 版式节奏

### 纵向三段

标题之后的主要关系占安全区约 55%–70% 高度，视觉重心接近页面中部：

- **标题区**：`.oil-head`（label + 标题 + 可选引导段），紧凑，约占安全区 12%–20%。
- **主关系区**：`.oil-main-fill`，内容在区域内默认垂直居中；只有时间线、长清单或明确从上向下阅读的内容顶端对齐。
- **收尾区**（可选）：hairline 分隔后的一到两行共享说明，只出现一次。

```html
<div class="frame oil-stack">
  <header class="oil-head">…</header>
  <main class="oil-main-fill">…</main>
</div>
```

```css
.s-page .frame {
  position: absolute;
  inset: 0;
}
```

`.oil-main-fill` 提供 `flex:1; min-height:0`。不要用一组固定 `top` 坐标把内容钉在页面上方。如果主要内容在页面约 60% 高度之前结束、页脚却贴在最底部，先重新分配高度、放大主要关系或改用聚焦构图——这是“上挤下空”，不是留白。

### 间距阶梯

只使用三档间距，页内保持一致：

```css
var(--oil-gap-sm)  /* 22px，单元内部、标题区内部 */
var(--oil-gap-md)  /* 34px，相关单元之间 */
var(--oil-gap-lg)  /* 56px，标题区与主关系区之间、主辅分栏之间 */
```

### 横向节奏

- 主辅分栏使用约 7:5 或 1.2:0.8 的比例；只有真正的对照才用 1:1。
- 左右分栏中，文字明显短于图片或主视觉时默认用 `.oil-copy-center` 垂直居中。
- 大卡片中的文字明显少于可用高度时，在卡片内部垂直居中；不要扩大卡片后仍将全部文字挤在左上角。时间线、表格和长清单除外。

### 留白规则

- 留白围绕视觉重心聚集，给它呼吸；不要把剩余空间均匀稀释到每一条缝隙——均匀稀释就是无效留白。
- 页面明显空时，先放大主要文字或视觉，再考虑装饰。
- 清爽不等于将内容缩在页面上方。

### 跨页节奏

正常 8–10 页至少使用 4 个构图家族；相邻两页不使用同一家族的同一轮廓。缩略图中两页剪影相同时，改其中一页的家族或重心位置。

## 构图家族

先判断内容关系，再选家族。每个家族的 starter 已经实现正确的重心和容量，优先从它们开始。

| 家族 | 内容关系 | starters | 重心与容量 |
| --- | --- | --- | --- |
| 聚焦 | 一个判断最重要 | statement、quote-focus、metric-spotlight、step-focus、section、ending | 单点居中；一句主张加一段支撑，不为了填满增加三张小卡 |
| 对照 | 两者差异或取舍 | comparison、bleed-split | 中轴两侧，只有一侧使用色调面；每侧标题加一段或三条内短列表，不继续嵌套多层面板 |
| 顺序 | 连续动作或循环 | sequence（2–4 步）、process-rail（4 阶段总览）、cycle（循环） | 轨道本身就是构图；节点只承担编号或时间、标题和一句说明，每一步不写成小文档 |
| 主次 | 一主多辅 | feature-grid、editorial-feature、problem-canvas | 主单元占约一半面积；辅助项用 hairline 列表，不用等权小卡 |
| 关系 | 多路输入汇聚或对象关系 | converge、relationship-map、hierarchy-tree | 中心或终点是唯一结论；连线表达关系，不把因果改写成卡片列表 |
| 证据 | 截图或材料支撑判断 | title-media、evidence、annotated-showcase、browser-showcase、media-collage | 媒体占至少一半面积；注释不超过三条，不用装饰图替代真实证据 |
| 数据 | 指标与趋势 | data | 一个主指标或一张主图；指标不超过四个，图注一行 |

## 字号与文字节奏

1920×1080 舞台按照投影内容处理：

- `h1`：阻塞下限 48px；常规页面标题 64–80px；statement、section、ending 等聚焦页主标题 88–108px。
- `h2`：阻塞下限 32px；单元标题常规 34–48px。`h3` 至 `h6`：阻塞下限 28px。
- 普通说明正文：阻塞下限 24px；默认 `var(--oil-text-body)`，即 28px。
- 图注、来源、表头、代码和短标签：阻塞下限 20px。
- 只有元素自身声明 `data-microcopy="index"` 或 `data-microcopy="meta"` 的短编号、辅助元数据可以低至 18px。
- 多行中文主标题使用 `var(--oil-leading-display)` 和 `var(--oil-tracking-display)`，默认约 1.14 行高、-0.02em 字距。
- 普通正文使用 `var(--oil-leading-body)`，默认约 1.5 行高。
- 可见文字与可确定纯色背景的对比度至少为 2.5:1。

文字密度上限：

- 单段说明不超过 3 行；并列单元的解释不超过 2 行。
- 整页可见正文（不含标题、编号和标签）约不超过 220 字；超过先删冗余或拆页。
- 内容放不下时，先删除冗余、拆页或改变构图，不能缩小观众文字。

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
var(--oil-gap-sm)
var(--oil-gap-md)
var(--oil-gap-lg)
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

### 标题区

`.oil-head` 是标准标题区：label、标题和可选引导段之间的节奏已经固定，页面只需要决定标题字号：

```html
<header class="oil-head">
  <span class="oil-label">family</span>
  <h1 data-fit data-min-size="52">标题</h1>
  <p class="oil-lede">可选的一到两行引导。</p>
</header>
```

- `.oil-lede`：标题下引导段，最多两行。
- `.oil-rule`：聚焦页使用的强调短尺，跟在主张之后，一页最多一处。

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

一组辅助说明默认不使用一排小卡片，使用 hairline 注释列表：

```html
<div class="oil-notes">
  <div class="oil-note"><strong>观察</strong><p>一句说明。</p></div>
  <div class="oil-note"><strong>含义</strong><p>一句说明。</p></div>
</div>
```

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

普通内容页不能因为留白较多就关闭网格。网格是这套视觉语言的一部分，关掉它的页面在整套演示中会显得突兀。

### 卡片点纹理和几何

只给一个主要表面添加一种局部装饰，位置跟随构图的空区：内容重心在左下时装饰在右上，重心在右上时装饰在左下。不要默认固定在右上角，也不要装饰所有表面。

```html
<article
  class="oil-surface"
  data-decor="dots"
  data-decor-pos="bottom-right">
  …
</article>
```

`data-decor-pos` 支持 `top-left`、`top-right`、`bottom-left`、`bottom-right`，使用时总是明确写出。

几何 motif 使用：

```html
<article class="oil-surface" data-motif="ring" data-motif-pos="top-right">
  <span class="oil-shape-window" aria-hidden="true"></span>
  …
</article>
```

`data-motif` 支持 `ring`、`triangle`、`slash`。同一表面不能同时使用 dots 和 motif。装饰伪元素不能承载文字或含义。

## 流程、关系和数据

### 流程

`.oil-timeline` 或 sequence starter 适合 2–4 个连续动作。`process-rail` 是四阶段总览：每个节点只承担编号或时间、标题和一句说明；共享规则放在轨道之外，只出现一次。

路线不是卡片墙。位置、连线、留白和一处强调已经可以表达顺序。

### 关系

`.oil-relationship`、`.oil-relationship-node` 和 `.oil-relationship-link` 只提供几何。真实标签和解释保留为 DOM 文字；连接线可以使用装饰性内联 SVG。不要将页面内容藏进 JSON schema 或 canvas。

### 数据

- `.oil-metric`、`.oil-metric-value`、`.oil-metric-label`：单个指标；指标本身不需要面板包裹，直接排在版面上更轻。
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

媒体与文字的平衡：

- 媒体是证据主角时占至少一半版面宽度，或直接接管一侧；不要把证据缩成文字墙旁边的小缩略图。
- 媒体不足版面三分之一时，换成聚焦或主次构图，让文字成为主角，媒体只作点缀。
- 文字一侧默认垂直居中，长度不超过媒体高度的阅读容量。

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

- 主要判断一眼可见，视觉重心只有一个，页面关系不是由多层容器代替。
- 主单元与次单元面积差明显，没有等权卡片墙。
- 标题后的主关系区使用 55%–70% 纵向空间并垂直居中，没有上挤下空。
- 留白围绕重心聚集，不是均匀稀释的无效留白。
- 左右分栏中的短文案默认垂直居中。
- 标题区使用 `.oil-head`，标题和正文使用统一 token，没有极紧行高和字距。
- 正文没有超过密度上限，没有通过缩小字号解决内容过载。
- 媒体是主角时占至少一半版面，没有小缩略图配文字墙。
- 页面保持默认局部网格，除非媒体或纯净底色明确接管。
- 点纹理或几何装饰只出现在一个主要表面，位置明确写出并跟随构图空区。
- 浅色比较或特征区之后没有通栏深色结论条；没有重复深色面或厚重描边。
- 真实媒体、数据、引文和来源保持保真。
