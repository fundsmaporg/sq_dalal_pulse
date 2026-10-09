#!/usr/bin/env python3
"""Build latest.json for the app from the raw half-hourly notes in days/<date>/<slot>.json.

latest.json = the current market mood (newest note) + one merged "insights" list across the
last 7 trading days: newest first, older ones in published order, duplicates (same "key")
collapsed to their most recent version.
"""
import json, os, glob, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLOTS = ["pre"] + [f"{m//60:02d}{m%60:02d}" for m in range(570, 931, 30)] + ["post"]
LABEL = {"pre": "Pre-open", "post": "Close", **{s: f"{int(s[:2])}:{s[2:]}" for s in SLOTS[1:-1]}}
STAGE = lambda s: "Pre-market" if s == "pre" else "Post-market" if s == "post" else ("Opening" if s <= "1000" else "Closing" if s >= "1500" else "Mid-market")

def load():
    days = {}
    for f in glob.glob(os.path.join(ROOT, "days", "*", "*.json")):
        date, slot = f.split(os.sep)[-2], os.path.basename(f)[:-5]
        if slot in SLOTS:
            days.setdefault(date, {})[slot] = json.load(open(f, encoding="utf-8"))
    return days


def _text(v):
    return v.strip() if isinstance(v, str) and v.strip() else None


def _src(v):
    """A source is only usable if it has a URL."""
    if isinstance(v, dict) and _text(v.get("url")):
        return {"title": _text(v.get("title")) or v["url"].strip(), "url": v["url"].strip()}
    return None


def norm_movers(detail):
    """Normalise detail.movers — the tappable breakdown behind leaders/laggards.

    The app shows detail.leaders / detail.laggards collapsed and opens this when the
    user taps. Returns a dict with any of "up"/"down", or None when the note carries
    nothing usable — in which case the key is dropped entirely so the app keeps
    falling back to the plain strings rather than rendering an empty drawer.
    """
    raw = detail.get("movers")
    if not isinstance(raw, dict):
        return None
    out = {}
    for side in ("up", "down"):
        grp = raw.get(side)
        if not isinstance(grp, dict):
            continue
        names = []
        for n in (grp.get("names") or [])[:6]:
            if not isinstance(n, dict):
                continue
            nm = _text(n.get("name"))
            if not nm:
                continue
            item = {"name": nm, "dir": n["dir"] if n.get("dir") in ("up", "down", "flat") else None}
            for k in ("move", "line"):
                if _text(n.get(k)):
                    item[k] = _text(n.get(k))
            names.append(item)
        g = {}
        for k in ("summary", "why"):
            if _text(grp.get(k)):
                g[k] = _text(grp.get(k))
        if names:
            g["names"] = names
        if _src(grp.get("src")):
            g["src"] = _src(grp.get("src"))
        # A side with neither names nor prose would open an empty drawer.
        if g.get("names") or g.get("why"):
            out[side] = g
    return out or None

def main():
    days = load()
    dates = sorted(days, reverse=True)[:7]
    if not dates:
        raise SystemExit("no notes")
    ld = dates[0]
    ls = max(days[ld], key=SLOTS.index)
    cur = days[ld][ls]
    seen, insights = {}, []
    for d in dates:
        for s in sorted(days[d], key=SLOTS.index, reverse=True):
            for t in days[d][s].get("top", []):
                k = (t.get("key") or t.get("title", "")).lower()
                when = LABEL[s] if d == ld else datetime.date.fromisoformat(d).strftime("%a") + " · " + LABEL[s]
                if k in seen:
                    seen[k]["updated"] = True
                    seen[k]["first_seen"] = {"date": d, "slot": s}
                    continue
                item = {**t, "date": d, "slot": s, "when": when, "updated": False,
                        "is_new": d == ld and s == ls, "first_seen": {"date": d, "slot": s}}
                seen[k] = item
                insights.append(item)
    detail = {k: v for k, v in cur["mood"].get("detail", {}).items() if k != "stats"}
    movers = norm_movers(detail)
    detail.pop("movers", None)
    if movers:
        detail["movers"] = movers
    out = {
        "schema": "dalal-pulse/v1",
        "generated_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).isoformat(timespec="seconds"),
        "date": ld, "slot": ls, "slot_label": LABEL[ls], "stage": STAGE(ls) + " mood",
        "asof": cur.get("asof"),
        "nifty": cur.get("nifty"),
        "mood": {"label": cur["mood"]["label"], "score": cur["mood"]["score"],
                 "summary": cur.get("summary"), "detail": detail},
        "insights": insights,
    }
    json.dump(out, open(os.path.join(ROOT, "latest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"latest.json: {ld} {ls} · {cur['mood']['label']} · {len(insights)} insights")

if __name__ == "__main__":
    main()
