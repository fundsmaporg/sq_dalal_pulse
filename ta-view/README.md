# Dalal Pulse · Technical View (MVP)

AI reasoning over computed values: a user picks an NSE stock and a horizon; a deterministic engine measures the
chart (pivots, levels, trendlines, pattern detectors with fit scores, indicators, weekly context) and produces an
evidence pack; a language model reads the pack plus annotated charts and returns a structured view; a checker
verifies every cited number; three samples must agree or the view is neutral. The UI draws the pattern on a
TradingView Lightweight Charts chart, shows the card, and offers a Pine Script export and a share card.

## Run it locally (two minutes)

```bash
cd ta-view
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
make demo            # or: uvicorn taview.api:app --port 8000
```

Open **http://localhost:8000** in your browser.

- Default data provider is the public NSE end-of-day mirror (`PRICE_PROVIDER=eod2`), so it works on any laptop with
  internet access. Nine stocks x three horizons are precomputed in `data/demo_views.json` and seeded into the store on first start; any other NSE symbol is computed on first request (a few seconds).
- Without `ANTHROPIC_API_KEY` the reasoner runs in **deterministic fallback** mode and says so on the card. Set the
  key to get real model views (`TAVIEW_MODEL`, default `claude-opus-5-5`; `TAVIEW_SAMPLES`, default 3).
- Share cards need Chromium via Playwright: `pip install playwright && playwright install chromium`.

## Inside the VPC with the PMSEC price service

```bash
export PRICE_PROVIDER=pmsec
export PRICE_SERVICE_URL=http://172.31.19.132:8766
export PRICE_INTERNAL_KEY=...            # from the secret store, never in code or git
python -m taview.batch --symbols NSE:BSE,NSE:RELIANCE --horizons swing,medium,long   # nightly precompute
uvicorn taview.api:app --host 0.0.0.0 --port 8000
```

The client implements the service rules: one symbol per history call, windows split to the per-interval maximum,
the candle after `to` dropped (known issue), `503 busy` waits `retry_after_ms`, `429` backs off five seconds,
`502` retried once, `400/401/403/404` never retried, bulk daily windows end two days back so they are cached for a
week, quotes batched 200 at a time, and a symbol is either priced or reported unavailable, never guessed. The
batch runs serially (one new window per second budget).

## Layout

| Path | What |
|---|---|
| `taview/engine.py` | features, causal pivots, levels, trendlines, detectors (cup & handle, rounding bottom, double top/bottom, head & shoulders, triangles/wedges, flags, rectangle, channel breakout), evidence pack, charts, geometry, Pine, checker, consensus |
| `taview/providers/` | `eod2.py` public mirror (daily), `pmsec.py` price-service client (daily, intraday, quotes) |
| `taview/reasoner.py` | Claude call with JSON-schema output and chart images; deterministic fallback; checker + unanimity gate |
| `taview/pipeline.py` | bars → engine → charts → reasoner → payload |
| `taview/api.py` | FastAPI: `/api/symbols`, `/api/view?symbol=&horizon=`, `/api/views`, `/api/card.png`, `/api/health`, static UI |
| `taview/batch.py` | nightly precompute CLI |
| `web/index.html` | the UI (Lightweight Charts + overlay primitive + card) |
| `web/card.html` | 1080×1920 share-card template |
| `tests/` | engine rules, checker, consensus, price-service client (mock HTTP), API end to end (offline) |

## Tests

```bash
pytest -q
```

## Configuration

See `.env.example`. Horizons: `swing` (daily, 250 bars, pivot order 5), `medium` (daily, 500 bars, order 10),
`long` (weekly, 260 bars, order 3). Intraday is wired in the provider but not exposed in this MVP.

## What was tested here

- `pytest`: 20 tests (engine rules on a designed cup-and-handle, causal pivots, double-top guard, checker tolerance and
  sign handling, consensus gate, price-service client against a mock transport, API end to end offline).
- Full pipeline run for 9 stocks x 3 horizons from the mirror data (as of 13 Oct 2026); API, UI (dark desktop,
  light phone, no overflow, no console errors) and card rendering verified in headless Chromium.
- Detector calibration on 120 random walks (250 daily bars, 1.3 %/day): a candidate above the 0.50 bar appears on
  **29 %** of pure-noise series (down from 87 % before the prior-trend and touch-count rules). That is the
  honest false-positive floor of rule-based detection; the next step is a human-labelled gold set to set
  per-pattern thresholds and precision, as described in the evaluation plan.

## What this is not

Prototype data from a community mirror is not a licensed feed; the engine's thresholds are not yet calibrated
against a human-labelled gold set; and a named-stock view is a research report under SEBI's Research Analyst
regulations, so a live product publishes it under a registered RA with the required disclosures. The UI and the
card carry the corresponding wording.
