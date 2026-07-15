---
name: oil-ppt
description: 使用 oil-ppt 创建和修改白底细网格、层级清楚、强调克制的 16:9 HTML 幻灯片。新建演示先询问用户希望通过对话共同梳理大纲，还是由 Codex 直接生成第一版；先产出并确认 Markdown 大纲，再制作正式预览，用户确认后才构建最终演示。
---

# oil-ppt

先确认内容，再设计页面。模型负责判断内容关系、素材角色和表达重点；几何、背景、容器纹理、适配、审计、确认状态与构建由程序负责。

`oil-ppt` 是 Skill、产品与仓库的统一名称。Skill 调用名和公开 CLI 都使用 `oil-ppt`。

## 统一入口

CLI 位于本 `SKILL.md` 的相对路径：

```text
scripts/oil-ppt
```

执行前解析成绝对路径，不依赖当前工作目录，也不直接调用内部脚本。

处理现有项目、批量验收或最终交付时，默认运行：

```text
scripts/oil-ppt batch <项目或父目录> [更多项目或父目录]
```

`batch` 自动发现项目，集中完成可确定的 `plan`、无界面 `preview` 与已确认项目的 `build`，一次返回所有素材、审计和浏览器渲染阻塞；不会打开编辑器，也不会替用户确认。用户明确确认全部待确认预览后，执行返回的 `next.command`，即追加 `--user-confirmed-preview` 的同一批处理命令。

新建单个演示、需要进入可视化文字编辑，或批处理返回单项目阻塞时，再运行：

```text
scripts/oil-ppt status <项目> --json
```

只按 `next.action` 前进：

- `run_command`：直接执行 `next.command`；它已是可从任意目录运行的绝对命令。
- `edit_outline` / `write_visual_plan`：只编辑 `next.path`，完成后重新运行 `status`。
- `ask_user_to_confirm_*`：展示 `next.artifact` 并停止；只有用户明确确认后才执行 `next.command_on_confirm`。
- `start_editor`：启动 `next.command` 后立即把页面交给用户，不等待这个本地服务退出；用户点击“完成编辑”后重新运行 `status`。
- `wait_for_editor` / `complete` / `choose_project_directory`：停止，不猜测下一命令。

不要替用户确认，也不要凭记忆拼接旧流程；多个项目不得逐套手工重复这些命令。

## 新建流程

### 1. 先选择大纲方式

开始时询问：

> 你希望我们先通过对话一起把大纲梳理出来，还是由我根据现有材料直接生成第一版大纲？

- 对话梳理：补齐目标、受众、场景、时长、已有材料和核心记忆点。
- 直接生成：事实只来自用户明确提供的材料；仍要标出需要搜索、生成或程序化制作的视觉，不扫描同目录、桌面或旧文件。
- 用户已明确选择或提供可用大纲时，不重复询问。

然后初始化唯一项目根目录：

```text
scripts/oil-ppt init <项目>
```

### 2. 完成并确认 `outline.md`

只修改项目根目录的 `outline.md`。每页写清标题、核心判断、支撑内容，以及素材展示什么、回答什么问题、通过已有素材 / 搜索 / 生成 / 程序化中的哪种方式获得。没有现成文件不等于不需要视觉；只有页面本身适合纯文字聚焦、并且整套仍满足媒体节奏时，才选择“确认无需”。不得写含义不明的“无”。鼠标点击翻页默认关闭；只有用户明确同意才开启。

此阶段不选择组件、不写 `outline.json`、不制作预览。用户明确确认 Markdown 大纲后记录确认：

```text
scripts/oil-ppt confirm <项目> --stage outline --user-confirmed
```

### 3. 生成视觉计划

先读取一个合法示例和紧凑组件目录；只在需要判断某个组件时查询该组件，不加载全部模板细节：

```text
scripts/oil-ppt contract --example
scripts/oil-ppt contract --list
scripts/oil-ppt contract --family <family>
scripts/oil-ppt contract --id <组件>
```

先按内容关系选 family，再查询其中一个组件。复杂组件先只填写 `minimum`；`optional` 缺省时模板必须仍然完整，不为追求装饰而补造字段。

在项目根目录写入 `outline.json`，再交给程序验证：

```text
scripts/oil-ppt plan <项目>
```

`plan` 会按内容关系推荐普通或 compound 组件，并拒绝组件不会显示的字段、不完整的可选字段组，以及不足的媒体与背景节奏；图标容器、真实数据图表、局部几何、空区域收合和密集组件字号由模板与 runtime 生成。

媒体策略默认是 `required`。只有用户明确要求整套演示不使用图片时才选择 `text-only`，并在 `plan` 命令追加 `--user-confirmed-text-only`；不得替用户确认。

一页只表达一个主要判断。内容少时选择聚焦组件，不用小字、空卡片或装饰填满空间；有真实证据时优先使用截图、材料或照片。标题中确有需要记住的短语时最多设置一处 `highlight`。

### 4. 准备素材并生成正式预览

`preview` 会自动生成 `media-plan.json` 并执行媒体门禁。需要提前准备素材时运行下面的命令，按其槽位比例和处理命令准备项目内最终素材；真实截图需要保真时使用程序化适配，不让图片模型重画：

```text
scripts/oil-ppt media plan <项目> --write
```

只有需要获取外部素材时读取 `references/media.md`；生成概念插画时读取 `references/illustration.md`；用代码绘制 UI、流程、关系或图表时读取 `references/programmatic-visuals.md`。

正式预览使用最终文案和素材，并默认打开可编辑预览：

```text
scripts/oil-ppt preview <项目>
```

用户点击任意页面即可打开大图并直接校对文字。编辑器自动保存独立草稿；用户点击“完成编辑”后，程序写回结构化内容并重新生成正式预览。不要直接修改预览或最终 HTML。

生成后停止，等待用户确认。根据反馈修改 `outline.md`、`outline.json`、素材或直接校对预览文字后，重新按 `status` 返回的命令完成确认和预览。

### 5. 确认并构建

用户明确确认正式预览后：

```text
scripts/oil-ppt confirm <项目> --stage preview --user-confirmed
scripts/oil-ppt build <项目>
```

`build` 会自行完成内部脚手架、逐页 HTML、素材内联和浏览器验证；不要手工调用内部阶段。

## 修改与交付

修改现有项目时只读取用户明确指定的项目或父目录，并先运行 `batch`；只有返回单项目阻塞、需要编辑文字或继续新建交互时才查看该项目的 `status --json`。内容结构变化先同步 `outline.md`；所有输入变化都服从状态机重新确认。

最终入口固定为项目根目录的 `演示文稿.html`。故障时读取 `references/troubleshooting.md`。

## Skill 维护

修改 oil-ppt 的程序、组件或设计系统时，先读取 `references/evolution.md`；制作或修改普通演示时不要读取。
