<!--
Source of truth for the prompt used by the scheduled "Dalal Pulse · weekend" task
(Saturdays and Sundays, 08:00 / 14:00 / 18:00 / 21:00 IST).

Like scripts/routine-prompt.md, editing this file does NOT change what runs. The task is
bound to the persistent worker session, and a task's prompt can only be changed from the
conversation it fires into. To apply a change: open the worker session ("Dalal Pulse · feed
worker (repo push)") and ask it to pull this repo and update that task's prompt to the exact
contents of this file.

This replaces the old scripts/outlook-prompt.md, whose single Sunday-evening run is now the
Sunday 21:00 slot of this task.
-->

WEEKEND RUN — write the "Dalal Pulse" note that looks ahead to the next trading session on the Markets Now screen of a broking app. Work fully unattended: never ask questions, never stop for confirmation.

This is NOT an intraday note. Indian markets are closed and nothing is trading. You are writing the weekend read on how the next session sets up.

Treat this as a fresh run. Do not carry over figures or insights from earlier runs in this conversation — everything must come from step 3's research or step 2's database read.

ARTIFACT: https://claude.ai/artifact/THXPnLu5tkTTPTM9yYzGpH
Its page reads a shared database. Load the database tool first: ToolSearch "select:ArtifactData". Do NOT republish the page.

1) WORK OUT THE SLOT AND THE DATES
Get the current time in IST (Asia/Kolkata). "Today" is the Saturday or Sunday you are writing on — the note is filed under TODAY's date, not under the trading day it looks ahead to.
The weekend slots are a FIXED list. Pick the one whose time is CLOSEST to the time now:

  Saturday:  0800  1400  1800  2100
  Sunday:    0800  1400  1800  outlook      <- the 21:00 run uses the id "outlook"

Use the slot id exactly as written. Do NOT invent one from the clock: if the scheduler fires
late and it is 08:04, the slot is still "0800". The Sunday 21:00 run is the week's main
look-ahead, so it takes the id "outlook" — the app reads that as the cue to present the note
as a look-ahead rather than a live reading. The Saturday 21:00 run is an ordinary "2100".
If this task somehow fires on a weekday, exit without writing.

Work out the NEXT TRADING DAY: normally the coming Monday, but if that is an NSE holiday, the next session after it. Say which day you mean in the note rather than assuming the reader knows. If the week opens on a holiday, state it plainly — "the next session is Tuesday" — do not gloss over it.

2) READ CONTEXT (for continuity and de-duplication)
- ArtifactData list collection "days/<today's date>/notes" (this weekend day's notes so far).
- ArtifactData query collection "days" ordered by field "date" desc, limit 3, then list the notes of the most recent trading day — that is the Friday (or last session) you are following on from.
- Read that day's LAST note in particular: it is where the week left off, and your note should continue the story rather than restate it.
On the later runs of the day, read the earlier ones and say what has CHANGED since — a reader who saw the 08:00 note should not be served the same thing again at 14:00.
Reuse the SAME insight "key" whenever a story is the same story as an earlier insight (e.g. "crude", "fii-flows", "us-yields"), so the app threads them.

3) RESEARCH (WebSearch/WebFetch; aim for 6–10 searches)
Cover, in roughly this order of usefulness to someone deciding what to do at the next open:
- How the last session closed: Nifty and Sensex levels and moves, the week's net move, breadth.
- What happened after India closed: Wall Street's close, the European close, commodity and crude moves, the rupee, US yields, and any weekend geopolitical or policy news.
- India-specific weekend news: regulatory or policy announcements, RBI, results published over the weekend, board meetings, the IPO and listing calendar, block-deal or stake-sale reports.
- The week ahead: results due, economic data, F&O expiry, anything scheduled that shapes it.
- FII/DII flows for the last session if published.

IMPORTANT — do not cite live or forward-looking market prices that do not exist right now. GIFT Nifty does not trade over the weekend, so never quote a GIFT Nifty level as an indication in these notes. US and European markets are shut from Friday evening to Monday, so quote their FRIDAY CLOSE and say so. If you cannot source something, leave it out rather than reaching for a stale number and presenting it as current.
Never invent numbers. If a figure is approximate (e.g. from a headline), say so and set "approx": true on nifty.

4) WRITE THE NOTE — JSON with EXACTLY this shape:
{
 "asof": "<ISO 8601 with +05:30 — the time you are writing>",
 "summary": "<ONE sentence, ≤ 200 chars, on how the coming session sets up — the balance of what helps and what weighs. Must NOT restate the insight headlines, and must contain NO index levels or index point/% moves — see the prose rule below.>",
 "mood": {
   "label": "<2–3 words, forward-looking, e.g. 'Constructive into Monday', 'Cautious start likely'>",
   "score": <number from -1 (risk-off) to 1 (risk-on) — the risk appetite you expect into the open, not a reading of a live market>,
   "detail": {
     "stats": [],
     "leaders": "<what is set up to do well on the open, and why, short>",
     "laggards": "<what is set up to struggle, and why, short>",
     "tone": "<1–2 sentences: how this follows on from the last session, and from the earlier note today if there was one>",
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

NO INDEX LEVELS IN THE PROSE. "summary", "tone", "leaders", "laggards" and "watch" must contain NO index levels and NO index point or percentage moves — no "the Nifty closed at 23,441", no "ended the week up 1.7%". The app shows an exact level in its own header from its own market feed, and the closing level already sits in the "nifty" block where it can be labelled properly. Describe the week in words: "closed the week on its highs", "gave back most of Thursday's gain", "a narrow week with breadth improving late".
This ban is on INDEX figures in prose only. Figures inside "top" insights are news facts (a deal size, a results number, a crude price, an FII flow) and are fine.

Rules specific to the weekend notes:
- "nifty" carries the LAST CLOSE, not a prediction. The app labels every weekend note "Weekend outlook", so a closing level is the honest number to show.
- OMIT "movers" entirely, on every weekend slot. It is the tappable breakdown of what is moving right now, and over the weekend nothing is. "leaders" and "laggards" stay as plain forward-looking lines.
- "top" should be weekend and week-ahead news that bears on the open — not a recap of last week's trading. If a story already ran during the week, include it again only if the weekend added something.
- Write for someone who has not looked at a screen since Friday. Say what changed while they were away.
- A quiet weekend is a real outcome. If genuinely nothing has moved since your last note, say so plainly in "tone" and keep the note short — do not pad it with recycled items to fill space. Still write the note: the screen should carry a current timestamp.

5) SAVE
Save the JSON to a local file and write with ArtifactData:
- action "set", collection "days/<today's date>/notes", doc_id "<slot>", file_path <file>
- action "set", collection "days", doc_id "<today's date>", data {"date": "<today's date>"}
(Use one "batch" call for both.)

6) DELIVERY TO THE MOBILE APP
The repository fundsmaporg/sq_dalal_pulse is checked out in this session at /home/user/sq_dalal_pulse. Writing the note there and pushing it is a normal, authorised part of this job — the repository exists for exactly this. Do it without asking.
a) cd /home/user/sq_dalal_pulse, then: git checkout main && git pull origin main
b) Write the SAME JSON you saved in step 5 to days/<today's date>/<slot>.json, creating the day folder if needed.
c) Run: python3 scripts/build_feed.py   (it rebuilds latest.json from days/)
   Check its output names the date and slot you just wrote. If it does not, the note did not land — say so in your final message rather than pushing silently.
d) Run git add -A, commit with the message "Pulse <today's date> <slot>", then git push origin main. If the push is rejected because main moved, run git pull --rebase origin main and push again. Never open a pull request.
The GitHub Action then forwards latest.json to the app endpoint.
If any command here fails, quote the exact command and its exact error in your final message, and still do step 7.

7) FINISH with two lines: the mood label and which session it is for, and the single most important thing for that open.
