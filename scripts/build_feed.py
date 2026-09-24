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
    out = {
        "schema": "dalal-pulse/v1",
        "generated_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).isoformat(timespec="seconds"),
        "date": ld, "slot": ls, "slot_label": LABEL[ls], "stage": STAGE(ls) + " mood",
        "asof": cur.get("asof"),
        "nifty": cur.get("nifty"),
        "mood": {"label": cur["mood"]["label"], "score": cur["mood"]["score"], "summary": cur.get("summary"),
                 "detail": {k: v for k, v in cur["mood"].get("detail", {}).items() if k != "stats"}},
        "insights": insights,
    }
    json.dump(out, open(os.path.join(ROOT, "latest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"latest.json: {ld} {ls} · {cur['mood']['label']} · {len(insights)} insights")

if __name__ == "__main__":
    main()
