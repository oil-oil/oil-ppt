---
name: oil-slides
description: oil 个人专用技术幻灯片 skill。与 oil-html 同一套设计语言(白底网格、黑白灰 + 暖黄、漫画墨水插画、蒙版色块容器)做技术分享/教程类 HTML 演示——零依赖单文件、固定 16:9、演讲型大字少字。触发:用户说「oil-slides」「用我的风格做 slide / 幻灯片 / PPT」「做个技术分享的 slide」,或要把内容做成演示。本 skill 做的是 16:9 翻页幻灯片;要做滚动阅读的 HTML 分享文档用 oil-html,不用本 skill。不照搬通用 frontend-slides 的发现流程。
---

# oil-slides

我自己的技术幻灯片 skill。砍掉通用流程的"问 4 个问题 + 选 3 个风格预览",风格早就定了——直接按我的设计语言生成。

零依赖、单 HTML 文件、固定 1920×1080 舞台、预览时默认宽度铺满。

## 风格已锁定(不问、不选)

- **第一原则**:可视化优先 + 克制。每页有一个「主视觉」承载信息(图示/插画/数据图),文字是注解;一页一个 idea、信息单元 ≤3、大量留白。**纯文字陈述页 = 干瘪,禁止。** 详见 slide-style.md 第〇节。
- **视觉**:与 oil-html 同一套——纯白底 + 细网格纹理,黑白灰为底,暖黄是唯一常驻色(高亮楔入 + 插画色块容器 + 插画里的边牧)。
- **强调**:高亮楔入——一句话里 1 个词垫暖黄荧光条,一页最多一处。不用斜体、不换字体。
- **密度**:演讲型,大字少字,但省下的空间留给主视觉,不是留空。
- **语言**:中文为主 + 英文术语,**不加署名页**。
- **配图**:概念用漫画墨水插画(火柴人主角 + 黄边牧同伴,与 oil-html 同角色同画风),默认放**蒙版色块容器**——圆角暖黄色块,插画一部分露出、一部分被容器边裁掉;真实产品 / 界面用**带壳截图**(ego-browser 抓图 + HTML 浏览器壳)。需要时生成 / 抓取。
- **文字**:真诚、温暖、简单;不编造、不提升立意、不说套话、不堆名词、不浮夸。

完整规则读 `references/slide-style.md`(视觉+版式+文字)。生图读 `references/illustration.md`。

## 工作流程(精简)

**Phase 0 · 认模式**
- 新建 → 直接往下走。
- 改已有 HTML → 读它再改,改完查不溢出/不重叠/16:9。
- 转 PPT → 先 `python3 ~/.claude/skills/frontend-slides/scripts/extract-pptx.py <in.pptx> <out_dir>` 提取,再往下走。

**Phase 1 · 接内容**
- 用户给了内容就用;只给主题就先帮列大纲(按演讲型,一页一个 idea),确认后再生成。
- **不要**问用途/篇幅/密度/风格——都定了。唯一值得问的:有没有现成内容,或要不要我先列大纲。

**Phase 2 · 定主视觉 + 生成**
1. 读 `references/slide-style.md`、`viewport-base.css`。
2. **先给每页定一个主视觉**(按第〇节「内容→怎么画」):概念页→墨水插画(蒙版容器);结构/对比/流程→CSS 图示;数据→大数字;能力网格→小线描图标;真实产品 / 界面 / 文档→**带壳截图**(ego-browser 抓)。纯文字陈述页要重做成可视化。
3. 按版式模板铺页,套用色与字的既定值;每页信息单元 ≤3、一处暖黄高亮、留白足。成组小模块(流程卡、能力卡、图标条、对比列)必须用 flex/grid 管宽高和间距,不要用一堆绝对定位小块硬摆。
4. 文字逐句过一遍「文字风格」铁律。
5. 每页加 `data-next` → 右下角下一页提示;按 `N` 可隐藏。
6. 单文件:viewport-base.css 全文内联,Inter + Noto Sans SC 从 Google Fonts 加载,关键段落加 `/* === 注释 === */`。预览缩放 JS 必须用宽度铺满:`scale = window.innerWidth / 1920`,舞台 `left:0`,背景白色,避免左右黑边。
- 参考实现:`assets/examples/sample-deck.html`(可直接拿来改)。

**Phase 3 · 配插画(概念页默认配,不等点名)**
- 铺页时先标出哪几页是概念/章节/封面/收束页 → 这些**默认各配一张墨水插画**。
- 默认管线:Codex image_gen 灰底 #808080 生成 → 检查背景干净均匀 → `python3 ~/.claude/skills/codex/scripts/cutout.py` 抠图 → 透明 PNG → 放进蒙版色块容器。无 Codex 环境用 `scripts/gen_art.py`(zenmux 绿幕管线,同画风)。细节读 `references/illustration.md`。
- 结构/对比/流程页用 CSS 图示,不用插画。用户说「先不配图」才跳过。
- **真实截图**:要展示官方页 / 界面 / 文档时,用 `/ego-browser` 抓图(`cdp('Page.captureScreenshot')`)→ 套 HTML 浏览器壳、部分溢出展示。见 `references/screenshot-frame.md`。

**Phase 4 · 交付**
- `open <file>.html` 打开。
- 说明:方向键/空格翻页;`N` 隐藏下一页提示。**默认鼠标单击不翻页**(避免手滑跳页);需要点击翻页时,URL 后加 `?click=1`,或在 `<body>` 上加 `data-click-nav` 属性。
- 自检:截图核对宽度铺满、无左右黑边、无溢出、无重叠、无局促小字、对比不刺眼。封面流程卡、对比卡、图标条这类高风险区域要单独放大看。

**Phase 5 · 分享(可选,问一句)**
- 部署:`bash ~/.claude/skills/frontend-slides/scripts/deploy.sh <path>`(Vercel)。
- 导 PDF:`bash ~/.claude/skills/frontend-slides/scripts/export-pdf.sh <path>`。

## 文件

| 文件 | 用途 | 何时读 |
|------|------|--------|
| `references/slide-style.md` | 视觉+版式+文字风格(核心) | 每次生成前 |
| `references/illustration.md` | 墨水插画生成+蒙版容器摆放 | 要配概念图时 |
| `references/screenshot-frame.md` | 带壳真实截图(ego-browser + 浏览器壳) | 要放真实界面 / 产品页时 |
| `viewport-base.css` | 固定舞台 CSS,全文内联 | 每次生成 |
| `scripts/gen_art.py` | 插画生成+抠图 fallback(无 Codex 时) | 要配图且没有 Codex 时 |
| `assets/examples/` | 样张 deck(风格锚点) | 参考/起手 |

## 不可违反

- **每页必须有主视觉,禁止纯文字陈述页(标题+一段话)和 4 条以上纯文字 bullet。** 干瘪是头号大忌。
- 不跑通用发现流程(4 问 + 3 预览选风格);风格已锁。
- 不加署名页/联系方式页。
- 文字必须过「不编造/不提升立意/不套话/不堆名词/不浮夸」铁律。
- 插画必须在纯色底(Codex 灰底或 gen_art.py 绿幕)上生成、抠成透明 PNG 后才进 slide,绝不白底直接生成;默认放蒙版色块容器,不裸放。
- 切页只用 `visibility/opacity`,固定舞台规则不破。
- 浏览器预览不得出现左右黑边;默认按宽度铺满,舞台外背景用白色或同款网格底。
- 三个以内的小模块也不能用固定小框硬塞文字;优先用 flex/grid,卡片内文案超两行就改短或加大卡片。
