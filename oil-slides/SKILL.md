---
name: oil-slides
description: 使用 oil-ppt 创建和修改白底细网格、层级清楚、强调克制的 16:9 HTML 幻灯片。新建演示先询问用户希望通过对话共同梳理大纲，还是由 Codex 直接生成第一版；先产出并确认 Markdown 大纲，再制作正式预览，用户确认后才构建最终演示。
---

# oil-ppt

先确认内容，再设计页面。模型负责判断内容关系、素材角色和表达重点；几何、背景、容器纹理、适配、审计、确认状态与构建由程序负责。

`oil-ppt` 是产品与仓库名称。为兼容已有安装，Skill 调用名、CLI、状态文件、CSS 类和 schema 命名空间继续使用 `oil-slides`；面向大家的标题、说明和运行提示统一使用 `oil-ppt`，不要混用两者。

## 统一入口

CLI 位于本 `SKILL.md` 的相对路径：

```text
scripts/oil-slides
```

执行前解析成绝对路径，不依赖当前工作目录，也不直接调用内部脚本。

项目建立后，任何阶段都先运行：

```text
scripts/oil-slides status <项目> --json
```

按返回的唯一 `next.command` 继续；不要凭记忆拼接旧流程。

## 新建流程

### 1. 先选择大纲方式

开始时询问：

> 你希望我们先通过对话一起把大纲梳理出来，还是由我根据现有材料直接生成第一版大纲？

- 对话梳理：补齐目标、受众、场景、时长、已有材料和核心记忆点。
- 直接生成：只使用用户明确提供的材料，不扫描同目录、桌面或旧文件。
- 用户已明确选择或提供可用大纲时，不重复询问。

然后初始化唯一项目根目录：

```text
scripts/oil-slides init <项目>
```

### 2. 完成并确认 `outline.md`

只修改项目根目录的 `outline.md`。每页写清标题、核心判断、支撑内容，以及素材展示什么、回答什么问题。鼠标点击翻页默认关闭；只有用户明确同意才开启。

此阶段不选择组件、不写 `outline.json`、不制作预览。用户明确确认 Markdown 大纲后记录确认：

```text
scripts/oil-slides confirm <项目> --stage outline --user-confirmed
```

### 3. 生成视觉计划

先读取一个合法示例和紧凑组件目录；只在需要判断某个组件时查询该组件，不加载全部模板细节：

```text
scripts/oil-slides contract --example
scripts/oil-slides contract --list
scripts/oil-slides contract --id <组件>
```

在项目根目录写入 `outline.json`，再交给程序验证：

```text
scripts/oil-slides plan <项目>
```

`plan` 会按内容关系推荐普通或 compound 组件；图标容器、真实数据图表、局部几何和密集组件字号由模板与 runtime 生成。

一页只表达一个主要判断。内容少时选择聚焦组件，不用小字、空卡片或装饰填满空间；有真实证据时优先使用截图、材料或照片。标题中确有需要记住的短语时最多设置一处 `highlight`。

### 4. 准备素材并生成正式预览

有媒体页时先运行 `media plan`，按其槽位比例和处理命令准备项目内最终素材；真实截图需要保真时使用程序化适配，不让图片模型重画：

```text
scripts/oil-slides media plan <项目> --write
```

只有需要获取外部素材时读取 `references/media.md`；生成概念插画时读取 `references/illustration.md`；用代码绘制 UI、流程、关系或图表时读取 `references/programmatic-visuals.md`。

正式预览使用最终文案和素材：

```text
scripts/oil-slides preview <项目>
```

生成后停止，等待用户确认。根据反馈修改 `outline.md`、`outline.json` 或素材后，重新按 `status` 返回的命令完成确认和预览。

### 5. 确认并构建

用户明确确认正式预览后：

```text
scripts/oil-slides confirm <项目> --stage preview --user-confirmed
scripts/oil-slides build <项目>
```

`build` 会自行完成内部脚手架、逐页 HTML、素材内联和浏览器验证；不要手工调用内部阶段。

## 修改与交付

修改现有项目时只读取用户明确指定的项目，并先运行 `status --json`。内容结构变化先同步 `outline.md`；所有输入变化都服从状态机重新确认。

最终入口固定为项目根目录的 `演示文稿.html`。故障时读取 `references/troubleshooting.md`。

## Skill 维护

修改 oil-ppt 的程序、组件或设计系统时，先读取 `references/evolution.md`；制作或修改普通演示时不要读取。
