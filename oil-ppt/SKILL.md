---
name: oil-ppt
description: 使用 oil-ppt 创建、修改、续做、检查和构建 16:9 HTML 演示文稿，并按需导出混合可编辑 PPTX。每张页面都是独立 HTML 源文件；适用于从主题、文档或材料新建演示，逐页精修现有项目，批量验收项目，以及交付最终离线 HTML。
---

# oil-ppt

oil-ppt 的北极星是：低地板，高天花板。能力较弱的模型从成熟 HTML 组件和 starter 开始；能力较强的模型可以直接改变单页 DOM 与局部 CSS。每次只创作或修复一张真实页面，程序负责基础设施、检查和交付，绝不重新生成或覆盖已经写好的页面。

## 唯一工作流

CLI 位于本 `SKILL.md` 的相对路径：

```text
scripts/oil-ppt
```

执行前解析成绝对路径。已有项目或多个项目先运行：

```text
scripts/oil-ppt batch <项目或父目录> [更多项目或父目录]
```

新项目或单个阻塞项目运行：

```text
scripts/oil-ppt status <项目> --json
```

之后只处理返回的顶层 `next`。`next.action` 是以下封闭集合：

<!-- next-action-contract:start -->
- `ask_user_to_confirm_outline`：展示 `next.artifact` 并停止；只有用户明确确认后才执行 `next.command_on_confirm`。大纲只是创作参考，确认不约束最终页面。
- `ask_user_to_confirm_preview`：展示 `next.artifact` 并停止；只有用户明确确认后才执行 `next.command_on_confirm`。
- `author_slides`：根据 `next.brief` 与当前叙事逐页创建或调整页面；每次只读写一张 `slides/*.html`。完成当前整套创作判断后执行 `next.command_when_ready`。
- `complete`：停止，流程已完成。
- `edit_outline`：只编辑 `next.path`，完成后重新运行 `status`。
- `edit_slide`：只编辑 `next.path`，依据 `next.issues` 修复真实 HTML，完成后运行 `next.rerun`。
- `fix_media`：只处理 `next.path` 与 `next.issues` 指向的页面和项目内素材，完成后运行 `next.rerun`。
- `run_command`：原样执行 `next.command`。
<!-- next-action-contract:end -->

不要凭记忆拼接内部命令，不替用户确认，不直接修改 `预览.html` 或 `演示文稿.html`。

打开既有项目时，程序会自动同步 package-owned 的 `runtime/deck.css` 与 `runtime/deck.js`，使项目获得当前运行时与演示 chrome；它不会覆盖 `slides/*.html`、`runtime/theme.css` 或项目 icons。

## 新建演示

开始时询问：

> 你希望我们先通过对话一起梳理创作大纲，还是由我根据现有材料直接整理第一版参考？

用户已经提供可用材料或选择时不重复询问。初始化项目：

```text
scripts/oil-ppt init <项目>
```

`outline.md` 只用于帮助 AI 理解受众、场景、核心判断、可用证据与可能的叙事顺序。制作时允许拆页、合页、删除、改标题和调整顺序；程序不把大纲转换成页面合同，也不要求成品与大纲一致。

用户确认参考方向后，按照 `status` 返回的 `author_slides` 开始逐页创作。先查看紧凑 starter 目录，只在需要时查看一个具体 starter：

```text
scripts/oil-ppt starter list --json
scripts/oil-ppt starter show <名称>
scripts/oil-ppt starter catalog [--output <离线HTML路径>]
```

用 `slide add` 创建一张真实 HTML 页面，再只编辑该文件。starter 是可复制起点，不是模板合同；复制后可以改变 DOM、组合组件、删除区域或完全重写局部 CSS。完成当前页意味着已替换 starter 的全部示例文案、数值、来源与占位视觉，并使构图服务这一页的真实判断；不得只改标题就继续下一页。常规页面优先复用 runtime 的 `oil-*` 组件，现有组件不能表达时直接自定义页面。

复制 starter 前先用一句话确定页面的视觉关系：聚焦、比较、顺序、汇聚、关系、证据或数据。不要先选“几张卡片”，再把内容塞进去。重复单元的承载量随列数下降：2–3 个单元可以各放标题与一段解释；4 个及以上等宽单元只保留编号或时间、标题和一句短解释。不要在每个轨道节点里继续重复护栏框、指标、引用或第二段说明；把第二层信息合成一个共享说明区、只展开一个重点，或拆到下一页。留白要围绕主要关系分布，不能把全部内容压在页面上半部、只在下半部留下无效空白。

需要选择构图、判断单元负载，或组合和调整通用组件时读取 `references/components.md`；只查看当前页面实际需要的部分。

每页只表达一个主要判断。优先使用真实证据、截图、材料、数据、HTML/CSS/SVG 关系图或确实承担信息的概念视觉。标题、正文与素材直接写进该页 HTML；颜色和字体优先使用 runtime token。1920×1080 原始舞台上的普通正文默认使用 28–32px，任何说明正文不得低于 24px；图注、来源、表头和短标签不得低于 20px。所有可见文字与可确定的纯色背景之间至少保持 2.5:1 对比度；浏览器门禁同时检查 HTML 文字颜色和内联 SVG `text` 的 `fill`。内容放不下时先删减、拆页或重组，不能用缩小字号解决；页面空白明显时主动放大核心文字和视觉。只有短编号或辅助元数据的文字元素自身可以使用 `data-microcopy="index"` 或 `data-microcopy="meta"`，不能把它放在容器、标题或解释性句子上。页面不得添加自定义 JavaScript、远程资源、绝对本地路径或污染其他页面的全局 CSS。

完成一张后重新运行 `status`。静态或浏览器问题会通过 `edit_slide` 返回真实文件、selector 与问题；只修该页。可见文字里要用真实换行，不得把 `\n`、`\r` 或 `\t` 当普通文字重复写进页面；确实在讲解转义字符时，在该文字元素上写 `data-literal-escape="true"`。AI 根据整套叙事自行决定何时增删、移动、复制页面以及何时执行 `command_when_ready` 生成正式预览。

正式预览直接读取真实页面文件，不重新生成页面。用户反馈某页时运行：

```text
scripts/oil-ppt status <项目> --json --intent edit --slide <页码或ID>
```

然后只编辑返回的页面。用户确认正式预览后执行状态机返回的构建命令。

## 组件、素材与设计

组件是稳定的 HTML/CSS 设计积木，不规定页面字段。starter 与组件必须保持业务无关，复制后归当前页面所有。全局配色、字体、圆角、密度、舞台、缩放和导航由 `deck.json`、runtime 与设计命令管理；全局设计调整不得重写页面。

查看可用主题值或调整整套主题时运行：

```text
scripts/oil-ppt theme list --json
scripts/oil-ppt theme catalog [--output <离线HTML路径>]
scripts/oil-ppt theme set <项目> --direction <方向> [--palette <名称>] [--typography <名称>] [--shape <名称>]
```

`theme catalog` 从当前真实 registry 输出 5 个方向、5 个配色、3 个字排和 3 个圆角样本；`starter catalog` 输出 24 个真实独立 starter 的可视化入口、构图家族分组及 deck.css 的通用 `oil-*` 示例。两者都是单文件、离线目录，不改变项目或页面源文件。

方向是语义简报与起始 preset，不是页面合同：`fresh-default`、`editorial-story`、`technical-system`、`warm-friendly`、`calm-research` 各自推荐一组配色、字排和圆角。`--direction` 先应用推荐三元组，显式 palette/type/shape 再覆盖；单独改任一 token 时保留当前方向，direction 缺省为 `fresh-default`。修改主题后重新生成正式预览；不要逐页复制主题色。

`starter list` 同时给出简短使用建议与 composition families。starter 只复制一次，是可任意改写的独立 HTML 起点，不是页面 schema 或合同。正常 8–10 页应混用至少 4 类构图：聚焦、证据/媒体、比较/特征、顺序/系统和数据，避免连续重复同一种等权卡片墙。默认视觉是暖白画布、局部淡网格、白色或柔和无边框表面、一处强调色、76–96px 主标题和 28–32px 正文；使用真实本地媒体、局部 dots/ring/geometric craft 与充足留白。不要默认整页满网格、重复等权卡片墙、厚边框/阴影、黑色终端式背景或到处装饰。`status`、`check` 和 `slide list` 可能给出 `style_advice`：它来自真实页面 HTML 的保守构图提醒，不阻塞预览、构建或下一步，但交付前必须逐条判断，只在有意保留该表达时才忽略。执行 preview 前并排检查整套页面的缩略轮廓，避免连续重复同一种等权卡片墙，也不在深色整页中嵌套多层深色容器。

素材只使用用户明确提供或主动选择的文件，不扫描同目录、桌面或旧项目。真实截图、界面、数据和文档保持保真；概念视觉才使用生成图。媒体直接以项目相对路径写入页面 HTML；程序静态检查路径、格式头、尺寸与 `alt`，并在 Chrome/Chromium 可用时检查真实解码、加载和页面边界。AI 对显示比例、裁切位置与证据保真负责。

需要获取外部素材时读取 `references/media.md`；生成概念插画时读取 `references/illustration.md`；用 HTML/CSS/SVG 绘制 UI、流程、关系或图表时读取 `references/programmatic-visuals.md`。

## 修改与交付

修改现有项目只读取用户明确指定的项目或父目录，并先运行 `batch`。大纲不需要与成品同步；实际页面和 `deck.json` 顺序是当前演示的事实来源。

最终入口固定为项目根目录的 `演示文稿.html`。只有用户明确需要 PowerPoint 时，才在项目完成且当前预览确认有效后运行：

```text
scripts/oil-ppt export-pptx <项目>
```

HTML 是规范成品；PPTX 是混合可编辑交付物，`pptx-editability.json` 必须逐页说明原生文字、原生媒体、栅格背景和不支持结构。故障时读取 `references/troubleshooting.md`。

聚合的 `预览.html` 和 `演示文稿.html` 内置演示总览：按 `O` 打开，`Escape` 关闭，点击缩略图跳转。总览临时移动真实页面 DOM，因此不会生成第二套页面、缩略图或 JSON。

## Skill 维护

修改 oil-ppt 的程序、组件或设计系统时，先读取 `references/evolution.md`；制作普通演示时不要读取。
