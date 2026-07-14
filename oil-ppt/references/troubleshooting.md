# 故障处理

以下路径都相对于 `SKILL.md` 所在目录；执行前解析为绝对路径，不调用裸命令，不依赖 PATH 或当前工作目录。

- 环境或浏览器异常：`scripts/oil-ppt doctor`
- 不确定组件、variant 或 decor：`scripts/oil-ppt contract`
- outline 校验失败：根据错误补齐当前组件所需内容。
- 浏览器构建失败：根据命令返回的具体页面和原因修复内容或素材，再运行 `scripts/oil-ppt status <项目> --json`，只执行其中的下一动作。

如果该精确入口不存在或不可执行，报告完整路径并停止；不搜索替代入口，不直接调用内部 Python 模块绕过入口。

不直接编辑生成的 `演示文稿.html`、公共 runtime 或模板几何。
