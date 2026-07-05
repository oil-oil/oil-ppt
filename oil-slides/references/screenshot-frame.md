# 带壳真实截图 — oil-slides

墨水插画之外的第二种主视觉:**真实界面截图,套一个 HTML 浏览器壳展示**。用来给「实操 / 产品 / 文档 / 数据看板」这类**需要真实证据**的页配图——抽象概念用插画,真实东西用带壳截图。

成品参考:它就是 oil-cover「轻 3D 屏幕 / 浏览器窗口」那种设计感,但**纯 HTML/CSS 复刻**,不生图。

---

## 两条原则

1. **截图带壳,不裸放**:真实截图直接贴上去很廉价。套一个 macOS 浏览器窗口壳(圆角 + 交通灯 + 地址栏 + 柔和大投影),立刻有产品展示页的高级感。
2. **露一部分,不摆正**:壳**部分溢出 slide 边缘**(右边或底边),只露大半张。配合左侧文字,是经典的「左字右屏」产品构图。摆在正中、完整居中 = 呆。

何时用截图、何时用插画:

| 内容 | 主视觉 |
|---|---|
| 抽象概念 / 判断 / 隐喻 | 墨水插画(`illustration.md`) |
| 真实产品页 / 软件界面 / 官方文档 / 数据看板 | **带壳截图**(本规范) |

---

## 一、配图来源:ego-browser 抓真实网页

用 `/ego-browser` 抓官方页 / 文档 / 控制台截图(走用户登录态)。验证过的 heredoc 模板:

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('grab shot for deck')
await openOrReuseTab('<URL>', { wait: true, timeout: 30 })
await ensureRealTab()
// 强制 viewport(后台 tab 的 pageInfo 常报 0×0,不能依赖它)
await cdp('Emulation.setDeviceMetricsOverride', { width:1440, height:900, deviceScaleFactor:2, mobile:false })
await wait(1.5)
await js(String.raw`window.scrollTo(0, 0)`)   // 想跳过顶部促销 banner 就 scrollTo 到 hero 区
await wait(1)
const shot = await cdp('Page.captureScreenshot', { format:'png', captureBeyondViewport:false })
const fs = await import('node:fs')               // ⚠️ ego 是 ESM,require 不可用,必须 import('node:fs')
fs.mkdirSync('<deck目录>/shots', { recursive:true })
fs.writeFileSync('<deck目录>/shots/<名字>.png', Buffer.from(shot.data, 'base64'))
cliLog('saved ' + Buffer.from(shot.data,'base64').length + ' bytes')
EOF
```

**踩过的三个坑(直接照上面写就行,别重蹈):**
- `pageInfo()` 在后台 tab 常返回 `w:0, h:0` → **别依赖它**,直接 `cdp('Emulation.setDeviceMetricsOverride', ...)` 强制 viewport 再截。
- ego 的 Node runtime 是 **ESM**,`require` 报 `require is not defined` → 用 `await import('node:fs')`。
- `captureScreenshot()` helper 在当前版本可能 Unknown → 直接用底层 `cdp('Page.captureScreenshot', { format:'png' })`,返回 `{ data: <base64> }`。
- `deviceScaleFactor:2` 出 2× 高清图(2880×1800),放 PPT 清楚;找不到官方页就先 bing `li.b_algo h2 a` 搜出 URL 再开。

> 另一类来源:产品截图也可以让用户直接给文件;或用 `gen_art.py` 生**抽象 UI**(不是真实界面,别伪造具体产品 UI)。真实证据优先 ego-browser 抓官方页。

## 二、浏览器壳 HTML(直接抄)

```html
<figure class="shot-frame reveal">
  <div class="sf-bar">
    <span class="sf-lights"><i></i><i></i><i></i></span>
    <span class="sf-url">aliyun.com/product/agentbay</span>   <!-- 真实 URL,去掉 https:// -->
  </div>
  <div class="sf-screen">
    <img src="shots/<名字>.png" alt="" onerror="this.parentElement.parentElement.style.display='none'">
  </div>
</figure>
```

## 三、浏览器壳 CSS(验证过的值,与 oil-html 同一套中性配色)

```css
/* 窗口:圆角 + 白底 + 柔和大投影,悬浮在白底网格上 */
.shot-frame { position:absolute; right:-80px; top:150px; width:1040px; z-index:15;
  border-radius:16px; overflow:hidden; background:#ffffff; border:1px solid #e8e8e8;
  box-shadow:0 50px 110px rgba(0,0,0,.12), 0 14px 34px rgba(0,0,0,.06); }
/* 标题栏:浅灰 */
.sf-bar { height:54px; display:flex; align-items:center; gap:22px; padding:0 26px;
  background:#f7f7f8; border-bottom:1px solid rgba(0,0,0,.05); }
/* 交通灯:macOS 标准三色,和 oil-html 的聊天窗口一致 */
.sf-lights { display:flex; gap:11px; }
.sf-lights i { width:14px; height:14px; border-radius:50%; }
.sf-lights i:nth-child(1){ background:#ff5f57; }
.sf-lights i:nth-child(2){ background:#ffbd2e; }
.sf-lights i:nth-child(3){ background:#28c840; }
/* 地址栏:白 pill */
.sf-url { font-family:var(--font-ui); font-size:21px; color:var(--ink-3); background:#ffffff;
  padding:9px 28px; border-radius:999px; border:1px solid rgba(0,0,0,.06); letter-spacing:.02em; }
.sf-screen { line-height:0; }
.sf-screen img { width:100%; display:block; }
```

配套的左侧文字列(`.s-shot`)：

```css
.s-shot .content { position:absolute; left:160px; top:230px; width:660px; z-index:20; }
.s-shot h3 { font-family:var(--font-zh); font-weight:700; font-size:62px; line-height:1.28; color:var(--ink); margin:0 0 40px; }
.s-shot .pts { display:flex; flex-direction:column; gap:20px; }
.s-shot .pt { display:flex; align-items:center; gap:18px; font-family:var(--font-zh); font-size:29px; color:var(--ink-2); }
.s-shot .pt::before { content:''; width:10px; height:10px; border-radius:50%; background:var(--ink); flex-shrink:0; }
```

## 四、落位与微调

- **露一部分**:`right:-80px`(右溢出)或 `bottom` 负值(下溢出)。宽 900–1100px,占 slide 一半多。
- **别压文字**:左侧文字列 ≤700px,截图从 x≈960 开始,留 150px 间隙。
- **顶部杂栏**:真实页常带促销 banner/导航,带壳展示其实更真实可信;要更干净就抓图时 `scrollTo` 到 hero,或给 `.sf-screen` 限高 + `img { object-position: 0 -120px }` 裁掉顶部。
- **一页一屏**:一页最多一个浏览器壳,和插画一样别堆。
- **倾斜可选**:想要更强的轻 3D,可加 `transform: perspective(2000px) rotateY(-6deg)`;但整套基调克制,默认正面 + 大投影就够,别过度。
