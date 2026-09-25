---
name: oil-ppt
description: "使用 oil-ppt 创建、修改、续做、检查和构建 16:9 HTML 演示文稿，并按需导出混合可编辑 PPTX。默认搭配 oil-tone 处理面向观众的文案，每页都是独立 HTML。用户要求新建演示、逐页精修、批量验收或交付离线演示时使用。不用于滚动网页、普通文章、单张海报，也不把任意已有 PPTX 当作可无损导入的源工程。"
---

# oil-ppt

把演示做成一组独立的 HTML 页面。先确定每页要展示什么，再做画面；页面少字、主视觉清楚、放映时能看清。使用本 Skill 相对路径下的 `scripts/oil-ppt` 命令。修改观众可见文案时同时使用 `oil-tone`。

## 大纲：只写每页做什么

`outline.md` 是给用户看的逐页清单。每页写标题和一句画面说明；只有确实影响这一页的事实或素材要求，才补一句。不要写受众分析、观看场景、创作理由、叙事建议、核验清单、给模型看的指令，也不要为了显得完整而增加总结页。实际制作时可以调整页数和顺序。

大纲的内容要能直接回答：“第几页讲什么，观众主要看见什么？”例如：

```text
1. 旧版分工：用一张图展示四种角色及原来的模型。
2. 新版分工：四种角色分别负责什么、使用什么模型。
3. 一个任务怎样选角色：画出按任务选择的分支。
```

## 页面：先画面，后文字

- 每页只讲一个判断或关系。先选择截图、图表、流程、对照或概念画面，再决定需要哪些字。具体画法和组件见 `references/components.md`。
- 默认只有短标题和主画面。眉题、副标题、图注、来源、脚注都是可选的：删掉后不会误解的文字就删，不把制作备注和口播安排写进页面，也不把它们换成胶囊小字。
- 看不清时先删重复说明、放大主画面或拆页，不通过缩小字号塞内容，也不能为了短而删掉材料中必要的事实、原因、影响或步骤。保留的文字按 `references/components.md` 的字号规范处理。
- 真实截图、数据、引文保持保真；概念图不要冒充真实界面或实测结果。材料没有的事实不补造。
- 不要先摆一排等权卡片再填字。画面需要表达顺序、比较或因果时，直接用轨道、分栏、连线或主次关系。

## 开始与续做

新建项目：

```text
scripts/oil-ppt init <项目>
scripts/oil-ppt status <项目> --json
```

已有项目先运行 `scripts/oil-ppt status <项目> --json`；用户点名修改某页时加 `--intent edit --slide <页码或ID>`。需要找多个项目时使用 `scripts/oil-ppt batch <项目或父目录> [更多项目或父目录]`。

`status`、`slide check` 和 `batch` 只读取项目；正式预览或通过命令修改页面、主题时，才同步 Skill 自带的 runtime 文件。

按返回的 `next` 做一件事，完成后执行它提供的命令并重新读取状态。大纲写完即可继续制作。不要修改生成的 `预览.html` 或 `演示文稿.html`；页面内容在 `slides/<id>.html`，顺序在 `deck.json`。正式预览由用户确认。

<!-- next-action-contract:start -->
- `edit_outline`：只编辑 `next.path`，写逐页清单，完成后执行 `next.rerun`。
- `author_slides`：依据 `next.brief` 一次做一张真实页面，完成后重新运行 `status`；页面齐了再执行 `next.command_when_ready`。
- `edit_slide`：只编辑 `next.path`，修复 `next.issues`，再执行 `next.rerun`。
- `fix_media`：只处理 `next.path` 指向的页面及相关素材，修复 `next.issues`，再执行 `next.rerun`。
- `run_command`：执行 `next.command`。
- `ask_user_to_confirm_preview`：展示 `next.artifact`；用户确认后执行 `next.command_on_confirm`，有页面反馈就修改对应页。
- `complete`：演示已完成。
<!-- next-action-contract:end -->

## 做一页

第一次制作页面时读 `references/components.md`，以后按需查相关段落。先看 starter 目录，选择最接近本页画面的一个；starter 只是起点，示例文字、数字、图和多余装饰都要替换或删除。

```text
scripts/oil-ppt starter list --json
scripts/oil-ppt starter show <名称>
scripts/oil-ppt slide add <项目> <页面ID> --title "<标题>" [--starter <名称>] [--after <页面ID>]
```

一页只编辑返回的 `slides/<id>.html`。检查原尺寸与放映缩放效果：主画面够大、字可读、图片没有误裁切、没有无用小字或示例内容。然后运行 `status` 修复它报告的实际问题。页面顺序调整可用 `slide move`，删页可用 `slide remove`。

需要外部素材时读 `references/media.md`；概念插画读 `references/illustration.md`；HTML/CSS/SVG 解释图读 `references/programmatic-visuals.md`。遇到构建或导出故障再读 `references/troubleshooting.md`。

## 检查与交付

放映前看整套缩略图，确认每页画面能区分、必要内容已覆盖，且没有示例文案、占位视觉、假来源或被卡片和小字淹没的信息。程序的结构、资源路径、溢出和最低字号检查是技术检查；`style_advice` 仅供参考，不要把它当作要逐条打勾的门禁，也不要为满足建议增加装饰或页面。

正式预览确认后按状态继续构建。只有用户明确需要 PowerPoint 时才运行 `scripts/oil-ppt export-pptx <项目>`。最终 HTML 是项目根目录的 `演示文稿.html`；PPTX 是混合可编辑交付物。
