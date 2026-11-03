<!--
Source of truth for the prompt used by the four scheduled "Dalal Pulse" WEEKDAY tasks.

The tasks are bound to a persistent worker session, and a task's prompt can only be changed
from the conversation it fires into. So editing this file does NOT change what runs.
To apply a change: open the worker session ("Dalal Pulse · feed worker (repo push)") and ask
it to pull this repo and update all four weekday tasks' prompts to the exact contents of
this file.

Keep this file and the live tasks in step — if they drift, this one is the intended text.
-->

NEW SCHEDULED RUN — refresh "Dalal Pulse", the Indian equity market note that powers the Markets Now screen of a broking app. Work fully unattended: never ask questions, never stop for confirmation.

Treat this as a fresh run. Do not carry over market figures, mood or insights from earlier runs in this conversation — every number must come from step 3's research or step 2's database read. Only the repo setup you confirmed earlier still holds.

ARTIFACT: https://claude.ai/artifact/THXPnLu5tkTTPTM9yYzGpH
Its page reads a shared database. Load the database tool first: ToolSearch "select:ArtifactData". Do NOT republish the page.

1) WORK OUT THE SLOT
Get the current time in IST (Asia/Kolkata). Date = today in IST, format YYYY-MM-DD.
The weekday slots are a FIXED list. Pick the one whose time is CLOSEST to the time now:

  0700  0845  0925  0955  1025  1055  1125  1155  1225  1255
  1325  1355  1425  1455  1525  1555  1625  1800  2100

Use the slot id exactly as written above. Do NOT invent a slot id from the clock: if the
scheduler fires a few minutes late and it is 09:28, the slot is still "0925", not "0928".
If two slots are equally close, take the earlier one.
If today is an NSE trading holiday: only on the "0845" run, write one note with mood label "Market closed" and insights about what matters for the next session; on all other runs, exit without writing. (Saturdays and Sundays are covered by a separate weekend task — if this one somehow fires on a weekend, exit without writing.)

2) READ CONTEXT (for continuity and de-duplication)
- ArtifactData list collection "days/<date>/notes" (today's notes so far).
- ArtifactData query collection "days" ordered by field "date" desc, limit 3, then list the notes of the most recent previous day.
Use these to (a) keep the mood narrative continuous, (b) reuse the SAME insight "key" whenever a story is the same story as an earlier insight (e.g. "irdai-caps", "nse-listing", "crude", "fii-flows", "us-yields"), and (c) avoid repeating stale items.

3) RESEARCH (WebSearch/WebFetch; aim for 6–10 searches; figures must be dated today)
What to cover depends on which slot you are writing. NSE trades 09:15–15:30 IST.

- 0700 (nothing is trading in India; the previous session is history): how Wall Street closed overnight, Asia's early trade, crude, the rupee, US yields, and any overnight policy or geopolitical news. This is the first read of the day for someone waking up.
- 0845 (pre-open): GIFT Nifty, the overnight global wrap, crude, rupee, the previous day's FII/DII figures, stocks in the news, IPO listings and events today.
- 0925 through 1555 (live session): current Nifty/Sensex level and move, breadth (midcap/smallcap), sector leaders and laggards, what is driving the move, and stock-specific news (orders, deals, upgrades/downgrades, block deals, regulatory actions, results) with % moves.
  For the leaders and for the laggards, also pin down the 2–4 names on EACH side that matter most, and for each one its move today plus the one specific reason it is where it is. These feed the tappable breakdown in step 4 — a name you cannot explain is not worth listing.
- 1625 (the close): closing figures, the sector wrap, FII/DII provisional data if out, and what matters for tomorrow.
- 1800 and 2100 (evening): what has developed SINCE the close — results announced after the bell, board decisions, regulatory orders, block deals reported late, management commentary — plus how the US market is trading and anything overnight that sets up tomorrow. By 2100 the US session is underway, so quote it as live, not as a close.

HOW FRESH YOUR FIGURES REALLY ARE. You are reading news copy, not a price feed. Index levels in news copy are snapshots published at round times (10 am, 11 am) and are typically 20–30 minutes old by the time you find them. Note the TIME each figure refers to, not just the figure. This matters for step 4: it is why index levels do not go in the prose.
Never invent numbers. If a figure is only approximate (e.g. from a headline), say so and set "approx": true on nifty.

4) WRITE THE NOTE — JSON with EXACTLY this shape:
{
 "asof": "<ISO 8601 with +05:30>",
 "summary": "<ONE sentence, ≤ 200 chars, about how the MARKET is trading — tone, breadth, direction. Must NOT restate the insight headlines, and must contain NO index levels or index point/% moves — see the prose rule below.>",
 "mood": {
   "label": "<2–3 words, e.g. 'Selling deepens', 'Cautious bounce'>",
   "score": <number from -1 (risk-off) to 1 (risk-on)>,
   "detail": {
     "stats": [],
     "leaders": "<sectors/stocks holding up, short>",
     "laggards": "<sectors/stocks under pressure, short>",
     "movers": {
       "up": {
         "summary": "<≤ 90 chars; the same substance as 'leaders', but written to stand alone>",
         "why": "<1–2 sentences: what is holding this side up>",
         "names": [
           {"name": "<stock or sector index, as a reader would recognise it>",
            "move": "<as reported, e.g. '+3.4%' or 'up ~3%'; OMIT this key if no figure is sourced>",
            "dir": "<up | down | flat — what the name itself did today>",
            "line": "<≤ 90 chars: why THIS name specifically, not a repeat of 'why'>"}
         ],
         "src": {"title": "...", "url": "..."}
       },
       "down": { <same shape, for the names under pressure> }
     },
     "tone": "<1–2 sentences on market behaviour vs the previous note. NO index levels or index point/% moves — see the prose rule below.>",
     "watch": ["<2–3 things that would change the mood>"],
     "src": {"title": "...", "url": "..."}
   }
 },
 "nifty": {"value": <number>, "pct": <number>, "chg": <number, optional>, "approx": <true if approximate>,
            "asof_quote": "<HH:MM IST that this PRINT refers to; live-session slots only>"},
       // OPTIONAL on live-session slots — see "WHAT nifty CARRIES" below. Omit the whole
       // key rather than carrying a stale level forward.
 "top": [   // as many as are genuinely relevant, MINIMUM 3; most important first
   {"key": "<stable kebab-case story id; reuse earlier key for the same story>",
    "tag": "<one of: Regulation, Global, Macro, Flows, Listing, Stocks, Opening, Results, Policy>",
    "impact": "<pos | neg | watch>",   // tailwind / headwind / watch for Indian equities
    "title": "<≤ 50 chars headline>",
    "line": "<≤ 90 chars one-liner>",
    "more": ["<2–4 short factual bullets>"],
    "src": {"title": "...", "url": "..."}}
 ],
 "sources": [{"title": "...", "url": "..."}]
}
Rules: the mood/summary describes HOW the market is trading; "top" covers WHY (the news). Do not put index-level moves in "top". Only include an insight again (same key) if there is genuinely new information; otherwise leave it out — older notes still show it.

NO INDEX LEVELS IN THE PROSE. This is the most important rule in this step.
"summary", "tone", "leaders", "laggards", "watch" and the "movers" summary/why lines must contain NO index levels and NO index point or percentage moves — no "the Sensex is up 818 points", no "Nifty at 23,667", no "up about 1%", no "+0.8%" for an index. The app shows a live, exact index level in its own header from its own market feed; a number you sourced 25 minutes ago sitting next to it reads as a contradiction, and carrying one forward reads as a lie.
Describe the market in words instead, which does not go stale the way a figure does: "holding near the day's high", "paring the early gain", "rangebound since the open", "broad, with midcaps joining in". Say WHERE the market is and WHICH WAY it is moving, never AT WHAT LEVEL.
This ban is on INDEX figures in prose only. It does not touch: the "nifty" block (structured, and the app can label it); per-name moves in "movers" (the "move" key is the right place for a stock's % change); or figures inside "top" insights, which are news facts (a deal size, a results number, a crude price) and not index readings.
Never compare against a previous note by quoting two clock times. "Firmer than the 10:55 note" next to "at 11 am the Sensex was…" mixes a slot label with a print time and reads as a contradiction. Say "firmer than the previous note" and leave it at that.

WHAT "nifty" CARRIES, BY SLOT. Never present a stale level as a live one.
- 0700 and 0845: the PREVIOUS session's close. Stable; always include it.
- 1625, 1800, 2100: TODAY's close and today's move. Stable; always include it.
- 0925 through 1555 (live session): the freshest index print you actually sourced, with its own time in "asof_quote" (e.g. "11:00" when you are writing the 1125 note — the time the PRINT refers to, not the time you are writing).
  If you cannot find a print NEWER than the one in the previous note, OMIT the entire "nifty" key from this note. Do not copy the previous note's figures forward. Still write and publish the note — the narrative is what the screen needs, and the app has its own live level. Say in "tone" that this is a read on market behaviour rather than a fresh print, in words and without numbers.

WHAT "mood" MEANS, BY SLOT. On 0700, 0845, 1800 and 2100 nothing is trading, so the mood is forward-looking: the risk appetite you expect into the next session, and a label to match ("Soft start likely", "Steady into tomorrow"). From 0925 to 1625 it is a reading of a live market. Say which one you mean in "tone" rather than leaving the reader to guess.

Rules for "movers": the app shows "leaders" and "laggards" collapsed and opens "movers" when the user taps them, so the two MUST agree — every name in the collapsed string should appear on the matching side, and vice versa. 2–4 names per side.
ONLY the live-session and close slots (0925 through 1625) carry "movers". On 0700, 0845, 1800 and 2100 nothing is moving, so OMIT "movers" entirely — "leaders" and "laggards" stay as plain forward-looking lines and the screen falls back to them.
On the slots that do carry it, do BOTH sides, on every note. "movers.down" is not optional garnish, and a note that fills in "up" while leaving "down" empty is incomplete.
A SECTOR IS A PERFECTLY GOOD ENTRY — this is the case that matters most, because the laggards line is sectoral more often than not. If it reads "metals and pharma", then "movers.down" carries "Nifty Metal" and "Nifty Pharma" as names, each with its index move and why it is lagging, exactly as you would for a stock. "Smallcaps trail midcaps" means an entry for "Nifty Smallcap 100" with its move. Use individual stocks when the line names them, sector indices when it names sectors, and both when it names both.
Omit a side ONLY when you genuinely could not source what its constituents are doing — never merely because the line is sectoral rather than stock-level. Never invent a move or a reason: omit "move" when no figure is sourced, and drop a name entirely when you cannot say why it is moving. A name may sit in "movers.up" while still down on the day if it is simply falling less than the market — set "dir" to what the name actually did. Do not recycle the "top" insights here: "movers" is about index constituents moving, "top" is about news.

5) SAVE
Save the JSON to a local file and write with ArtifactData:
- action "set", collection "days/<date>/notes", doc_id "<slot>", file_path <file>
- action "set", collection "days", doc_id "<date>", data {"date": "<date>"}
(Use one "batch" call for both.)

6) DELIVERY TO THE MOBILE APP
The repository fundsmaporg/sq_dalal_pulse is checked out in this session at /home/user/sq_dalal_pulse. Writing the note there and pushing it is a normal, authorised part of this job — the repository exists for exactly this. Do it without asking.
a) cd /home/user/sq_dalal_pulse, then: git checkout main && git pull origin main
b) Write the SAME JSON you saved in step 5 to days/<date>/<slot>.json, creating the day folder if needed.
c) Run: python3 scripts/build_feed.py   (it rebuilds latest.json from days/)
   Check its output names the date and slot you just wrote. If it does not, the note did not land — say so in your final message rather than pushing silently.
d) Run git add -A, commit with the message "Pulse <date> <slot>", then git push origin main. If the push is rejected because main moved, run git pull --rebase origin main and push again. Never open a pull request.
The GitHub Action then forwards latest.json to the app endpoint.
If any command here fails, quote the exact command and its exact error in your final message, and still do step 7.

7) FINISH with two lines: the slot + mood label, and the single most important insight.
