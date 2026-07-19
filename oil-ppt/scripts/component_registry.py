#!/usr/bin/env python3
"""Single declarative registry for oil-ppt component discovery and quality."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


DATA_STORY_QUESTIONS = {
    "category-comparison": "哪些类别更大或更小？",
    "trend": "数值如何随时间变化？",
    "composition": "各部分如何组成整体？",
    "relationship": "两个指标是否共同变化，样本分布在哪里？",
}


@dataclass(frozen=True)
class ComponentSpec:
    """Stable component identity projected into CLI, schema, audit, and catalog maps."""

    name: str
    family: str
    use_when: str
    avoid_when: str
    aliases: tuple[str, ...]
    effects: tuple[str, ...]
    variants: tuple[str, ...] = ("default",)
    decorations: tuple[str, ...] = ("none",)
    silhouette: str = "focal"
    surface_density: str = "none"
    frame_owner: str = "none"
    variant_quality: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    variant_help: Mapping[str, str] = field(default_factory=dict)
    media: bool = False
    page_blend: bool = False
    closed_structure: bool = False
    native_visual: bool = False
    native_visual_variants: tuple[str, ...] = ()


def _spec(name: str, **values: object) -> ComponentSpec:
    return ComponentSpec(name=name, **values)  # type: ignore[arg-type]


COMPONENT_SPECS = {
    "artifact-focus": _spec(
        "artifact-focus", family="focal",
        use_when="一张非二维码的插画、物件或交付物需要以 70–80% 页面高度成为唯一视觉焦点，文字只作短标题或说明。",
        avoid_when="视觉只是小型附件、需要扫码语义，或正文需要承担主要论证",
        aliases=("巨型物件焦点", "交付物主视觉", "单一大视觉"), effects=("artifact-focal", "page-blend-illustration"),
        silhouette="artifact-focus", surface_density="none", frame_owner="none", media=True,
        page_blend=True, closed_structure=True,
        variant_quality={"default": {"layout_signature": "artifact-focal", "visual_energy": "anchor"}},
        variant_help={"default": "单一视觉居中占屏，文字保持克制"},
    ),
    "brand-matrix": _spec(
        "brand-matrix", family="collection",
        use_when="两组品牌、工具或能力集合需要按分组快速扫描，并保持每个条目同等权重。",
        avoid_when="条目存在先后顺序、需要长段说明，或分组多于两组",
        aliases=("品牌矩阵", "工具分组", "品牌墙"), effects=("grouped-brand-matrix",),
        silhouette="brand-matrix", surface_density="heavy", closed_structure=True, native_visual=True,
    ),
    "bleed-split": _spec(
        "bleed-split", family="bleed",
        use_when="文字与一张可出血的主视觉共同表达判断；按主体位置选择左右出血。",
        avoid_when="素材不可裁切或已有重要外框",
        aliases=("边缘出血", "破框主视觉", "半屏铺满"), effects=("edge-bleed",),
        variants=("media-right", "media-left"), silhouette="bleed", frame_owner="media", media=True,
        variant_quality={
            "media-right": {"layout_signature": "edge-bleed", "visual_energy": "anchor"},
            "media-left": {"layout_signature": "edge-bleed", "visual_energy": "anchor"},
        },
        variant_help={"media-right": "主视觉从右侧出血", "media-left": "主视觉从左侧出血"},
    ),
    "browser-showcase": _spec(
        "browser-showcase", family="split",
        use_when="真实界面截图或明确标注的 UI 演示是主要证据；按讲述顺序选择界面在左或右。",
        avoid_when="窗口语境本身不是证据",
        aliases=("网页截图", "产品界面", "浏览器壳"), effects=("browser-frame",),
        variants=("media-right", "media-left"), silhouette="browser", surface_density="light",
        frame_owner="template", media=True,
        variant_quality={
            "media-right": {"layout_signature": "browser-split", "visual_energy": "anchor"},
            "media-left": {"layout_signature": "browser-split", "visual_energy": "anchor"},
        },
        variant_help={"media-right": "界面证据在右", "media-left": "界面证据在左"},
    ),
    "card-trio": _spec(
        "card-trio", family="cards",
        use_when="三个可独立拿走的信息单元共同支撑一个判断，并且有一主两辅；左右型强调纵向主卡，feature-top 先给总领再读两项支撑，media-evidence 用两组图片证据与一个文字决策块完成路由。",
        avoid_when="三项完全等权或存在顺序",
        aliases=("一主两辅", "三块卡片", "饭盒卡片", "三类路由"),
        effects=("feature-support", "evidence-routing"),
        variants=("feature-left", "feature-right", "feature-top", "media-evidence"),
        silhouette="card-grid", surface_density="heavy", closed_structure=True,
        variant_quality={
            "feature-left": {"layout_signature": "feature-support-vertical", "visual_energy": "structured"},
            "feature-right": {"layout_signature": "feature-support-vertical", "visual_energy": "structured"},
            "feature-top": {"layout_signature": "feature-support-band", "visual_energy": "structured"},
            "media-evidence": {"layout_signature": "evidence-routing", "visual_energy": "anchor"},
        },
        variant_help={
            "feature-left": "左侧纵向主卡", "feature-right": "右侧纵向主卡",
            "feature-top": "上方横向总领、下方两项支撑",
            "media-evidence": "两组图片证据与一个文字决策块",
        },
    ),
    "comparison": _spec(
        "comparison", family="comparison",
        use_when="两个对象需要以相同维度直接对照；有成组真实图片证据时使用 visual-evidence。",
        avoid_when="两侧维度不同",
        aliases=("二选一", "两方案", "左右对比", "证据对比"),
        effects=("paired-comparison", "evidence-comparison"),
        variants=("default", "visual-evidence"), decorations=("dots",),
        silhouette="two-panel", surface_density="heavy",
        variant_quality={
            "default": {"layout_signature": "two-panel", "visual_energy": "structured"},
            "visual-evidence": {"layout_signature": "evidence-comparison", "visual_energy": "anchor"},
        },
        variant_help={"default": "纯文字双栏对比", "visual-evidence": "每侧两张真实图片证据与两条判断"},
    ),
    "comparison-list": _spec(
        "comparison-list", family="comparison",
        use_when="两个责任域或方案需要逐项对齐比较。",
        avoid_when="每侧不足三项或没有共享维度",
        aliases=("逐项对照", "责任边界", "对比清单"), effects=("aligned-comparison",),
        variants=("focus-right", "focus-left", "balanced"), decorations=("dots",),
        silhouette="matrix", surface_density="light",
        variant_quality={
            "focus-right": {"layout_signature": "comparison-matrix", "visual_energy": "structured"},
            "focus-left": {"layout_signature": "comparison-matrix", "visual_energy": "structured"},
            "balanced": {"layout_signature": "comparison-matrix", "visual_energy": "structured"},
        },
        variant_help={
            "focus-right": "右侧结论更重要", "focus-left": "左侧结论更重要", "balanced": "两侧完全等权",
        },
    ),
    "code-to-render": _spec(
        "code-to-render", family="compound",
        use_when="两段源码与各自的可见结果需要一一对应，解释从输入到呈现的转换。",
        avoid_when="只需要展示源码，或源码与结果无法形成明确配对",
        aliases=("代码到渲染", "源码与结果", "输入输出面板"), effects=("source-to-render",),
        silhouette="code-render", surface_density="heavy", closed_structure=True, native_visual=True,
    ),
    "converge": _spec(
        "converge", family="canvas", use_when="多个输入汇聚为一个结果或判断。",
        avoid_when="内容是顺序流程", aliases=("汇聚", "合流", "输入到结果"), effects=("merge-diagram",),
        silhouette="diagram", surface_density="light", closed_structure=True, native_visual=True,
    ),
    "cycle": _spec(
        "cycle", family="sequence",
        use_when="四个有明确顺序的阶段彼此供给，最后一个阶段会回到第一个阶段并形成持续循环。",
        avoid_when="最后一步不会重新供给第一步，或内容只是一次性线性流程",
        aliases=("循环", "飞轮", "闭环"), effects=("closed-cycle",),
        silhouette="cycle", surface_density="light", closed_structure=True, native_visual=True,
        variant_quality={"default": {"layout_signature": "closed-cycle", "visual_energy": "anchor"}},
        variant_help={"default": "四个阶段顺时针推进，最后一段回到第一阶段"},
    ),
    "cover": _spec(
        "cover", family="focal",
        use_when="演示开场。statement=大字焦点；media=标题+铺满版位的真实主视觉，不使用通用卡片外框。",
        avoid_when="普通内容页", aliases=("封面", "开场", "首屏"),
        effects=("opening-focal", "open-full-slot-media"), variants=("statement", "media"),
        silhouette="focal",
        variant_quality={
            "statement": {"layout_signature": "focal-statement", "visual_energy": "anchor"},
            "media": {"layout_signature": "cover-media-split", "visual_energy": "anchor"},
        },
        variant_help={"statement": "纯大字开场", "media": "标题与真实主视觉共同开场"},
    ),
    "data-story": _spec(
        "data-story", family="data",
        use_when="真实数值需要回答一个关系问题：哪些类别更大、如何随时间变化、各部分如何组成整体，或两个指标是否共同变化/样本如何分布。",
        avoid_when="没有真实数值、没有来源，或页面只需强调一个数字",
        aliases=("数据关系", "量化证据", "原生数据图"),
        effects=("category-comparison", "trend", "composition", "relationship-distribution"),
        variants=("category-comparison", "trend", "composition", "relationship"),
        silhouette="data-story", surface_density="light", closed_structure=True, native_visual=True,
        variant_quality={
            "category-comparison": {"layout_signature": "data-category-comparison", "visual_energy": "structured"},
            "trend": {"layout_signature": "data-trend", "visual_energy": "anchor"},
            "composition": {"layout_signature": "data-composition", "visual_energy": "structured"},
            "relationship": {"layout_signature": "data-relationship", "visual_energy": "structured"},
        },
        variant_help={variant: f"回答“{question.rstrip('？')}”" for variant, question in DATA_STORY_QUESTIONS.items()},
    ),
    "decision-matrix": _spec(
        "decision-matrix", family="comparison",
        use_when="三个候选方案需要沿三个共享准则用同向 1–5 分（5 更优）评估，并由程序汇总出唯一推荐项。",
        avoid_when="没有明确候选项、共享准则、评分依据，或需要权重、反向指标与更复杂的决策模型",
        aliases=("决策矩阵", "方案评分", "选型矩阵"), effects=("criteria-scoring",),
        silhouette="decision-table", surface_density="heavy", closed_structure=True, native_visual=True,
        variant_quality={"default": {"layout_signature": "decision-table", "visual_energy": "structured"}},
        variant_help={"default": "三项方案沿三项同向准则评分，程序汇总并突出唯一推荐项"},
    ),
    "evidence-matrix": _spec(
        "evidence-matrix", family="comparison",
        use_when="两至四个可核验主张需要与多条真实来源逐项对应，并区分支持、质疑和仅提供语境的证据关系。",
        avoid_when="没有可访问的真实来源、证据与主张无法逐项对应，或只需要展示一条引文",
        aliases=("证据矩阵", "主张证据表", "来源核验"), effects=("claim-evidence-matrix",),
        silhouette="evidence-matrix", surface_density="heavy", closed_structure=True, native_visual=True,
        variant_quality={"default": {"layout_signature": "claim-evidence-matrix", "visual_energy": "structured"}},
        variant_help={"default": "程序按主张生成列、按真实来源生成行，并绘制三种证据关系"},
    ),
    "gantt-roadmap": _spec(
        "gantt-roadmap", family="sequence",
        use_when="两至五条工作泳道需要放进三至八个有界时间段，任务跨期且可包含明确的前置依赖。",
        avoid_when="没有明确时间边界、任务只是无期限清单，或需要项目管理软件级的任意排期",
        aliases=("甘特路线图", "分泳道排期", "有界计划"), effects=("bounded-gantt-roadmap",),
        silhouette="gantt-roadmap", surface_density="heavy", closed_structure=True, native_visual=True,
        variant_quality={"default": {"layout_signature": "bounded-gantt-roadmap", "visual_energy": "anchor"}},
        variant_help={"default": "程序拥有时间轴、泳道、跨度与依赖连接；输入只引用时间段和任务 id"},
    ),
    "hierarchy-tree": _spec(
        "hierarchy-tree", family="canvas",
        use_when="四至九个对象存在一个根节点与清楚的父子归属，需要自上而下读出最多三层结构。",
        avoid_when="存在多个根、节点彼此断开、关系是任意网络，或需要超过三层的组织浏览器",
        aliases=("层级树", "父子结构", "归属树"), effects=("connected-hierarchy-tree",),
        silhouette="hierarchy-tree", surface_density="light", closed_structure=True, native_visual=True,
        variant_quality={"default": {"layout_signature": "connected-hierarchy-tree", "visual_energy": "anchor"}},
        variant_help={"default": "程序按 parent 关系生成层级、节点位置与连接线，可选说明缺省时节点自然收拢"},
    ),
    "dialogue-vs-task": _spec(
        "dialogue-vs-task", family="comparison",
        use_when="需要把开放式对话与可交付任务沿输出方式、步骤和结果直接对照。",
        avoid_when="两侧并非同一问题的两种工作方式，或没有三步任务路径",
        aliases=("对话与任务", "聊天对任务", "工作方式对比"), effects=("dialogue-task-contrast",),
        silhouette="dialogue-task", surface_density="heavy", closed_structure=True, native_visual=True,
    ),
    "dual-table-matrix": _spec(
        "dual-table-matrix", family="comparison",
        use_when="两组二维表格需要使用相同阅读节奏并列检查，最后收束为一个判断。",
        avoid_when="两表列数不同、单元格需要长段落，或需要计算型数据图",
        aliases=("双表矩阵", "并列表格", "两组清单矩阵"), effects=("paired-table-matrix",),
        silhouette="dual-table", surface_density="heavy", closed_structure=True, native_visual=True,
    ),
    "diagonal-split": _spec(
        "diagonal-split", family="bleed",
        use_when="内容表达转向、过渡、边界、对立或冲突，并有一张可裁切主视觉；斜切方向应跟随内容动势。",
        avoid_when="页面语气平静且无方向、过渡、边界或冲突关系",
        aliases=("斜切", "斜杠分区", "方向冲突", "转向", "过渡", "边界"), effects=("diagonal-bleed",),
        variants=("media-right", "media-left"), silhouette="bleed", frame_owner="media", media=True,
        variant_quality={
            "media-right": {"layout_signature": "diagonal-bleed", "visual_energy": "anchor"},
            "media-left": {"layout_signature": "diagonal-bleed", "visual_energy": "anchor"},
        },
        variant_help={"media-right": "斜切主视觉在右", "media-left": "斜切主视觉在左"},
    ),
    "editorial-canvas": _spec(
        "editorial-canvas", family="canvas",
        use_when="一段说明与素材、局部或批注共同组成展陈式页面。",
        avoid_when="只有一张普通照片与一句说明",
        aliases=("展陈", "素材画布", "局部批注"), effects=("editorial-canvas",),
        silhouette="canvas", surface_density="light", frame_owner="template", media=True,
    ),
    "editorial-feature": _spec(
        "editorial-feature", family="compound",
        use_when="一张主视觉与三个支撑信息共同解释一个核心判断；有第二张辅助图且需要更强编辑感时使用 hero-collage。",
        avoid_when="没有主视觉或三项支撑并不共同解释标题",
        aliases=("编辑式主视觉", "主视觉加三条支撑", "主副图拼贴", "融页概念图"),
        effects=("editorial-feature", "editorial-hero-collage", "page-blend-illustration"),
        variants=("default", "hero-collage"), silhouette="editorial-feature", surface_density="light",
        frame_owner="template", media=True, page_blend=True, closed_structure=True,
        variant_quality={
            "default": {"layout_signature": "editorial-feature", "visual_energy": "anchor"},
            "hero-collage": {"layout_signature": "editorial-hero-collage", "visual_energy": "anchor"},
        },
        variant_help={"default": "单主视觉与三条支撑", "hero-collage": "主图、辅助图与三项支撑共同形成编辑式主视觉"},
    ),
    "end": _spec(
        "end", family="focal",
        use_when="演示结束。line=一句刀；line-note=一句+余韵；line-artifact=一句+二维码/物件。",
        avoid_when="尚未完成论证", aliases=("结尾", "收束", "行动页"), effects=("closing-focal",),
        variants=("line", "line-note", "line-artifact"), silhouette="focal", frame_owner="template",
        variant_quality={
            "line": {"layout_signature": "focal-closing", "visual_energy": "anchor"},
            "line-note": {"layout_signature": "closing-aside", "visual_energy": "quiet"},
            "line-artifact": {"layout_signature": "closing-artifact", "visual_energy": "anchor"},
        },
        variant_help={"line": "一句话结束", "line-note": "一句话加余韵", "line-artifact": "一句话加二维码或物件"},
    ),
    "metric": _spec(
        "metric", family="focal",
        use_when="一个真实指标及其意义是页面焦点；delta 表达较前值变化，progress 表达当前值相对目标。",
        avoid_when="多个无共同口径的数字同等重要",
        aliases=("大数字", "指标", "单一数据", "指标变化", "目标进度"),
        effects=("numeric-focal", "numeric-delta", "target-progress"),
        variants=("default", "delta", "progress"), decorations=("dots",),
        silhouette="metric", surface_density="light", native_visual=True,
        variant_quality={
            "default": {"layout_signature": "metric-single", "visual_energy": "anchor"},
            "delta": {"layout_signature": "metric-delta", "visual_energy": "structured"},
            "progress": {"layout_signature": "metric-progress", "visual_energy": "structured"},
        },
        variant_help={
            "default": "一个指标及其口径是唯一焦点",
            "delta": "一个指标与较前值变化共同出现",
            "progress": "当前值与目标值共享口径，程序生成进度",
        },
    ),
    "photo-gradient": _spec(
        "photo-gradient", family="bleed",
        use_when="照片铺满页面并与少量文字自然融合；按主体空白选择文字落在左或右。",
        avoid_when="文字较多或主体落在文字区", aliases=("全屏照片", "照片铺底", "图上叠字", "满屏样式"),
        effects=("full-bleed", "text-overlay"), variants=("copy-left", "copy-right"),
        silhouette="bleed", frame_owner="media", media=True,
        variant_quality={
            "copy-left": {"layout_signature": "full-photo-overlay", "visual_energy": "anchor"},
            "copy-right": {"layout_signature": "full-photo-overlay", "visual_energy": "anchor"},
        },
        variant_help={"copy-left": "文字落在左侧渐变区", "copy-right": "文字落在右侧渐变区"},
    ),
    "photo-split": _spec(
        "photo-split", family="split",
        use_when="照片与解释文字权重接近；按阅读顺序选择媒体在左或右。",
        avoid_when="UI 截图或不可裁切材料", aliases=("照片分栏", "图文等权", "半屏照片"),
        effects=("balanced-photo",), variants=("media-right", "media-left"), silhouette="split",
        frame_owner="media", media=True,
        variant_quality={
            "media-right": {"layout_signature": "balanced-photo-split", "visual_energy": "anchor"},
            "media-left": {"layout_signature": "balanced-photo-split", "visual_energy": "anchor"},
        },
        variant_help={"media-right": "照片在右、文字在左", "media-left": "照片在左、文字在右"},
    ),
    "process-rail": _spec(
        "process-rail", family="sequence",
        use_when="六个带简短解释的步骤，或八个只需短标签的动作，组成一条完整流程总览。",
        avoid_when="六步需要长段落，或八步仍需要解释正文",
        aliases=("六步流程", "八步流程", "完整路径"), effects=("serpentine-sequence",),
        variants=("steps-8", "steps-6"), silhouette="rail", closed_structure=True,
        variant_quality={
            "steps-6": {"layout_signature": "serpentine-rail", "visual_energy": "anchor"},
            "steps-8": {"layout_signature": "serpentine-rail", "visual_energy": "anchor"},
        },
        variant_help={"steps-6": "两行折返的六步详解", "steps-8": "两行折返的八个短动作总览"},
    ),
    "project-card-grid": _spec(
        "project-card-grid", family="collection",
        use_when="六个项目、计划或资源需要以统一卡片结构组成可扫描的 2×3 集合。",
        avoid_when="项目不足六个、存在主次或步骤关系，或每项需要长篇叙述",
        aliases=("项目卡片网格", "六项目总览", "项目集合"), effects=("six-card-collection",),
        silhouette="project-grid", surface_density="heavy", closed_structure=True, native_visual=True,
    ),
    "quote": _spec(
        "quote", family="focal", use_when="一段真实引用或一句需要独立停留的原话是页面焦点。",
        avoid_when="没有可核验来源的改写句", aliases=("引言", "原话", "金句"), effects=("editorial-quote",),
        silhouette="focal",
    ),
    "quadrant": _spec(
        "quadrant", family="comparison",
        use_when="四组对象需要同时放进两个概念维度中定位，并且其中一个象限需要明确强调。",
        avoid_when="只有一个判断维度、对象需要精确数值坐标，或没有重点象限",
        aliases=("四象限", "二维矩阵", "优先级矩阵"), effects=("conceptual-quadrant",),
        silhouette="quadrant", surface_density="heavy", closed_structure=True, native_visual=True,
        variant_quality={"default": {"layout_signature": "conceptual-quadrant", "visual_energy": "structured"}},
        variant_help={"default": "四组内容按两个概念维度定位，并强调一个象限"},
    ),
    "recap": _spec(
        "recap", family="cards", use_when="一句收束判断由三条原则支撑。", avoid_when="没有总领判断",
        aliases=("总结", "三条原则", "结论回顾"), effects=("thesis-support",),
        variants=("thesis-left", "thesis-right"), decorations=("dots",),
        silhouette="editorial-list", surface_density="heavy",
        variant_quality={
            "thesis-left": {"layout_signature": "thesis-principles", "visual_energy": "structured"},
            "thesis-right": {"layout_signature": "thesis-principles", "visual_energy": "structured"},
        },
        variant_help={"thesis-left": "结论在左", "thesis-right": "结论在右"},
    ),
    "relationship-map": _spec(
        "relationship-map", family="canvas",
        use_when="一个核心对象与三至五个角色或要素存在明确的命名关系，需要看清每个外围节点如何连接中心。",
        avoid_when="不存在明确中心节点，关系只是顺序流程，或需要任意网络布局",
        aliases=("关系图", "中心关系", "角色网络"), effects=("hub-relationship",),
        silhouette="relationship-map", surface_density="light", closed_structure=True, native_visual=True,
        variant_quality={"default": {"layout_signature": "hub-relationship", "visual_energy": "anchor"}},
        variant_help={"default": "一个中心节点连接三至五个外围节点，source→target 表达方向，程序拥有布局与连线"},
    ),
    "section": _spec(
        "section", family="focal", use_when="内容确实进入一个新的章节。", avoid_when="没有真实章节变化",
        aliases=("章节页", "转场", "分隔页"), effects=("section-pause",), silhouette="focal",
    ),
    "split-visual": _spec(
        "split-visual", family="split",
        use_when="一张真实图片、插画或材料组合与正文并置；按信息权重选择均衡、视觉主导或文字主导。",
        avoid_when="图片值得全屏或需要浏览器壳",
        aliases=("图文并排", "配图说明", "通用分栏", "融页插画"),
        effects=("inset-media", "page-blend-illustration"),
        variants=("media-dominant", "balanced", "copy-dominant"), silhouette="split",
        surface_density="light", media=True, page_blend=True,
        variant_quality={
            "media-dominant": {"layout_signature": "inset-split", "visual_energy": "anchor"},
            "balanced": {"layout_signature": "inset-split", "visual_energy": "structured"},
            "copy-dominant": {"layout_signature": "inset-split", "visual_energy": "structured"},
        },
        variant_help={
            "media-dominant": "图片约占七栏", "balanced": "图文各半", "copy-dominant": "文字约占七栏",
        },
    ),
    "step-hero": _spec(
        "step-hero", family="sequence",
        use_when="一个关键步骤需要用大号序号、简短行动要点与一张融页视觉单独停留。",
        avoid_when="需要在一页总览多个步骤，或没有可支撑该步骤的视觉",
        aliases=("步骤主视觉", "单步大页", "关键步骤"), effects=("numbered-step-hero", "page-blend-illustration"),
        variants=("media-right", "media-left"), silhouette="step-hero", surface_density="light", frame_owner="none", media=True,
        page_blend=True, closed_structure=True,
        variant_quality={
            "media-right": {"layout_signature": "numbered-step-hero", "visual_energy": "anchor"},
            "media-left": {"layout_signature": "numbered-step-hero", "visual_energy": "anchor"},
        },
        variant_help={"media-right": "步骤视觉在右", "media-left": "步骤视觉在左"},
    ),
    "tabs": _spec(
        "tabs", family="comparison", use_when="同一对象的多个状态或视图需要切换式对照。",
        avoid_when="两个对象需要同时可见", aliases=("状态切换", "前后视图", "两个模式"),
        effects=("interactive-state",), decorations=("dots",), silhouette="state-panel", surface_density="heavy",
    ),
    "tier-stack": _spec(
        "tier-stack", family="canvas",
        use_when="四层内容存在稳定的筛选收窄或基础支撑关系；漏斗表达聚焦，金字塔表达递进。",
        avoid_when="四层只是并列清单，或不存在筛选收窄与基础支撑关系",
        aliases=("层级堆叠", "漏斗", "金字塔"), effects=("tier-funnel", "tier-pyramid"),
        variants=("funnel", "pyramid"), silhouette="tier-stack", surface_density="heavy", closed_structure=True,
        native_visual=True,
        variant_quality={
            "funnel": {"layout_signature": "tier-funnel", "visual_energy": "anchor"},
            "pyramid": {"layout_signature": "tier-pyramid", "visual_energy": "anchor"},
        },
        variant_help={"funnel": "从广泛输入逐层收窄到聚焦结果", "pyramid": "从宽阔基础逐层支撑到顶层结果"},
    ),
    "three-steps": _spec(
        "three-steps", family="sequence", use_when="三个连续动作构成可读完的短流程。",
        avoid_when="三项只是并列而非顺序", aliases=("三步", "短流程", "三个动作"), effects=("linear-sequence",),
        variants=("linear", "focus-middle"), decorations=("dots",), silhouette="step-grid",
        surface_density="light", closed_structure=True,
        variant_quality={
            "linear": {"layout_signature": "three-stage-spine", "visual_energy": "structured"},
            "focus-middle": {"layout_signature": "three-stage-spine", "visual_energy": "structured"},
        },
        variant_help={"linear": "三步连续推进", "focus-middle": "第二步是关键转折"},
    ),
    "timeline": _spec(
        "timeline", family="sequence", use_when="四个阶段沿时间推进，且每个阶段都需要一句解释。",
        avoid_when="没有时间或阶段推进", aliases=("时间线", "四阶段", "里程碑"), effects=("temporal-sequence",),
        silhouette="timeline", closed_structure=True,
    ),
    "catalog-board": _spec(
        "catalog-board", family="compound",
        use_when="四个分类下各有三个同构条目，需要在一页形成可浏览的结构化目录。",
        avoid_when="条目无法稳定分成四组或每组不是三项",
        aliases=("结构化目录", "知识地图", "分类展板"), effects=("catalog-density",),
        silhouette="catalog", surface_density="heavy", closed_structure=True,
    ),
    "case-study-board": _spec(
        "case-study-board", family="compound",
        use_when="真实案例需要同时展示证据、两个指标与一个核心洞察；没有截图但有真实数据时使用 chart。",
        avoid_when="没有真实证据、真实数据或明确洞察",
        aliases=("案例证据板", "项目复盘", "案例指标"), effects=("case-evidence", "native-chart"),
        variants=("evidence", "chart"), silhouette="case-board", surface_density="light",
        frame_owner="template", closed_structure=True, native_visual_variants=("chart",),
        variant_quality={
            "evidence": {"layout_signature": "case-evidence", "visual_energy": "anchor"},
            "chart": {"layout_signature": "case-chart", "visual_energy": "structured"},
        },
        variant_help={"evidence": "左侧展示真实截图或作品", "chart": "左侧由真实数值生成原生柱状图"},
    ),
    "annotated-showcase": _spec(
        "annotated-showcase", family="compound",
        use_when="一张真实界面、作品或材料需要用三个局部标注明确阅读重点。",
        avoid_when="标注无法对应图片中的明确位置",
        aliases=("标注式展示", "局部说明", "界面解读"), effects=("annotated-evidence",),
        silhouette="annotated", surface_density="light", frame_owner="template", media=True, closed_structure=True,
    ),
    "narrative-bento": _spec(
        "narrative-bento", family="compound",
        use_when="一个主判断、两项补充和一句收束需要形成明显主次，而不是平均卡片。",
        avoid_when="所有内容完全等权", aliases=("叙事饭盒", "一主两辅", "主次卡片"),
        effects=("narrative-bento",), silhouette="bento", surface_density="heavy", closed_structure=True,
    ),
    "sequence-gallery": _spec(
        "sequence-gallery", family="compound",
        use_when="三个连续画面共同呈现输入、变化与输出，每一步都有真实图片。",
        avoid_when="没有三个真实画面或步骤没有顺序", aliases=("序列画廊", "三帧过程", "前中后"),
        effects=("visual-sequence",), silhouette="gallery", surface_density="heavy",
        frame_owner="template", closed_structure=True,
    ),
    "process-cards": _spec(
        "process-cards", family="sequence",
        use_when="四个带解释的连续步骤需要横向读完；terminal-focus 用深色结果块明确收束。",
        avoid_when="步骤少于四个、超过四个，或每步只有短标签",
        aliases=("四步流程", "解释型流程", "交付路径", "结果收束"),
        effects=("four-step-cards", "terminal-focus"), variants=("linear", "terminal-focus"),
        silhouette="step-cards", surface_density="heavy", closed_structure=True,
        variant_quality={
            "linear": {"layout_signature": "four-step-cards", "visual_energy": "structured"},
            "terminal-focus": {"layout_signature": "four-step-terminal", "visual_energy": "anchor"},
        },
        variant_help={"linear": "四个解释型步骤等权推进", "terminal-focus": "第四步以深色结果块收束"},
    ),
}


COMPONENT_CONTRACTS = {
    name: {
        "use_when": spec.use_when,
        "variants": spec.variants,
        "decorations": spec.decorations,
    }
    for name, spec in COMPONENT_SPECS.items()
}

COMPONENT_QUALITY = {
    name: {
        "silhouette": spec.silhouette,
        "surface_density": spec.surface_density,
        "frame_owner": spec.frame_owner,
    }
    for name, spec in COMPONENT_SPECS.items()
}

VARIANT_QUALITY = {
    name: {variant: dict(values) for variant, values in spec.variant_quality.items()}
    for name, spec in COMPONENT_SPECS.items()
    if spec.variant_quality
}

TEMPLATE_FAMILIES = {name: spec.family for name, spec in COMPONENT_SPECS.items()}

TEMPLATE_DISCOVERY = {
    name: {
        "aliases": list(spec.aliases),
        "effects": list(spec.effects),
        "avoid_when": spec.avoid_when,
    }
    for name, spec in COMPONENT_SPECS.items()
}

VARIANT_HELP = {
    name: dict(spec.variant_help)
    for name, spec in COMPONENT_SPECS.items()
    if spec.variant_help
}

MEDIA_TEMPLATES = frozenset(name for name, spec in COMPONENT_SPECS.items() if spec.media)
PAGE_BLEND_TEMPLATES = frozenset(name for name, spec in COMPONENT_SPECS.items() if spec.page_blend)
CLOSED_STRUCTURE_TEMPLATES = frozenset(
    name for name, spec in COMPONENT_SPECS.items() if spec.closed_structure
)
