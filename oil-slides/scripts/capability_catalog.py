#!/usr/bin/env python3
"""Compact capability map exposed by the oil-ppt CLI.

This file is deliberately executable knowledge: agents read the generated
contract instead of hunting through templates, runtime CSS, and references.
"""
from __future__ import annotations


FAMILY_GUIDANCE = {
    "focal": {
        "question": "这一页是否只需要观众记住一个判断、数字、原话或章节转折？",
        "reading_path": "单焦点",
    },
    "sequence": {
        "question": "内容是否有明确的先后、阶段或多步路径？",
        "reading_path": "顺序推进",
    },
    "cards": {
        "question": "多个信息单元是否共同支撑一个结论，并存在主次关系？",
        "reading_path": "主次聚合",
    },
    "comparison": {
        "question": "两个对象是否需要沿同一维度对照，或同一对象是否需要切换状态？",
        "reading_path": "左右对照",
    },
    "canvas": {
        "question": "信息是否需要在开放画布中展陈、汇聚或被批注？",
        "reading_path": "空间关系",
    },
    "split": {
        "question": "真实素材与解释文字是否都承担主要信息？",
        "reading_path": "图文并置",
    },
    "bleed": {
        "question": "主视觉是否值得打破安全区，承担一次全屏或强方向的节奏变化？",
        "reading_path": "全屏视觉",
    },
    "compound": {
        "question": "这一页是否需要主叙事、支撑模块与元信息三个尺度共同工作？",
        "reading_path": "复合编辑",
    },
}


TEMPLATE_DISCOVERY = {
    "cover": {"aliases": ["封面", "开场", "首屏"], "effects": ["opening-focal"], "avoid_when": "普通内容页"},
    "end": {"aliases": ["结尾", "收束", "行动页"], "effects": ["closing-focal"], "avoid_when": "尚未完成论证"},
    "section": {"aliases": ["章节页", "转场", "分隔页"], "effects": ["section-pause"], "avoid_when": "没有真实章节变化"},
    "quote": {"aliases": ["引言", "原话", "金句"], "effects": ["editorial-quote"], "avoid_when": "没有可核验来源的改写句"},
    "metric": {"aliases": ["大数字", "指标", "单一数据"], "effects": ["numeric-focal"], "avoid_when": "多个数字同等重要"},
    "three-steps": {"aliases": ["三步", "短流程", "三个动作"], "effects": ["linear-sequence"], "avoid_when": "三项只是并列而非顺序"},
    "timeline": {"aliases": ["时间线", "四阶段", "里程碑"], "effects": ["temporal-sequence"], "avoid_when": "没有时间或阶段推进"},
    "process-rail": {"aliases": ["六步流程", "八步流程", "完整路径"], "effects": ["serpentine-sequence"], "avoid_when": "每步需要长解释"},
    "card-trio": {"aliases": ["一主两辅", "三块卡片", "饭盒卡片"], "effects": ["feature-support"], "avoid_when": "三项完全等权或存在顺序"},
    "recap": {"aliases": ["总结", "三条原则", "结论回顾"], "effects": ["thesis-support"], "avoid_when": "没有总领判断"},
    "comparison": {"aliases": ["二选一", "两方案", "左右对比"], "effects": ["paired-comparison"], "avoid_when": "两侧维度不同"},
    "comparison-list": {"aliases": ["逐项对照", "责任边界", "对比清单"], "effects": ["aligned-comparison"], "avoid_when": "每侧不足三项或没有共享维度"},
    "tabs": {"aliases": ["状态切换", "前后视图", "两个模式"], "effects": ["interactive-state"], "avoid_when": "两个对象需要同时可见"},
    "converge": {"aliases": ["汇聚", "合流", "输入到结果"], "effects": ["merge-diagram"], "avoid_when": "内容是顺序流程"},
    "editorial-canvas": {"aliases": ["展陈", "素材画布", "局部批注"], "effects": ["editorial-canvas"], "avoid_when": "只有一张普通照片与一句说明"},
    "split-visual": {"aliases": ["图文并排", "配图说明", "通用分栏"], "effects": ["inset-media"], "avoid_when": "图片值得全屏或需要浏览器壳"},
    "photo-split": {"aliases": ["照片分栏", "图文等权", "半屏照片"], "effects": ["balanced-photo"], "avoid_when": "UI 截图或不可裁切材料"},
    "browser-showcase": {"aliases": ["网页截图", "产品界面", "浏览器壳"], "effects": ["browser-frame"], "avoid_when": "窗口语境本身不是证据"},
    "bleed-split": {"aliases": ["边缘出血", "破框主视觉", "半屏铺满"], "effects": ["edge-bleed"], "avoid_when": "素材不可裁切或已有重要外框"},
    "diagonal-split": {"aliases": ["斜切", "斜杠分区", "方向冲突"], "effects": ["diagonal-bleed"], "avoid_when": "页面语气平静且无方向关系"},
    "photo-gradient": {"aliases": ["全屏照片", "照片铺底", "图上叠字", "满屏样式"], "effects": ["full-bleed", "text-overlay"], "avoid_when": "文字较多或主体落在文字区"},
    "editorial-feature": {"aliases": ["编辑式主视觉", "主视觉加三条支撑"], "effects": ["editorial-feature"], "avoid_when": "没有主视觉或三项支撑并不共同解释标题"},
    "catalog-board": {"aliases": ["结构化目录", "知识地图", "分类展板"], "effects": ["catalog-density"], "avoid_when": "条目无法稳定分成四组或每组不是三项"},
    "case-study-board": {"aliases": ["案例证据板", "项目复盘", "案例指标"], "effects": ["case-evidence", "native-chart"], "avoid_when": "没有真实证据、真实数据或明确洞察"},
    "annotated-showcase": {"aliases": ["标注式展示", "局部说明", "界面解读"], "effects": ["annotated-evidence"], "avoid_when": "标注无法对应图片中的明确位置"},
    "narrative-bento": {"aliases": ["叙事饭盒", "一主两辅", "主次卡片"], "effects": ["narrative-bento"], "avoid_when": "所有内容完全等权"},
    "sequence-gallery": {"aliases": ["序列画廊", "三帧过程", "前中后"], "effects": ["visual-sequence"], "avoid_when": "没有三个真实画面或步骤没有顺序"},
}


VARIANT_HELP = {
    "bleed-split": {"media-right": "主视觉从右侧出血", "media-left": "主视觉从左侧出血", "default": "兼容名，等同 media-right"},
    "browser-showcase": {"media-right": "界面证据在右", "media-left": "界面证据在左", "default": "兼容名，等同 media-right"},
    "cover": {"statement": "纯大字开场", "media": "标题与真实主视觉共同开场"},
    "end": {"line": "一句话结束", "line-note": "一句话加余韵", "line-artifact": "一句话加二维码或物件"},
    "diagonal-split": {"media-right": "斜切主视觉在右", "media-left": "斜切主视觉在左", "default": "兼容名，等同 media-right"},
    "card-trio": {"feature-left": "左侧纵向主卡", "feature-right": "右侧纵向主卡", "feature-top": "上方横向总领、下方两项支撑"},
    "comparison-list": {"focus-right": "右侧结论更重要", "focus-left": "左侧结论更重要", "balanced": "两侧完全等权"},
    "process-rail": {"steps-6": "两行折返的六步总览", "steps-8": "两行折返的八步总览"},
    "photo-gradient": {"copy-left": "文字落在左侧渐变区", "copy-right": "文字落在右侧渐变区", "default": "兼容名，等同 copy-left"},
    "photo-split": {"media-right": "照片在右、文字在左", "media-left": "照片在左、文字在右", "default": "兼容名，等同 media-right"},
    "recap": {"thesis-left": "结论在左", "thesis-right": "结论在右"},
    "split-visual": {"media-dominant": "图片约占七栏", "balanced": "图文各半", "copy-dominant": "文字约占七栏", "default": "兼容名，等同 media-dominant"},
    "three-steps": {"linear": "三步连续推进", "focus-middle": "第二步是关键转折"},
    "case-study-board": {"evidence": "左侧展示真实截图或作品", "chart": "左侧由真实数值生成原生柱状图"},
}


DECOR_GUIDANCE = {
    "none": "关系和素材已经足够时使用",
    "dots": "开放区域需要轻微节奏点阵",
    "corner-grid": "结构页需要局部网格坐标感",
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
        "automatic": "容器底色、细纹理、矢量 motif、边框与圆角由模板/runtime 组合；Agent 不写 CSS。",
        "automatic_motifs": ["ring", "triangle", "slash", "plot"],
        "decorations": DECOR_GUIDANCE,
    },
    "page_atmosphere": {
        "backgrounds": ["grid-fade", "grid-wide", "soft-spotlight", "block-field"],
        "content_accents": ["highlight", "backdrop_text", "quote"],
    },
    "media": {
        "compositions": [
            "inset split", "balanced photo split", "browser frame", "editorial canvas",
            "edge bleed", "diagonal bleed", "full-photo gradient",
        ],
        "automatic": "槽位比例、适配、裁切、遮罩、渐变和 frame ownership 由程序管理；Agent 提供真实素材及其角色和回答的问题。",
        "source_command": "scripts/oil-slides media sources",
        "plan_command": "scripts/oil-slides media plan <项目> --write",
        "frame_command": "scripts/oil-slides media frame <截图> <输出.png> --project <项目> --ratio <ratio>",
        "render_html_command": "scripts/oil-slides media render-html <作者文件.html> <项目/assets/视觉.png>",
        "verification_command": "scripts/oil-slides media verify <项目>",
    },
    "interaction": {
        "navigation": ["键盘", "触摸滑动", "可选鼠标左右半页翻页", "进度条", "页码", "下一页预告"],
        "components": ["tabs"],
    },
    "icons": {
        "family": "Phosphor regular",
        "usage": "内容图标统一使用 Phosphor regular，并由模板放入 oil-icon-frame；只在图标能缩短识别时间时使用。",
        "search_command": "scripts/oil-slides icon search <语义>",
        "verification_command": "scripts/oil-slides icon verify",
    },
    "compound_layouts": {
        "recipes": ["editorial-feature", "catalog-board", "case-study-board", "annotated-showcase", "narrative-bento", "sequence-gallery"],
        "automatic": "模板固定主叙事、支撑模块与元信息的尺度关系；Agent 只提供结构化内容、真实数据和素材。",
    },
}


SELECTION_ORDER = (
    "先按内容关系选择 family，不按外观挑模板。",
    "再看整套 silhouette 节奏；有真实素材时必须同时考虑 split 与 bleed 两类。",
    "最后选择 variant、decor、background 和可选强调字段；程序校验所有组合。",
    "生成 outline.json 后运行 recommend 与 audit；高置信专用能力和整套节奏都在程序必经路径复核。",
)
