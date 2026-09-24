# Dalal Pulse feed

Half-hourly Indian equity market notes for the Markets Now screen, written by scheduled Claude runs
(weekdays, 08:31 pre-open → every 30 min → 16:01 post-close IST).

| Path | What it is |
|---|---|
| `latest.json` | **What the app reads.** Current market mood + merged, de-duplicated insights (newest first, last 7 trading days). |
| `days/<YYYY-MM-DD>/<slot>.json` | Raw note for each slot. Slots: `pre`, `0930` … `1530`, `post`. |
| `scripts/build_feed.py` | Rebuilds `latest.json` from `days/`. |
| `.github/workflows/push.yml` | On every change to `latest.json`, POSTs it to `PULSE_ENDPOINT_URL` (repo secret), with `Authorization: Bearer PULSE_ENDPOINT_TOKEN` if set. |

## latest.json (schema `dalal-pulse/v1`)

```jsonc
{
  "schema": "dalal-pulse/v1",
  "generated_at": "2026-09-24T15:40:00+05:30",
  "date": "2026-09-24", "slot": "1330", "slot_label": "13:30", "stage": "Mid-market mood",
  "asof": "2026-09-24T13:30:00+05:30",
  "nifty": { "value": 23200, "pct": -1.05, "chg": null, "approx": true },
  "mood": {
    "label": "Selling deepens",
    "score": -0.7,                 // -1 risk-off … +1 risk-on (red ≤ -0.25, amber, green ≥ 0.25)
    "summary": "One sentence on how the market is trading.",
    "detail": { "leaders": "…", "laggards": "…", "tone": "…", "watch": ["…"], "src": { "title": "…", "url": "…" } }
  },
  "insights": [
    {
      "key": "pb-fintech",           // stable story id used for de-duplication
      "tag": "Stocks",               // Regulation | Global | Macro | Flows | Listing | Stocks | Opening | Results | Policy
      "impact": "neg",               // pos = tailwind, neg = headwind, watch
      "title": "…", "line": "…", "more": ["…"], "src": { "title": "…", "url": "…" },
      "date": "2026-09-24", "slot": "1330", "when": "13:30",
      "is_new": true,                // first appeared in the latest note
      "updated": false,              // same story appeared in an earlier note too
      "first_seen": { "date": "2026-09-24", "slot": "1330" }
    }
  ]
}
```

Figures come from public news sources and can be approximate (`nifty.approx`). Use your own market feed for exact levels.
