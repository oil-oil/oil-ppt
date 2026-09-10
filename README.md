<p align="center">
  <img src="./assets/readme/readme-title.svg" width="100%" alt="oil-ppt：用最简单的方式，做出最好看的 PPT。">
</p>

<p align="center">
  <img src="./assets/readme/readme-showcase.png" width="100%" alt="01 先看效果：oil-ppt 生成的四套不同配色演示文稿，共十五张页面">
</p>

<p align="center">
  <img src="./assets/readme/readme-section-system.svg" width="100%" alt="02 oil-ppt 是什么">
</p>

oil-ppt 是一个给 Agent 使用的 PPT Skill。我们可以给它一个主题、一份文档或一组材料，它会直接创作可以全屏播放、离线打开的 16:9 HTML 演示文稿。

上面的十五张页面来自四套真实演示，分别使用黄色、钴蓝、苔绿和陶土色。它们共享同一套设计系统，但素材、密度和页面结构会跟着内容改变。

每张页面都是独立、可单独打开的 HTML 源文件。Agent 一次只创作或修改一页；oil-ppt 提供成熟组件、全局设计 token、真实浏览器检查和最终单文件构建。最后只交付一个 `演示文稿.html`。

| Agent 负责 | oil-ppt 负责 | 我们负责 |
| --- | --- | --- |
| 理解受众、组织叙事、逐页编写 HTML、选择素材与构图 | 舞台、缩放、设计 token、组件、素材内联与浏览器检查 | 确认创作方向和正式预览 |

<p align="center">
  <img src="./assets/readme/readme-section-model.svg" width="100%" alt="03 为什么性价比模型也能做好">
</p>

oil-ppt 的北极星是：低地板，高天花板。性价比模型可以从成熟的 HTML starter 和组件开始；更强的模型可以直接改变单页 DOM 与局部 CSS，不会被页面字段限制。

oil-ppt 把大任务拆成一个局部循环：

1. 参考材料或 Markdown 创作 brief。
2. 创建一张真实 HTML 页面。
3. 选择 starter、组合组件或完全自定义。
4. 用程序检查这一页的结构、素材和浏览器结果。
5. 回到整套预览调整顺序、拆页、合页或删除页面。

弱模型不需要同时维护整套页面结构；强模型也不需要为了一个新构图修改渲染程序。两者使用同一条渐进式路径：starter → 组合组件 → 修改局部 DOM/CSS → 完全自定义页面。

<p align="center">
  <img src="./assets/readme/readme-section-workflow.svg" width="100%" alt="04 怎么完成一套演示">
</p>

```text
主题或材料
  → 可选的 Markdown 创作参考
  → Agent 逐页编写 HTML
  → 单页检查与整套调整
  → 正式预览
  → 我们确认视觉
  → 演示文稿.html
```

大纲只是参考，实际演示可以自然拆页、合页、改标题和重排。正式预览直接读取真实页面源码；预览和构建都不会重新生成或覆盖页面。对某一页不满意时直接告诉 Agent，它只修改对应的 `slides/<id>.html`，然后重新检查整套结果。

<p align="center">
  <img src="./assets/readme/readme-section-start.svg" width="100%" alt="05 怎么使用">
</p>

**方式一 · 执行命令**

```bash
npx skills add oil-oil/oil-ppt
```

**方式二 · 直接交给 Agent**

把下面这句话发给 Agent，让它完成安装：

```text
请安装这个 Skill：https://github.com/oil-oil/oil-ppt
```

安装完成后，调用名是 `oil-ppt`：

```text
[$oil-ppt] 帮我做一份关于这个主题的演示文稿。
```

新建演示时，我们可以选择通过对话一起整理大纲，或根据已有材料直接生成第一版。

适合产品介绍、设计方案、案例展示、教程、研究结论和项目汇报。它更适合有明确观点、需要现场讲述的内容，不会把长文机械切成几十张信息密集的页面。

<details>
<summary><strong>维护与本地检查</strong></summary>

```bash
oil-ppt/scripts/oil-ppt doctor
python3 -m unittest discover -s tests -p 'test_*.py'
```

</details>

<p align="center">
  <a href="https://github.com/oil-oil/beautify-github-readme"><img src="./assets/readme/made-with-beautify.svg" width="300" alt="README made with beautify-github-readme"></a>
</p>

<p align="center"><sub>MIT License</sub></p>

## 配置、依赖与使用边界

需要 Python / Node.js 及项目中声明的构建依赖；油式文案使用 oil-tone，生图按可用工具配置。不是所有页面都能无损转成可编辑 PowerPoint。

导出与渲染按当前运行环境验收；来源、字体与图像权利由实际材料决定。页面检查不能以文件存在替代。

使用示例：

```text
用 oil-ppt 把这份材料做成 8 页演示文稿。
```
