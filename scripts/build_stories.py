#!/usr/bin/env python3
"""Build stories/<key>.json and threads/<thread>.json from the notes in days/.

A note is a snapshot of one moment. A STORY is one subject followed across notes:
stories/<key>.json carries its whole timeline, oldest first, one entry per appearance.
A THREAD is the long-running theme several stories belong to ("crude-iran-war"), and
threads/<slug>.json lists its stories plus the metric series that bear on it.

Everything here is derived from days/, which is append-only, so this script is safe to
re-run: it rebuilds each file from scratch and writes only when the content changed.
The one thing it does NOT own is "dossier" — the written-up summary a scheduled run adds
to a story. That is read back from the existing file and preserved verbatim.

Run it wherever build_feed.py is run, so the two stay in step.
"""
import json, os, glob, re, datetime, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORIES, THREADS = os.path.join(ROOT, "stories"), os.path.join(ROOT, "threads")

# Which metric series is worth carrying on a thread's page. Matched against the thread
# slug, so "crude" also covers "crude-iran-war". A thread that matches nothing carries
# no series rather than every number we happen to hold.
THREAD_METRICS = {
    "crude": ["brent_usd"],
    "oil": ["brent_usd"],
    "rupee": ["usd_inr"],
    "inr": ["usd_inr"],
    "fii": ["fii_net_cr", "dii_net_cr"],
    "dii": ["fii_net_cr", "dii_net_cr"],
    "flows": ["fii_net_cr", "dii_net_cr"],
    "vix": ["india_vix"],
    "volatility": ["india_vix"],
}

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("build_feed", os.path.join(ROOT, "scripts", "build_feed.py"))
_bf = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_bf)
slot_key, LABEL, norm_metrics = _bf.slot_key, _bf.LABEL, _bf.norm_metrics
norm_thread, norm_results, _text, _src = _bf.norm_thread, _bf.norm_results, _bf._text, _bf._src


def safe_name(key):
    """A filename for a story key. Keys are model-written, so never trust them."""
    slug = re.sub(r"[^a-z0-9._-]+", "-", key.lower()).strip("-.") or "story"
    slug = slug[:60]
    # A key that only differs outside the safe set would collide; keep them apart.
    if slug != key:
        slug = f"{slug}-{hashlib.sha1(key.encode()).hexdigest()[:6]}"
    return slug


def load_notes():
    """Every note, oldest first, as (date, slot, note)."""
    notes = []
    for f in glob.glob(os.path.join(ROOT, "days", "*", "*.json")):
        date, slot = f.split(os.sep)[-2], os.path.basename(f)[:-5]
        if slot_key(slot) is None:
            continue
        try:
            notes.append((date, slot, json.load(open(f, encoding="utf-8"))))
        except (ValueError, OSError) as e:
            print(f"  skipped {date}/{slot}: {e}")
    notes.sort(key=lambda n: (n[0], slot_key(n[1])))
    return notes


def when_of(date, slot):
    return datetime.date.fromisoformat(date).strftime("%a") + " · " + LABEL(slot)


def entry_of(date, slot, t):
    """One timeline entry: what this note said about this story, and when."""
    e = {"date": date, "slot": slot, "when": when_of(date, slot)}
    for k in ("title", "line", "impact", "tag"):
        if _text(t.get(k)):
            e[k] = _text(t[k])
    more = [_text(m) for m in (t.get("more") or []) if _text(m)]
    if more:
        e["more"] = more
    th = norm_thread(t.get("thread"))
    if th:
        e["thread"] = th
    rs = norm_results(t.get("results"))
    if rs:
        e["results"] = rs
    if _src(t.get("src")):
        e["src"] = _src(t["src"])
    return e


def write_json(path, obj):
    """Write only when the content actually changed, so re-runs make no git noise."""
    new = json.dumps(obj, ensure_ascii=False, indent=1) + "\n"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            if fh.read() == new:
                return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new)
    return True


def read_dossier(path):
    """A dossier is written by a scheduled run, not by this script. Never lose one."""
    if not os.path.exists(path):
        return None
    try:
        return json.load(open(path, encoding="utf-8")).get("dossier")
    except (ValueError, OSError):
        return None


def main():
    notes = load_notes()
    stories, metrics_by_note = {}, []
    for date, slot, n in notes:
        m = norm_metrics(n)
        if m:
            metrics_by_note.append((date, slot, m))
        for t in n.get("top", []):
            key = (t.get("key") or t.get("title", "")).lower().strip()
            if not key:
                continue
            stories.setdefault(key, []).append(entry_of(date, slot, t))

    written = 0
    story_meta = {}
    for key, timeline in sorted(stories.items()):
        name = safe_name(key)
        path = os.path.join(STORIES, name + ".json")
        last = timeline[-1]
        # The story's thread is the most recent one any appearance named.
        thread = next((e["thread"] for e in reversed(timeline) if e.get("thread")), None)
        doc = {
            "key": key,
            "title": last.get("title", key),
            "tag": last.get("tag"),
            **({"thread": thread} if thread else {}),
            "first_seen": {"date": timeline[0]["date"], "slot": timeline[0]["slot"]},
            "last_seen": {"date": last["date"], "slot": last["slot"]},
            "count": len(timeline),
            "timeline": timeline,
        }
        dossier = read_dossier(path)
        if dossier:
            doc["dossier"] = dossier
        written += write_json(path, doc)
        story_meta[key] = (name, thread, doc["first_seen"], doc["last_seen"], len(timeline),
                           doc["title"])

    # --- threads -------------------------------------------------------------
    threads = {}
    for key, (name, thread, first, last, count, title) in story_meta.items():
        if thread:
            threads.setdefault(thread, []).append(
                {"key": key, "title": title, "first_seen": first, "last_seen": last,
                 "count": count})

    # threads/index.json is the REGISTRY the scheduled runs read to reuse a thread name
    # rather than coining a new one. It is therefore not purely derived: a slug may be
    # registered before any story carries it. Merge, never overwrite.
    tw = 0
    idx_path = os.path.join(THREADS, "index.json")
    registered = {}
    if os.path.exists(idx_path):
        try:
            for row in json.load(open(idx_path, encoding="utf-8")):
                if isinstance(row, dict) and row.get("slug"):
                    registered[row["slug"]] = row
        except (ValueError, OSError):
            pass
    index = [dict(r) for s_, r in sorted(registered.items()) if s_ not in threads]

    for slug, keys in sorted(threads.items()):
        keys.sort(key=lambda k: (k["first_seen"]["date"], k["key"]))
        first = min(k["first_seen"]["date"] for k in keys)
        last = max(k["last_seen"]["date"] for k in keys)
        wanted = []
        for frag, names in THREAD_METRICS.items():
            if frag in slug:
                wanted += [m for m in names if m not in wanted]
        series = {}
        for mname in wanted:
            pts = [{"date": d, "slot": s, **mt[mname]} for d, s, mt in metrics_by_note
                   if mname in mt and first <= d <= last]
            if pts:
                series[mname] = pts
        prev = registered.get(slug, {})
        title = prev.get("title") or slug.replace("-", " ").title()
        # first_seen on the registry is the earliest we ever recorded, not just what the
        # current window of notes shows.
        first = min([first] + ([prev["first_seen"]] if prev.get("first_seen") else []))
        doc = {"thread": slug, "title": title, "first_seen": first, "last_seen": last,
               "story_count": len(keys), "keys": keys,
               **({"metrics": series} if series else {})}
        tw += write_json(os.path.join(THREADS, slug + ".json"), doc)
        index.append({"slug": slug, "title": title, "first_seen": first})


    index.sort(key=lambda r: r["slug"])
    tw += write_json(idx_path, index)
    print(f"stories: {len(story_meta)} ({written} written) · "
          f"threads: {len(threads)} ({tw} written) · notes read: {len(notes)}")


if __name__ == "__main__":
    main()
