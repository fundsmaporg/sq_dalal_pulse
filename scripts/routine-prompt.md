<!--
Source of truth for the prompt used by the two scheduled "Dalal Pulse" routines.

The routines are bound to a persistent worker session, and a routine's prompt can only be
changed from the conversation it fires into. So editing this file does NOT change what runs.
To apply a change: open the worker session ("Dalal Pulse · feed worker (repo push)") and ask
it to pull this repo and update both routines' prompts to the exact contents of this file.

Keep this file and the live routines in step — if they drift, this one is the intended text.
-->

NEW SCHEDULED RUN — refresh "Dalal Pulse", the half-hourly Indian equity market note that powers the Markets Now screen of a broking app. Work fully unattended: never ask questions, never stop for confirmation.

Treat this as a fresh run. Do not carry over market figures, mood or insights from earlier runs in this conversation — every number must come from step 3's research or step 2's database read. Only the repo setup you confirmed earlier still holds.

ARTIFACT: https://claude.ai/artifact/THXPnLu5tkTTPTM9yYzGpH
Its page reads a shared database. Load the database tool first: ToolSearch "select:ArtifactData". Do NOT republish the page.

1) WORK OUT THE SLOT
Get the current time in IST (Asia/Kolkata). Slot ids: "pre" (before 09:15), then "0930","1000",…,"1530" (every 30 min; pick the latest slot whose time has passed), and "post" (16:00 or later). Date = today in IST, format YYYY-MM-DD.
If today is an NSE trading holiday or weekend: only on the "pre" run, write one note with mood label "Market closed" and insights about what matters for the next session; on all other runs, exit without writing.

2) READ CONTEXT (for continuity and de-duplication)
- ArtifactData list collection "days/<date>/notes" (today's notes so far).
- ArtifactData query collection "days" ordered by field "date" desc, limit 3, then list the notes of the most recent previous day.
Use these to (a) keep the mood narrative continuous, (b) reuse the SAME insight "key" whenever a story is the same story as an earlier insight (e.g. "irdai-caps", "nse-listing", "crude", "fii-flows", "us-yields"), and (c) avoid repeating stale items.

3) RESEARCH (WebSearch/WebFetch; aim for 6–10 searches; figures must be dated today)
Pre-open: Gift Nifty, overnight US/Asia, crude, rupee, previous-day FII/DII, stocks in news, IPO listings/events.
Market hours: current Nifty/Sensex level and move, breadth (midcap/smallcap), sector leaders/laggards, what is driving the move, stock-specific news (orders, deals, upgrades/downgrades, block deals, regulatory actions, results) with % moves.
For the leaders and for the laggards, also pin down the 2–4 names on EACH side that matter most, and for each one its move today plus the one specific reason it is where it is. These feed the tappable breakdown in step 4 — a name you cannot explain is not worth listing.
Post-close: closing figures, sector wrap, FII/DII provisional data if out, what matters for tomorrow.
Never invent numbers. If a figure is only approximate (e.g. from a headline), say so and set "approx": true on nifty.

4) WRITE THE NOTE — JSON with EXACTLY this shape:
{
 "asof": "<ISO 8601 with +05:30>",
 "summary": "<ONE sentence, ≤ 200 chars, about how the MARKET is trading — tone, breadth, direction. Must NOT restate the insight headlines.>",
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
     "tone": "<1–2 sentences on market behaviour vs the previous note>",
     "watch": ["<2–3 things that would change the mood>"],
     "src": {"title": "...", "url": "..."}
   }
 },
 "nifty": {"value": <number>, "pct": <number>, "chg": <number, optional>, "approx": <true if approximate>},
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
Rules for "movers": the app shows "leaders" and "laggards" collapsed and opens "movers" when the user taps them, so the two MUST agree — every name in the collapsed string should appear on the matching side, and vice versa. 2–4 names per side.
Do BOTH sides. "movers.down" is not optional garnish: if the "laggards" line names any stock, "movers.down" must cover those names, and a note that fills in "up" while leaving "down" empty is incomplete. The only acceptable reason to omit a side is that its collapsed line names no individual stocks at all (e.g. laggards is just "metals and pharma" or "smallcaps") — then there is nothing per-name to stand behind. Never invent a move or a reason: omit "move" when no figure is sourced, and drop a name entirely when you cannot say why it is moving. A name may sit in "movers.up" while still down on the day if it is simply falling less than the market — set "dir" to what the name actually did. If you genuinely cannot source per-name detail this slot, omit "movers" altogether and the screen falls back to the plain lines. Do not recycle the "top" insights here: "movers" is about index constituents moving, "top" is about news.

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
d) Run git add -A, commit with the message "Pulse <date> <slot>", then git push origin main. If the push is rejected because main moved, run git pull --rebase origin main and push again. Never open a pull request.
The GitHub Action then forwards latest.json to the app endpoint.
If any command here fails, quote the exact command and its exact error in your final message, and still do step 7.

7) FINISH with two lines: the slot + mood label, and the single most important insight.
