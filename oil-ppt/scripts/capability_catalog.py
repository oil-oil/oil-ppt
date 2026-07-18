#!/usr/bin/env python3
"""Compact capability map exposed by the oil-ppt CLI.

This file is deliberately executable knowledge: agents read the generated
contract instead of hunting through templates, runtime CSS, and references.
"""
from __future__ import annotations

from component_registry import TEMPLATE_DISCOVERY, VARIANT_HELP


FAMILY_GUIDANCE = {
    "focal": {
        "question": "这一页是否只需要观众记住一个判断、数字、原话或章节转折？",
        "reading_path": "单焦点",
    },
    "sequence": {
        "question": "内容是否有明确的先后、阶段、多步路径，或四个阶段构成闭环？",
        "reading_path": "顺序推进",
    },
    "cards": {
        "question": "多个信息单元是否共同支撑一个结论，并存在主次关系？",
        "reading_path": "主次聚合",
    },
    "collection": {
        "question": "多个同类项目或品牌是否需要按固定分组和统一单元快速扫描？",
        "reading_path": "集合扫描",
    },
    "comparison": {
        "question": "对象是否需要沿共享维度对照、评分决策、在两个概念维度中定位，或切换同一对象的状态？",
        "reading_path": "共享维度判断",
    },
    "data": {
        "question": "真实数值要回答哪一种关系：类别大小、时间变化、整体构成，还是两个指标的共同变化与分布？",
        "reading_path": "数据关系",
    },
    "canvas": {
        "question": "信息是否需要在开放画布中展陈、汇聚、被批注、围绕中心形成关系，或形成清楚的层级轮廓？",
        "reading_path": "空间关系",
    },
    "split": {
        "question": "真实素材与解释文字是否都承担主要信息？",
        "reading_path": "图文并置",
    },
    "bleed": {
        "question": "主视觉是否值得打破安全区，或内容是否表达方向、过渡、边界与冲突，需要一次强节奏变化？",
        "reading_path": "全屏视觉",
    },
    "compound": {
        "question": "这一页是否需要主叙事、支撑模块与元信息三个尺度共同工作？",
        "reading_path": "复合编辑",
    },
}


# Compact labels are owned by the preview UI. Internal identifiers stay stable
# for JSON and CLI contracts, while users only see readable Chinese names.
VARIANT_UI_LABELS = {
    "balanced": "均衡",
    "chart": "原生图表",
    "category-comparison": "类别大小",
    "composition": "整体构成",
    "copy-dominant": "文字主导",
    "copy-left": "文字在左",
    "copy-right": "文字在右",
    "default": "默认",
    "delta": "较前变化",
    "evidence": "真实证据",
    "feature-left": "左侧主卡",
    "feature-right": "右侧主卡",
    "feature-top": "上方主卡",
    "focus-left": "左侧重点",
    "focus-middle": "中间重点",
    "focus-right": "右侧重点",
    "funnel": "漏斗",
    "hero-collage": "主副图拼贴",
    "line": "单句收束",
    "line-artifact": "单句加物件",
    "line-note": "单句加注",
    "linear": "线性推进",
    "media": "图文开场",
    "media-dominant": "视觉主导",
    "media-evidence": "图片证据",
    "media-left": "视觉在左",
    "media-right": "视觉在右",
    "pyramid": "金字塔",
    "progress": "目标进度",
    "statement": "纯文字",
    "steps-6": "六步流程",
    "steps-8": "八步流程",
    "terminal-focus": "结果收束",
    "thesis-left": "结论在左",
    "thesis-right": "结论在右",
    "trend": "时间变化",
    "relationship": "指标关系",
    "visual-evidence": "图片证据",
}


DECOR_UI_LABELS = {
    "none": "无装饰",
    "dots": "点阵",
}


def template_ui_label(template: str) -> str:
    try:
        return str(TEMPLATE_DISCOVERY[template]["aliases"][0])
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(f"Missing Chinese UI label for template {template!r}.") from error


def variant_ui_label(variant: str) -> str:
    try:
        return VARIANT_UI_LABELS[variant]
    except KeyError as error:
        raise ValueError(f"Missing Chinese UI label for variant {variant!r}.") from error


def decor_ui_label(decor: str) -> str:
    try:
        return DECOR_UI_LABELS[decor]
    except KeyError as error:
        raise ValueError(f"Missing Chinese UI label for decoration {decor!r}.") from error


DECOR_GUIDANCE = {
    "none": "关系和素材已经足够时使用",
    "dots": "开放区域需要轻微节奏点阵",
}


# These capabilities are implemented by templates/runtime. Agents should know
# that they exist, but must not redraw their geometry or duplicate the CSS.
PROGRAM_OWNED_CAPABILITIES = {
    "layout": {
        "fixed_stage": "1920×1080 固定舞台与等比缩放",
        "grid": "12 列 minmax 网格、safe area 与防溢出",
        "fit": "标题和正文的受控适配",
    },
    "surface": {
        "tones": ["neutral", "soft", "accent", "ink"],
        "automatic": "容器底色、低对比灰色几何、局部纹理、圆角与图标容器由模板/runtime 组合；Agent 不写 CSS。",
        "detail_budget": "每页只保留一个主要装饰家族；主题色用于信息强调，装饰几何保持灰色、粗或面性。",
        "automatic_motifs": ["ring", "triangle", "slash"],
        "decorations": DECOR_GUIDANCE,
    },
    "page_atmosphere": {
        "backgrounds": ["grid-fade", "grid-wide", "soft-spotlight", "block-field"],
        "content_accents": ["highlight", "由节奏页 highlight 自动生成的背景大字", "quote"],
    },
    "media": {
        "compositions": [
            "inset split", "balanced photo split", "browser frame", "editorial canvas",
            "edge bleed", "diagonal bleed", "full-photo gradient",
        ],
        "automatic": "程序按真实版位比例规划素材：照片默认 cover 铺满，UI/文档 strict 素材用 contain 保真，概念插画和 self-framed 证据可 page-blend 融入页面；裁切、遮罩、渐变和 frame ownership 统一管理，避免通用灰框与双重外壳。Agent 只提供素材角色和它回答的问题。",
        "source_command": "scripts/oil-ppt media sources",
        "plan_command": "scripts/oil-ppt media plan <项目> --write",
        "frame_command": "scripts/oil-ppt media frame <截图> <输出.png> --project <项目> --ratio <ratio>",
        "render_html_command": "scripts/oil-ppt media render-html <作者文件.html> <项目/assets/视觉.png>",
        "verification_command": "scripts/oil-ppt media verify <项目>",
    },
    "interaction": {
        "navigation": ["键盘", "触摸滑动", "可选鼠标左右半页翻页", "进度条", "页码", "下一页预告"],
        "components": ["tabs"],
    },
    "data_expression": {
        "relationships": ["类别大小", "时间变化", "整体构成", "两指标关系与样本分布"],
        "automatic": "Agent 提交真实 JSON 数值、单位、结论与来源；程序统一生成坐标轴、标签、几何、主题色序列和数值格式，不使用 CDN。",
        "component": "data-story",
    },
    "metric_expression": {
        "variants": ["default", "delta", "progress"],
        "automatic": "Agent 提交指标口径；程序负责变化信息与目标进度的稳定布局和进度计算。",
        "component": "metric",
    },
    "relationship_expression": {
        "components": ["cycle", "quadrant", "tier-stack", "relationship-map"],
        "automatic": "Agent 只提交阶段、象限、轴、层级、节点与命名关系；程序拥有环形箭头、二维坐标、强调象限、漏斗/金字塔轮廓，以及中心关系图的布局与连线。",
    },
    "decision_expression": {
        "components": ["decision-matrix"],
        "automatic": "Agent 提交三个候选项、三个共享准则与 1–5 分；程序汇总总分并只突出唯一推荐项。",
    },
    "icons": {
        "family": "Phosphor regular",
        "usage": "内容图标统一使用 Phosphor regular，并由模板放入 oil-icon-frame；只在图标能缩短识别时间时使用。",
        "search_command": "scripts/oil-ppt icon search <语义>",
        "verification_command": "scripts/oil-ppt icon verify",
    },
    "compound_layouts": {
        "recipes": ["editorial-feature", "catalog-board", "case-study-board", "annotated-showcase", "narrative-bento", "sequence-gallery", "process-cards", "code-to-render"],
        "automatic": "模板固定主叙事、支撑模块与元信息的尺度关系；Agent 只提供结构化内容、真实数据和素材。",
    },
}


SELECTION_ORDER = (
    "先按内容关系选择 family，不按外观挑模板；量化内容只需回答它在比较类别、展示时间变化、解释整体构成，还是观察两指标关系。",
    "再看整套 silhouette 节奏；有真实素材时必须同时考虑 split 与 bleed 两类，并把出血节奏分布在前、中段，而不是只放结尾。",
    "最后选择 variant、decor、background 和可选强调字段；程序校验所有组合。",
    "生成 outline.json 后运行 plan；推荐、节奏与专用能力门禁由程序统一完成。",
)
