# 素材

只读取用户明确提供、附加或指向的材料；不扫描同目录、桌面或旧项目。最终素材放入项目 `assets/`，Outline 只写项目相对路径。

## 先绑定页面，再处理图片

在 `outline.md` 中写清素材展示什么、回答什么问题；在 `outline.json` 中可记录：

- `media_role`：截图、证据、照片、插画等页面角色。
- `media_fidelity`：`strict` 保留 UI/数据/文档；`contextual` 保持真实语境；`illustrative` 只表达概念。
- `media_question`：这张素材回答的具体问题。
- `media_source`：来源类型、URL、作者、许可、权利依据和修改说明。

运行 `scripts/oil-ppt media plan <项目> --write`。程序会输出槽位比例、目标尺寸、frame owner、文件状态与哈希；需要截图适配时还会给出完整 `media frame` 命令。不要先生成任意比例图片再硬塞进页面。

## 选择视觉

- 产品界面、数据、案例、真人和文档是事实证据，使用真实素材；不让图片模型重画。
- 截图需要补足比例时使用 `media frame`，它只做等比缩放、对齐和块状背景，不改变截图内容。
- 流程、关系、对比和数据优先使用 HTML/CSS/SVG 程序化视觉。
- AI 生成只用于无事实指向的概念插画或隐喻，图中不生成文字、数字、标签、假 UI 或图表。
- 每张图片必须回答一个问题；纯氛围图不算视觉锚点。

## 来源

- 用户文件、网页和产品：保留用户提供或内部使用依据。
- Wikimedia Commons：读取原始页的作者、许可和修改要求。
- Pexels：保留摄影师和来源页，遵守 Pexels License。
- Openverse：只用于发现，回原始页二次核验后才能使用。
- Unsplash API 与离线单文件交付默认不兼容，不作为默认管线。

获取外部图片时必须回到原始授权页；普通搜索结果图不能直接进入正式预览。渠道的机器可读策略由 `scripts/oil-ppt media sources` 输出。
