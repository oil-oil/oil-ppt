#!/usr/bin/env python3
"""Check required oil-slides infrastructure without installing anything."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from build_deck import chrome_binary
from cdp_validate import validate_file
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
    image = "assets/smoke.svg"
    return [
        {"id": "cover", "title": "稳定构建验证", "highlight": "稳定构建", "background": "soft-spotlight", "template": "cover", "variant": "statement", "decor": "none", "content": "一次覆盖全部组件"},
        {"id": "section", "title": "进入核心内容", "background": "section-glow", "template": "section", "variant": "default", "decor": "none", "content": "接下来检查各类信息关系"},
        {"id": "steps", "title": "三个连续动作", "background": "mist-grid", "template": "three-steps", "variant": "linear", "decor": "dots", "steps": steps3},
        {"id": "timeline", "title": "四个时间阶段", "template": "timeline", "variant": "default", "decor": "none", "steps": steps4},
        {"id": "split", "title": "视觉与解释并置", "background": "soft-spotlight", "template": "split-visual", "variant": "default", "decor": "none", "content": "主视觉承担大部分信息", "image": image, "media_frame": "content"},
        {"id": "rail", "title": "六步完成流程", "template": "process-rail", "variant": "steps-6", "decor": "none", "steps": [{"label": f"动作{i}"} for i in range(1, 7)]},
        {"id": "cards", "title": "三个并列要点", "template": "card-trio", "variant": "feature-left", "decor": "none", "cards": cards},
        {"id": "compare", "title": "两个方案直接对比", "background": "paper-wash", "template": "comparison", "variant": "default", "decor": "halo", "sides": sides2},
        {"id": "compare-list", "title": "两类产物逐项对齐", "template": "comparison-list", "variant": "balanced", "decor": "corner-grid", "sides": sides3},
        {"id": "browser", "title": "真实界面是证据", "template": "browser-showcase", "variant": "default", "decor": "none", "content": "在浏览器外壳中展示界面", "image": image, "media_frame": "content"},
        {"id": "bleed", "title": "主视觉打破页面边界", "template": "bleed-split", "variant": "default", "decor": "none", "content": "为演示带来一次节奏变化", "image": image, "media_frame": "content"},
        {"id": "section-media", "title": "进入媒体组件", "template": "section", "variant": "default", "decor": "none", "content": "分段检查不同媒体轮廓"},
        {"id": "diagonal", "title": "方向感强化冲突", "template": "diagonal-split", "variant": "default", "decor": "none", "content": "斜线用于章节转折", "image": image, "media_frame": "content"},
        {"id": "photo-gradient", "title": "照片与文字融合", "template": "photo-gradient", "variant": "default", "decor": "none", "content": "渐变保证文字区域稳定可读", "image": image, "media_frame": "content"},
        {"id": "photo-split", "title": "照片与解释并重", "template": "photo-split", "variant": "default", "decor": "none", "content": "两侧信息权重保持接近", "image": image, "media_frame": "content"},
        {"id": "metric", "title": "一个数字是页面焦点", "template": "metric", "variant": "default", "decor": "orbit", "content": "用一句话解释数字的意义", "metric": {"value": "86", "unit": "%", "caption": "样本范围与时间口径保持一致"}},
        {"id": "recap", "title": "三条原则支撑一个结论", "template": "recap", "variant": "thesis-left", "decor": "dots", "content": "最后回到一个清楚的判断", "cards": cards},
        {"id": "tabs", "title": "同一对象的两个视角", "template": "tabs", "variant": "default", "decor": "halo", "sides": [{"title": "视角 A", "body": "从使用者任务理解界面"}, {"title": "视角 B", "body": "从系统实现理解界面"}]},
        {"id": "converge", "title": "两组输入汇聚为结果", "template": "converge", "variant": "default", "decor": "none", "groups": [{"title": "内容输入", "items": ["明确目标", "整理材料"]}, {"title": "设计输入", "items": ["选择组件", "准备视觉"]}], "outcome": "共同形成可交付的演示"},
        {"id": "editorial", "title": "展陈式页面保留编辑感", "template": "editorial-canvas", "variant": "default", "decor": "none", "content": "把材料、局部和批注放在同一个画布中"},
        {"id": "end", "title": "稳定的事情交给程序", "template": "end", "variant": "line", "decor": "none"},
    ]


TEMPLATE_SEEDS = (
    "第一步", "Markdown", "00</span>", "点击上方标签切换内容",
    "用一句话说明这一章", "适合材料、局部、批注",
)


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

    print("[INFO] Node, npm, and external image APIs are not required.")

    smoke_ok = False
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
            outline.write_text(
                json.dumps(
                    {
                        "title": "oil-slides smoke",
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
            for background in ("soft-spotlight", "section-glow", "mist-grid", "paper-wash"):
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
                    and all(f'data-bg="{background}"' in final_text for background in ("soft-spotlight", "section-glow", "mist-grid", "paper-wash"))
                    and not any(seed in final_text for seed in TEMPLATE_SEEDS)
                )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or str(error)).strip()
        print(f"[DETAIL] {detail}")
        smoke_ok = False
    except (OSError, RuntimeError) as error:
        print(f"[DETAIL] {error}")
        smoke_ok = False
    required_ok &= smoke_ok
    print(f"[{mark(smoke_ok)}] Preview gate + end-to-end scaffold/build with root 演示文稿.html")

    if not required_ok:
        raise SystemExit(1)
    print("oil-slides infrastructure is ready.")


if __name__ == "__main__":
    main()
