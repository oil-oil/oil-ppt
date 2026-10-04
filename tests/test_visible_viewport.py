"""验证整套预览与单页在窗口变化、视觉视口放大时完整可见。"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1] / "oil-ppt"
sys.path.insert(0, str(ROOT / "scripts"))
from build_deck import chrome_binary
from cdp_validate import _stop_browser
from pptx_export import _browser_session, _cdp_command
from project import deck_chrome
from slide_html import new_slide_document


class AudienceText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.classes = set()
    def handle_starttag(self, tag, attrs):
        self.classes.update((dict(attrs).get("class") or "").split())
    def handle_data(self, value):
        if value.strip():
            self.text.append(value.strip())


class VisibleViewportTests(unittest.TestCase):
    def test_default_slide_and_starters_have_no_production_notes(self):
        reader = AudienceText()
        source = new_slide_document("sample", "任务执行流程")
        reader.feed(source.split("<!-- OIL-SLIDE:START -->")[1].split("<!-- OIL-SLIDE:END -->")[0])
        self.assertEqual(reader.text, ["任务执行流程"])
        for path in (ROOT / "assets/starters").glob("*.html"):
            with self.subTest(starter=path.stem):
                reader = AudienceText()
                reader.feed(path.read_text(encoding="utf-8").split("<!-- OIL-SLIDE:START -->")[1].split("<!-- OIL-SLIDE:END -->")[0])
                self.assertFalse(reader.classes & {"oil-label", "oil-lede", "rail-note"})

    def test_stage_and_controls_follow_visible_viewport(self):
        chrome = chrome_binary()
        if not chrome:
            self.skipTest("需要 Chrome 或 Chromium")
        css = (ROOT / "assets/runtime/deck.css").read_text(encoding="utf-8")
        js = (ROOT / "assets/runtime/deck.js").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            for single in (False, True):
                with self.subTest(single=single):
                    prefix = "slide-preview" if single else "deck"
                    body = ' data-oil-mode="preview"' if single else ''
                    slides = ''.join(f'<section class="oil-slide" data-slide-id="s{i}"><div class="slide-safe"><h1 style="font-size:64px;letter-spacing:var(--oil-tracking-display);line-height:var(--oil-leading-display)">任务执行流程</h1></div></section>' for i in range(1 if single else 3))
                    chrome_html = '' if single else deck_chrome({"controls":{"next_preview":True,"show_progress":True,"show_counter":True}})
                    path = Path(directory) / 'viewport.html'
                    shell_class = 'slide-preview-shell' if single else 'deck-stage-shell'
                    path.write_text(f'<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style></head><body{body}><div class="{prefix}-viewport"><div class="{shell_class}"><div class="{prefix}-stage">{slides}</div></div></div>{chrome_html}<script>{js}</script></body></html>', encoding='utf-8')
                    process, profile, socket = _browser_session(chrome, path)
                    seq = 0
                    def call(method, params=None):
                        nonlocal seq
                        seq += 1
                        return _cdp_command(socket, seq, method, params)
                    try:
                        call('Runtime.enable')
                        call('Page.bringToFront')
                        for w,h,z in [(1920,1080,1),(1440,900,1),(390,844,1),(1440,900,1.2),(1440,900,1.5),(1280,720,2),(1100,680,1)]:
                            call('Emulation.setPageScaleFactor', {'pageScaleFactor':1})
                            call('Emulation.setDeviceMetricsOverride', {'width':w,'height':h,'deviceScaleFactor':1,'mobile':False})
                            call('Emulation.setPageScaleFactor', {'pageScaleFactor':z})
                            result = call('Runtime.evaluate', {'awaitPromise':True,'returnByValue':True,'expression':'''(async()=>{
                              await new Promise(done=>setTimeout(done,450));
                              const v=visualViewport;
                              const stage=document.querySelector('.deck-stage,.slide-preview-stage');
                              const inside=e=>{const b=e.getBoundingClientRect();return b.left>=v.offsetLeft-1&&b.top>=v.offsetTop-1&&b.right<=v.offsetLeft+v.width+1&&b.bottom<=v.offsetTop+v.height+1};
                              const controls=[...document.querySelectorAll('.deck-counter,.next-preview,.deck-overview-toggle')].filter(e=>getComputedStyle(e).display!=='none');
                              const b=stage.getBoundingClientRect();
                              const progress=document.querySelector('.progress-bar');
                              const h=getComputedStyle(document.querySelector('h1'));
                              return {box:b.toJSON(),visible:[v.width,v.height],scale:stage.dataset.scale,inside:inside(stage),controls:controls.every(inside),ratio:b.width/b.height,scroll:document.documentElement.scrollWidth>innerWidth+1||document.documentElement.scrollHeight>innerHeight+1,progress:!progress||Math.abs(progress.getBoundingClientRect().width-v.width/3)<1,weight:h.fontWeight,tracking:parseFloat(h.letterSpacing)};
                            })()'''})['result']['value']
                            self.assertTrue(result['inside'] and result['controls'] and result['progress'], (w,h,z,result))
                            self.assertFalse(result['scroll'], (w,h,z,result))
                            self.assertAlmostEqual(result['ratio'], 16/9, places=3)
                            self.assertEqual(result['weight'], '500')
                            self.assertGreaterEqual(result['tracking'], 0)
                    finally:
                        socket.close()
                        _stop_browser(process, Path(profile.name))
                        profile.cleanup()

if __name__ == '__main__':
    unittest.main()
