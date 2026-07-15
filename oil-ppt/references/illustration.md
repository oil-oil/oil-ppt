# 概念插画

概念插画只用于抽象机制、冲突或人的感受。它必须帮助观众更快理解当前页，不作为填空装饰。

## 使用边界

- 一套 10–15 页演示通常使用 2–3 张插画；已有真实界面或结构图时不再叠加插画。
- 每张插画只表达一个动作、冲突或关系，远距离也能一眼看懂。
- AI 生成图中禁止出现任何文字、字母、数字、标签、图表、代码和假 UI。
- 需要准确文字的内容使用页面原生 HTML；真实产品证据使用真实截图。
- 插画构图必须服从页面：先读取 media plan 的真实槽位比例，再生成对应横竖构图；主体占最终版位约 65%–80%，避免素材内部自带大面积空边。

## 画风

沿用 oil 体系的漫画墨水与半调网点，但为投影观看简化细节：

- 黑白灰占画面九成；暖黄是唯一常驻色，不引入蓝紫 AI 渐变。
- 使用干净、自信、粗细分明的黑色墨线；灰面用规则圆形半调网点，不使用柔和渐变。
- 主角是圆头、圆框眼镜、点状眼睛和细线四肢的极简火柴人。
- 同伴是圆滚滚的暖黄色边牧，白胸、小短腿，约主角高度的一半。
- 动作要自然、有一点幽默，但不要卖萌过度；不用机器人、发光大脑、芯片和通用科技意象。

## 生成提示

先用一句中文写清：谁在做什么、和什么对象发生关系、画面重心放在哪里。随后固定加入：

```text
Style: professional manga/comic ink illustration for a premium presentation.
Clean confident black ink outlines with varied line weight. Use classic circular
halftone screentone for grey and shadow areas, flat black fills, and large white
areas. The main character is a minimal stick figure with a round head, thin round
glasses, dot eyes, a simple mouth, and thin line-drawn limbs. The companion is a
small chubby Border Collie with warm yellow fur, a white chest, short legs, and a
calm friendly expression. Color usage is extremely restrained: 90% black, white,
and grey halftone; warm yellow only on the dog and one or two small accents.
No text, no letters, no numbers, no labels, no logo, no watermark, no chart,
no code, no interface, no speech bubble, and no fake UI.
```

需要透明主体时，使用当前 imagegen skill 规定的纯色键控背景与抠图流程。生成后检查：

1. 图内完全没有文字或类似文字的符号。
2. 主体动作确实对应当前页的判断。
3. 缩小到幻灯片实际占位后仍能看懂。
4. 透明边缘干净，没有键控残色。

## 页面摆放

- 概念插画优先使用 `split-visual` 或 `editorial-feature` 的 `media_surface: page-blend`，让透明素材或与页面同底色的画面直接融入版式；不要默认套浅灰圆角卡片。
- 只有色块本身表达边界、状态或层级时，才使用 `media_surface: component`。浏览器壳、设备壳与文档框只服务真实证据，不用来包装普通插画。
- 照片和有边到边背景的插画默认使用 `cover` 铺满版位；UI、文档、图表等不可裁切素材使用 `contain`。若 `cover`，用 `media_position` 保护偏离中心的主体。
- 同一页只允许一个主要外框；素材已经自带必须保留的外框时声明 `media_frame: self-framed`，模板不再增加第二层阴影与边框。
- 角色视线和动作朝向正文或页面中心，避免把观众注意力带出画面。
