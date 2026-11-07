# Dalal Pulse feed

Indian equity market notes for the Markets Now screen, written by scheduled Claude runs.

**Weekdays (19 notes):** 07:00, 08:45, 09:25, then every 30 minutes on the `:05`/`:35`
grid (10:05, 10:35 … 16:35), then 18:00 and 21:00 IST.
**Weekends (8 notes):** 08:00, 14:00, 18:00 and 21:00 IST on both Saturday and Sunday.

The intraday runs sit a few minutes **past** the hour and half hour on purpose. News sites
publish their market snapshots at round times, so a run at 10:35 reads a 10:30 update that
is about five minutes old; the earlier `:25`/`:55` grid could only reach the previous round
time and so formed every judgement from data roughly 25 minutes stale.

| Path | What it is |
|---|---|
| `latest.json` | **What the app reads.** Current market mood + merged, de-duplicated insights (newest first, last 7 trading days). |
| `days/<YYYY-MM-DD>/<slot>.json` | Raw note for each slot — see **Slot ids** below. |
| `scripts/build_feed.py` | Rebuilds `latest.json` from `days/`. |
| `.github/workflows/push.yml` | On every change to `latest.json`, POSTs it to `PULSE_ENDPOINT_URL` (repo secret), with `Authorization: Bearer PULSE_ENDPOINT_TOKEN` if set. |

## latest.json (schema `dalal-pulse/v1`)

```jsonc
{
  "schema": "dalal-pulse/v1",
  "generated_at": "2026-09-24T15:40:00+05:30",
  "date": "2026-09-24", "slot": "1325", "slot_label": "13:25", "stage": "Mid-market mood",
  "asof": "2026-09-24T13:30:00+05:30",
  "nifty": {                       // OPTIONAL — may be absent, see "Index figures" below
    "value": 23200, "pct": -1.05, "chg": null, "approx": true,
    "asof_quote": "13:00"          // the time this PRINT refers to, not when the note was
  },                               // written; live-session slots only
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
      "date": "2026-09-24", "slot": "1325", "when": "13:25",
      "is_new": true,                // first appeared in the latest note
      "updated": false,              // same story appeared in an earlier note too
      "first_seen": { "date": "2026-09-24", "slot": "1325" }
    }
  ]
}
```

### Index figures

The runs read public news copy, not a price feed. Index snapshots in news copy are published
at round times and are typically **20–30 minutes old** by the time a run finds them. Two
consequences, both deliberate:

- **No index levels appear in the prose.** `mood.summary`, `detail.tone`, `leaders`,
  `laggards` and `watch` describe the market in words — "holding near the day's high",
  "paring the early gain" — and never carry an index level or an index point/% move. Show
  your own live level alongside them; a figure sourced 25 minutes ago next to a live ticker
  reads as a contradiction. Figures inside `insights` are news facts (deal sizes, results,
  crude, flows), not index readings, and are unaffected.
- **`nifty` is optional and may be absent.** On a live-session slot, a run that cannot
  source a print newer than the previous note's omits the key rather than carrying a stale
  level forward — so the key's absence means "no fresh print", not "no note". Treat it as
  progressive enhancement exactly like `movers`, and fall back to your own feed.

When present on a live-session slot, `nifty.asof_quote` is the time the print refers to,
which is **not** the note's `asof`. Label it with that time or not at all.
`nifty.approx` still flags a figure taken from a headline. Use your own market feed for
exact levels in every case.

### Slot ids

A slot id is the run's own clock time in IST as `HHMM` — `0700`, `0925`, `1625`, `2100` —
plus one named slot, `outlook`, used by the Sunday 21:00 run. Ids sort chronologically on
the minute they stand for, so the latest note of a day is simply the one with the largest id.

Two legacy ids appear on notes written before November 2026 and never again: `pre` (the
08:31 pre-open note) and `post` (the 16:01 close note). They sort at 08:31 and 16:01
respectively. **Do not switch exhaustively on slot ids** — treat an unrecognised one as an
ordinary note and render `slot_label`.

### Notes written while nothing is trading

NSE trades 09:15–15:30 IST, so the `0700`, `0845`, `1800` and `2100` weekday notes and all
eight weekend notes are written while the market is shut. They are ordinary notes and need
no special handling, but three things differ:

- **`stage` is the cue.** It reads `Pre-market mood`, `Evening wrap` or `Weekend outlook`
  rather than `… mood`, which is how a consumer knows to present a look-ahead rather than a
  live reading. Weekend notes always read `Weekend outlook`, whatever the hour.
- **`nifty` carries a close**, not a live level — the previous session's close before the
  open, today's close in the evening, Friday's close over the weekend. It is never a
  prediction.
- **`movers` is deliberately absent**, because nothing is moving. `leaders` and `laggards`
  are still present as forward-looking lines, so a consumer that makes them tappable should
  fall back to plain text here, exactly as on any other note without `movers`.

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
