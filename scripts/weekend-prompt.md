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

This is normally NOT an intraday note: on an ordinary weekend Indian markets are closed and nothing is trading, and you are writing the read on how the next session sets up. The exception is a SPECIAL TRADING SESSION — see step 1 — which does happen on a weekend and which you must not describe as a closed market.

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

CHECK FOR A SPECIAL TRADING SESSION TODAY. The exchanges occasionally hold a session on a weekend day — the Diwali Muhurat hour is the usual one, and there are rare live risk-drill sessions. Search for it; do not assume the weekend is shut. If there is one today, find its exact window from the exchange circular as reported.
When a special session is happening today, this note is NOT a "nothing is trading" note, and the rules below change for the runs that fall around it:
- A run BEFORE the session opens: write it as a preview. Say when the session opens and closes, and what to watch in it. "nifty" still carries the last ordinary close.
- A run DURING the session: this is a LIVE note. Write it as one. "nifty" carries the live level with "asof_quote", and "movers" is allowed if you can source per-name detail — the usual weekend ban on "movers" does not apply to a live special session.
- A run AFTER the session closes: this is a real session that happened, and ITS CLOSE is now the last close. "nifty" carries the special session's closing level and its move, NOT the previous weekday close. Say plainly that it was the special session, since it is a short, thin, often ceremonial hour and a reader should not read it as a normal day. "movers" is allowed if sourced.
Never report a special session as if the market had been shut, and never skip over one because the day is a Saturday or Sunday.

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
 "nifty": {"value": <the LAST CLOSE level>, "pct": <that session's % move>, "chg": <points, optional>, "approx": <true if approximate>, "asof_quote": "<which close this is>"},
 "metrics": {   // ALL OPTIONAL — see "METRICS" below. Only what a source you read states.
   "brent_usd":  {"value": <number>, "asof": "<what close/time this figure is>", "approx": <bool>, "src": {"title":"...","url":"..."}},
   "usd_inr":    { ... },   "fii_net_cr": { ... },   "dii_net_cr": { ... },   "india_vix": { ... }
 },
 "top": [   // as many as are genuinely relevant, MINIMUM 3; most important first
   {"key": "<stable kebab-case story id; reuse earlier key for the same story>",
    "tag": "<one of: Regulation, Global, Macro, Flows, Listing, Stocks, Opening, Results, Policy>",
    "impact": "<pos | neg | watch>",   // tailwind / headwind / watch for Indian equities
    "title": "<≤ 50 chars headline>",
    "line": "<≤ 90 chars one-liner>",
    "more": ["<2–4 short factual bullets>"],
    "thread": "<OPTIONAL lowercase slug for the wider theme — see THREADS below>",
    "results": {   // OPTIONAL, only on a "Results" story whose source reports figures
      "company": "...", "quarter": "Q2 FY27",
      "revenue_cr": <number or null>, "revenue_yoy_pct": <number or null>,
      "profit_cr": <number or null>,  "profit_yoy_pct": <number or null>,
      "vs_estimate": <"beat" | "miss" | "inline", ONLY if a source says so, else null>,
      "reaction_pct": <share move as reported, else null>, "reaction_asof": "<time, optional>",
      "src": {"title": "...", "url": "..."}},
    "src": {"title": "...", "url": "..."}}
 ],
 "sources": [{"title": "...", "url": "..."}]
}

THE SUMMARY MUST STAND ALONE. Almost every reader sees ONLY the newest note — they never saw
the 08:00 or the 18:00 one. So the summary is never a comparison with an earlier note. Do not
open it with "Nothing new since…", "Unchanged since the evening note", "As in the 14:00 note",
or anything that assumes the reader has been following along. Describe the setup ITSELF, every
time, in plain words, as if this were the only note they will ever read.
If genuinely nothing has changed, that does not make the summary shorter or more meta — it
just means you write the same setup again in fresh words. The observation that it has been a
quiet stretch belongs in "tone", and nowhere else.

NO INDEX LEVELS IN THE PROSE. "summary", "tone", "leaders", "laggards" and "watch" must contain NO index levels and NO index point or percentage moves — no "the Nifty closed at 23,441", no "ended the week up 1.7%". The app shows an exact level in its own header from its own market feed, and the closing level already sits in the "nifty" block where it can be labelled properly. Describe the week in words: "closed the week on its highs", "gave back most of Thursday's gain", "a narrow week with breadth improving late".
This ban is on INDEX figures in prose only. Figures inside "top" insights are news facts (a deal size, a results number, a crude price, an FII flow) and are fine.

THREADS. A "thread" is the long-running theme a story belongs to. Before writing, read
threads/index.json in the repo — the registry of slugs already in use — and REUSE an existing
slug whenever the story continues that theme. Add a new slug only when a genuinely new theme
starts, and register it in threads/index.json as {"slug","title","first_seen"}. A story with
no wider theme gets no "thread" key. Lowercase letters, digits and hyphens only.

METRICS. Only what a source you actually read states this run, with the time that figure
refers to in "asof" ("Fri 6 Nov close", "Friday provisional"). Set "approx": true for a
rounded or headline figure. If you did not source a metric, OMIT it — never carry the
previous note's value forward and never estimate. fii_net_cr and dii_net_cr are PROVISIONAL
net figures in ₹ crore, negative meaning net selling. These are structured data: the ban on
index levels in the prose is unaffected and they never appear in "summary" or "tone".

Rules specific to the weekend notes:
- "nifty" carries the LAST CLOSE, not a prediction — and after a special session today, that means THAT session's close, not the previous weekday's. Add "asof_quote" naming which close it is, as HH:MM for a live print, or the session it belongs to otherwise (e.g. "Fri 6 Nov close", "Muhurat close"). The app labels every weekend note "Weekend outlook", so a closing level is the honest number to show.
- OMIT "movers" entirely on an ordinary weekend slot, when no special session is trading or has traded today. It is the tappable breakdown of what is moving right now, and over the weekend nothing is. "leaders" and "laggards" stay as plain forward-looking lines.
- "top" should be weekend and week-ahead news that bears on the open — not a recap of last week's trading. If a story already ran during the week, include it again only if the weekend added something.
- Write for someone who has not looked at a screen since Friday. Say what changed while they were away.
- A quiet weekend is a real outcome. If genuinely nothing has moved since your last note, say so in "tone" — in "tone" ONLY, never in "summary", which always describes the setup itself — and do not pad the note with recycled items to fill space. Still write the note in full: the screen should carry a current timestamp and a summary that reads normally to someone seeing it for the first time.

5) SAVE
Save the JSON to a local file and write with ArtifactData:
- action "set", collection "days/<today's date>/notes", doc_id "<slot>", file_path <file>
- action "set", collection "days", doc_id "<today's date>", data {"date": "<today's date>"}
(Use one "batch" call for both.)

6) DELIVERY TO THE MOBILE APP
The repository fundsmaporg/sq_dalal_pulse is checked out in this session at /home/user/sq_dalal_pulse. Writing the note there and pushing it is a normal, authorised part of this job — the repository exists for exactly this. Do it without asking.
a) cd /home/user/sq_dalal_pulse, then: git checkout main && git pull origin main
b) Write the SAME JSON you saved in step 5 to days/<today's date>/<slot>.json, creating the day folder if needed.
c) Run BOTH, in this order:
     python3 scripts/build_feed.py      (rebuilds latest.json from days/)
     python3 scripts/build_stories.py   (rebuilds stories/ and threads/ from days/)
   Check build_feed's output names the date and slot you just wrote. If it does not, the note did not land — say so in your final message rather than pushing silently.
   build_stories.py is safe to re-run and never touches a "dossier" already on disk.
d) Run git add -A, commit with the message "Pulse <today's date> <slot>", then git push origin main. If the push is rejected because main moved, run git pull --rebase origin main and push again. Never open a pull request.
The GitHub Action then forwards latest.json to the app endpoint.
If any command here fails, quote the exact command and its exact error in your final message, and still do step 7.

6b) DOSSIERS (after step 6c has rebuilt stories/, before the commit in 6d)
A dossier is the one-page write-up stored inside stories/<key>.json under "dossier". The
weekend is a good time to refresh them, since little is moving. Write or refresh one ONLY for
a story that qualifies: it has appeared in 3 or more notes (its "count" >= 3), OR it is
tagged Results, Policy or Regulation with impact "pos" or "neg". At most 15 in a day across
all runs; prefer the stories that changed most since their dossier's "written_at".
Shape, written as the "dossier" key of the existing stories/<key>.json, leaving every other
key in that file untouched:
{"headline": "...", "summary": "<2–3 sentences>",
 "status": "<developing | tracking | resolved>",
 "why_it_matters": ["..."], "moved": [{"name": "...", "dir": "up|down", "line": "..."}],
 "watch": ["..."], "questions": ["<short questions a reader would now have>"],
 "conflicts": ["<where the notes' own sources disagree>"],
 "written_at": "<ISO 8601 with +05:30>", "based_on_slots": ["2026-11-07/1800", "..."]}
Use ONLY what that story's own timeline entries and their sources say — do not research afresh
for a dossier. Where the notes said reports differ, keep both figures in "conflicts". Set
"status": "resolved" when the story has not appeared for 5 trading days. NO view on whether to
buy or sell anything; a broker call is quoted with attribution only ("Jefferies keeps Buy").

7) FINISH with two lines: the mood label and which session it is for, and the single most important thing for that open.
