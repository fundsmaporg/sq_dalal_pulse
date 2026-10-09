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
    "detail": {
      "leaders": "…",              // collapsed one-liner — what is holding up
      "laggards": "…",             // collapsed one-liner — what is under pressure
      "tone": "…", "watch": ["…"], "src": { "title": "…", "url": "…" },
      "movers": {                  // OPTIONAL — the tappable breakdown behind the two lines above
        "up": {
          "summary": "…",          // ≤ 90 chars, same substance as `leaders`
          "why": "…",              // 1–2 sentences: what is driving this side
          "names": [
            { "name": "TCS",
              "move": "+3.4%",     // as reported; omitted when the source gives no figure
              "dir": "up",         // up | down | flat | null
              "line": "…" }        // ≤ 90 chars: why THIS name
          ],
          "src": { "title": "…", "url": "…" }
        },
        "down": { /* same shape, for the names under pressure */ }
      }
    }
  },
  "insights": [
    {
      "key": "pb-fintech",           // stable story id used for de-duplication
      "tag": "Stocks",               // usually: Regulation | Global | Macro | Flows | Listing |
                                     // Stocks | Opening | Results | Policy — but treat as OPEN,
                                     // see "Tags are an open set" below
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

### Tags are an open set

The nine values above are what the generator is asked for and what it emits almost all of
the time — but it is a language model writing JSON, not a database with a constraint, and
it does occasionally coin a new one. A live payload on 2026-10-09 carried `"Deals"`.

So consumers must **cope rather than assume**: render an unrecognised tag as plain text
with neutral styling, and never switch exhaustively on it or index into a lookup that can
miss. Tag counts are also heavily skewed — 83 of 132 insights were `Stocks` in that same
payload — so don't build a layout that needs an even spread.

### Making "holding up" / "under pressure" tappable

`detail.leaders` and `detail.laggards` are the collapsed one-liners the screen already
shows. `detail.movers` is what opens when the user taps one of them:
`movers.up` sits behind **leaders**, `movers.down` behind **laggards**.

`movers` is **optional and may be missing entirely** — on older notes, or whenever a run
could not source per-name detail it can stand behind. Treat it as progressive enhancement:
show the row as tappable only when the matching side exists and has `names` or `why`,
and otherwise render the plain string exactly as today. The feed builder drops any side it
cannot normalise rather than emitting an empty one, so `movers.up` existing is a sufficient
signal that there is something worth opening. At most 6 names per side.

`move` is a string, not a number, because sources quote ranges and approximations
("+2.8–3%", "up ~3%"). Use `dir` for colour — a name can be in `movers.up` while still
down on the day, when it is simply falling less than the market.
