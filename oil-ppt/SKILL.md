---
name: oil-ppt
description: 使用 oil-ppt 创建和修改白底细网格、层级清楚、强调克制的 16:9 HTML 幻灯片。新建演示先询问用户希望通过对话共同梳理大纲，还是由 Codex 直接生成第一版；先产出并确认 Markdown 大纲，再制作正式预览，用户确认后才构建最终演示。
---

# oil-ppt

先确认内容，再设计页面。模型负责判断内容关系、素材角色和表达重点；几何、背景、容器纹理、适配、审计、确认状态与构建由程序负责。

`oil-ppt` 是 Skill、产品与仓库的统一名称。Skill 调用名和公开 CLI 都使用 `oil-ppt`。

## 唯一工作流

CLI 位于本 `SKILL.md` 的相对路径：

```text
scripts/oil-ppt
```

执行前解析成绝对路径，不依赖当前工作目录，也不直接调用内部脚本。

已有项目或多个项目默认只运行：

```text
scripts/oil-ppt batch <项目或父目录> [更多项目或父目录]
```

`batch` 自动完成所有能确定的步骤，不打开编辑器、不替用户确认。读取每个项目的 `blockers` 与 `next`，然后只处理顶层唯一的 `next`。用户明确确认本轮开始前已经存在的全部待确认预览后，才执行返回的确认命令。

新建单个演示，或 `batch` 指向某个阻塞项目时，运行：

```text
scripts/oil-ppt status <项目> --json
```

之后形成一个循环：执行 `next.command` 或编辑 `next.path`，再重新运行 `status --json`。只解释以下动作，不另外拼接流程：

- `run_command`：直接执行 `next.command`；它已是可从任意目录运行的绝对命令。
- `edit_outline` / `write_visual_plan` / `fix_media`：只处理 `next.path` 和 `next.issues`，完成后重新运行 `status`。
- `ask_user_to_confirm_*`：展示 `next.artifact` 并停止；只有用户明确确认后才执行 `next.command_on_confirm`。
- `start_editor`：启动 `next.command` 后立即把页面交给用户，不等待这个本地服务退出；用户点击“完成编辑”后重新运行 `status`。
- `wait_for_editor` / `complete` / `choose_project_directory`：停止，不猜测下一命令。

需要重新打开已完成演示的文字编辑器时，不重走构建流程：

```text
scripts/oil-ppt status <项目> --json --intent edit
```

不要替用户确认，不凭记忆拼接命令，多个项目不逐套手工重复执行。

## 新建演示

### 1. 先选择大纲方式

开始时询问：

> 你希望我们先通过对话一起把大纲梳理出来，还是由我根据现有材料直接生成第一版大纲？

- 对话梳理：补齐目标、受众、场景、时长、已有材料和核心记忆点。
- 直接生成：事实只来自用户明确提供的材料；仍要标出需要搜索、生成或程序化制作的视觉，不扫描同目录、桌面或旧文件。
- 用户已明确选择或提供可用大纲时，不重复询问。

然后初始化唯一项目根目录，填写程序创建的 `outline.md`：

```text
scripts/oil-ppt init <项目>
```

每页写清标题、核心判断、支撑内容，以及素材展示什么、回答什么问题、通过已有素材 / 搜索 / 生成 / 程序化中的哪种方式获得。没有现成文件不等于不需要视觉；不得写含义不明的“无”。此阶段不选择组件、不写 `outline.json`。填写后回到 `status --json`；展示 `ask_user_to_confirm_outline.artifact`，用户明确确认后才执行其 `command_on_confirm`。

从这一步起只依赖 `status --json`。当它返回 `write_visual_plan` 时，先读取合法示例与紧凑目录，再按内容关系查询至多一个 family；不加载全部模板：

```text
scripts/oil-ppt contract --example
scripts/oil-ppt contract --list
scripts/oil-ppt contract --family <family>
scripts/oil-ppt contract --id <组件>
```

先判断页面表达的是聚焦、顺序、比较、集合、媒体证据、数据或关系，再由 family 选择组件，并用该组件的 `--id` 查询一次最小字段。复杂组件只填写 `minimum`，不为装饰补造字段。数据页只提供真实数据、来源和要表达的关系；图表类型、坐标、标注和适配由程序处理。不同单位或量级的两个指标不要强行放在同一图中；拆页，或在问题确实是相关性时使用关系图。

媒体策略默认是 `required`。只有用户明确要求整套不使用图片时才选择 `text-only`；状态机会返回相应确认动作，不得替用户确认。

一页只表达一个主要判断。内容少时选择聚焦组件，不用小字、空卡片或装饰填满空间；有真实证据时优先使用截图、材料或照片。标题中确有需要记住的短语时最多设置一处 `highlight`。

`status` 返回 `fix_media` 时，一次处理完 `next.issues`；`next.reference_command` 会生成槽位与比例计划。真实截图使用程序化适配，不让图片模型重画。

只有需要获取外部素材时读取 `references/media.md`；生成概念插画时读取 `references/illustration.md`；用代码绘制 UI、流程、关系或图表时读取 `references/programmatic-visuals.md`。

正式预览默认打开可编辑页面。用户点击页面即可校对文字；草稿自动保存，完成后程序写回结构化内容并重新生成预览。不要直接修改预览或最终 HTML。生成后停止等待用户确认；确认后仍只执行状态机返回的命令，`build` 会自行完成脚手架、素材内联和浏览器验证。

## 修改与交付

修改现有项目时只读取用户明确指定的项目或父目录，并先运行 `batch`；只有返回单项目阻塞、需要编辑文字或继续新建交互时才查看该项目的 `status --json`。内容结构变化先同步 `outline.md`；所有输入变化都服从状态机重新确认。

最终入口固定为项目根目录的 `演示文稿.html`。故障时读取 `references/troubleshooting.md`。

## Skill 维护

修改 oil-ppt 的程序、组件或设计系统时，先读取 `references/evolution.md`；制作或修改普通演示时不要读取。
