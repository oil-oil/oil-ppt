# oil-ppt

使用 HTML 工作流创建、修改和检查 16:9 演示文稿，并按需导出混合可编辑的 PPTX。最终交付通常是项目根目录的 `演示文稿.html`；PPTX 只在正式预览确认后导出。

## 安装

```bash
npx skills add oil-oil/oil-ppt
```

也可以把完整仓库地址交给 Agent：

```text
请帮我安装这个 Skill：https://github.com/oil-oil/oil-ppt
```

## 使用

```text
使用 $oil-ppt，根据这份材料制作一套 16:9 HTML 演示文稿。
```

Skill 会按状态返回的 `next` 逐页创建或修改页面。创建或改写面向观众的文字时，默认搭配 `oil-tone`；它不负责把任意已有 PPTX 无损导入为源工程，也不用于普通文章或单张海报。

## 配置

不需要额外 API Key。页面项目、素材和构建产物使用用户指定的本地路径；需要浏览器检查时，由当前宿主提供本地浏览器能力。全局主题、字体和页面形状通过项目命令配置，不写入用户级 Skill 目录。

## 依赖与数据边界

需要运行环境提供 Python、Node.js 以及项目声明的构建依赖；浏览器检查需要可用的本地浏览器能力。项目、素材和生成的演示文稿默认保存在用户指定的本地目录，外部素材和字体的权利由使用者负责确认。

## 本地检查

在仓库根目录运行：

```bash
python3 oil-ppt/scripts/package_manifest.py --verify --json
python3 oil-ppt/scripts/validate_skill.py
python3 -m unittest discover -s tests -p 'test_*.py'
```
