#!/usr/bin/env python3
"""Check required oil-ppt infrastructure without installing anything."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from build_deck import chrome_binary
from cdp_validate import validate_file
from component_contracts import COMPONENT_CONTRACTS
from design_quality import audit_summary
from fill_slots import set_slot_text_force
from media_assets import inspect_image
from media_frame import frame_media
from media_plan import build_media_plan
from outline_schema import validate_outline
from render_programmatic_visual import render_html_visual
from render_outline_review import EDITOR_FRAME_CSS, PREVIEW_SHELL_CSS, RUNTIME_CSS, RUNTIME_JS, prepared_slide, render, theme_css
from text_editor import EditorSession
from validate_skill import validate_skill


def mark(ok: bool) -> str:
    return "OK" if ok else "MISSING"


def smoke_slides() -> list[dict]:
    steps3 = [{"label": f"步骤{i}", "body": f"完成第{i}个动作"} for i in range(1, 4)]
    steps4 = [{"label": f"阶段{i}", "body": f"处理第{i}个阶段"} for i in range(1, 5)]
    cards = [{"title": f"要点{i}", "body": f"这是第{i}个要点"} for i in range(1, 4)]
    sides2 = [
        {"title": "方案 A", "evidence": ["assets/smoke.svg", "assets/smoke.svg"], "points": [{"title": "结构", "body": "保持结构清楚"}, {"title": "阅读", "body": "适合快速阅读"}]},
        {"title": "方案 B", "evidence": ["assets/smoke.svg", "assets/smoke.svg"], "points": [{"title": "重点", "body": "强调关键结论"}, {"title": "讲解", "body": "适合现场讲解"}]},
    ]
    sides3 = [
        {"title": "文档", "points": ["承载结构", "保留事实", "支持协作"]},
        {"title": "演示", "points": ["呈现重点", "引导观众", "支持讲解"]},
    ]
    compound_cards = [
        {"title": "关系", "body": "先明确内容之间的主次", "icon": "lightbulb"},
        {"title": "边界", "body": "把稳定动作交给程序", "icon": "code"},
        {"title": "判断", "body": "把选择留给真实需要", "icon": "check-circle"},
    ]
    catalog_groups = [
        {"title": f"分类{i}", "meta": f"Group {i}", "items": [{"title": f"条目{i}-{j}", "body": "简短说明"} for j in range(1, 4)]}
        for i in range(1, 5)
    ]
    image = "assets/smoke.svg"
    gallery_steps = [
        {"title": f"画面{i}", "body": f"第{i}个可见阶段", "image": image}
        for i in range(1, 4)
    ]
    return [
        {"id": "cover", "title": "稳定构建验证", "highlight": "稳定构建", "backdrop_text": "BUILD", "background": "soft-spotlight", "template": "cover", "variant": "statement", "decor": "none", "content": "一次覆盖全部组件"},
        {"id": "section", "title": "进入核心内容", "background": "block-field", "template": "section", "variant": "default", "decor": "none", "content": "接下来检查各类信息关系"},
        {"id": "quote", "title": "关键观点", "template": "quote", "variant": "default", "decor": "none", "quote": "真正稳定的设计来自清楚的内容关系。", "source": "oil-ppt"},
        {"id": "steps", "title": "三个连续动作", "background": "grid-wide", "template": "three-steps", "variant": "linear", "decor": "dots", "steps": steps3},
        {"id": "timeline", "title": "四个时间阶段", "template": "timeline", "variant": "default", "decor": "none", "steps": steps4},
        {"id": "split", "title": "视觉与解释并置", "background": "soft-spotlight", "template": "split-visual", "variant": "media-dominant", "decor": "none", "content": "主视觉承担大部分信息", "image": image, "media_frame": "content"},
        {"id": "rail", "title": "六步完成流程", "template": "process-rail", "variant": "steps-6", "decor": "none", "steps": [{"label": f"动作{i}", "body": f"说明第{i}步如何推进"} for i in range(1, 7)]},
        {"id": "cards", "title": "三个并列要点", "template": "card-trio", "variant": "media-evidence", "decor": "none", "content": "两组可见证据最终收束为一个判断", "cards": [{**cards[0], "images": [image, image]}, {**cards[1], "images": [image, image]}, cards[2]], "media_frame": "content"},
        {"id": "compare", "title": "两个方案直接对比", "content": "同一组标准需要放在两侧同时判断", "background": "block-field", "template": "comparison", "variant": "visual-evidence", "decor": "dots", "sides": sides2, "media_frame": "content"},
        {"id": "compare-list", "title": "两类产物逐项对齐", "template": "comparison-list", "variant": "balanced", "decor": "dots", "sides": sides3},
        {"id": "browser", "title": "真实界面是证据", "template": "browser-showcase", "variant": "media-right", "decor": "none", "content": "在浏览器外壳中展示界面", "image": image, "media_frame": "content"},
        {"id": "bleed", "title": "主视觉打破页面边界", "template": "bleed-split", "variant": "media-right", "decor": "none", "content": "为演示带来一次节奏变化", "image": image, "media_frame": "content"},
        {"id": "section-media", "title": "进入媒体组件", "template": "section", "variant": "default", "decor": "none", "content": "分段检查不同媒体轮廓"},
        {"id": "diagonal", "title": "方向感强化冲突", "template": "diagonal-split", "variant": "media-right", "decor": "none", "content": "斜线用于章节转折", "image": image, "media_frame": "content"},
        {"id": "photo-gradient", "title": "照片与文字融合", "template": "photo-gradient", "variant": "copy-left", "decor": "none", "content": "渐变保证文字区域稳定可读", "image": image, "media_frame": "content"},
        {"id": "photo-split", "title": "照片与解释并重", "template": "photo-split", "variant": "media-right", "decor": "none", "content": "两侧信息权重保持接近", "image": image, "media_frame": "content"},
        {"id": "metric", "title": "一个数字是页面焦点", "template": "metric", "variant": "default", "decor": "dots", "content": "用一句话解释数字的意义", "metric": {"value": "86", "unit": "%", "caption": "样本范围与时间口径保持一致"}},
        {"id": "recap", "title": "三条原则支撑一个结论", "template": "recap", "variant": "thesis-left", "decor": "dots", "content": "最后回到一个清楚的判断", "cards": cards},
        {"id": "tabs", "title": "同一对象的两个视角", "template": "tabs", "variant": "default", "decor": "dots", "sides": [{"title": "视角 A", "body": "从使用者任务理解界面"}, {"title": "视角 B", "body": "从系统实现理解界面"}]},
        {"id": "converge", "title": "两组输入汇聚为结果", "template": "converge", "variant": "default", "decor": "none", "groups": [{"title": "内容输入", "items": ["明确目标", "整理材料"]}, {"title": "设计输入", "items": ["选择组件", "准备视觉"]}], "outcome": "共同形成可交付的演示"},
        {"id": "editorial", "title": "展陈式页面保留编辑感", "template": "editorial-canvas", "variant": "default", "decor": "none", "content": "把材料、局部和批注放在同一个画布中", "image": image, "media_frame": "content"},
        {"id": "editorial-feature", "title": "主视觉与三条支撑并置", "template": "editorial-feature", "variant": "hero-collage", "decor": "none", "content": "主视觉承担证据，支撑模块解释判断依据", "image": image, "secondary_image": "assets/secondary.svg", "media_frame": "content", "cards": [{key: value for key, value in card.items() if key != "icon"} for card in compound_cards]},
        {"id": "catalog-board", "title": "把重复内容整理为知识地图", "template": "catalog-board", "variant": "default", "decor": "none", "metrics": [{"value": "12", "label": "条目"}, {"value": "4", "label": "分类"}, {"value": "1", "label": "体系"}], "groups": catalog_groups},
        {"id": "case-study-board", "title": "证据与结论共享同一页", "template": "case-study-board", "variant": "evidence", "decor": "none", "content": "主要证据占据页面主体", "image": image, "media_frame": "content", "metrics": [{"value": "12 周", "label": "周期"}, {"value": "+36%", "label": "变化"}], "insight": {"title": "核心判断", "body": "结论必须能回到证据", "icon": "chart-line"}},
        {"id": "annotated-showcase", "title": "同一份材料读出三个判断", "template": "annotated-showcase", "variant": "default", "decor": "none", "content": "标注只指出应该观察的局部", "image": image, "media_frame": "content", "annotations": [{"title": "入口", "body": "先看哪里"}, {"title": "主体", "body": "承接什么"}, {"title": "支撑", "body": "解释什么"}]},
        {"id": "narrative-bento", "title": "不同信息拥有不同权重", "template": "narrative-bento", "variant": "default", "decor": "none", "content": "页面通过面积和位置建立主次", "statement": "核心判断占据最大的连续区域", "statement_body": "其他模块补充证据和条件", "statement_icon": "lightbulb", "quote": "清楚的主次，本身就是设计感。", "quote_icon": "check-circle", "cards": compound_cards[:2]},
        {"id": "sequence-gallery", "title": "过程也值得被看见", "template": "sequence-gallery", "variant": "default", "decor": "none", "content": "三个真实画面共享框架", "steps": gallery_steps, "conclusion": "一致的容器，让变化更容易比较", "media_frame": "content"},
        {"id": "process-cards", "title": "四个动作组成稳定路径", "template": "process-cards", "variant": "terminal-focus", "decor": "none", "content": "每一步都有明确动作，最后一步用深色结果块收束", "steps": [{"title": "发现", "body": "先定位需要回答的问题", "icon": "magnifying-glass"}, {"title": "重排", "body": "让素材和结论形成对应", "icon": "image"}, {"title": "保存", "body": "把外部素材变成本地资产", "icon": "download-simple"}, {"title": "交付", "body": "离线打开仍然保持同样画面", "icon": "file-text"}], "measurements": [{"label": "来源", "value": "已记录"}, {"label": "尺寸", "value": "已检查"}, {"label": "授权", "value": "已核验"}, {"label": "交付", "value": "可离线"}], "measurement_note": "程序化验收", "measurement_meta": "构建时统一完成"},
        {"id": "end", "title": "稳定的事情交给程序", "template": "end", "variant": "line", "decor": "none"},
    ]


TEMPLATE_SEEDS = (
    "第一步", "Markdown", "00</span>", "点击上方标签切换内容",
    "用一句话说明这一章", "适合材料、局部、批注",
)


def render_component_matrix(root: Path, browser: str) -> int:
    base = {
        "title": "oil-ppt component matrix",
        "palette": "dusty-plum",
        "typography": "editorial",
        "shape": "crisp",
        "click_navigation": False,
    }
    seeds = {slide["template"]: slide for slide in smoke_slides()}
    css_parts: list[str] = []
    fragments: list[str] = []
    index = 0
    for template, contract in COMPONENT_CONTRACTS.items():
        for variant in contract["variants"]:
            for decor in contract["decorations"]:
                index += 1
                slide = json.loads(json.dumps(seeds[template], ensure_ascii=False))
                slide["id"] = re.sub(r"[^a-z0-9-]", "-", f"probe-{template}-{variant}-{decor}-{index}".lower())
                slide["variant"] = variant
                slide["decor"] = decor
                if template == "cover" and variant == "media":
                    slide.update({"image": "assets/smoke.svg", "media_frame": "content", "image_alt": "程序验证图"})
                if template == "end" and variant == "line-note":
                    slide.update({"aside": "保留一句收束说明", "aside_label": "NOTE"})
                if template == "end" and variant == "line-artifact":
                    slide.update({
                        "image": "assets/smoke.svg", "media_frame": "content", "image_alt": "程序验证图",
                        "artifact_title": "交付物", "artifact_body": "扫码或查看最终文件", "content": "交付保持清楚",
                    })
                if template == "process-rail" and variant == "steps-8":
                    slide["steps"] = [{"label": f"动作{i}"} for i in range(1, 9)]
                css, fragment = prepared_slide(slide, index)
                css_parts.append(css)
                fragments.append(fragment)
    matrix = root / "component-matrix.html"
    matrix.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        + RUNTIME_CSS + theme_css(base) + "\n".join(css_parts)
        + "</style></head><body data-oil-mode='preview'><div class='slide-preview-viewport'><div class='slide-preview-shell'><main class='slide-preview-stage'>"
        + "\n".join(fragments)
        + f"</main></div></div><script>{RUNTIME_JS}</script></body></html>",
        encoding="utf-8",
    )
    report = validate_file(browser, matrix, timeout=20)
    tokens = report.get("tokens") or {}
    theme_ok = (
        str(tokens.get("accent", "")).upper() == "#C8B8FF"
        and tokens.get("surfaceRadius") == "12px"
        and "Songti SC" in str(tokens.get("fontZh", ""))
    )
    if (
        report.get("status") != "ok"
        or report.get("slides") != index
        or report.get("brokenImages")
        or report.get("invalidBleeds")
        or not theme_ok
    ):
        raise RuntimeError(f"component matrix browser validation failed: {report}")
    matrix.unlink(missing_ok=True)
    return index


def verify_layout_containment_guard(root: Path, browser: str) -> None:
    probe = root / "invalid-layout-probe.html"
    probe.write_text(
        "<!doctype html><html data-oil-validated='ok'><body>"
        "<main class='deck-stage'><section class='oil-slide' data-slide-id='layout-probe'>"
        "<div class='slide-safe' style='position:relative;width:500px;height:300px'>"
        "<div data-layout style='display:grid;grid-template-columns:1fr 1fr;width:300px;height:100px'>"
        "<div style='height:100px'></div><div style='height:100px'></div><div style='height:100px'></div>"
        "</div></div></section></main></body></html>",
        encoding="utf-8",
    )
    report = validate_file(browser, probe, timeout=10)
    invalid_layouts = report.get("invalidLayouts") or []
    probe.unlink(missing_ok=True)
    if report.get("status") != "error" or not any(
        item.get("reason") == "layout-child-outside-container" for item in invalid_layouts
    ):
        raise RuntimeError(f"layout containment guard missed an implicit grid row: {report}")


def verify_optional_region_guard(root: Path, browser: str) -> None:
    probe = root / "empty-optional-region-probe.html"
    probe.write_text(
        "<!doctype html><html data-oil-validated='ok'><body>"
        "<main class='deck-stage'>"
        "<section class='oil-slide' data-slide-id='active-probe'><div class='slide-safe'>"
        "<div data-optional-region='filled'>内容</div>"
        "<div data-optional-region='explicitly-hidden' hidden style='width:200px;height:80px'></div>"
        "</div></section>"
        "<section class='oil-slide' data-slide-id='inactive-probe' style='visibility:hidden'><div class='slide-safe'>"
        "<div data-optional-region='footer' style='display:block;width:200px;height:80px'></div>"
        "</div></section></main></body></html>",
        encoding="utf-8",
    )
    report = validate_file(browser, probe, timeout=10)
    invalid = report.get("invalidOptionalRegions") or []
    probe.unlink(missing_ok=True)
    if report.get("status") != "error" or len(invalid) != 1 or not any(
        item.get("reason") == "empty-optional-region" and item.get("region") == "footer" for item in invalid
    ):
        raise RuntimeError(f"empty optional-region guard did not fire: {report}")

    slide = {
        "id": "process-collapse", "title": "没有附加测量区", "template": "process-cards", "variant": "linear", "decor": "none",
        "content": "可选字段缺省后，步骤卡片自动占满主体区域。",
        "steps": [{"title": f"步骤{i}", "body": f"完成第{i}个动作"} for i in range(1, 5)],
    }
    css, fragment = prepared_slide(slide, 1)
    positive = root / "process-cards-optional-collapse.html"
    positive.write_text(
        "<!doctype html><html data-oil-validated='ok'><head><style>"
        + RUNTIME_CSS + theme_css({"palette": "oil-yellow", "typography": "clean", "shape": "soft"}) + css
        + "</style></head><body data-oil-mode='preview'><main class='slide-preview-stage'>"
        + fragment + f"</main><script>{RUNTIME_JS}</script></body></html>",
        encoding="utf-8",
    )
    positive_report = validate_file(browser, positive, timeout=10)
    positive.unlink(missing_ok=True)
    if positive_report.get("status") != "ok" or positive_report.get("invalidOptionalRegions"):
        raise RuntimeError(f"process-cards optional collapse did not survive browser validation: {positive_report}")


def verify_specialized_capability_advice() -> None:
    summary = audit_summary({
        "media_policy": "text-only",
        "slides": [{
            "id": "generic-four-step",
            "title": "四步完成交付",
            "template": "timeline",
            "variant": "default",
            "decor": "none",
            "steps": [{"label": f"动作{i}", "body": f"完成第{i}个动作"} for i in range(1, 5)],
        }],
    })
    if summary.get("status") != "warning" or not any(
        item.get("code") == "specialized-capability-suggestion"
        and item.get("level") == "warning"
        and item.get("blocking") is False
        for item in summary.get("issues") or []
    ):
        raise RuntimeError(f"specialized capability advice did not remain non-blocking: {summary}")


def verify_regression_guards(entry: Path) -> None:
    templates = Path(__file__).resolve().parent.parent / "assets" / "templates"
    decorative_hairline = re.compile(
        r"border-(?:top|right|bottom|left):\s*1px"
        r"|(?:width|height):\s*(?:1|2)px;\s*background:\s*(?:var\(--border\)|color-mix\([^;}]*var\(--ink\))"
    )
    hairline_offenders = [
        path.name for path in templates.glob("*.html")
        if decorative_hairline.search(path.read_text(encoding="utf-8"))
    ]
    if hairline_offenders:
        raise RuntimeError(
            "block-first component templates reintroduced decorative gray hairlines: "
            + ", ".join(sorted(hairline_offenders))
        )
    section_source = (templates / "section.html").read_text(encoding="utf-8")
    if "repeating-linear-gradient" in section_source:
        raise RuntimeError("section reintroduced thin striped decoration instead of a cropped block geometry")

    rhythm_slide = {
        "id": "auto-backdrop", "title": "把重点留给重点", "highlight": "重点",
        "template": "section", "variant": "default", "decor": "none",
        "content": "背景大字应复用标题高亮。",
    }
    _, rhythm_fragment = prepared_slide(rhythm_slide, 1)
    if '<div class="oil-backdrop-text" aria-hidden="true">重点</div>' not in rhythm_fragment:
        raise RuntimeError("rhythm pages did not derive background type from the existing highlight")

    runtime_source = (Path(__file__).resolve().parent.parent / "assets" / "runtime" / "deck.css").read_text(encoding="utf-8")
    filler_source = (Path(__file__).resolve().parent / "fill_slots.py").read_text(encoding="utf-8")
    if "edge-slice" in runtime_source or "edge-slice" in filler_source:
        raise RuntimeError("repetitive accent edge slices must not return to automatic container styling")
    triangle_rule = re.search(r'\.oil-surface\[data-motif="triangle"\]::after\s*\{([^}]*)\}', runtime_source, re.S)
    ring_rule = re.search(r'\.oil-surface\[data-motif="ring"\]::after\s*\{([^}]*)\}', runtime_source, re.S)
    slash_rule = re.search(r'\.oil-surface\[data-motif="slash"\]::after\s*\{([^}]*)\}', runtime_source, re.S)
    if not triangle_rule or "clip-path:polygon" not in triangle_rule.group(1) or "mask:" in triangle_rule.group(1):
        raise RuntimeError("triangle motif must remain a quiet filled surface")
    if not ring_rule or "var(--accent)" in ring_rule.group(1) or "border:32px" not in ring_rule.group(1):
        raise RuntimeError("ring motif must remain thick and neutral")
    if not slash_rule or "repeating-linear-gradient" in slash_rule.group(1) or "clip-path:polygon" not in slash_rule.group(1):
        raise RuntimeError("slash motif must remain a single filled surface")

    def expect_outline_rejected(slide: dict, reason: str) -> None:
        deck = {
            "title": reason, "palette": "oil-yellow", "typography": "clean", "shape": "soft",
            "click_navigation": False, "media_policy": "text-only", "slides": [slide],
        }
        try:
            validate_outline(deck, templates)
        except SystemExit:
            return
        raise RuntimeError(reason)

    mutually_exclusive = subprocess.run(
        [sys.executable, str(entry), "contract", "--schema", "--list"],
        check=False,
        capture_output=True,
        text=True,
    )
    if mutually_exclusive.returncode == 0:
        raise RuntimeError("contract accepted multiple selector flags")

    schema_result = subprocess.run(
        [sys.executable, str(entry), "contract", "--schema", "--compact"],
        check=True,
        capture_output=True,
        text=True,
    )
    schema = json.loads(schema_result.stdout)
    definitions = schema.get("$defs") or {}
    slide_schema = (((schema.get("properties") or {}).get("slides") or {}).get("items") or {})
    slide_properties = slide_schema.get("properties") or {}
    if (
        not {
            "card", "plainCard", "iconCard", "evidenceCard", "decisionCard",
            "step", "stepBody", "stepIconBody", "stepMediaBody", "stepLabel",
            "side", "plainSide", "visualSide", "tabSide", "group", "convergeGroup", "measurement", "annotation",
        }.issubset(definitions)
        or set((slide_properties.get("metric") or {}).get("required") or ()) != {"value", "unit", "caption"}
        or not (slide_properties.get("cards") or {}).get("items")
    ):
        raise RuntimeError("public JSON Schema does not expose compound input structures")

    replaced = set_slot_text_force('<p data-slot="value"></p>', "value", r"C:\Users\oil\deck")
    if r"C:\Users\oil\deck" not in replaced:
        raise RuntimeError("slot filling corrupted backslashes in user text")

    nested = next(slide for slide in smoke_slides() if slide["id"] == "cards")
    nested = json.loads(json.dumps(nested, ensure_ascii=False))
    nested.update({"media_fit": "contain", "media_position": "top-left", "media_treatment": "mono"})
    _, nested_fragment = prepared_slide(nested, 1)
    if any(nested_fragment.count(token) != 4 for token in (
        'data-media-fit="contain"', 'data-media-position="top-left"', 'data-media-treatment="mono"',
    )):
        raise RuntimeError("nested media did not receive the slide-level crop and treatment contract")

    _, end_fragment = prepared_slide({
        "id": "end-note", "title": "收束", "template": "end", "variant": "line-note", "decor": "none",
        "content": "这句必须显示在余韵区",
    }, 1)
    if 'data-slot="aside"' not in end_fragment or "这句必须显示在余韵区" not in end_fragment:
        raise RuntimeError("end/line-note content was not mapped into its visible aside")

    rail = {
        "id": "rail-body", "title": "六步流程", "template": "process-rail", "variant": "steps-6", "decor": "none",
        "steps": [{"title": f"步骤{i}", "body": f"可见解释{i}"} for i in range(1, 7)],
    }
    _, rail_fragment = prepared_slide(rail, 1)
    if any(f"可见解释{i}" not in rail_fragment for i in range(1, 7)):
        raise RuntimeError("process-rail/steps-6 accepted body copy but did not render it")
    expect_outline_rejected(
        {
            "id": "rail-eight-body", "title": "八步流程", "template": "process-rail", "variant": "steps-8", "decor": "none",
            "steps": [{"title": f"步骤{i}", "body": "八步变体没有正文槽"} for i in range(1, 9)],
        },
        "process-rail/steps-8 accepted body copy that it cannot render",
    )

    process_without_optional = {
        "id": "process-clean", "title": "四步路径", "template": "process-cards", "variant": "linear", "decor": "none",
        "content": "没有图标和测量数据时仍然占满主体区域",
        "steps": [{"title": f"步骤{i}", "body": f"完成动作{i}"} for i in range(1, 5)],
    }
    validate_outline({
        "title": "optional collapse", "palette": "oil-yellow", "typography": "clean", "shape": "soft",
        "click_navigation": False, "media_policy": "text-only", "slides": [process_without_optional],
    }, templates)
    _, process_fragment = prepared_slide(process_without_optional, 1)
    if 'data-measurements="none"' not in process_fragment or 'data-icons="none"' not in process_fragment:
        raise RuntimeError("process-cards did not expose the programmatic optional-region collapse state")
    if not re.search(r'class="measurements"[^>]*\bhidden\b', process_fragment):
        raise RuntimeError("process-cards left its empty measurements region visible")

    partial_icons = json.loads(json.dumps(process_without_optional, ensure_ascii=False))
    partial_icons["steps"][0]["icon"] = "lightbulb"
    expect_outline_rejected(partial_icons, "process-cards accepted a partially populated icon group")

    measurements_without_context = json.loads(json.dumps(process_without_optional, ensure_ascii=False))
    measurements_without_context["measurements"] = [{"label": f"项{i}", "value": "完成"} for i in range(1, 5)]
    expect_outline_rejected(measurements_without_context, "process-cards accepted measurements without the note column content")

    expect_outline_rejected(
        {
            "id": "recap-hidden-media", "title": "总结", "template": "recap", "variant": "thesis-left", "decor": "dots",
            "content": "结论", "cards": [
                {"title": "一", "body": "说明", "images": ["assets/smoke.svg"]},
                {"title": "二", "body": "说明"}, {"title": "三", "body": "说明"},
            ],
        },
        "recap accepted nested media that it cannot render",
    )
    expect_outline_rejected(
        {
            "id": "tabs-hidden-evidence", "title": "视角", "template": "tabs", "variant": "default", "decor": "dots",
            "sides": [
                {"title": "一", "body": "说明", "evidence": ["assets/smoke.svg"]},
                {"title": "二", "body": "说明"},
            ],
        },
        "tabs accepted nested evidence that it cannot render",
    )
    expect_outline_rejected(
        {
            "id": "converge-object", "title": "汇聚", "template": "converge", "variant": "default", "decor": "none",
            "groups": [
                {"title": "输入一", "items": [{"title": "会被 stringify", "body": "错误"}, "普通文本"]},
                {"title": "输入二", "items": ["普通文本", "普通文本"]},
            ], "outcome": "结果",
        },
        "converge accepted object items that the filler would stringify",
    )
    expect_outline_rejected(
        {"id": "end-hidden", "title": "结束", "template": "end", "variant": "line", "decor": "none", "content": "不会显示"},
        "end/line accepted hidden supporting copy",
    )
    expect_outline_rejected(
        {
            "id": "tabs-alias", "title": "视角", "template": "tabs", "variant": "default", "decor": "dots",
            "sides": [{"h2": "旧标题", "p": "旧正文"}, {"h2": "旧标题", "p": "旧正文"}],
        },
        "nested legacy aliases passed validation even though fillers use title/label/body",
    )

    catalog_without_meta = next(slide for slide in smoke_slides() if slide["template"] == "catalog-board")
    catalog_without_meta = json.loads(json.dumps(catalog_without_meta, ensure_ascii=False))
    catalog_without_meta["groups"][0].pop("meta")
    expect_outline_rejected(catalog_without_meta, "catalog-board accepted a group with an empty metadata slot")

    invalid_metric = {
        "title": "metric guard", "palette": "oil-yellow", "typography": "clean", "shape": "soft",
        "click_navigation": False, "media_policy": "text-only", "slides": [{
            "id": "metric", "title": "指标", "template": "metric", "variant": "default", "decor": "dots",
            "content": "说明", "metric": {"value": "1234567890123456789012345678901234567890", "unit": "%", "caption": "口径"},
        }],
    }
    try:
        validate_outline(invalid_metric, templates)
    except SystemExit:
        pass
    else:
        raise RuntimeError("metric accepted a value that cannot fit its fixed component")
    valid_zero_metric = json.loads(json.dumps(invalid_metric, ensure_ascii=False))
    valid_zero_metric["slides"][0]["metric"] = {"value": 0, "unit": "%", "caption": "允许真实的零值"}
    validate_outline(valid_zero_metric, templates)
    invalid_boolean_metric = json.loads(json.dumps(valid_zero_metric, ensure_ascii=False))
    invalid_boolean_metric["slides"][0]["metric"]["value"] = False
    try:
        validate_outline(invalid_boolean_metric, templates)
    except SystemExit:
        pass
    else:
        raise RuntimeError("metric accepted a boolean value that the public Schema rejects")

    zero_slots = (
        ("catalog-board", "metric-value-1", "metrics"),
        ("case-study-board", "metric-value-1", "metrics"),
        ("process-cards", "measurement-value-1", "measurements"),
    )
    slides_by_template = {slide["template"]: slide for slide in smoke_slides()}
    for template, slot, collection in zero_slots:
        slide = json.loads(json.dumps(slides_by_template[template], ensure_ascii=False))
        slide[collection][0]["value"] = 0
        _, fragment = prepared_slide(slide, 1)
        if not re.search(rf'data-slot="{re.escape(slot)}"[^>]*>0</', fragment):
            raise RuntimeError(f"{template} swallowed a valid numeric zero in {slot}")

    invalid_measurements = {
        "title": "measurement guard", "palette": "oil-yellow", "typography": "clean", "shape": "soft",
        "click_navigation": False, "media_policy": "text-only", "slides": [{
            "id": "process", "title": "过程", "template": "process-cards", "variant": "linear", "decor": "none",
            "content": "说明", "steps": [{"title": f"步骤{i}", "body": "动作"} for i in range(1, 5)],
            "measurement_note": "不允许生成空白测量块",
        }],
    }
    try:
        validate_outline(invalid_measurements, templates)
    except SystemExit:
        pass
    else:
        raise RuntimeError("process-cards accepted measurement copy without measurements[4]")
    invalid_boolean_measurement = json.loads(json.dumps(slides_by_template["process-cards"], ensure_ascii=False))
    invalid_boolean_measurement["measurements"][0]["value"] = False
    invalid_boolean_deck = {
        "title": "boolean guard", "palette": "oil-yellow", "typography": "clean", "shape": "soft",
        "click_navigation": False, "media_policy": "text-only", "slides": [invalid_boolean_measurement],
    }
    try:
        validate_outline(invalid_boolean_deck, templates)
    except SystemExit:
        pass
    else:
        raise RuntimeError("process measurements accepted a boolean value that the public Schema rejects")

    no_media = audit_summary({
        "media_policy": "required",
        "slides": [
            {"id": "cover", "title": "开场", "template": "cover", "variant": "statement", "decor": "none"},
            {"id": "end", "title": "结束", "template": "end", "variant": "line", "decor": "none"},
        ],
    })
    if not any(item.get("code") == "media-required" for item in no_media.get("issues") or []):
        raise RuntimeError("short media-required decks can still pass with zero visible media")
    if any(item.get("code") == "media-coverage" for item in no_media.get("issues") or []):
        raise RuntimeError("zero-media decks report both media-required and media-coverage for the same defect")

    sparse_visual_slides = [
        {"id": "m1", "title": "媒体", "template": "split-visual", "variant": "balanced", "decor": "none", "image": "assets/smoke.svg", "media_frame": "content", "background": "soft-spotlight"},
        {"id": "m2", "title": "引用", "template": "quote", "variant": "default", "decor": "none", "background": "grid-wide"},
        {"id": "m3", "title": "三步", "template": "three-steps", "variant": "linear", "decor": "dots", "background": "block-field"},
        {"id": "m4", "title": "对比", "template": "comparison", "variant": "default", "decor": "dots", "background": "grid-fade"},
        {"id": "m5", "title": "指标", "template": "metric", "variant": "default", "decor": "dots", "background": "soft-spotlight"},
        {"id": "m6", "title": "总结", "template": "recap", "variant": "thesis-left", "decor": "dots", "background": "block-field"},
        {"id": "m7", "title": "时间", "template": "timeline", "variant": "default", "decor": "none", "background": "grid-wide"},
        {"id": "m8", "title": "叙事", "template": "narrative-bento", "variant": "default", "decor": "none", "background": "grid-fade"},
    ]
    sparse_media = audit_summary({"media_policy": "required", "slides": sparse_visual_slides})
    if not any(
        item.get("code") == "media-coverage"
        and item.get("level") == "warning"
        and item.get("blocking") is False
        for item in sparse_media.get("issues") or []
    ):
        raise RuntimeError("sparse media coverage did not remain visible as non-blocking advice")

    monotone_slides = json.loads(json.dumps(sparse_visual_slides, ensure_ascii=False))
    for slide in monotone_slides:
        slide.pop("image", None)
        slide.pop("media_frame", None)
        slide["background"] = "grid-fade"
    monotone = audit_summary({"media_policy": "text-only", "slides": monotone_slides})
    if not any(
        item.get("code") in {"background-monotony", "background-class-monotony"}
        and item.get("level") == "warning"
        and item.get("blocking") is False
        for item in monotone.get("issues") or []
    ):
        raise RuntimeError("perceptually monotone backgrounds did not remain non-blocking advice")

    same_class_slides = json.loads(json.dumps(monotone_slides, ensure_ascii=False))
    for index, slide in enumerate(same_class_slides):
        slide["background"] = "grid-fade" if index % 2 == 0 else "grid-wide"
    same_class = audit_summary({"media_policy": "text-only", "slides": same_class_slides})
    if not any(item.get("code") == "background-class-monotony" for item in same_class.get("issues") or []):
        raise RuntimeError("mixed preset names bypassed same-class background monotony")

    media_owned = [
        {
            "id": f"photo-{index}", "title": f"照片 {index}", "template": "photo-gradient",
            "variant": "copy-left", "decor": "none", "image": f"assets/photo-{index}.jpg", "media_frame": "content",
        }
        for index in range(1, 9)
    ]
    media_owned_audit = audit_summary({"media_policy": "required", "slides": media_owned})
    if any(str(item.get("code", "")).startswith("background-") for item in media_owned_audit.get("issues") or []):
        raise RuntimeError("media-owned full-screen images were treated as a monotonous runtime background")

    with tempfile.TemporaryDirectory(prefix="oil-ppt-state-regression-") as temp_dir:
        project = Path(temp_dir) / "project"
        subprocess.run([sys.executable, str(entry), "init", str(project)], check=True, capture_output=True, text=True)
        markdown = project / "outline.md"
        markdown.write_text("# 状态验证\n\n- 验证异常输入。\n", encoding="utf-8")
        subprocess.run(
            [sys.executable, str(entry), "confirm", str(project), "--stage", "outline", "--user-confirmed"],
            check=True, capture_output=True, text=True,
        )
        wrong_status = subprocess.run(
            [sys.executable, str(entry), "status", project.name, "--json"],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
        )
        wrong_payload = json.loads(wrong_status.stdout)
        if (
            wrong_payload.get("code") != "WRONG_PROJECT_PATH"
            or str(project.resolve()) not in str((wrong_payload.get("next") or {}).get("command") or "")
        ):
            raise RuntimeError("status misreported a repeated relative project name as an uninitialized project")
        wrong_build = subprocess.run(
            [sys.executable, str(entry), "build", project.name],
            cwd=project,
            check=False,
            capture_output=True,
            text=True,
        )
        if wrong_build.returncode == 0 or "resolved to" not in wrong_build.stderr:
            raise RuntimeError("build misreported a wrong project path as an outline confirmation failure")
        (project / "outline.json").write_text("[]\n", encoding="utf-8")
        bad_plan = subprocess.run(
            [sys.executable, str(entry), "plan", str(project)], check=False, capture_output=True, text=True,
        )
        if bad_plan.returncode == 0 or "top level" not in bad_plan.stderr or "Traceback" in bad_plan.stderr:
            raise RuntimeError("non-object outline JSON was not rejected cleanly")
        state_path = project / ".oil-ppt-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["outline_confirmation"] = ["invalid"]
        state_path.write_text(json.dumps(state), encoding="utf-8")
        stable_status = subprocess.run(
            [sys.executable, str(entry), "status", str(project), "--json"],
            check=True, capture_output=True, text=True,
        )
        if json.loads(stable_status.stdout).get("phase") != "needs_outline_confirmation":
            raise RuntimeError("malformed outline confirmation did not become a recoverable status")

        for current in (project / ".oil-ppt-state.json", project / ".oil-ppt-preview-outline.json", project / ".oil-ppt-build.json"):
            current.unlink(missing_ok=True)
        (project / ".oil-slides-state.json").write_text("{}\n", encoding="utf-8")
        (project / ".oil-slides-preview-outline.json").write_text("{}\n", encoding="utf-8")
        (project / ".oil-slides-build.json").write_text("{}\n", encoding="utf-8")
        subprocess.run(
            [sys.executable, str(entry), "status", str(project), "--json"],
            check=True, capture_output=True, text=True,
        )
        if any(project.joinpath(name).exists() for name in (
            ".oil-slides-state.json", ".oil-slides-preview-outline.json", ".oil-slides-build.json",
        )) or not all(project.joinpath(name).exists() for name in (
            ".oil-ppt-state.json", ".oil-ppt-preview-outline.json", ".oil-ppt-build.json",
        )):
            raise RuntimeError("legacy oil-slides state files were not migrated atomically")


def verify_responsive_stage(root: Path, browser: str) -> None:
    probe = root / "responsive-stage.html"
    probe.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        + RUNTIME_CSS
        + "</style></head><body data-oil-mode='preview'><div class='slide-preview-viewport'>"
        "<div class='slide-preview-shell'><main class='slide-preview-stage'>"
        "<section class='oil-slide active' data-slide-id='scale'><div class='slide-safe'></div></section>"
        "</main></div></div><script>"
        + RUNTIME_JS
        + "</script></body></html>",
        encoding="utf-8",
    )
    for viewport in ((1600, 600), (600, 1000)):
        report = validate_file(browser, probe, timeout=12, viewport=viewport)
        stage = report.get("stage") or {}
        window = report.get("viewport") or {}
        if report.get("status") != "ok" or not stage or not window:
            raise RuntimeError(f"responsive stage validation failed at {viewport}: {report}")
        if stage["width"] > window["width"] + 2 or stage["height"] > window["height"] + 2:
            raise RuntimeError(f"responsive stage was cropped at {viewport}: {report}")
        center_x = (stage["left"] + stage["right"]) / 2
        center_y = (stage["top"] + stage["bottom"]) / 2
        if abs(center_x - window["width"] / 2) > 3 or abs(center_y - window["height"] / 2) > 3:
            raise RuntimeError(f"responsive stage was not centered at {viewport}: {report}")
    probe.unlink(missing_ok=True)


def verify_media_policy_interface(entry: Path) -> None:
    example_result = subprocess.run(
        [sys.executable, str(entry), "contract", "--example"],
        check=True,
        capture_output=True,
        text=True,
    )
    example = json.loads(example_result.stdout)
    media_slides = [
        slide for slide in example.get("slides") or []
        if any(slide.get(field) for field in ("image", "media", "artifact_image"))
    ]
    if example.get("media_policy") != "required" or not media_slides:
        raise RuntimeError("public outline example must demonstrate the recommended media-required workflow")
    if not any(slide.get("media_question") for slide in media_slides):
        raise RuntimeError("public outline example media must state the question it answers")

    with tempfile.TemporaryDirectory(prefix="oil-ppt-media-policy-") as temp_dir:
        project = Path(temp_dir) / "project"
        subprocess.run(
            [sys.executable, str(entry), "init", str(project)],
            check=True,
            capture_output=True,
            text=True,
        )
        (project / "outline.md").write_text("# 已确认大纲\n\n- 只验证媒体策略接口。\n", encoding="utf-8")
        subprocess.run(
            [sys.executable, str(entry), "confirm", str(project), "--stage", "outline", "--user-confirmed"],
            check=True,
            capture_output=True,
            text=True,
        )
        text_only_with_media = json.loads(json.dumps(example, ensure_ascii=False))
        text_only_with_media["media_policy"] = "text-only"
        outline = project / "outline.json"
        outline.write_text(json.dumps(text_only_with_media, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        hidden_media = subprocess.run(
            [sys.executable, str(entry), "plan", str(project), "--user-confirmed-text-only"],
            check=False,
            capture_output=True,
            text=True,
        )
        if hidden_media.returncode == 0 or "media_policy is 'text-only'" not in hidden_media.stderr:
            raise RuntimeError("text-only policy accepted a slide that still declares media")

        text_only = dict(example)
        text_only["media_policy"] = "text-only"
        text_only["slides"] = [slide for slide in example["slides"] if slide not in media_slides]
        outline.write_text(json.dumps(text_only, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        blocked = subprocess.run(
            [sys.executable, str(entry), "plan", str(project)],
            check=False,
            capture_output=True,
            text=True,
        )
        if blocked.returncode == 0 or "--user-confirmed-text-only" not in blocked.stderr:
            raise RuntimeError("text-only planning did not require explicit user confirmation")
        status = subprocess.run(
            [sys.executable, str(entry), "status", str(project), "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        status_payload = json.loads(status.stdout)
        if status_payload.get("phase") != "needs_plan" or (status_payload.get("next") or {}).get("command") is not None:
            raise RuntimeError(f"unconfirmed text-only status exposed a blindly executable confirmation: {status_payload}")

        subprocess.run(
            [sys.executable, str(entry), "plan", str(project), "--user-confirmed-text-only"],
            check=True,
            capture_output=True,
            text=True,
        )
        changed = json.loads(outline.read_text(encoding="utf-8"))
        changed["title"] = "确认后又被修改"
        outline.write_text(json.dumps(changed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        invalidated = subprocess.run(
            [sys.executable, str(entry), "status", str(project), "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        invalidated_payload = json.loads(invalidated.stdout)
        if invalidated_payload.get("phase") != "needs_plan" or (invalidated_payload.get("next") or {}).get("command") is not None:
            raise RuntimeError("outline edits did not invalidate the text-only user confirmation")


def main() -> None:
    required_ok = True
    entry = Path(__file__).resolve().parent / "oil_ppt.py"

    validate_skill()
    verify_specialized_capability_advice()
    verify_regression_guards(entry)
    verify_media_policy_interface(entry)

    python_ok = sys.version_info >= (3, 10)
    required_ok &= python_ok
    print(f"[{mark(python_ok)}] Python {sys.version.split()[0]} (required: 3.10+)")

    browser = chrome_binary()
    browser_ok = bool(browser)
    if browser:
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as handle:
                handle.write("<!doctype html><html data-oil-validated='ok'><body><main class='deck-stage'><section class='oil-slide'></section></main></body></html>")
                smoke = Path(handle.name)
            try:
                browser_ok = validate_file(browser, smoke, timeout=10).get("status") == "ok"
            finally:
                smoke.unlink(missing_ok=True)
        except (OSError, RuntimeError):
            browser_ok = False
    print(f"[{mark(browser_ok)}] Chromium DOM engine (required for build-time loading and structure validation)")
    required_ok &= browser_ok
    if browser and browser_ok:
        print(f"     engine: {browser}")
    elif not browser:
        print("     install Chrome/Chromium/Edge/Brave, provide Chrome for Testing, or set CHROME_BIN")
    else:
        print("     browser was found but failed an isolated DevTools smoke test; try CHROME_BIN with Chrome for Testing")

    print("[INFO] Core decks need no npm, Playwright, or external image API; Chromium also renders local programmatic visuals.")

    if not browser_ok:
        raise SystemExit(1)

    smoke_ok = False
    matrix_ok = False
    matrix_count = 0
    try:
        with tempfile.TemporaryDirectory(prefix="oil-ppt-doctor-") as temp_dir:
            root = Path(temp_dir)
            outline = root / "outline.json"
            project = root
            assets = root / "assets"
            subprocess.run(
                [sys.executable, str(entry), "init", str(project)],
                check=True,
                capture_output=True,
                text=True,
            )
            (project / "outline.md").write_text("# 已确认的完整组件验证大纲\n\n- 用于 doctor 自动回归。\n", encoding="utf-8")
            subprocess.run(
                [sys.executable, str(entry), "confirm", str(project), "--stage", "outline", "--user-confirmed"],
                check=True,
                capture_output=True,
                text=True,
            )
            credits = project / "CREDITS.md"
            credits_text = "# 素材来源\n\n这份附加说明不属于构建器，但必须被保留。\n"
            credits.write_text(credits_text, encoding="utf-8")
            (assets / "smoke.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600"><rect width="800" height="600" fill="#f7f7f8"/><circle cx="400" cy="300" r="170" fill="#ffd54a"/><path d="M220 420L400 150l180 270z" fill="#292929" opacity=".82"/></svg>',
                encoding="utf-8",
            )
            (assets / "secondary.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480"><rect width="640" height="480" fill="#eef6ff"/><path d="M90 360L320 80l230 280z" fill="#9ed0ff"/></svg>',
                encoding="utf-8",
            )
            inspected = inspect_image(assets / "smoke.svg")
            if inspected["width"] != 800 or inspected["height"] != 600:
                raise RuntimeError("media inspector returned incorrect SVG dimensions")
            (assets / "broken.png").write_text("not an image", encoding="utf-8")
            try:
                inspect_image(assets / "broken.png")
            except ValueError:
                pass
            else:
                raise RuntimeError("media inspector accepted a corrupt PNG")
            (assets / "broken.png").unlink()
            if browser:
                authoring = assets / "programmatic.html"
                authoring.write_text(
                    '<!doctype html><html><style>*{box-sizing:border-box}body{margin:0;width:100vw;height:100vh;display:grid;place-items:center;background:#fff}.scene{width:70%;height:58%;border:2px solid #292929;background:linear-gradient(135deg,#fff,#fff8d8)}</style><body><div class="scene"></div></body></html>',
                    encoding="utf-8",
                )
                rendered = render_html_visual(authoring, assets / "programmatic.png", width=640, height=360)
                if rendered["width"] != 640 or rendered["height"] != 360:
                    raise RuntimeError("programmatic HTML renderer returned incorrect dimensions")
                framed = frame_media(
                    assets / "programmatic.png", assets / "programmatic-framed.png",
                    ratio="16:10", palette={"canvas": "#FFFFFF", "surface": "#F1F5F9", "accent_soft": "#F0F4FF"},
                )
                if framed["output"]["width"] != 1600 or framed["output"]["height"] != 1000:
                    raise RuntimeError("media frame returned the wrong slot dimensions")
                protected = assets / "protected.png"
                protected.write_bytes(b"keep-existing-asset")
                remote_authoring = assets / "programmatic-remote.html"
                remote_authoring.write_text(
                    "<!doctype html><body><script>fetch('https://example.invalid/remote.png')</script></body>",
                    encoding="utf-8",
                )
                try:
                    render_html_visual(remote_authoring, protected, width=640, height=360)
                except SystemExit:
                    pass
                else:
                    raise RuntimeError("programmatic HTML renderer allowed a remote request")
                if protected.read_bytes() != b"keep-existing-asset":
                    raise RuntimeError("failed programmatic render replaced an existing asset")
                verify_responsive_stage(root, browser)
                verify_layout_containment_guard(root, browser)
                verify_optional_region_guard(root, browser)
                matrix_count = render_component_matrix(root, browser)
                matrix_ok = matrix_count > 0
            smoke_deck_slides = smoke_slides()
            background_cycle = ("grid-fade", "block-field", "soft-spotlight")
            content_index = 0
            for slide in smoke_deck_slides:
                if slide["template"] in {"cover", "section", "end"}:
                    continue
                slide["background"] = background_cycle[content_index % len(background_cycle)]
                content_index += 1
            outline.write_text(
                json.dumps(
                    {
                        "title": "oil-ppt smoke",
                        "palette": {
                            "accent": "#9ED0FF", "accent_soft": "#F5FAFF", "accent_strong": "#292929",
                            "canvas": "#FDFCF8", "ink": "#303133",
                        },
                        "palette_source": "brand",
                        "typography": "clean",
                        "shape": "soft",
                        "click_navigation": False,
                        "slides": smoke_deck_slides,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            media_plan = build_media_plan(json.loads(outline.read_text(encoding="utf-8")), root, cli="scripts/oil-ppt")
            if media_plan["summary"]["count"] < 7 or media_plan["summary"]["ready"] != media_plan["summary"]["count"]:
                raise RuntimeError(f"media plan did not compile every smoke asset: {media_plan['summary']}")
            if any(
                item["adaptation"]["needed"]
                for item in media_plan["items"]
                if str(item["asset"]["relative_path"] or "").lower().endswith((".svg", ".gif"))
            ):
                raise RuntimeError("media plan generated an impossible frame command for SVG/GIF media")
            custom_media_plan = root / "assets" / "custom-media-plan.json"
            subprocess.run(
                [sys.executable, str(entry), "media", "plan", str(project), "--out", str(custom_media_plan)],
                check=True,
                capture_output=True,
                text=True,
            )
            if not custom_media_plan.is_file():
                raise RuntimeError("media plan --out did not write the requested output without --write")
            subprocess.run(
                [sys.executable, str(entry), "plan", str(project)],
                check=True,
                capture_output=True,
                text=True,
            )
            planned_status = subprocess.run(
                [sys.executable, str(entry), "status", str(project), "--json"],
                check=True,
                capture_output=True,
                text=True,
            )
            planned_payload = json.loads(planned_status.stdout)
            if (
                planned_payload.get("phase") != "needs_preview"
                or (planned_payload.get("next") or {}).get("action") != "start_editor"
            ):
                raise RuntimeError("the default preview workflow did not expose the editable preview as the next action")
            custom_preview = root / "review.html"
            subprocess.run(
                [sys.executable, str(entry), "preview", str(project), "--out", str(custom_preview), "--no-open"],
                check=True,
                capture_output=True,
                text=True,
            )
            custom_status = subprocess.run(
                [sys.executable, str(entry), "status", str(project), "--json"],
                check=True,
                capture_output=True,
                text=True,
            )
            custom_payload = json.loads(custom_status.stdout)
            if (
                custom_payload.get("phase") != "needs_preview_confirmation"
                or not (custom_payload.get("artifacts") or {}).get("preview")
                or not any(item.get("path") == str(custom_preview.resolve()) for item in custom_payload.get("blockers") or [])
            ):
                raise RuntimeError(f"custom preview path was not reflected in status: {custom_payload}")
            bypass = subprocess.run(
                [sys.executable, str(entry), "preview", str(outline), "--no-open"],
                check=False,
                capture_output=True,
                text=True,
            )
            if bypass.returncode == 0 or "project root" not in bypass.stderr:
                raise RuntimeError("preview accepted outline.json and bypassed the project confirmation boundary")
            outline_before_collision = outline.read_bytes()
            collision = subprocess.run(
                [sys.executable, str(entry), "preview", str(project), "--out", str(outline), "--no-open"],
                check=False,
                capture_output=True,
                text=True,
            )
            if collision.returncode == 0 or outline.read_bytes() != outline_before_collision:
                raise RuntimeError("preview output collision overwrote outline.json")
            subprocess.run(
                [sys.executable, str(entry), "preview", str(project), "--no-open"],
                check=True,
                capture_output=True,
                text=True,
            )
            preview_file = root / "预览.html"
            preview_text = preview_file.read_text(encoding="utf-8")
            if preview_text.count('class="page-card"') != len(smoke_slides()):
                raise RuntimeError("preview did not render every slide as a real template iframe")
            if 'id="slide-lightbox"' not in preview_text or 'class="preview-open"' not in preview_text:
                raise RuntimeError("preview did not expose the program-owned click-to-enlarge viewer")
            if 'class=&quot;hl&quot;' not in preview_text:
                raise RuntimeError("preview did not render the exposed highlight field")
            if 'class="rhythm-panel"' not in preview_text:
                raise RuntimeError("preview did not render the deck rhythm panel")
            if '<span title="版式">封面</span>' not in preview_text or '<span title="背景">柔光聚焦</span>' not in preview_text:
                raise RuntimeError("preview did not translate internal metadata into concise Chinese labels")
            base_edit_rule = re.search(r"\[data-edit-path\]\{([^}]*)\}", EDITOR_FRAME_CSS)
            hover_edit_rule = re.search(r'\[data-edit-path\]\[contenteditable="plaintext-only"\]:hover\{([^}]*)\}', EDITOR_FRAME_CSS)
            focus_rule = re.search(r"\[data-edit-path\]:focus\{([^}]*)\}", EDITOR_FRAME_CSS)
            if not focus_rule or "background" in focus_rule.group(1) or (hover_edit_rule and "background" in hover_edit_rule.group(1)):
                raise RuntimeError("text editor interaction states may only draw restrained outlines")
            if (
                not base_edit_rule
                or "dashed" not in base_edit_rule.group(1)
                or "transparent" not in base_edit_rule.group(1)
                or "box-shadow:none" not in base_edit_rule.group(1)
                or not hover_edit_rule
                or "var(--ink)" not in hover_edit_rule.group(1)
                or "oil-editor-focus-in" not in EDITOR_FRAME_CSS
            ):
                raise RuntimeError("text editor must stay clean at idle, show a gray dashed hover boundary, and use a themed focus state")
            if "oil-lightbox-in" not in PREVIEW_SHELL_CSS or "prefers-reduced-motion:reduce" not in PREVIEW_SHELL_CSS:
                raise RuntimeError("enlarged editor must animate in smoothly and respect reduced motion")
            for background in ("soft-spotlight", "block-field", "grid-wide"):
                if f'data-bg=&quot;{background}&quot;' not in preview_text:
                    raise RuntimeError(f"preview did not render background {background}")
            if any(seed in preview_text for seed in TEMPLATE_SEEDS):
                raise RuntimeError("preview leaked bundled template example copy")
            editor = EditorSession(project)
            authoring_text = render(
                editor.data,
                authoring=True,
                editor_token="doctor-token",
                editor_recovery_id=editor.recovery_id,
            )
            if "放大编辑" in authoring_text:
                raise RuntimeError("text editor still exposed the removed enlarge-edit button")
            if authoring_text.count('class="preview-open"') != len(smoke_slides()):
                raise RuntimeError("text editor did not make every thumbnail a click-to-open target")
            if authoring_text.count('tabindex="-1" aria-hidden="true"') != len(smoke_slides()):
                raise RuntimeError("text editor thumbnails remained keyboard-editable")
            if (
                "navigator.locks.request" not in authoring_text
                or "setInterval(renewLease" in authoring_text
                or "expires:Date.now" in authoring_text
            ):
                raise RuntimeError("text editor must use the browser-owned edit lock instead of a stale timeout lease")
            dialog_match = re.search(r'<dialog id="slide-lightbox".*?</dialog>', authoring_text, re.S)
            if not dialog_match or 'class="editor-toolbar"' not in dialog_match.group(0):
                raise RuntimeError("text editor controls were not contained inside the enlarged editor")
            try:
                EditorSession(project)
            except ValueError as error:
                if "already open" not in str(error):
                    raise RuntimeError(f"second text editor failed for the wrong reason: {error}") from error
            else:
                raise RuntimeError("a second text editor opened for the same project")
            edited_copy = "接下来检查全部信息关系，并允许用户直接校对文字"
            edit_state = editor.apply_edit("/slides/1/content", edited_copy)
            if not edit_state.get("draft") or not edit_state.get("can_undo"):
                raise RuntimeError("text editor did not persist an undoable draft")
            editor_status = subprocess.run(
                [sys.executable, str(entry), "status", str(project), "--json"],
                check=True, capture_output=True, text=True,
            )
            editor_payload = json.loads(editor_status.stdout)
            if editor_payload.get("phase") != "editing_in_progress" or (editor_payload.get("next") or {}).get("action") != "wait_for_editor":
                raise RuntimeError("active text editor did not become the unique next workflow step")
            draft_confirm = subprocess.run(
                [sys.executable, str(entry), "confirm", str(project), "--stage", "preview", "--user-confirmed"],
                check=False, capture_output=True, text=True,
            )
            if draft_confirm.returncode == 0 or "text-edit draft" not in draft_confirm.stderr:
                raise RuntimeError("preview confirmation did not reject an active text-edit draft")
            if editor.undo().get("draft"):
                raise RuntimeError("undoing back to the original outline left a redundant draft")
            if not editor.redo().get("draft"):
                raise RuntimeError("redo did not restore the text-edit draft")
            editor.discard()
            if (project / ".oil-ppt-edit-draft.json").exists():
                raise RuntimeError("discard did not remove the text-edit draft")
            editor.apply_edit("/slides/1/content", edited_copy)
            try:
                editor.finish([{"path": "/slides/1/content", "reason": "text-overflow"}], report_complete=True)
            except ValueError as error:
                if "text overflow" not in str(error):
                    raise RuntimeError(f"geometric text overflow failed for the wrong reason: {error}") from error
            else:
                raise RuntimeError("text editor accepted real geometric overflow")
            finish_state = editor.finish([{"path": "/slides/1/content", "reason": "text-budget"}], report_complete=True)
            if not finish_state.get("changed") or json.loads(outline.read_text(encoding="utf-8"))["slides"][1]["content"] != edited_copy:
                raise RuntimeError("finishing text editing did not promote the draft into outline.json")
            finished_status = subprocess.run(
                [sys.executable, str(entry), "status", str(project), "--json"],
                check=True, capture_output=True, text=True,
            )
            if json.loads(finished_status.stdout).get("phase") != "needs_preview_confirmation":
                raise RuntimeError("finishing text editing did not regenerate an unconfirmed formal preview")
            preview_state = root / ".oil-ppt-preview-outline.json"
            renderer_state = json.loads(preview_state.read_text(encoding="utf-8"))
            outside_contract = dict(renderer_state)
            outside_contract["preview"] = str(outline)
            outside_contract["preview_sha256"] = hashlib.sha256(outline.read_bytes()).hexdigest()
            outside_contract["confirmed"] = True
            preview_state.write_text(json.dumps(outside_contract), encoding="utf-8")
            protected_status = subprocess.run(
                [sys.executable, str(entry), "status", str(project), "--json"],
                check=True, capture_output=True, text=True,
            )
            if json.loads(protected_status.stdout).get("phase") != "needs_preview":
                raise RuntimeError("preview state accepted a protected non-HTML project file")
            preview_state.write_text(json.dumps(renderer_state), encoding="utf-8")
            renderer_state["renderer_sha256"] = "retired-renderer"
            preview_state.write_text(json.dumps(renderer_state), encoding="utf-8")
            renderer_status = subprocess.run(
                [sys.executable, str(entry), "status", str(project), "--json"],
                check=True,
                capture_output=True,
                text=True,
            )
            if json.loads(renderer_status.stdout).get("phase") != "needs_preview":
                raise RuntimeError("renderer changes did not invalidate preview confirmation")
            subprocess.run(
                [sys.executable, str(entry), "preview", str(project), "--no-open"],
                check=True,
                capture_output=True,
                text=True,
            )
            preview_state.write_text("[]\n", encoding="utf-8")
            malformed_status = subprocess.run(
                [sys.executable, str(entry), "status", str(project), "--json"],
                check=True,
                capture_output=True,
                text=True,
            )
            malformed_payload = json.loads(malformed_status.stdout)
            if malformed_payload.get("phase") != "needs_preview":
                raise RuntimeError(f"malformed preview state was not converted into a recoverable status: {malformed_payload}")
            subprocess.run(
                [sys.executable, str(entry), "preview", str(project), "--no-open"],
                check=True,
                capture_output=True,
                text=True,
            )
            unverified = subprocess.run(
                [sys.executable, str(entry), "confirm", str(project), "--stage", "preview"],
                check=False,
                capture_output=True,
                text=True,
            )
            if unverified.returncode == 0 or "--user-confirmed" not in unverified.stderr:
                raise RuntimeError("confirm did not require explicit user attestation")
            blocked = subprocess.run(
                [sys.executable, str(entry), "scaffold", str(project), str(outline)],
                check=False,
                capture_output=True,
                text=True,
            )
            if blocked.returncode == 0 or "not been confirmed" not in blocked.stderr:
                raise RuntimeError("scaffold did not enforce preview confirmation")
            subprocess.run(
                [sys.executable, str(entry), "confirm", str(project), "--stage", "preview", "--user-confirmed"],
                check=True,
                capture_output=True,
                text=True,
            )
            secondary_asset = assets / "secondary.svg"
            secondary_original = secondary_asset.read_text(encoding="utf-8")
            secondary_asset.write_text(secondary_original + "\n", encoding="utf-8")
            nested_invalidated = subprocess.run(
                [sys.executable, str(entry), "scaffold", str(project), str(outline)],
                check=False,
                capture_output=True,
                text=True,
            )
            if nested_invalidated.returncode == 0 or "media assets changed" not in nested_invalidated.stderr:
                raise RuntimeError("secondary_image changes did not invalidate preview confirmation")
            secondary_asset.write_text(secondary_original, encoding="utf-8")
            subprocess.run(
                [sys.executable, str(entry), "preview", str(project), "--no-open"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, str(entry), "confirm", str(project), "--stage", "preview", "--user-confirmed"],
                check=True,
                capture_output=True,
                text=True,
            )
            changed = json.loads(outline.read_text(encoding="utf-8"))
            changed["slides"][0]["title"] = "稳定构建验证 updated"
            outline.write_text(json.dumps(changed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            invalidated = subprocess.run(
                [sys.executable, str(entry), "scaffold", str(project), str(outline)],
                check=False,
                capture_output=True,
                text=True,
            )
            if invalidated.returncode == 0 or not any(
                message in invalidated.stderr for message in ("changed after preview", "not bound")
            ):
                raise RuntimeError("outline edits did not invalidate preview confirmation")
            subprocess.run(
                [sys.executable, str(entry), "plan", str(project)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, str(entry), "preview", str(project), "--no-open"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, str(entry), "confirm", str(project), "--stage", "preview", "--user-confirmed"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, str(entry), "scaffold", str(project), str(outline)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, str(entry), "build", str(project)],
                check=True,
                capture_output=True,
                text=True,
            )
            if not credits.is_file() or credits.read_text(encoding="utf-8") != credits_text:
                raise RuntimeError("build removed or modified an unrelated project-side documentation file")
            final = project / "演示文稿.html"
            smoke_ok = final.is_file()
            if smoke_ok:
                final_text = final.read_text(encoding="utf-8")
                smoke_ok = (
                    'data-validation="browser"' in final_text
                    and '<span class="hl">稳定构建</span>' in final_text
                    and "--slide-bg:#FDFCF8;" in final_text
                    and "--ink:#303133;" in final_text
                    and all(f'data-bg="{background}"' in final_text for background in ("soft-spotlight", "block-field", "grid-wide"))
                    and not any(seed in final_text for seed in TEMPLATE_SEEDS)
                    and 'id="oil-third-party-notices"' in final_text
                )
            if smoke_ok:
                first_config = json.loads((project / "deck.json").read_text(encoding="utf-8"))
                smoke_ok = (
                    first_config.get("palette", {}).get("canvas") == "#FDFCF8"
                    and first_config.get("palette", {}).get("ink") == "#303133"
                )
            if smoke_ok:
                build_state_path = project / ".oil-ppt-build.json"
                build_state = json.loads(build_state_path.read_text(encoding="utf-8"))
                renderer_sha256 = build_state.get("renderer_sha256")
                build_state["renderer_sha256"] = "retired-renderer"
                build_state_path.write_text(json.dumps(build_state), encoding="utf-8")
                stale_build_status = subprocess.run(
                    [sys.executable, str(entry), "status", str(project), "--json"],
                    check=True, capture_output=True, text=True,
                )
                if json.loads(stale_build_status.stdout).get("phase") != "needs_build":
                    raise RuntimeError("renderer changes did not invalidate the previously built final artifact")
                build_state["renderer_sha256"] = renderer_sha256
                build_state_path.write_text(json.dumps(build_state), encoding="utf-8")
            if smoke_ok:
                markdown = project / "outline.md"
                markdown.write_text(markdown.read_text(encoding="utf-8") + "\n- 用户补充了一个已确认判断。\n", encoding="utf-8")
                subprocess.run(
                    [sys.executable, str(entry), "confirm", str(project), "--stage", "outline", "--user-confirmed"],
                    check=True, capture_output=True, text=True,
                )
                markdown_status = subprocess.run(
                    [sys.executable, str(entry), "status", str(project), "--json"],
                    check=True, capture_output=True, text=True,
                )
                if json.loads(markdown_status.stdout).get("phase") != "needs_plan":
                    raise RuntimeError("Markdown changes did not invalidate plan, preview, and build evidence")
                subprocess.run(
                    [sys.executable, str(entry), "plan", str(project)],
                    check=True, capture_output=True, text=True,
                )
                replanned_status = subprocess.run(
                    [sys.executable, str(entry), "status", str(project), "--json"],
                    check=True, capture_output=True, text=True,
                )
                if json.loads(replanned_status.stdout).get("phase") != "needs_preview":
                    raise RuntimeError("replanning after a Markdown change reused the old preview confirmation")
            if smoke_ok:
                rebuilt = json.loads(outline.read_text(encoding="utf-8"))
                rebuilt["palette"] = "dusty-plum"
                rebuilt.pop("palette_source", None)
                rebuilt["typography"] = "editorial"
                rebuilt["shape"] = "crisp"
                rebuilt["click_navigation"] = True
                rebuilt["next_preview"] = False
                rebuilt["show_progress"] = False
                rebuilt["show_counter"] = False
                outline.write_text(json.dumps(rebuilt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                subprocess.run(
                    [sys.executable, str(entry), "plan", str(project)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    [sys.executable, str(entry), "preview", str(project), "--no-open"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    [sys.executable, str(entry), "confirm", str(project), "--stage", "preview", "--user-confirmed"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    [sys.executable, str(entry), "build", str(project)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                rebuilt_config = json.loads((project / "deck.json").read_text(encoding="utf-8"))
                rebuilt_final = final.read_text(encoding="utf-8")
                smoke_ok = (
                    rebuilt_config.get("palette", {}).get("accent") == "#C8B8FF"
                    and rebuilt_config.get("typography", {}).get("profile") == "editorial"
                    and rebuilt_config.get("shape", {}).get("profile") == "crisp"
                    and rebuilt_config.get("click_navigation") is True
                    and rebuilt_config.get("next_preview") is False
                    and rebuilt_config.get("show_progress") is False
                    and rebuilt_config.get("show_counter") is False
                    and "--accent:#C8B8FF;" in rebuilt_final
                    and "--surface-radius:12px;" in rebuilt_final
                    and '--font-zh:"Songti SC"' in rebuilt_final
                )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or str(error)).strip()
        print(f"[DETAIL] {detail}")
        smoke_ok = False
    except (OSError, RuntimeError, SystemExit) as error:
        print(f"[DETAIL] {error}")
        smoke_ok = False
    required_ok &= smoke_ok
    required_ok &= matrix_ok
    print(f"[{mark(matrix_ok)}] Browser render matrix covers {matrix_count} template × variant × decor combinations")
    print(f"[{mark(smoke_ok)}] Preview gate + end-to-end scaffold/build with root 演示文稿.html")

    if not required_ok:
        raise SystemExit(1)
    print("oil-ppt infrastructure is ready.")


if __name__ == "__main__":
    main()
