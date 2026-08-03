---
name: oil-ppt
description: 使用 oil-ppt 创建、修改、续做、检查和构建 16:9 HTML 演示文稿，并按需导出混合可编辑 PPTX。默认搭配 oil-tone 处理面向观众的文案；每张页面都是独立 HTML 源文件。适用于从主题、文档或材料新建演示，逐页精修现有项目，批量验收项目，以及交付最终离线 HTML。
---

# oil-ppt

oil-ppt 只维护一条创作路径：弱模型从 starter 和组件开始，强模型可以继续修改单页 DOM 与局部 CSS。每次只创作或修复一张真实页面；程序负责状态、检查和交付，不覆盖已经写好的页面。

## 开始前

将下列 CLI 解析为相对本 `SKILL.md` 的绝对路径，后续命令都使用同一个路径：

```text
scripts/oil-ppt
```

创建或改写标题、正文、图注和结尾时，同时使用 `oil-tone`。`oil-tone` 是事实边界、叙述身份、用词、句子和结尾的唯一文案规范；oil-ppt 只负责演示叙事、跨页拆合、页面容量、素材角色和版面表达。拆页或压缩只能删除冗余，不能删除材料中的事实、原因、影响或处理步骤。

页面事实来源固定为：

- `slides/<id>.html`：单页文案、DOM、局部 CSS 和素材。
- `deck.json`：页面顺序和全局主题。
- `outline.md`：创作参考，不是页面合同。

不要直接修改 `预览.html` 或 `演示文稿.html`，不要替用户确认。

## 最短执行路径

### 新建演示

1. 用户没有给出材料或方向时询问：“先一起梳理创作大纲，还是根据现有材料直接整理第一版参考？”已经有答案时不重复询问。
2. 初始化并立即读取状态：

```text
scripts/oil-ppt init <项目>
scripts/oil-ppt status <项目> --json
```

3. 只处理返回的顶层 `next`。完成该动作后执行其中的 `rerun`、`command_on_confirm`、`command_when_ready` 或 `command`，再读取新的状态。

### 续做或修改现有演示

先检查用户明确指定的项目或父目录：

```text
scripts/oil-ppt batch <项目或父目录> [更多项目或父目录]
```

然后对要处理的单个项目运行：

```text
scripts/oil-ppt status <项目> --json
```

用户指定某页时使用：

```text
scripts/oil-ppt status <项目> --json --intent edit --slide <页码或ID>
```

只编辑返回的 `next.path`，完成后执行 `next.rerun`。修改可见文案时使用 `oil-tone`；只修布局、样式或媒体时不需要改写文案。

## 只执行 next

`next.action` 是以下封闭集合：

<!-- next-action-contract:start -->
- `ask_user_to_confirm_outline`：展示 `next.artifact` 并停止。用户确认后原样执行 `next.command_on_confirm`；用户要求修改时运行 `status <项目> --json --intent edit`，只编辑返回的 `next.path`，再执行 `next.rerun`。
- `ask_user_to_confirm_preview`：展示 `next.artifact` 并停止。用户确认后原样执行 `next.command_on_confirm`；用户提出页面反馈时使用 `status <项目> --json --intent edit --slide <页码或ID>`。
- `author_slides`：依据 `next.brief` 逐页创作或调整。每次只读写一张 `slides/*.html`；完成一张后重新运行 `status`。
- `complete`：停止，演示已经完成。
- `edit_outline`：只编辑 `next.path`，完成后执行 `next.rerun`。
- `edit_slide`：只编辑 `next.path`，依据 `next.issues` 修复真实 HTML，完成后执行 `next.rerun`。
- `fix_media`：只处理 `next.path`、`next.issues` 和项目内相关素材，完成后执行 `next.rerun`。
- `run_command`：原样执行 `next.command`。
<!-- next-action-contract:end -->

不要凭记忆拼接状态机内部命令，不跳过确认，不同时处理两个 `next`。

## author_slides 的逐页循环

第一次进入 `author_slides` 时完整读取 `references/components.md`。它是视觉层级、版式节奏、构图家族、网格、字号、纵向占满、分栏、表面纹理和媒体组件的唯一设计规范；主 Skill 不重复这些数值和 API。

查看 24 个真实独立 starter 的紧凑目录，只在当前页面需要时读取一个具体 starter：

```text
scripts/oil-ppt starter list --json
scripts/oil-ppt starter show <名称>
scripts/oil-ppt starter catalog [--output <离线HTML路径>]
```

先用一句话确定页面关系，再选择 starter：聚焦、比较、顺序、汇聚、关系、证据或数据。优先按照 `next.slide_add_usage` 创建页面；完整语法是：

```text
scripts/oil-ppt slide add <项目> <页面ID> --title "<标题>" [--starter <名称>] [--after <页面ID>]
```

`页面ID` 只使用小写字母、数字和连字符。命令会返回真实页面路径；只编辑该文件。需要调整页面时使用：

```text
scripts/oil-ppt slide duplicate <项目> <原页面ID> <新页面ID> [--title "<标题>"]
scripts/oil-ppt slide move <项目> <页面ID> --to <位置>
scripts/oil-ppt slide remove <项目> <页面ID>
```

完成一张页面必须同时满足：

- 已替换 starter 的全部示例文案、数值、来源和占位视觉。
- 页面只有一个主要判断，构图服务该判断，而不是先生成卡片再填内容。
- 真实截图、数据、引文和界面保持保真；概念视觉不能伪装成事实证据。
- 页面不依赖自定义 JavaScript、远程资源、绝对本地路径或跨页全局 CSS。
- 运行 `status` 后没有该页的阻塞问题。

完成当前页后重新运行 `status`。如果仍返回 `author_slides`，继续下一张真实页面或调整叙事；不要一次生成全部页面再统一修复。

## 进入正式预览的条件

只有同时满足以下条件，才执行 `next.command_when_ready`：

1. 核心判断、必要原因、影响、过程和证据已经在整套页面中完整覆盖。
2. 所有计划中的页面都已创建或明确删除，没有示例内容、虚构来源或占位视觉。
3. 每页只有一个主要判断，所有阻塞问题已经修复。
4. 正常 8–10 页至少使用 4 类构图，缩略轮廓没有连续重复同一种等权卡片墙。
5. 已逐条处理 `style_advice`：修复不需要的模式；有意保留时记录原因。

正式预览读取真实页面，不重新生成页面。用户确认后继续处理状态机返回的动作，直到 `complete`。

## 质量门禁

以下问题会阻塞预览或构建：HTML 结构损坏、路径越界、远程资源、自定义脚本、跨页 CSS 污染、素材损坏、文字溢出、内容越界、页面滚动、字号低于门槛，以及可确定纯色背景上的文字对比度不足。

只有短编号或辅助元数据的文字元素自身可以使用 `data-microcopy="index"` 或 `data-microcopy="meta"`。可见文字使用真实换行；只有确实讲解转义字符时才使用 `data-literal-escape="true"`。

`style_advice` 是必须判断的非阻塞设计提醒，不自动决定页面修改。详细设计规范以 `references/components.md` 为准。

## 参考资料路由

- 视觉层级、版式节奏、构图家族、网格、字号、组件、表面纹理和媒体框架：`references/components.md`
- 外部素材选择：`references/media.md`
- 概念插画：`references/illustration.md`
- HTML/CSS/SVG 流程、关系、UI 和图表：`references/programmatic-visuals.md`
- 构建或导出故障：`references/troubleshooting.md`
- 修改本 Skill 的程序、组件或设计系统：`references/evolution.md`

只读取当前任务需要的参考资料。

## 主题与交付

全局配色、字体和圆角通过主题命令调整，不逐页复制主题色：

```text
scripts/oil-ppt theme list --json
scripts/oil-ppt theme catalog [--output <离线HTML路径>]
scripts/oil-ppt theme set <项目> --direction <方向> [--palette <名称>] [--typography <名称>] [--shape <名称>]
```

最终 HTML 固定为项目根目录的 `演示文稿.html`。只有用户明确需要 PowerPoint，并且正式预览已经确认后，才运行：

```text
scripts/oil-ppt export-pptx <项目>
```

HTML 是规范成品；PPTX 是混合可编辑交付物。`pptx-editability.json` 必须逐页说明原生文字、原生媒体、栅格背景和不支持结构。
