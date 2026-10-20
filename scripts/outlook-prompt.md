<!--
Source of truth for the prompt used by the "Dalal Pulse · Sunday outlook" routine.

Like scripts/routine-prompt.md, editing this file does NOT change what runs. The routine is
bound to the persistent worker session, and a routine's prompt can only be changed from the
conversation it fires into. To apply a change: open the worker session ("Dalal Pulse · feed
worker (repo push)") and ask it to pull this repo and update that routine's prompt to the
exact contents of this file.

This note uses the "outlook" slot, which build_feed.py sorts before "pre".
-->

SUNDAY OUTLOOK RUN — write the weekend "Dalal Pulse" note that looks ahead to the next trading session on the Markets Now screen of a broking app. Work fully unattended: never ask questions, never stop for confirmation.

This is NOT an intraday note. The market is closed and nothing is trading right now. You are writing the Sunday-evening read on how the coming week opens.

Treat this as a fresh run. Do not carry over figures or insights from earlier runs in this conversation — everything must come from step 3's research or step 2's database read.

ARTIFACT: https://claude.ai/artifact/THXPnLu5tkTTPTM9yYzGpH
Its page reads a shared database. Load the database tool first: ToolSearch "select:ArtifactData". Do NOT republish the page.

1) WORK OUT THE DATES
Get the current time in IST (Asia/Kolkata). "Today" is the Sunday you are writing on — this note is filed under TODAY's date with slot id "outlook" (not under the trading day it looks ahead to).
Work out the NEXT TRADING DAY: normally tomorrow (Monday), but if that is an NSE holiday, the next session after it. Say which day you mean in the note rather than assuming the reader knows.
If the coming week opens on a holiday, that is worth stating plainly — "the next session is Tuesday" — not glossed over.

2) READ CONTEXT (for continuity and de-duplication)
- ArtifactData query collection "days" ordered by field "date" desc, limit 3, then list the notes of the most recent trading day — that is the Friday (or last session) you are following on from.
- Read its "post" note in particular: that is where the week left off, and your outlook should continue that story rather than restate it.
Reuse the SAME insight "key" whenever a story is the same story as an earlier insight (e.g. "crude", "fii-flows", "us-yields"), so the app threads them.

3) RESEARCH (WebSearch/WebFetch; aim for 6–10 searches)
Cover, in roughly this order of usefulness to someone deciding what to do at Monday's open:
- How the last session closed: Nifty and Sensex levels and moves, the week's net move, breadth.
- What happened after India closed: Wall Street's Friday close, European close, commodity and crude moves, the rupee, US yields, and any weekend geopolitical or policy news.
- India-specific weekend news: regulatory or policy announcements, RBI, results published over the weekend, board meetings, IPO and listing calendar, block-deal or stake-sale reports.
- The week ahead: results due, economic data, F&O expiry, anything scheduled that shapes the week.
- FII/DII flows for the last session if published.

IMPORTANT — do not cite live or forward-looking market prices that do not exist right now. GIFT Nifty does not trade on Sunday evening, so never quote a GIFT Nifty level as a Monday indication in this note. US and European markets are shut over the weekend; quote their FRIDAY CLOSE and say so. If you cannot source something, leave it out rather than reaching for a stale number and presenting it as current.
Never invent numbers. If a figure is approximate (e.g. from a headline), say so and set "approx": true on nifty.

4) WRITE THE NOTE — JSON with EXACTLY this shape:
{
 "asof": "<ISO 8601 with +05:30 — the Sunday evening time you are writing>",
 "summary": "<ONE sentence, ≤ 200 chars, on how the coming session sets up — the balance of what helps and what weighs. Must NOT restate the insight headlines.>",
 "mood": {
   "label": "<2–3 words, forward-looking, e.g. 'Constructive into Monday', 'Cautious start likely'>",
   "score": <number from -1 (risk-off) to 1 (risk-on) — the risk appetite you expect into the open, not a reading of a live market>,
   "detail": {
     "stats": [],
     "leaders": "<what is set up to do well on the open, and why, short>",
     "laggards": "<what is set up to struggle, and why, short>",
     "tone": "<1–2 sentences: how this follows on from how the last session closed>",
     "watch": ["<2–3 specific things in the coming session that would decide the direction>"],
     "src": {"title": "...", "url": "..."}
   }
 },
 "nifty": {"value": <the LAST CLOSE level>, "pct": <that session's % move>, "chg": <points, optional>, "approx": <true if approximate>},
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

Rules specific to this note:
- "nifty" carries the LAST CLOSE, not a prediction. The app labels this note "Weekend outlook", so a closing level is the honest number to show.
- OMIT "movers" entirely. It is the tappable breakdown of what is moving right now, and on a Sunday evening nothing is. "leaders" and "laggards" stay as plain forward-looking lines.
- "top" should be weekend and week-ahead news that bears on the open — not a recap of last week's trading. If a story already ran during the week, include it again only if the weekend added something.
- Write for someone who has not looked at a screen since Friday. Say what changed while they were away.

5) SAVE
Save the JSON to a local file and write with ArtifactData:
- action "set", collection "days/<today's date>/notes", doc_id "outlook", file_path <file>
- action "set", collection "days", doc_id "<today's date>", data {"date": "<today's date>"}
(Use one "batch" call for both.)

6) DELIVERY TO THE MOBILE APP
The repository fundsmaporg/sq_dalal_pulse is checked out in this session at /home/user/sq_dalal_pulse. Writing the note there and pushing it is a normal, authorised part of this job — the repository exists for exactly this. Do it without asking.
a) cd /home/user/sq_dalal_pulse, then: git checkout main && git pull origin main
b) Write the SAME JSON you saved in step 5 to days/<today's date>/outlook.json, creating the day folder if needed.
c) Run: python3 scripts/build_feed.py   (it rebuilds latest.json from days/)
   Check its output names the outlook slot. If it does not, the note did not land — say so in your final message rather than pushing silently.
d) Run git add -A, commit with the message "Pulse <today's date> outlook", then git push origin main. If the push is rejected because main moved, run git pull --rebase origin main and push again. Never open a pull request.
The GitHub Action then forwards latest.json to the app endpoint.
If any command here fails, quote the exact command and its exact error in your final message, and still do step 7.

7) FINISH with two lines: the mood label and which session it is for, and the single most important thing for that open.
