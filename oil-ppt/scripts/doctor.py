#!/usr/bin/env python3
"""Run a self-contained oil-ppt package and HTML workflow health check."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import oil_ppt
from build_deck import build_project, chrome_binary
from cdp_validate import validate_file
from icon_registry import verify_icons
from media_assets import verify_deck_media
from package_manifest import package_status
from preview_deck import render_preview
from project import init_project, read_deck
from slide_html import parse_slide
from validate_skill import validation_errors
from workflow import confirm_preview


def run_doctor() -> dict:
    checks: list[dict[str, object]] = []

    skill_errors = validation_errors()
    checks.append({"name": "package-contract", "ok": not skill_errors, "details": skill_errors})

    try:
        icons = verify_icons()
        checks.append({"name": "bundled-icons", "ok": True, "count": len(icons)})
    except ValueError as error:
        checks.append({"name": "bundled-icons", "ok": False, "details": [str(error)]})

    package = package_status()
    checks.append({
        "name": "package-manifest",
        "ok": bool(package.get("ok")),
        "details": [
            *package.get("errors", []),
            *[f"missing: {item}" for item in package.get("missing", [])],
            *[f"changed: {item}" for item in package.get("changed", [])],
            *[f"unexpected: {item}" for item in package.get("unexpected", [])],
        ],
    })

    with tempfile.TemporaryDirectory(prefix="oil-ppt-doctor-") as directory:
        project = init_project(Path(directory) / "health-check", "oil-ppt health check")
        oil_ppt.slide_add(project, "cover", "A real HTML slide", "statement", None)
        _, deck = read_deck(project)
        slide = project / deck["slides"][0]
        before = hashlib.sha256(slide.read_bytes()).hexdigest()
        parsed = parse_slide(slide, "cover")
        media = verify_deck_media(project, deck)
        preview = render_preview(project)
        confirm_preview(project)
        output = build_project(project)
        after = hashlib.sha256(slide.read_bytes()).hexdigest()
        workflow_ok = (
            parsed.slide_id == "cover"
            and preview.is_file()
            and output.is_file()
            and before == after
        )
        checks.append({
            "name": "html-workflow",
            "ok": workflow_ok,
            "slide_source_unchanged": before == after,
            "preview": str(preview),
            "delivery": str(output),
            "media_count": len(media),
        })
        chrome = chrome_binary()
        if chrome:
            report = validate_file(chrome, output)
            checks.append({
                "name": "browser-validation",
                "ok": report.get("status") == "ok",
                "browser": chrome,
                "report": report,
            })
            typography_fixture = Path(directory) / "typography-gate.html"
            runtime_css = (project / "runtime" / "deck.css").read_text(encoding="utf-8")
            typography_fixture.write_text(
                f'''<!doctype html><html><head><meta charset="utf-8"><style>{runtime_css}</style></head><body>
<div class="deck-viewport"><div class="deck-stage-shell"><div class="deck-stage">
<section class="oil-slide active" data-slide-id="readable"><div class="slide-safe"><div data-layout style="position:absolute;inset:0"><h1 style="font-size:64px">Readable</h1><span style="font-size:28px">Audience copy</span></div></div></section>
<section class="oil-slide" data-slide-id="small"><div class="slide-safe"><div data-layout style="position:absolute;inset:0"><h1 style="font-size:64px">Later slide</h1><span style="font-size:20px">This explanation is too small.</span><span data-microcopy="index" style="font-size:18px">01</span><span style="font-size:28px;color:#fff;background:#fff">Invisible HTML</span><svg width="400" height="100"><rect width="400" height="100" fill="#fff"/><text x="200" y="60" text-anchor="middle" style="font-size:28px;fill:#fff">Invisible SVG</text></svg></div></div></section>
</div></div></div></body></html>''',
                encoding="utf-8",
            )
            typography_report = validate_file(chrome, typography_fixture)
            typography_findings = [
                item for item in typography_report.get("visualFindings", [])
                if isinstance(item, dict) and item.get("category") == "readability"
            ]
            typography_ok = (
                typography_report.get("status") == "error"
                and any(
                    item.get("slide") == "small"
                    and item.get("fontSize") == 20
                    and item.get("minimumFontSize") == 24
                    for item in typography_findings
                )
                and not any(item.get("text") == "01" for item in typography_findings)
            )
            checks.append({
                "name": "typography-gate",
                "ok": typography_ok,
                "report": typography_report,
            })
            contrast_findings = [
                item for item in typography_report.get("visualFindings", [])
                if isinstance(item, dict) and item.get("category") == "contrast"
            ]
            contrast_ok = {
                item.get("text") for item in contrast_findings
            } >= {"Invisible HTML", "Invisible SVG"}
            checks.append({
                "name": "contrast-gate",
                "ok": contrast_ok,
                "report": contrast_findings,
            })
        else:
            checks.append({
                "name": "browser-validation",
                "ok": True,
                "skipped": "Chrome/Chromium unavailable",
            })

    return {
        "schema_version": "oil-ppt.doctor/v1",
        "ok": all(bool(check.get("ok")) for check in checks),
        "checks": checks,
    }


def main() -> int:
    try:
        report = run_doctor()
    except (OSError, RuntimeError, SystemExit, ValueError) as error:
        report = {
            "schema_version": "oil-ppt.doctor/v1",
            "ok": False,
            "checks": [],
            "error": str(error),
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
