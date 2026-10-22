"""Build a static copy of the demo (no backend): web/ + data/index.json + data/views/*.json (+ card PNGs).
python -m taview.static_bundle out_dir   -> open out_dir/index.html from any static host.
The UI switches to static mode when window.TAVIEW_STATIC is set (index.html is patched on copy)."""
from __future__ import annotations
import json, os, shutil, sys
from .config import Settings, ROOT
from .store import Store


def main(argv=None):
    argv = argv or sys.argv[1:]
    out = argv[0] if argv else os.path.join(ROOT, "dist")
    with_cards = "--cards" in argv
    settings = Settings(); store = Store(settings.db_path)
    os.makedirs(os.path.join(out, "data", "views"), exist_ok=True)
    shutil.copy(os.path.join(ROOT, "web", "lightweight-charts.js"), os.path.join(out, "lightweight-charts.js"))
    html = open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8").read().replace('<script src="lightweight-charts.js"></script>', '<script>window.TAVIEW_STATIC = true;</script>\n<script src="lightweight-charts.js"></script>')
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(html)
    symbols = {}
    for v in store.list():
        payload = store.latest(v["symbol"], v["horizon"])
        name = f"{v['symbol'].replace(':', '_')}_{v['horizon']}"
        json.dump(payload, open(os.path.join(out, "data", "views", name + ".json"), "w"), default=str)
        symbols.setdefault(v["symbol"], {"symbol": v["symbol"], "name": payload["company"], "precomputed": []})["precomputed"].append(v["horizon"])
        if with_cards:
            from .render import render_card
            render_card(payload, os.path.join(out, "data", "views", name + ".png"))
    for s in symbols.values(): s["precomputed"].sort()
    json.dump({"symbols": sorted(symbols.values(), key=lambda s: s["symbol"]), "horizons": ["swing", "medium", "long"]}, open(os.path.join(out, "data", "index.json"), "w"))
    print(f"static bundle at {out}: {len(symbols)} symbols, {sum(len(s['precomputed']) for s in symbols.values())} views")
    return 0


if __name__ == "__main__":
    sys.exit(main())
