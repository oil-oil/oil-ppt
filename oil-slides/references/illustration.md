# 墨水插画生成与摆放 — oil-slides

幻灯片的概念插画用这一套:**漫画墨水 + 半调网点**,和 oil-html 完全同一套角色与画风,两个 skill 的产出摆在一起要像一个人画的。

## 画风与角色(与 oil-html 同源,改动要两边同步)

```text
线条: 干净利落、粗细分明的黑色墨水勾线。粗线做轮廓,细线做内部结构。
填色: 大面积留白 + 黑色实填 + 半调网点(screentone)做中间灰。
      不用渐变,灰色全靠网点密度控制。这是风格的核心视觉元素。
主角: 可爱火柴人——圆形头(白色填充,网点做阴影),细线条四肢,
      圆框细边眼镜,两个圆点眼睛,弯弯的微笑嘴。可加小配件突出主题。
同伴: 黄色胖嘟嘟的小边牧犬,黑色墨水轮廓,毛色暖黄 + 白色胸口,
      约主角 40-50% 大小。
配色: 九成画面只有黑 + 白 + 灰(网点)。暖黄只用在边牧毛色、局部暖光
      色块、少量星星装饰。不引入其他色相。
```

## 生成管线

### 默认:Codex 生图 + cutout.py 抠图

1. 让 Codex 用 image_gen 生成,prompt 结尾统一追加这段风格锚定:

   ```text
   Style: professional manga/comic ink illustration. Clean confident ink outlines
   with varying line weights (thick for contours, thin for details), NOT wobbly
   or sketchy. Heavy use of classic circular halftone screentone dot patterns for
   all grey/shadow areas — this is the signature visual element. Flat black fills
   for hair and dark areas. White for skin/body with screentone shading. The main
   character is a cute stick figure with a round head, thin round glasses, dot
   eyes, simple smile, and thin line-drawn limbs — minimal and charming, not
   detailed. Color usage is extremely restrained — 90% of the image is black,
   white, and grey halftone screentone. Warm yellow only on the chubby Border
   Collie companion dog, small warm light patches, and sparse star decorations.
   Rich detail and visual complexity like a printed comic page or indie zine
   illustration, not a simple mascot icon.
   CRITICAL — Background must be PERFECTLY UNIFORM flat grey (#808080) with
   ZERO gradient, ZERO texture, ZERO noise, ZERO speckles. Every single
   background pixel must be the exact same grey value. Do NOT let screentone
   dots, halftone patterns, ink splatter, or any visual element bleed into the
   background area. The background is a clean solid rectangle of #808080 —
   treat it like a green screen. PNG format, square composition.
   ```

2. Codex 生成后让它把 PNG 复制到 deck 输出目录的 `art/` 子目录(不放进 Skill 目录)。
3. **Claude 接手检查背景是否干净均匀**——cutout.py 是从四角 flood-fill 去背景,背景有渐变、散点、纹理溢出就会抠花,必须重新生成。
4. 抠图:`python3 ~/.claude/skills/codex/scripts/cutout.py <in.png> <out.png>`,得到透明 PNG。

### fallback:没有 Codex 环境时用 gen_art.py

`scripts/gen_art.py` 走 zenmux `gpt-image-2`,绿幕生成 + 自动抠图,风格 prompt 与上面同一套(写死在脚本 `STYLE` 常量里):

```bash
python3 scripts/gen_art.py --subject "<英文,具体概念>" --out <deck目录>/art/<名字>.png
```

key 取 `$ZENMUX_API_KEY` 或 `~/.zenmux_api_key`。

## subject 怎么写

- **英文、具体、单一概念**。一句话说清"谁在做什么",别堆细节。角色出场就写 the stick-figure character (round head, round glasses) 和 his chubby yellow Border Collie。
- 保持抽象:用「手 / 卡片 / 节点 / 台阶 / 容器 / 箭头 / 种子」这类朴素元素表达概念,不要具体品牌或界面。

### 概念库(够用的起手式)

| 想表达 | subject 起手式 |
|--------|---------------|
| 构建 / 选择 | the character placing one card onto a short stack of cards |
| 协作 / 连接 | the character and the dog looking at a small node graph between them |
| 成长 / 积累 | a small sprout growing out of a stack of blocks, the dog watching |
| 简化 / 删减 | the character sweeping clutter off to leave one clean shape |
| 流程 / 步骤 | the character walking up three simple stepping stones |
| 容器 / 系统 | an open box holding a few simple shapes, the character peeking in |
| 选择 / 分流 | one path splitting into two, the character standing at the fork |

## 摆进幻灯片:默认放蒙版色块容器

透明 PNG 不裸放白底——默认放进圆角暖黄色块容器,让图**一部分露出、一部分被容器边裁掉**(蒙版感),或头顶探出色块顶边。这是本风格的招牌摆法。

```css
/* 蒙版式:容器 overflow hidden 当蒙版,图探入,超出部分被圆角边裁掉 */
.illo-card {
  position: absolute;
  border-radius: 28px;
  background: var(--illo-bg);   /* #f9f0d8 */
  overflow: hidden;
}
.illo-card img {
  position: absolute;
  filter: drop-shadow(0 8px 24px rgba(0,0,0,.08));
}
/* 常用落位:右下探入(right:-6%; bottom:-12%; width:~70%),或底部站立脚被裁 */

/* 探出式:色块只垫下半,角色头顶冒出色块顶边(外层不裁切) */
.illo-pop { position: absolute; }
.illo-pop .illo-frame {
  position: absolute; left: 0; right: 0; bottom: 0;
  height: 66%; border-radius: 28px; background: var(--illo-bg);
}
.illo-pop img {
  position: absolute; bottom: 0; left: 50%;
  transform: translateX(-50%); height: 96%;
  filter: drop-shadow(0 8px 24px rgba(0,0,0,.08));
}

/* 半调网点装饰面:放容器空白角落,一个容器最多一块 */
.dots {
  position: absolute; pointer-events: none;
  background-image: radial-gradient(circle, rgba(0,0,0,.16) 2px, transparent 2.2px);
  background-size: 18px 18px;
}
```

- 尺寸参考:1920×1080 舞台里,概念页容器 520–720px 见方;封面/章节页可更大(700–900px),容器本身可溢出 slide 边缘。
- 容器放内容区的对角空白处,**不压正文**,一页最多一张插画。
- 容器底色统一用 `--illo-bg` 暖黄,整套 deck 一个色,和高亮楔入、边牧毛色形成呼应。
