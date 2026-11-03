Pull fundsmaporg/sq_dalal_pulse and update the five scheduled tasks' prompts from the repo.

cd /home/user/sq_dalal_pulse && git checkout main && git pull origin main

Then set each task's prompt to the EXACT contents of the file below, excluding the
HTML comment block at the top of the file (everything from <!-- to --> is a note to
humans and must not go into the prompt). Use update_trigger with the prompt field.

Four tasks all get the SAME text, from scripts/routine-prompt.md:
  - Dalal Pulse · weekday 07:00 / 18:00 / 21:00 IST
  - Dalal Pulse · weekday 08:45 IST pre-open
  - Dalal Pulse · weekday :25 past (09:25–16:25 IST)
  - Dalal Pulse · weekday :55 past (09:55–15:55 IST)

One task gets the text from scripts/weekend-prompt.md:
  - Dalal Pulse · weekend (08:00 / 14:00 / 18:00 / 21:00 IST, Sat & Sun)

Do not touch the three tasks named "[RETIRED 2026-11-02] …". They are disabled on
purpose and must stay disabled.

WHAT CHANGED, so you can confirm it applied. Both prompts now ban index levels and
index point/percentage moves from the prose — summary, tone, leaders, laggards, watch
and the movers summary/why lines. The market gets described in words instead ("holding
near the day's high", "paring the early gain"), never at a level. Per-name moves inside
"movers" and figures inside "top" insights are unaffected. On a live-session slot, a run
that cannot source an index print newer than the previous note's now OMITS the whole
"nifty" key instead of copying the previous note's figures forward, and still publishes
the note. A new optional "nifty.asof_quote" carries the time the print refers to.

Reply with: the five task names you updated, and the first line of the "NO INDEX LEVELS
IN THE PROSE" paragraph as it now reads in each of the two prompts, so I can verify the
text landed rather than a paraphrase.
