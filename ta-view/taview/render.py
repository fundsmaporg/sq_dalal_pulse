"""Share-card renderer: the web UI's own card template screenshotted in headless Chromium (Playwright)."""
from __future__ import annotations
import json, os
from .config import ROOT


def render_card(payload: dict, out_path: str, width: int = 1080, height: int = 1920) -> str:
    from playwright.sync_api import sync_playwright
    tpl = open(os.path.join(ROOT, "web", "card.html"), encoding="utf-8").read()
    lib = open(os.path.join(ROOT, "web", "lightweight-charts.js"), encoding="utf-8").read()
    html = tpl.replace("/*__LIB__*/", lib).replace("/*__DATA__*/", "window.VIEW = " + json.dumps(payload, default=str) + ";")
    tmp = out_path + ".html"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(tmp, "w", encoding="utf-8").write(html)
    with sync_playwright() as p:
        exe = os.environ.get("TAVIEW_CHROMIUM")
        browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=2)
        page.goto("file://" + os.path.abspath(tmp)); page.wait_for_function("window.__ready === true"); page.wait_for_timeout(500)
        h = page.evaluate("document.querySelector('.frame').scrollHeight")
        if h > height:
            page.evaluate(f"document.querySelector('.frame').style.zoom='{round(height / h, 4)}'"); page.wait_for_timeout(300)
        page.screenshot(path=out_path, clip={"x": 0, "y": 0, "width": width, "height": height})
        browser.close()
    os.remove(tmp)
    return out_path
