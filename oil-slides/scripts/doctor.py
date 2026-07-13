#!/usr/bin/env python3
"""Check required oil-ppt infrastructure without installing anything."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from build_deck import chrome_binary
from cdp_validate import validate_file
from component_contracts import COMPONENT_CONTRACTS
from media_assets import inspect_image
from media_frame import frame_media
from media_plan import build_media_plan
from render_programmatic_visual import render_html_visual
from render_outline_review import RUNTIME_CSS, RUNTIME_JS, prepared_slide, theme_css
from validate_skill import validate_skill


def mark(ok: bool) -> str:
    return "OK" if ok else "MISSING"


def smoke_slides() -> list[dict]:
    steps3 = [{"label": f"步骤{i}", "body": f"完成第{i}个动作"} for i in range(1, 4)]
    steps4 = [{"label": f"阶段{i}", "body": f"处理第{i}个阶段"} for i in range(1, 5)]
    cards = [{"title": f"要点{i}", "body": f"这是第{i}个要点"} for i in range(1, 4)]
    sides2 = [
        {"title": "方案 A", "points": ["保持结构清楚", "适合快速阅读"]},
        {"title": "方案 B", "points": ["强调关键结论", "适合现场讲解"]},
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
        {"title": f"分类{i}", "subtitle": f"Group {i}", "items": [{"title": f"条目{i}-{j}", "body": "简短说明"} for j in range(1, 4)]}
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
        {"id": "split", "title": "视觉与解释并置", "background": "soft-spotlight", "template": "split-visual", "variant": "default", "decor": "none", "content": "主视觉承担大部分信息", "image": image, "media_frame": "content"},
        {"id": "rail", "title": "六步完成流程", "template": "process-rail", "variant": "steps-6", "decor": "none", "steps": [{"label": f"动作{i}"} for i in range(1, 7)]},
        {"id": "cards", "title": "三个并列要点", "template": "card-trio", "variant": "feature-left", "decor": "none", "cards": cards},
        {"id": "compare", "title": "两个方案直接对比", "background": "block-field", "template": "comparison", "variant": "default", "decor": "corner-grid", "sides": sides2},
        {"id": "compare-list", "title": "两类产物逐项对齐", "template": "comparison-list", "variant": "balanced", "decor": "corner-grid", "sides": sides3},
        {"id": "browser", "title": "真实界面是证据", "template": "browser-showcase", "variant": "default", "decor": "none", "content": "在浏览器外壳中展示界面", "image": image, "media_frame": "content"},
        {"id": "bleed", "title": "主视觉打破页面边界", "template": "bleed-split", "variant": "default", "decor": "none", "content": "为演示带来一次节奏变化", "image": image, "media_frame": "content"},
        {"id": "section-media", "title": "进入媒体组件", "template": "section", "variant": "default", "decor": "none", "content": "分段检查不同媒体轮廓"},
        {"id": "diagonal", "title": "方向感强化冲突", "template": "diagonal-split", "variant": "default", "decor": "none", "content": "斜线用于章节转折", "image": image, "media_frame": "content"},
        {"id": "photo-gradient", "title": "照片与文字融合", "template": "photo-gradient", "variant": "default", "decor": "none", "content": "渐变保证文字区域稳定可读", "image": image, "media_frame": "content"},
        {"id": "photo-split", "title": "照片与解释并重", "template": "photo-split", "variant": "default", "decor": "none", "content": "两侧信息权重保持接近", "image": image, "media_frame": "content"},
        {"id": "metric", "title": "一个数字是页面焦点", "template": "metric", "variant": "default", "decor": "corner-grid", "content": "用一句话解释数字的意义", "metric": {"value": "86", "unit": "%", "caption": "样本范围与时间口径保持一致"}},
        {"id": "recap", "title": "三条原则支撑一个结论", "template": "recap", "variant": "thesis-left", "decor": "dots", "content": "最后回到一个清楚的判断", "cards": cards},
        {"id": "tabs", "title": "同一对象的两个视角", "template": "tabs", "variant": "default", "decor": "dots", "sides": [{"title": "视角 A", "body": "从使用者任务理解界面"}, {"title": "视角 B", "body": "从系统实现理解界面"}]},
        {"id": "converge", "title": "两组输入汇聚为结果", "template": "converge", "variant": "default", "decor": "none", "groups": [{"title": "内容输入", "items": ["明确目标", "整理材料"]}, {"title": "设计输入", "items": ["选择组件", "准备视觉"]}], "outcome": "共同形成可交付的演示"},
        {"id": "editorial", "title": "展陈式页面保留编辑感", "template": "editorial-canvas", "variant": "default", "decor": "none", "content": "把材料、局部和批注放在同一个画布中", "image": image, "media_frame": "content"},
        {"id": "editorial-feature", "title": "主视觉与三条支撑并置", "template": "editorial-feature", "variant": "default", "decor": "none", "content": "主视觉承担证据，支撑模块解释判断依据", "image": image, "media_frame": "content", "cards": compound_cards},
        {"id": "catalog-board", "title": "把重复内容整理为知识地图", "template": "catalog-board", "variant": "default", "decor": "none", "metrics": [{"value": "12", "label": "条目"}, {"value": "4", "label": "分类"}, {"value": "1", "label": "体系"}], "groups": catalog_groups},
        {"id": "case-study-board", "title": "证据与结论共享同一页", "template": "case-study-board", "variant": "evidence", "decor": "none", "content": "主要证据占据页面主体", "image": image, "media_frame": "content", "metrics": [{"value": "12 周", "label": "周期"}, {"value": "+36%", "label": "变化"}], "insight": {"title": "核心判断", "body": "结论必须能回到证据", "icon": "chart-line"}, "chart": {"label": "变化趋势", "values": [34, 58, 51, 76, 64]}},
        {"id": "annotated-showcase", "title": "同一份材料读出三个判断", "template": "annotated-showcase", "variant": "default", "decor": "none", "content": "标注只指出应该观察的局部", "image": image, "media_frame": "content", "annotations": [{"title": "入口", "body": "先看哪里"}, {"title": "主体", "body": "承接什么"}, {"title": "支撑", "body": "解释什么"}]},
        {"id": "narrative-bento", "title": "不同信息拥有不同权重", "template": "narrative-bento", "variant": "default", "decor": "none", "content": "页面通过面积和位置建立主次", "statement": "核心判断占据最大的连续区域", "statement_body": "其他模块补充证据和条件", "statement_icon": "lightbulb", "quote": "清楚的主次，本身就是设计感。", "quote_icon": "check-circle", "cards": compound_cards[:2]},
        {"id": "sequence-gallery", "title": "过程也值得被看见", "template": "sequence-gallery", "variant": "default", "decor": "none", "content": "三个真实画面共享框架", "steps": gallery_steps, "conclusion": "一致的容器，让变化更容易比较", "media_frame": "content"},
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
        and tokens.get("surfaceRadius") == "10px"
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


def main() -> None:
    required_ok = True

    validate_skill()

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
    print(f"[{'OK' if browser_ok else 'RECOMMENDED'}] Chromium DOM engine (used for build-time loading and structure validation)")
    required_ok &= browser_ok
    if browser and browser_ok:
        print(f"     engine: {browser}")
    elif not browser:
        print("     install Chrome/Chromium/Edge/Brave, provide Chrome for Testing, or set CHROME_BIN")
    else:
        print("     browser was found but failed an isolated DevTools smoke test; try CHROME_BIN with Chrome for Testing")

    print("[INFO] Core decks need no npm or external image API; media render-html uses the bundled Node + Playwright runtime.")

    smoke_ok = False
    matrix_ok = False
    matrix_count = 0
    try:
        with tempfile.TemporaryDirectory(prefix="oil-slides-doctor-") as temp_dir:
            root = Path(temp_dir)
            outline = root / "outline.json"
            project = root
            assets = root / "assets"
            assets.mkdir()
            (assets / "smoke.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600"><rect width="800" height="600" fill="#f7f7f8"/><circle cx="400" cy="300" r="170" fill="#ffd54a"/><path d="M220 420L400 150l180 270z" fill="#292929" opacity=".82"/></svg>',
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
                matrix_count = render_component_matrix(root, browser)
                matrix_ok = matrix_count > 0
            outline.write_text(
                json.dumps(
                    {
                        "title": "oil-ppt smoke",
                        "palette": {"accent": "#9ED0FF", "accent_soft": "#F5FAFF", "accent_strong": "#292929"},
                        "palette_source": "brand",
                        "typography": "clean",
                        "shape": "soft",
                        "click_navigation": False,
                        "slides": smoke_slides(),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            media_plan = build_media_plan(json.loads(outline.read_text(encoding="utf-8")), root, cli="scripts/oil-slides")
            if media_plan["summary"]["count"] < 7 or media_plan["summary"]["ready"] != media_plan["summary"]["count"]:
                raise RuntimeError(f"media plan did not compile every smoke asset: {media_plan['summary']}")
            entry = Path(__file__).resolve().parent / "oil_slides.py"
            subprocess.run(
                [sys.executable, str(entry), "preview", str(outline), "--no-open"],
                check=True,
                capture_output=True,
                text=True,
            )
            preview_file = root / "预览.html"
            preview_text = preview_file.read_text(encoding="utf-8")
            if preview_text.count("<iframe ") != len(smoke_slides()):
                raise RuntimeError("preview did not render every slide as a real template iframe")
            if 'class=&quot;hl&quot;' not in preview_text:
                raise RuntimeError("preview did not render the exposed highlight field")
            if 'class="rhythm-panel"' not in preview_text:
                raise RuntimeError("preview did not render the deck rhythm panel")
            for background in ("soft-spotlight", "block-field", "grid-wide"):
                if f'data-bg=&quot;{background}&quot;' not in preview_text:
                    raise RuntimeError(f"preview did not render background {background}")
            if any(seed in preview_text for seed in TEMPLATE_SEEDS):
                raise RuntimeError("preview leaked bundled template example copy")
            unverified = subprocess.run(
                [sys.executable, str(entry), "confirm", str(outline)],
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
                [sys.executable, str(entry), "confirm", str(outline), "--user-confirmed"],
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
            if invalidated.returncode == 0 or "outline changed after preview" not in invalidated.stderr:
                raise RuntimeError("outline edits did not invalidate preview confirmation")
            subprocess.run(
                [sys.executable, str(entry), "preview", str(outline), "--no-open"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, str(entry), "confirm", str(outline), "--user-confirmed"],
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
            final = project / "演示文稿.html"
            smoke_ok = final.is_file()
            if smoke_ok:
                final_text = final.read_text(encoding="utf-8")
                smoke_ok = (
                    'data-validation="browser"' in final_text
                    and '<span class="hl">稳定构建</span>' in final_text
                    and all(f'data-bg="{background}"' in final_text for background in ("soft-spotlight", "block-field", "grid-wide"))
                    and not any(seed in final_text for seed in TEMPLATE_SEEDS)
                    and 'id="oil-third-party-notices"' in final_text
                )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or str(error)).strip()
        print(f"[DETAIL] {detail}")
        smoke_ok = False
    except (OSError, RuntimeError) as error:
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
