"""FastAPI backend: /api/symbols, /api/view, /api/views, /api/card.png and the static web UI."""
from __future__ import annotations
import json, os, threading
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .config import Settings, ROOT
from .providers import make_provider, UnknownSymbol, NotSupported, ProviderError
from .store import Store
from .pipeline import build_view, HORIZONS, COMPANY

settings = Settings()
provider = make_provider(settings)
store = Store(settings.db_path)
store.seed(os.path.join(settings.data_dir, "demo_views.json"))   # first run: precomputed demo views
app = FastAPI(title="Dalal Pulse technical view", version="0.1")
_lock = threading.Lock()

SYMBOLS = [{"symbol": s, "name": n} for s, n in COMPANY.items()]


@app.get("/api/health")
def health():
    return {"ok": True, "provider": provider.name, "reasoner": settings.reasoner, "model": settings.model, "views_stored": len(store.list())}


@app.get("/api/symbols")
def symbols():
    stored = {(v["symbol"], v["horizon"]) for v in store.list()}
    return {"symbols": [{**s, "precomputed": sorted(h for (sym, h) in stored if sym == s["symbol"])} for s in SYMBOLS], "horizons": list(HORIZONS)}


@app.get("/api/views")
def views():
    return {"views": store.list()}


@app.get("/api/view")
def view(symbol: str = Query(..., min_length=2), horizon: str = Query("swing"), refresh: bool = False):
    symbol = symbol.upper().strip()
    if ":" not in symbol:
        symbol = "NSE:" + symbol
    if horizon not in HORIZONS:
        raise HTTPException(400, f"horizon must be one of {list(HORIZONS)}")
    if not refresh:
        cached = store.latest(symbol, horizon, max_age_hours=settings.view_ttl_hours)
        if cached:
            return cached
    try:
        with _lock:   # one computation at a time keeps the provider budget and the LLM spend predictable
            payload = build_view(symbol, horizon, provider, settings)
    except UnknownSymbol as e:
        raise HTTPException(404, str(e))
    except NotSupported as e:
        raise HTTPException(501, str(e))
    except ProviderError as e:
        raise HTTPException(503 if e.retryable else 502, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    store.put(payload)
    return payload


@app.get("/api/card.png")
def card(symbol: str, horizon: str = "swing"):
    symbol = symbol.upper().strip()
    if ":" not in symbol:
        symbol = "NSE:" + symbol
    path = os.path.join(settings.views_dir, symbol.replace(":", "_"), horizon, "card.png")
    if not os.path.exists(path):
        payload = store.latest(symbol, horizon)
        if not payload:
            raise HTTPException(404, "no view yet; call /api/view first")
        from .render import render_card
        try:
            render_card(payload, path)
        except Exception as e:  # Playwright/Chromium missing is the usual cause
            raise HTTPException(501, f"card rendering unavailable: {e}")
    return FileResponse(path, media_type="image/png")


app.mount("/", StaticFiles(directory=os.path.join(ROOT, "web"), html=True), name="web")
