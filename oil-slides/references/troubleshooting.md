# 故障处理

以下路径都相对于 `SKILL.md` 所在目录；执行前解析为绝对路径，不调用裸命令，不依赖 PATH 或当前工作目录。

- 环境或浏览器异常：`scripts/oil-slides doctor`
- 不确定组件、variant 或 decor：`scripts/oil-slides contract`
- 项目中的 runtime 或 icons 过旧：`scripts/oil-slides sync <项目>`
- 页序或文件清单异常：`scripts/oil-slides list <项目>`
- outline 校验失败：根据错误补齐当前组件所需内容。
- 浏览器构建失败：缩短报错页内容、补齐素材或更换组件后，使用同一绝对入口重新执行 `build <项目>`。

如果该精确入口不存在或不可执行，报告完整路径并停止；不搜索替代入口，不直接调用 `oil_slides.py`绕过入口。

不直接编辑生成的 `演示文稿.html`、公共 runtime 或模板几何。
