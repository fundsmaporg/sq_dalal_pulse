"""Orchestration: bars -> engine -> charts -> reasoner -> stored view payload (what the API serves)."""
from __future__ import annotations
import json, os
from datetime import datetime, timedelta, timezone
import pandas as pd
from . import engine as E
from .reasoner import reason

IST = timezone(timedelta(hours=5, minutes=30))
HORIZONS = {"swing": E.HORIZON["swing"], "medium": E.HORIZON["medium"], "long": E.HORIZON["long"]}
COMPANY = {"NSE:BSE": "BSE Ltd", "NSE:RELIANCE": "Reliance Industries", "NSE:HDFCBANK": "HDFC Bank", "NSE:TCS": "Tata Consultancy Services", "NSE:SBIN": "State Bank of India",
           "NSE:TATASTEEL": "Tata Steel", "NSE:BAJFINANCE": "Bajaj Finance", "NSE:INFY": "Infosys", "NSE:ITC": "ITC"}


def _dstr(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, IST).strftime("%Y-%m-%d")


def compute(symbol: str, horizon: str, bars: pd.DataFrame, out_dir: str, provenance: str) -> dict:
    """Deterministic stage. Writes evidence_pack.json, model_input_*.png into out_dir and returns the pieces."""
    if horizon not in HORIZONS:
        raise ValueError(f"unknown horizon {horizon}")
    H = HORIZONS[horizon]
    if horizon == "long":
        full = bars.resample("W-FRI").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
    else:
        full = bars.copy()
    if len(full) < 60:
        raise ValueError(f"{symbol}: only {len(full)} bars, need at least 60")
    full, _ = E.features(full.copy())
    df = full.iloc[-H["lookback"]:].copy()
    _, feats = E.features(full.copy())
    w, wctx = E.weekly_context(bars, H["ctx_bars"]) if horizon != "long" else E.weekly_context(bars, 156)
    piv = E.pivots(df, H["order"])
    atr_v = float(df.ATR14.iloc[-1])
    sup, res = E.levels(piv, float(df.Close.iloc[-1]), atr_v)
    tls = E.trendlines(piv, df, atr_v)
    struct = E.structure_facts(piv)
    cands = E.run_detectors(df, piv, H["order"], atr_v, tls)
    flags = []
    r = (df.Close.shift(1) / df.Open)
    for f in (2, 3, 1.5, 4, 5, 10):
        for d in df[(r > f * 0.95) & (r < f * 1.05)].index:
            flags.append({"date": str(d.date()), "ratio": round(float(r[d]), 3), "likely": f"{f}:1-style adjustment missing"})
    prov = {"source": provenance, "last_bar": str(df.index[-1].date()), "note": "prototype data unless the provider is the licensed feed"}
    pack = E.build_pack(symbol, COMPANY.get(symbol, symbol.split(":")[-1]), horizon, df, feats, wctx, piv, sup, res, tls, struct, cands, flags, prov)
    pack["interval"] = "1W" if horizon == "long" else "1D"
    os.makedirs(out_dir, exist_ok=True)
    json.dump(pack, open(os.path.join(out_dir, "evidence_pack.json"), "w"), indent=1, default=str)
    json.dump({"candidates": cands, "pivots": piv}, open(os.path.join(out_dir, "_internal.json"), "w"), default=str)
    daily_png, weekly_png = os.path.join(out_dir, "model_input_daily.png"), os.path.join(out_dir, "model_input_weekly.png")
    E.model_input_chart(df, piv, sup, res, tls, pack, daily_png)
    E.weekly_chart(w, pack, weekly_png)
    return {"pack": pack, "cands": cands, "piv": piv, "df": df, "images": [daily_png, weekly_png]}


def assemble(symbol: str, horizon: str, computed: dict, reasoned: dict, bars: pd.DataFrame, settings) -> dict:
    """Build the payload the UI consumes: bars, geometry, card, consensus, pine, facts."""
    pack, cands, df = computed["pack"], computed["cands"], computed["df"]
    card, cons = reasoned["card"], reasoned["consensus"]
    pid = card.get("pattern_id")
    cand = next((c for c in cands if c["id"] == pid), None)
    view = {"symbol": symbol, "interval": pack["interval"], "as_of": pack["as_of"], "view": cons["final_view"]}
    geo, pine = None, None
    if cand:
        geo = E.geometry_for(df, cand, view)
        for p in geo["primitives"]:
            for q in p.get("points", []): q["d"] = _dstr(q["t"])
            for k in ("t", "from", "to", "t1", "t2"):
                if k in p: p[k + "_d"] = _dstr(p[k])
        pine = E.to_pine(geo, " ".join(r["text"] for r in card.get("reasons", [])))
    n_bars = 500 if horizon != "long" else 260
    series = bars if horizon != "long" else df
    out_bars = [{"time": d.strftime("%Y-%m-%d"), "open": float(r.Open), "high": float(r.High), "low": float(r.Low), "close": float(r.Close), "volume": int(r.Volume)}
                for d, r in series.tail(n_bars).iterrows()]
    tv_interval = "W" if horizon == "long" else "D"
    return {"schema": "dalal-pulse/view/v0", "symbol": symbol, "company": pack["company"], "horizon": horizon, "interval": pack["interval"], "as_of": pack["as_of"],
            "view": cons["final_view"], "setup": cons["final_setup"], "confidence": card.get("confidence"), "headline": card.get("headline"),
            "reasons": card.get("reasons", []), "invalidation": card.get("invalidation"), "levels": card.get("levels"), "what_would_strengthen": card.get("what_would_strengthen", []),
            "what_to_watch": card.get("what_to_watch", []), "image_check": card.get("image_check"), "horizon_note": card.get("horizon_note"),
            "facts": {f["id"]: f["text"] for f in pack["facts"]}, "candidate": cand and {k: v for k, v in cand.items() if k not in ("geometry", "last_anchor_i")},
            "candidates": [{k: v for k, v in c.items() if k not in ("geometry", "last_anchor_i")} for c in cands],
            "support": pack["levels"]["support"], "resistance": pack["levels"]["resistance"], "trendlines": pack["levels"]["trendlines"],
            "consensus": cons, "samples": [{"id": s["_id"], "view": s["view"], "setup": s["setup"], "pattern_id": s.get("pattern_id"), "confidence": s.get("confidence"), "checker": s["_problems"], "headline": s.get("headline")} for s in reasoned["samples"]],
            "reasoner": reasoned["reasoner"], "reasoner_mode": reasoned["mode"], "geometry": geo, "pine": pine,
            "tv_link": f"https://www.tradingview.com/chart/?symbol={symbol.replace(':', '%3A')}&interval={tv_interval}",
            "provenance": pack["data_provenance"], "corporate_action_flags": pack.get("corporate_action_flags", []), "bars": out_bars,
            "generated_at": datetime.now(IST).isoformat(timespec="seconds")}


def build_view(symbol: str, horizon: str, provider, settings, samples: list[dict] | None = None) -> dict:
    symbol = symbol.upper().strip()
    if ":" not in symbol:
        symbol = "NSE:" + symbol
    bars = provider.daily(symbol, years=6 if horizon == "long" else 3)
    out_dir = os.path.join(settings.views_dir, symbol.replace(":", "_"), horizon)
    computed = compute(symbol, horizon, bars, out_dir, provenance=f"{provider.name} provider")
    reasoned = reason(computed["pack"], computed["images"], settings, samples=samples)
    payload = assemble(symbol, horizon, computed, reasoned, bars, settings)
    json.dump(payload, open(os.path.join(out_dir, "view.json"), "w"), default=str)
    return payload
