"""
Deterministic technical-analysis engine: features, causal pivots, levels, trendlines, pattern detectors,
evidence pack, charts, geometry, Pine export, output checker.

Stages
  1. load daily OHLCV (already bonus/split adjusted) and verify no residual corporate-action cliffs
  2. features: EMAs, RSI, MACD, ATR, Bollinger, volume stats, 52-week position, returns, weekly context
  3. structure: causal swing pivots (confirmed only after `order` bars), support/resistance clusters, trendlines
  4. detectors (deterministic geometry + 0-1 fit score + status): cup & handle, rounding bottom,
     double top/bottom, head & shoulders (+inverse), triangles/wedges, flag/pennant, rectangle
  5. evidence pack JSON: every number the model may use carries a fact id
  6. charts: model-input chart (no pattern overlay, lettered pivots, levels), weekly context chart
  7. (external) k independent model samples read the pack + chart and return a structured view
  8. checker: cited ids exist, every number in the prose exists in the pack, unanimity gate
  9. final: user chart with the chosen pattern drawn, geometry JSON, Pine Script

Usage: python ta_view.py --csv data/bse_daily.csv --symbol NSE:BSE --name "BSE Ltd" --horizon swing --out out
       python ta_view.py --finalize out --samples out/samples/*.json
"""
import argparse, glob, json, math, re, sys
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
from scipy.signal import argrelextrema
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplfinance as mpf

IST = timezone(timedelta(hours=5, minutes=30))
HORIZON = {  # primary interval, lookback bars, pivot order, context interval
    "swing":  dict(interval="1D", lookback=250, order=5,  ctx="1W", ctx_bars=156),
    "medium": dict(interval="1D", lookback=500, order=10, ctx="1W", ctx_bars=156),
    "long":   dict(interval="1W", lookback=260, order=3,  ctx="1M", ctx_bars=120),
}

# ----------------------------------------------------------------------------- helpers
def ts_ms(d):  # NSE daily bar open 09:15 IST as unix ms
    d = pd.Timestamp(d)
    return int(datetime(d.year, d.month, d.day, 9, 15, tzinfo=IST).timestamp() * 1000)

def pct(a, b):
    return (a / b - 1.0) * 100.0

def r2_of(y, fit):
    ss = ((y - y.mean()) ** 2).sum()
    return 1 - ((y - fit) ** 2).sum() / ss if ss > 0 else 0.0

def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()

def rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

def atr(df, n=14):
    pc = df.Close.shift(1)
    tr = pd.concat([df.High - df.Low, (df.High - pc).abs(), (df.Low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()

# ----------------------------------------------------------------------------- 1. load
def load(csv):
    df = pd.read_csv(csv)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df[["Date", "Open", "High", "Low", "Close", "Volume"]].dropna().sort_values("Date").drop_duplicates("Date")
    df = df.set_index("Date")
    # residual corporate-action cliffs: open/prev_close ratio near a bonus/split factor with a volume jump
    r = (df.Close.shift(1) / df.Open)
    flags = []
    for f in (2, 3, 1.5, 4, 5, 10):
        hit = df[(r > f * 0.95) & (r < f * 1.05)]
        for d in hit.index:
            flags.append({"date": str(d.date()), "ratio": round(float(r[d]), 3), "likely": f"{f}:1-style adjustment missing"})
    return df, flags

# ----------------------------------------------------------------------------- 2. features
def features(df):
    f = {}
    c = df.Close
    for n in (20, 50, 200):
        if len(df) >= n:
            df[f"EMA{n}"] = ema(c, n)
    df["RSI14"] = rsi(c)
    m = ema(c, 12) - ema(c, 26); sig = ema(m, 9)
    df["MACD"], df["MACDsig"], df["MACDhist"] = m, sig, m - sig
    df["ATR14"] = atr(df)
    mid = c.rolling(20).mean(); sd = c.rolling(20).std()
    df["BBu"], df["BBl"] = mid + 2 * sd, mid - 2 * sd
    df["VolSMA20"] = df.Volume.rolling(20).mean()
    df["VolZ"] = (df.Volume - df.VolSMA20) / df.Volume.rolling(20).std()
    last = df.iloc[-1]
    n = len(df)
    hi52 = df.High.iloc[-250:].max(); lo52 = df.Low.iloc[-250:].min()
    f["last_close"] = round(float(last.Close), 2)
    f["last_date"] = str(df.index[-1].date())
    f["ret_1w_pct"] = round(pct(last.Close, df.Close.iloc[-6]), 2) if n > 6 else None
    f["ret_1m_pct"] = round(pct(last.Close, df.Close.iloc[-22]), 2) if n > 22 else None
    f["ret_3m_pct"] = round(pct(last.Close, df.Close.iloc[-64]), 2) if n > 64 else None
    f["ret_6m_pct"] = round(pct(last.Close, df.Close.iloc[-126]), 2) if n > 126 else None
    f["high_52w"] = round(float(hi52), 2); f["low_52w"] = round(float(lo52), 2)
    f["dist_from_52w_high_pct"] = round(pct(last.Close, hi52), 2)
    f["dist_from_52w_low_pct"] = round(pct(last.Close, lo52), 2)
    f["high_52w_date"] = str(df.High.iloc[-250:].idxmax().date())
    for k in ("EMA20", "EMA50", "EMA200"):
        if k in df:
            f[k] = round(float(last[k]), 2); f[f"close_vs_{k}_pct"] = round(pct(last.Close, last[k]), 2)
    f["ema_alignment"] = ("bullish (20>50>200)" if all(k in df for k in ("EMA20", "EMA50", "EMA200")) and last.EMA20 > last.EMA50 > last.EMA200
                          else "bearish (20<50<200)" if all(k in df for k in ("EMA20", "EMA50", "EMA200")) and last.EMA20 < last.EMA50 < last.EMA200
                          else "mixed")
    f["RSI14"] = round(float(last.RSI14), 1)
    f["MACD_hist"] = round(float(last.MACDhist), 2)
    f["MACD_state"] = "above signal" if last.MACD > last.MACDsig else "below signal"
    f["ATR14"] = round(float(last.ATR14), 2); f["ATR14_pct"] = round(float(last.ATR14 / last.Close * 100), 2)
    f["BB_position"] = round(float((last.Close - last.BBl) / (last.BBu - last.BBl)), 2) if last.BBu > last.BBl else None
    f["volume_last"] = int(last.Volume); f["volume_sma20"] = int(last.VolSMA20)
    f["volume_ratio_vs_20d"] = round(float(last.Volume / last.VolSMA20), 2)
    f["volume_ratio_last5_vs_20d"] = round(float(df.Volume.iloc[-5:].mean() / last.VolSMA20), 2)
    return df, f

def weekly_context(df_full, bars=156):
    w = df_full.resample("W-FRI").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
    w = w.iloc[-bars:]
    w["EMA10"], w["EMA40"] = ema(w.Close, 10), ema(w.Close, 40)
    last = w.iloc[-1]
    hi, lo = argrelextrema(w.High.values, np.greater_equal, order=3)[0], argrelextrema(w.Low.values, np.less_equal, order=3)[0]
    ph = [float(w.High.iloc[i]) for i in hi[-3:]]; pl = [float(w.Low.iloc[i]) for i in lo[-3:]]
    structure = ("higher highs and higher lows" if len(ph) >= 2 and len(pl) >= 2 and ph[-1] > ph[-2] and pl[-1] > pl[-2]
                 else "lower highs and lower lows" if len(ph) >= 2 and len(pl) >= 2 and ph[-1] < ph[-2] and pl[-1] < pl[-2] else "mixed")
    ctx = {"interval": "1W", "bars": len(w), "trend": "up" if last.Close > last.EMA10 > last.EMA40 else "down" if last.Close < last.EMA10 < last.EMA40 else "mixed",
           "close_vs_EMA10_pct": round(pct(last.Close, last.EMA10), 2), "close_vs_EMA40_pct": round(pct(last.Close, last.EMA40), 2),
           "structure_last_3_pivots": structure, "ret_26w_pct": round(pct(last.Close, w.Close.iloc[-27]), 2) if len(w) > 27 else None,
           "ret_52w_pct": round(pct(last.Close, w.Close.iloc[-53]), 2) if len(w) > 53 else None,
           "weekly_high_all": round(float(w.High.max()), 2), "weekly_high_date": str(w.High.idxmax().date())}
    return w, ctx

# ----------------------------------------------------------------------------- 3. structure
def pivots(df, order):
    """Causal pivots: a pivot is only known `order` bars after it forms."""
    n = len(df)
    hi = [int(i) for i in argrelextrema(df.High.values, np.greater_equal, order=order)[0] if i <= n - 1 - order]
    lo = [int(i) for i in argrelextrema(df.Low.values, np.less_equal, order=order)[0] if i <= n - 1 - order]
    piv = [{"i": i, "type": "H", "price": float(df.High.iloc[i]), "date": str(df.index[i].date())} for i in hi] + \
          [{"i": i, "type": "L", "price": float(df.Low.iloc[i]), "date": str(df.index[i].date())} for i in lo]
    piv.sort(key=lambda p: p["i"])
    # alternate: within a run of same-type pivots keep the extreme
    alt = []
    for p in piv:
        if alt and alt[-1]["type"] == p["type"]:
            if (p["type"] == "H" and p["price"] >= alt[-1]["price"]) or (p["type"] == "L" and p["price"] <= alt[-1]["price"]):
                alt[-1] = p
        else:
            alt.append(p)
    for k, p in enumerate(alt):
        p["id"] = f"P{k + 1}"
    return alt

def levels(piv, close, atr_v, tol_pct=1.5):
    tol = max(close * tol_pct / 100, atr_v)
    prices = sorted(p["price"] for p in piv)
    clusters = []
    for p in prices:
        if clusters and p - clusters[-1][-1] <= tol:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    out = []
    for c in clusters:
        if len(c) >= 2:
            lvl = float(np.mean(c))
            touches = len(c)
            out.append({"price": round(lvl, 2), "touches": touches, "kind": "support" if lvl < close else "resistance",
                        "dist_pct": round(pct(lvl, close), 2)})
    sup = sorted([l for l in out if l["kind"] == "support"], key=lambda l: -l["price"])[:3]
    res = sorted([l for l in out if l["kind"] == "resistance"], key=lambda l: l["price"])[:3]
    return sup, res

def fit_line(xs, ys):
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    if len(xs) < 2:
        return None
    a, b = np.polyfit(xs, ys, 1)
    res = np.abs(ys - (a * xs + b))
    return {"slope": float(a), "intercept": float(b), "max_res": float(res.max())}

def trendlines(piv, df, atr_v):
    """Lines through the last 3+ pivot lows (support) / highs (resistance) with all residuals < 0.6 ATR."""
    n = len(df); out = []
    for typ, name in (("L", "rising_support" ), ("H", "falling_resistance")):
        pts = [p for p in piv if p["type"] == typ][-6:]
        best = None
        for k in (5, 4, 3):
            if len(pts) >= k:
                sub = pts[-k:]
                ln = fit_line([p["i"] for p in sub], [p["price"] for p in sub])
                if ln and ln["max_res"] <= 0.6 * atr_v:
                    best = (sub, ln); break
        if best:
            sub, ln = best
            val_now = ln["slope"] * (n - 1) + ln["intercept"]
            out.append({"kind": name if (ln["slope"] > 0) == (typ == "L") else ("falling_support" if typ == "L" else "rising_resistance"),
                        "through": [p["id"] for p in sub], "slope_pct_per_bar": round(ln["slope"] / val_now * 100, 3),
                        "value_at_last_bar": round(val_now, 2), "from": sub[0]["date"],
                        "anchors": [{"date": sub[0]["date"], "price": round(ln["slope"] * sub[0]["i"] + ln["intercept"], 2)},
                                    {"date": str(df.index[-1].date()), "price": round(val_now, 2)}]})
    return out

def structure_facts(piv):
    hs = [p for p in piv if p["type"] == "H"][-3:]; ls = [p for p in piv if p["type"] == "L"][-3:]
    def seq(ps):
        return ["up" if ps[i]["price"] > ps[i - 1]["price"] else "down" for i in range(1, len(ps))]
    return {"last_pivot_highs": [{"id": p["id"], "date": p["date"], "price": round(p["price"], 2)} for p in hs],
            "last_pivot_lows": [{"id": p["id"], "date": p["date"], "price": round(p["price"], 2)} for p in ls],
            "highs_sequence": seq(hs), "lows_sequence": seq(ls)}

# ----------------------------------------------------------------------------- 4. detectors
def status_from(close, breakout, direction, fail_level=None):
    if direction == "bullish":
        if close > breakout: return "confirmed"
        if fail_level is not None and close < fail_level: return "failed"
        return "forming"
    else:
        if close < breakout: return "confirmed"
        if fail_level is not None and close > fail_level: return "failed"
        return "forming"

def recency_weight(last_anchor_i, n, half_life=60):
    return 0.5 ** ((n - 1 - last_anchor_i) / half_life)

def prior_move_pct(closes, i, lookback=60):
    """Percent move into bar i over the preceding `lookback` bars (reversal patterns need a trend to reverse)."""
    j = max(0, i - lookback)
    return (closes[i] / closes[j] - 1) * 100 if i > j else 0.0

def det_cup_and_handle(df, piv, order):
    highs, lows, closes = df.High.values, df.Low.values, df.Close.values
    n = len(df); out = []
    ph = [p for p in piv if p["type"] == "H"]
    for a in range(len(ph)):
        for b in range(a + 1, len(ph)):
            L, R = ph[a]["i"], ph[b]["i"]; span = R - L
            if span < 30 or span > 160: continue
            rimL, rimR = highs[L], highs[R]
            if abs(rimR - rimL) / rimL > 0.05: continue
            if prior_move_pct(closes, L, 60) < 12: continue   # O'Neil: a cup needs a prior uptrend
            rim = min(rimL, rimR); seg = lows[L:R + 1]
            t_rel = int(np.argmin(seg)); T = L + t_rel; depth = rim - lows[T]
            if not (0.08 <= depth / rim <= 0.40) or not (0.25 <= t_rel / span <= 0.75): continue
            x = np.arange(span + 1); coef = np.polyfit(x, seg, 2)
            if coef[0] <= 0: continue
            r2 = r2_of(seg, np.polyval(coef, x))
            if r2 < 0.70: continue
            after = lows[R + 1:min(R + 36, n)]
            if len(after) < 4: continue
            hb = int(np.argmin(after)); H = R + 1 + hb; hdepth = rim - lows[H]
            if hdepth <= 0 or hdepth / depth >= 0.5 or hb < 2: continue
            close = closes[-1]
            st = status_from(close, rim, "bullish", fail_level=lows[H] * 0.98)
            vol_base = df.Volume.iloc[T - 10:T + 10].mean(); vol_recent = df.Volume.iloc[-5:].mean()
            volf = min(1.0, 0.7 + 0.3 * min(vol_recent / vol_base, 2) / 2)
            score = r2 * (1 - hdepth / depth) * (1 - abs(rimR - rimL) / rimL * 5) * volf
            target = rim + depth; stop = lows[H] * 0.99
            out.append(dict(pattern="cup_and_handle", direction="bullish", status=st, score=round(float(score), 3),
                            components=dict(cup_fit_r2=round(r2, 3), cup_depth_pct=round(depth / rim * 100, 1), span_bars=int(span),
                                            rim_mismatch_pct=round(abs(rimR - rimL) / rimL * 100, 2), handle_retrace_pct_of_cup=round(hdepth / depth * 100, 1),
                                            handle_bars=int(hb + 1), volume_recent_vs_base=round(float(vol_recent / vol_base), 2)),
                            anchors=[dict(role="left_rim", i=L), dict(role="cup_low", i=T), dict(role="right_rim", i=R), dict(role="handle_low", i=H)],
                            levels=dict(breakout=round(rim, 2), target=round(target, 2), stop=round(stop, 2)),
                            last_anchor_i=H, geometry=dict(kind="cup", L=L, T=T, R=R, H=H, coef=[float(c) for c in coef], rim=float(rim))))
    return out

def det_rounding_bottom(df, piv, order):
    highs, lows, closes = df.High.values, df.Low.values, df.Close.values
    n = len(df); out = []
    ph = [p for p in piv if p["type"] == "H"]
    for a in range(len(ph)):
        for b in range(a + 1, len(ph)):
            L, R = ph[a]["i"], ph[b]["i"]; span = R - L
            if span < 40 or span > 200 or n - 1 - R > 25: continue
            rimL, rimR = highs[L], highs[R]
            if abs(rimR - rimL) / rimL > 0.08: continue
            if prior_move_pct(closes, L, 60) > -12: continue   # a rounding bottom reverses a decline
            rim = min(rimL, rimR); seg = lows[L:R + 1]
            t_rel = int(np.argmin(seg)); T = L + t_rel; depth = rim - lows[T]
            if not (0.10 <= depth / rim <= 0.45) or not (0.3 <= t_rel / span <= 0.7): continue
            x = np.arange(span + 1); coef = np.polyfit(x, seg, 2)
            if coef[0] <= 0: continue
            r2 = r2_of(seg, np.polyval(coef, x))
            if r2 < 0.80: continue
            close = closes[-1]
            st = status_from(close, rim, "bullish", fail_level=lows[T] * 1.05)
            score = r2 * (1 - abs(rimR - rimL) / rimL * 4) * recency_weight(R, n)
            out.append(dict(pattern="rounding_bottom", direction="bullish", status=st, score=round(float(score), 3),
                            components=dict(fit_r2=round(r2, 3), depth_pct=round(depth / rim * 100, 1), span_bars=int(span)),
                            anchors=[dict(role="left_rim", i=L), dict(role="low", i=T), dict(role="right_rim", i=R)],
                            levels=dict(breakout=round(rim, 2), target=round(rim + depth, 2), stop=round(lows[T] + depth * 0.5, 2)),
                            last_anchor_i=R, geometry=dict(kind="cup", L=L, T=T, R=R, H=None, coef=[float(c) for c in coef], rim=float(rim))))
    return out

def det_double(df, piv, order):
    highs, lows, closes = df.High.values, df.Low.values, df.Close.values
    n = len(df); out = []
    for typ, direction in (("H", "bearish"), ("L", "bullish")):
        ps = [p for p in piv if p["type"] == typ]
        for a in range(len(ps)):
            for b in range(a + 1, len(ps)):
                i, j = ps[a]["i"], ps[b]["i"]
                if not (20 <= j - i <= 120) or n - 1 - j > 40: continue
                p1, p2 = ps[a]["price"], ps[b]["price"]
                if abs(p2 - p1) / p1 > 0.02: continue
                trend = prior_move_pct(closes, i, 60)
                if (typ == "H" and trend < 12) or (typ == "L" and trend > -12): continue   # a reversal needs a trend to reverse
                if typ == "H" and highs[i:j + 1].max() > max(p1, p2) * 1.005: continue
                if typ == "L" and lows[i:j + 1].min() < min(p1, p2) * 0.995: continue
                if typ == "H":
                    mid_i = i + int(np.argmin(lows[i:j + 1])); neck = lows[mid_i]; height = max(p1, p2) - neck
                    if height / neck < 0.08: continue
                    st = status_from(closes[-1], neck, "bearish", fail_level=max(p1, p2) * 1.02)
                    levels_ = dict(breakout=round(neck, 2), target=round(neck - height, 2), stop=round(max(p1, p2) * 1.01, 2))
                else:
                    mid_i = i + int(np.argmax(highs[i:j + 1])); neck = highs[mid_i]; height = neck - min(p1, p2)
                    if height / neck < 0.08: continue
                    st = status_from(closes[-1], neck, "bullish", fail_level=min(p1, p2) * 0.98)
                    levels_ = dict(breakout=round(neck, 2), target=round(neck + height, 2), stop=round(min(p1, p2) * 0.99, 2))
                sym = 1 - abs(p2 - p1) / p1 / 0.02
                score = (0.5 * sym + 0.3 * min(height / neck / 0.10, 1) + 0.2) * recency_weight(j, n)
                out.append(dict(pattern="double_top" if typ == "H" else "double_bottom", direction=direction, status=st, score=round(float(score), 3),
                                components=dict(peak_mismatch_pct=round(abs(p2 - p1) / p1 * 100, 2), height_pct=round(height / neck * 100, 1), bars_between=int(j - i)),
                                anchors=[dict(role="first", i=i), dict(role="neckline_pivot", i=mid_i), dict(role="second", i=j)],
                                levels=levels_, last_anchor_i=j, geometry=dict(kind="double", pts=[i, mid_i, j], neck=float(neck), typ=typ)))
    return out

def det_head_shoulders(df, piv, order):
    closes = df.Close.values; n = len(df); out = []
    for k in range(len(piv) - 4):
        seq = piv[k:k + 5]
        types = "".join(p["type"] for p in seq)
        if types not in ("HLHLH", "LHLHL"): continue
        S1, T1, HD, T2, S2 = seq
        if n - 1 - S2["i"] > 45 or S2["i"] - S1["i"] > 200: continue
        trend = prior_move_pct(closes, S1["i"], 60)
        if (types == "HLHLH" and trend < 10) or (types == "LHLHL" and trend > -10): continue
        if types == "HLHLH":
            if not (HD["price"] > S1["price"] * 1.03 and HD["price"] > S2["price"] * 1.03): continue
            if abs(S1["price"] - S2["price"]) / S1["price"] > 0.10: continue
            direction = "bearish"
        else:
            if not (HD["price"] < S1["price"] * 0.97 and HD["price"] < S2["price"] * 0.97): continue
            if abs(S1["price"] - S2["price"]) / S1["price"] > 0.10: continue
            direction = "bullish"
        ln = fit_line([T1["i"], T2["i"]], [T1["price"], T2["price"]])
        neck_now = ln["slope"] * (n - 1) + ln["intercept"]
        neck_head = ln["slope"] * HD["i"] + ln["intercept"]
        height = abs(HD["price"] - neck_head)
        if height / neck_head < 0.05: continue
        st = status_from(closes[-1], neck_now, direction, fail_level=HD["price"])
        tgt = neck_now - height if direction == "bearish" else neck_now + height
        stop = S2["price"] * (1.01 if direction == "bearish" else 0.99)
        sym = 1 - abs(S1["price"] - S2["price"]) / S1["price"] / 0.10
        tsym = 1 - abs((HD["i"] - S1["i"]) - (S2["i"] - HD["i"])) / max(S2["i"] - S1["i"], 1)
        score = (0.4 * sym + 0.3 * tsym + 0.3 * min(height / neck_head / 0.12, 1)) * recency_weight(S2["i"], n)
        out.append(dict(pattern="head_and_shoulders" if direction == "bearish" else "inverse_head_and_shoulders", direction=direction, status=st,
                        score=round(float(score), 3),
                        components=dict(head_vs_shoulders_pct=round((HD["price"] / max(S1["price"], S2["price"]) - 1) * 100, 1), shoulder_mismatch_pct=round(abs(S1["price"] - S2["price"]) / S1["price"] * 100, 1),
                                        neckline_slope_pct_per_bar=round(ln["slope"] / neck_now * 100, 3), height_pct=round(height / neck_head * 100, 1)),
                        anchors=[dict(role="left_shoulder", i=S1["i"]), dict(role="neck1", i=T1["i"]), dict(role="head", i=HD["i"]), dict(role="neck2", i=T2["i"]), dict(role="right_shoulder", i=S2["i"])],
                        levels=dict(breakout=round(neck_now, 2), target=round(tgt, 2), stop=round(stop, 2)), last_anchor_i=S2["i"],
                        geometry=dict(kind="hs", pts=[p["i"] for p in seq], neck=[T1["i"], T2["i"]])))
    return out

def det_triangles(df, piv, atr_v):
    closes = df.Close.values; n = len(df); out = []
    for k in (6, 5):
        recent = piv[-k:]
        if len(recent) < 5 or n - 1 - recent[-1]["i"] > 30: continue
        hs = [p for p in recent if p["type"] == "H"]; ls = [p for p in recent if p["type"] == "L"]
        if len(hs) < 2 or len(ls) < 2: continue
        up = fit_line([p["i"] for p in hs], [p["price"] for p in hs]); lo = fit_line([p["i"] for p in ls], [p["price"] for p in ls])
        if up["max_res"] > 0.8 * atr_v or lo["max_res"] > 0.8 * atr_v: continue
        start = recent[0]["i"]; width = n - 1 - start
        price = closes[-1]
        su, sl = up["slope"] / price * 100, lo["slope"] / price * 100   # % per bar
        flat = 0.04
        if abs(su) < flat and sl > flat: kind = "ascending_triangle"; direction = "bullish"
        elif abs(sl) < flat and su < -flat: kind = "descending_triangle"; direction = "bearish"
        elif su < -flat and sl > flat: kind = "symmetrical_triangle"; direction = "neutral"
        elif su > flat and sl > flat and sl > su: kind = "rising_wedge"; direction = "bearish"
        elif su < -flat and sl < -flat and su < sl: kind = "falling_wedge"; direction = "bullish"
        else: continue
        if abs(up["slope"] - lo["slope"]) < 1e-9: continue
        apex = (lo["intercept"] - up["intercept"]) / (up["slope"] - lo["slope"])
        if not (n - 1 < apex < n - 1 + 2.5 * width): continue
        up_now = up["slope"] * (n - 1) + up["intercept"]; lo_now = lo["slope"] * (n - 1) + lo["intercept"]
        height0 = (up["slope"] * start + up["intercept"]) - (lo["slope"] * start + lo["intercept"])
        if height0 / price < 0.04: continue
        if price > up_now + 0.3 * atr_v: st, brk = "confirmed_up", up_now
        elif price < lo_now - 0.3 * atr_v: st, brk = "confirmed_down", lo_now
        else: st, brk = "forming", None
        score = (1 - (up["max_res"] + lo["max_res"]) / (1.6 * atr_v)) * min(len(recent) / 6, 1) * recency_weight(recent[-1]["i"], n)
        out.append(dict(pattern=kind, direction=direction, status=st, score=round(float(score), 3),
                        components=dict(upper_slope_pct_per_bar=round(su, 3), lower_slope_pct_per_bar=round(sl, 3), height_at_start_pct=round(height0 / price * 100, 1),
                                        bars_to_apex=int(apex - (n - 1)), pivots_used=len(recent), upper_now=round(up_now, 2), lower_now=round(lo_now, 2)),
                        anchors=[dict(role=("H" if p["type"] == "H" else "L"), i=p["i"]) for p in recent],
                        levels=dict(breakout_up=round(up_now, 2), breakout_down=round(lo_now, 2), target_up=round(up_now + height0, 2), target_down=round(lo_now - height0, 2)),
                        last_anchor_i=recent[-1]["i"], geometry=dict(kind="lines", start=start, up=up, lo=lo)))
        break
    return out

def det_flag(df, atr_v):
    closes, highs, lows = df.Close.values, df.High.values, df.Low.values; n = len(df); out = []
    for i in range(max(0, n - 70), n - 8):
        for j in range(i + 3, min(i + 16, n - 5)):
            ret = closes[j] / closes[i] - 1
            if abs(ret) < 0.12: continue
            direction = "bullish" if ret > 0 else "bearish"
            cons = slice(j + 1, n)
            m = n - 1 - j
            if m < 4 or m > 25: continue
            ch, cl = highs[cons], lows[cons]
            pole_h = abs(closes[j] - closes[i])
            if (ch.max() - cl.min()) > 0.5 * pole_h: continue
            x = np.arange(m); a_h, _ = np.polyfit(x, ch, 1); a_l, _ = np.polyfit(x, cl, 1)
            drift = (a_h + a_l) / 2 / closes[j] * 100
            if direction == "bullish" and drift > 0.3: continue
            if direction == "bearish" and drift < -0.3: continue
            kind = "pennant" if (a_h < 0 < a_l) else ("bull_flag" if direction == "bullish" else "bear_flag")
            if direction == "bullish":
                brk = ch[:-1].max() if m > 1 else ch.max(); st = "confirmed" if closes[-1] > brk else "forming"
                lv = dict(breakout=round(brk, 2), target=round(brk + pole_h, 2), stop=round(cl.min() * 0.99, 2))
            else:
                brk = cl[:-1].min() if m > 1 else cl.min(); st = "confirmed" if closes[-1] < brk else "forming"
                lv = dict(breakout=round(brk, 2), target=round(brk - pole_h, 2), stop=round(ch.max() * 1.01, 2))
            tight = 1 - (ch.max() - cl.min()) / (0.5 * pole_h)
            score = (0.5 * min(abs(ret) / 0.2, 1) + 0.5 * tight) * recency_weight(j, n, half_life=40)
            out.append(dict(pattern=kind, direction=direction, status=st, score=round(float(score), 3),
                            components=dict(pole_move_pct=round(ret * 100, 1), pole_bars=int(j - i), consolidation_bars=int(m),
                                            consolidation_range_pct_of_pole=round((ch.max() - cl.min()) / pole_h * 100, 1), drift_pct_per_bar=round(drift, 3)),
                            anchors=[dict(role="pole_start", i=i), dict(role="pole_end", i=j), dict(role="last", i=n - 1)], levels=lv, last_anchor_i=j,
                            geometry=dict(kind="flag", i=i, j=j, hi=float(ch.max()), lo=float(cl.min()))))
    out.sort(key=lambda c: -c["score"])
    return out[:1]

def det_channel_break(df, piv, tls, atr_v):
    """Break of a falling (or rising) trendline with >=3 touches, within the last 15 bars; channel if a near-parallel second line exists."""
    closes, vols = df.Close.values, df.Volume.values; n = len(df); out = []
    pos = {str(d.date()): i for i, d in enumerate(df.index)}
    for t in tls:
        if len(t["through"]) < 3: continue
        falling = t["slope_pct_per_bar"] < 0
        res_line = t["kind"].endswith("resistance")
        if not ((falling and res_line) or ((not falling) and not res_line)): continue  # downtrend line broken up, or uptrend line broken down
        x0 = pos[t["anchors"][0]["date"]]; y0 = t["anchors"][0]["price"]; y1 = t["value_at_last_bar"]
        slope = (y1 - y0) / max(n - 1 - x0, 1)
        line = lambda i: y0 + slope * (i - x0)
        above = [closes[i] > line(i) for i in range(x0, n)]
        if falling:
            if not above[-1]: continue
            k = len(above) - 1
            while k > 0 and above[k - 1]: k -= 1
            brk_i = x0 + k
            if n - 1 - brk_i > 15 or brk_i == x0: continue
            direction = "bullish"
        else:
            if above[-1]: continue
            k = len(above) - 1
            while k > 0 and not above[k - 1]: k -= 1
            brk_i = x0 + k
            if n - 1 - brk_i > 15 or brk_i == x0: continue
            direction = "bearish"
        other = [u for u in tls if u is not t and abs(u["slope_pct_per_bar"] - t["slope_pct_per_bar"]) <= 0.35 * abs(t["slope_pct_per_bar"]) + 0.02]
        channel = other[0] if other else None
        height = abs(channel["value_at_last_bar"] - y1) if channel else float(df.ATR14.iloc[-1]) * 3
        vol_brk = vols[brk_i] / df.VolSMA20.iloc[brk_i]
        bars_since = n - 1 - brk_i
        follow = pct(closes[-1], closes[brk_i])
        last_piv = [p for p in piv if p["type"] == ("L" if direction == "bullish" else "H")][-1]
        lv = (dict(breakout=round(line(brk_i), 2), target=round(line(brk_i) + height, 2), stop=round(min(last_piv["price"], y1) * 0.99, 2)) if direction == "bullish"
              else dict(breakout=round(line(brk_i), 2), target=round(line(brk_i) - height, 2), stop=round(max(last_piv["price"], y1) * 1.01, 2)))
        st = "confirmed" if (closes[-1] > y1 if direction == "bullish" else closes[-1] < y1) else "failed"
        score = min(len(t["through"]) / 4, 1) * (0.6 + 0.4 * min(vol_brk / 1.5, 1)) * (1 if channel else 0.85) * recency_weight(brk_i, n, half_life=30)
        out.append(dict(pattern=("descending_channel_breakout" if (channel and direction == "bullish") else "ascending_channel_breakdown" if channel else ("downtrend_line_breakout" if direction == "bullish" else "uptrend_line_breakdown")),
                        direction=direction, status=st, score=round(float(score), 3),
                        components=dict(line_touches=len(t["through"]), line_from=t["anchors"][0]["date"], line_value_at_last_bar=round(y1, 2), breakout_date=str(df.index[brk_i].date()),
                                        breakout_close=round(float(closes[brk_i]), 2), breakout_volume_vs_20d=round(float(vol_brk), 2), bars_since_breakout=int(bars_since),
                                        move_since_breakout_pct=round(float(follow), 2), channel_other_line=(channel["kind"] if channel else None),
                                        channel_height=round(float(height), 2), last_pivot_before_break=dict(id=last_piv["id"], price=round(last_piv["price"], 2))),
                        anchors=[dict(role="line_start", i=x0), dict(role="breakout_bar", i=brk_i), dict(role="last", i=n - 1)], levels=lv, last_anchor_i=brk_i,
                        geometry=dict(kind="channel", line=dict(x0=x0, y0=y0, slope=slope), other=(dict(x0=pos[channel["anchors"][0]["date"]], y0=channel["anchors"][0]["price"],
                                                                                                        slope=(channel["value_at_last_bar"] - channel["anchors"][0]["price"]) / max(n - 1 - pos[channel["anchors"][0]["date"]], 1)) if channel else None), brk_i=brk_i)))
    return out

def det_rectangle(df, piv, atr_v):
    closes = df.Close.values; n = len(df); out = []
    recent = [p for p in piv if n - 1 - p["i"] <= 120]
    hs = [p for p in recent if p["type"] == "H"]; ls = [p for p in recent if p["type"] == "L"]
    if len(hs) >= 3 and len(ls) >= 3:
        top = np.mean([p["price"] for p in hs[-3:]]); bot = np.mean([p["price"] for p in ls[-3:]])
        if all(abs(p["price"] - top) / top <= 0.025 for p in hs[-3:]) and all(abs(p["price"] - bot) / bot <= 0.025 for p in ls[-3:]):
            h = (top - bot) / bot
            start0 = min(hs[-3:][0]["i"], ls[-3:][0]["i"])
            if 0.05 <= h <= 0.20 and n - 1 - start0 >= 40:
                price = closes[-1]
                st = "confirmed_up" if price > top else "confirmed_down" if price < bot else "forming"
                start = min(hs[-3:][0]["i"], ls[-3:][0]["i"])
                score = (1 - max(abs(p["price"] - top) / top for p in hs[-3:]) / 0.025 * 0.5) * recency_weight(max(hs[-1]["i"], ls[-1]["i"]), n)
                out.append(dict(pattern="rectangle", direction="neutral", status=st, score=round(float(score), 3),
                                components=dict(top=round(top, 2), bottom=round(bot, 2), height_pct=round(h * 100, 1), bars=int(n - 1 - start)),
                                anchors=[dict(role="H", i=p["i"]) for p in hs[-3:]] + [dict(role="L", i=p["i"]) for p in ls[-3:]],
                                levels=dict(breakout_up=round(top, 2), breakout_down=round(bot, 2), target_up=round(top * (1 + h), 2), target_down=round(bot * (1 - h), 2)),
                                last_anchor_i=max(hs[-1]["i"], ls[-1]["i"]), geometry=dict(kind="rect", start=start, top=float(top), bot=float(bot))))
    return out

def run_detectors(df, piv, order, atr_v, tls=()):
    cands = []
    cands += det_channel_break(df, piv, list(tls), atr_v)
    cands += det_cup_and_handle(df, piv, order)
    cands += det_rounding_bottom(df, piv, order)
    cands += det_double(df, piv, order)
    cands += det_head_shoulders(df, piv, order)
    cands += det_triangles(df, piv, atr_v)
    cands += det_flag(df, atr_v)
    cands += det_rectangle(df, piv, atr_v)
    n = len(df)
    for c in cands:
        for a in c["anchors"]:
            a["date"] = str(df.index[a["i"]].date())
            a["price"] = round(float(df.High.iloc[a["i"]] if a["role"] in ("left_rim", "right_rim", "H", "first", "second", "left_shoulder", "head", "right_shoulder", "pole_end") and df.High.iloc[a["i"]] >= df.Close.iloc[a["i"]] else df.Low.iloc[a["i"]]), 2) \
                if a["role"] not in ("pole_start", "last", "line_start", "breakout_bar") else round(float(df.Close.iloc[a["i"]]), 2)
        c["bars_since_last_anchor"] = int(n - 1 - c["last_anchor_i"])
    cands = [c for c in cands if c["score"] >= 0.50]
    cands.sort(key=lambda c: -c["score"])
    for k, c in enumerate(cands[:5]):
        c["id"] = f"C{k + 1}"
    return cands[:5]

# ----------------------------------------------------------------------------- 5. evidence pack
def build_pack(symbol, name, horizon, df, feats, wctx, piv, sup, res, tls, struct, cands, flags, provenance):
    facts = []
    def F(text, value=None, unit=None):
        facts.append({"id": f"F{len(facts) + 1}", "text": text, **({"value": value} if value is not None else {}), **({"unit": unit} if unit else {})})
        return facts[-1]["id"]
    F(f"Last close {feats['last_close']} on {feats['last_date']} (data as of that date)", feats["last_close"], "INR")
    for k, lab in (("ret_1w_pct", "1-week"), ("ret_1m_pct", "1-month"), ("ret_3m_pct", "3-month"), ("ret_6m_pct", "6-month")):
        if feats.get(k) is not None: F(f"{lab} return {feats[k]}%", feats[k], "%")
    F(f"52-week high {feats['high_52w']} on {feats['high_52w_date']}; close is {feats['dist_from_52w_high_pct']}% from it", feats["dist_from_52w_high_pct"], "%")
    F(f"52-week low {feats['low_52w']}; close is {feats['dist_from_52w_low_pct']}% above it", feats["dist_from_52w_low_pct"], "%")
    for k in ("EMA20", "EMA50", "EMA200"):
        if k in feats: F(f"{k} = {feats[k]}; close is {feats['close_vs_' + k + '_pct']}% vs {k}", feats[k], "INR")
    F(f"EMA alignment: {feats['ema_alignment']}")
    F(f"RSI(14) = {feats['RSI14']}", feats["RSI14"])
    F(f"MACD histogram {feats['MACD_hist']}, MACD {feats['MACD_state']}", feats["MACD_hist"])
    F(f"ATR(14) = {feats['ATR14']} ({feats['ATR14_pct']}% of price)", feats["ATR14"], "INR")
    if feats.get("BB_position") is not None: F(f"Position within Bollinger band (0=lower, 1=upper): {feats['BB_position']}", feats["BB_position"])
    F(f"Last-day volume {feats['volume_ratio_vs_20d']}x the 20-day average; last 5 days average {feats['volume_ratio_last5_vs_20d']}x", feats["volume_ratio_vs_20d"])
    F(f"Weekly trend: {wctx['trend']} (close {wctx['close_vs_EMA10_pct']}% vs 10-week EMA, {wctx['close_vs_EMA40_pct']}% vs 40-week EMA); weekly structure: {wctx['structure_last_3_pivots']}")
    if wctx.get("ret_26w_pct") is not None: F(f"26-week return {wctx['ret_26w_pct']}%; 52-week return {wctx['ret_52w_pct']}%", wctx["ret_26w_pct"], "%")
    F(f"Daily pivot highs sequence: {struct['highs_sequence']}; pivot lows sequence: {struct['lows_sequence']}")
    for l in sup: F(f"Support cluster at {l['price']} ({l['touches']} pivot touches, {l['dist_pct']}% from close)", l["price"], "INR")
    for l in res: F(f"Resistance cluster at {l['price']} ({l['touches']} pivot touches, {l['dist_pct']}% from close)", l["price"], "INR")
    for t in tls: F(f"Trendline ({t['kind']}) through {t['through']} from {t['from']}, value at last bar {t['value_at_last_bar']}, slope {t['slope_pct_per_bar']}%/bar", t["value_at_last_bar"], "INR")
    for c in cands:
        comp = ", ".join(f"{k}={v}" for k, v in c["components"].items())
        F(f"Candidate {c['id']}: {c['pattern']} ({c['direction']}), status {c['status']}, fit score {c['score']}, anchors {[(a['role'], a['date'], a['price']) for a in c['anchors']]}, levels {c['levels']}; {comp}", c["score"])
    if not cands: F("No chart-pattern candidate passed the detector thresholds (score >= 0.50)")
    pack = {"schema": "dalal-pulse/evidence-pack/v0", "symbol": symbol, "company": name, "horizon": horizon, "interval": HORIZON[horizon]["interval"],
            "as_of": feats["last_date"], "bars_in_window": int(len(df)), "window_from": str(df.index[0].date()),
            "data_provenance": provenance, "corporate_action_flags": flags,
            "price_and_returns": {k: feats[k] for k in feats if k.startswith(("last_", "ret_", "high_52w", "low_52w", "dist_"))},
            "indicators": {k: feats[k] for k in feats if k.startswith(("EMA", "close_vs", "ema_", "RSI", "MACD", "ATR", "BB_", "volume"))},
            "weekly_context": wctx, "structure": struct,
            "pivots": [{"id": p["id"], "type": p["type"], "date": p["date"], "price": round(p["price"], 2)} for p in piv[-16:]],
            "levels": {"support": sup, "resistance": res, "trendlines": tls},
            "candidates": [{k: v for k, v in c.items() if k not in ("geometry", "last_anchor_i")} for c in cands],
            "facts": facts}
    return pack

# ----------------------------------------------------------------------------- 6. charts
def style(dark):
    bg, fg, grid = ("#131722", "#d1d4dc", "#1e222d") if dark else ("#ffffff", "#131722", "#e6e6e6")
    mc = mpf.make_marketcolors(up="#26a69a", down="#ef5350", edge="inherit", wick="inherit", volume={"up": "#26a69a66", "down": "#ef535066"})
    return mpf.make_mpf_style(marketcolors=mc, facecolor=bg, figcolor=bg, edgecolor=grid, gridcolor=grid, gridstyle="-",
                              rc={"axes.labelcolor": fg, "xtick.color": fg, "ytick.color": fg, "font.size": 9, "axes.edgecolor": grid}), bg, fg

def model_input_chart(df, piv, sup, res, tls, pack, path):
    """What the model sees: candles, EMAs, volume, lettered pivots, levels. No pattern overlay."""
    st, bg, fg = style(dark=False)
    adds = [mpf.make_addplot(df[k], color=c, width=1.0) for k, c in (("EMA20", "#1e88e5"), ("EMA50", "#fb8c00"), ("EMA200", "#8e24aa")) if k in df]
    fig, axes = mpf.plot(df, type="candle", style=st, volume=True, addplot=adds, returnfig=True, figsize=(15.68, 8.82),
                         hlines=dict(hlines=[l["price"] for l in sup + res], colors=["#26a69a"] * len(sup) + ["#ef5350"] * len(res), linestyle="--", linewidths=1.0),
                         tight_layout=True, xrotation=0, datetime_format="%d %b %y")
    ax = axes[0]; n = len(df)
    ax.set_xlim(-2, n + 26)
    for p in piv[-16:]:
        y = p["price"]; off = 12 if p["type"] == "H" else -12
        ax.annotate(f"{p['id']}\n{p['price']:.0f}" if p["type"] == "H" else f"{p['price']:.0f}\n{p['id']}", (p["i"], y), xytext=(0, off), textcoords="offset points",
                    ha="center", va="bottom" if p["type"] == "H" else "top", fontsize=8, color="#37474f", fontweight="bold")
    for l in sup + res:
        ax.annotate(f"{l['kind'][0].upper()} {l['price']:.0f}", (n + 1, l["price"]), color="#26a69a" if l["kind"] == "support" else "#ef5350", fontsize=8, va="center")
    for t in tls:
        pos = {ts: i for i, ts in enumerate(df.index)}
        x0 = pos[pd.Timestamp(t["anchors"][0]["date"])]; x1 = n - 1
        ax.plot([x0, x1], [t["anchors"][0]["price"], t["anchors"][1]["price"]], color="#607d8b", lw=1.2, ls="-.")
    ax.set_title(f"{pack['symbol']} ({pack['company']}) · {pack['interval']} · last {n} bars to {pack['as_of']} · EMA20 blue, EMA50 orange, EMA200 purple · "
                 f"P# = confirmed swing pivots · dashed = support/resistance clusters", color=fg, fontsize=10, loc="left")
    fig.savefig(path, dpi=100, facecolor=bg); plt.close(fig)

def weekly_chart(w, pack, path):
    st, bg, fg = style(dark=False)
    adds = [mpf.make_addplot(w["EMA10"], color="#1e88e5", width=1.0), mpf.make_addplot(w["EMA40"], color="#8e24aa", width=1.0)]
    fig, axes = mpf.plot(w, type="candle", style=st, volume=True, addplot=adds, returnfig=True, figsize=(15.68, 6.0), tight_layout=True, xrotation=0, datetime_format="%b %y")
    axes[0].set_title(f"{pack['symbol']} · weekly context · {len(w)} weeks · EMA10 blue, EMA40 purple", color=fg, fontsize=10, loc="left")
    fig.savefig(path, dpi=100, facecolor=bg); plt.close(fig)

# ----------------------------------------------------------------------------- 9. geometry, overlay, pine
def geometry_for(df, cand, view):
    idx = df.index; g = cand["geometry"]; prims = []; lv = cand["levels"]
    last_t = ts_ms(idx[-1])
    if g["kind"] == "cup":
        L, T, R, H = g["L"], g["T"], g["R"], g["H"]
        xs = np.linspace(0, R - L, 15); ys = np.polyval(g["coef"], xs); ys[0], ys[-1] = df.High.iloc[L], df.High.iloc[R]
        prims.append({"type": "curve", "role": "cup", "points": [{"t": ts_ms(idx[L + int(round(x))]), "p": round(float(y), 2)} for x, y in zip(xs, ys)]})
        if H is not None:
            prims.append({"type": "polyline", "role": "handle", "points": [{"t": ts_ms(idx[R]), "p": round(float(df.High.iloc[R]), 2)}, {"t": ts_ms(idx[H]), "p": round(float(df.Low.iloc[H]), 2)},
                                                                            {"t": ts_ms(idx[min(len(df) - 1, H + max(3, H - R))]), "p": round(float(g["rim"]), 2)}]})
        prims.append({"type": "label", "role": "annotation", "t": ts_ms(idx[T]), "p": round(float(df.Low.iloc[T]) + (g["rim"] - df.Low.iloc[T]) * 0.18, 2), "text": "Cup"})
    elif g["kind"] == "double":
        pts = g["pts"]; col = "High" if g["typ"] == "H" else "Low"
        prims.append({"type": "polyline", "role": "outline", "points": [{"t": ts_ms(idx[i]), "p": round(float(df[col].iloc[i] if k != 1 else (df.Low.iloc[i] if g["typ"] == "H" else df.High.iloc[i])), 2)} for k, i in enumerate(pts)]})
    elif g["kind"] == "hs":
        pts = g["pts"]
        prims.append({"type": "polyline", "role": "outline", "points": [{"t": ts_ms(idx[i]), "p": round(float(df.High.iloc[i] if k % 2 == 0 else df.Low.iloc[i]) if cand["direction"] == "bearish" else float(df.Low.iloc[i] if k % 2 == 0 else df.High.iloc[i]), 2)} for k, i in enumerate(pts)]})
        n1, n2 = g["neck"]; col = "Low" if cand["direction"] == "bearish" else "High"
        prims.append({"type": "trendline", "role": "neckline", "points": [{"t": ts_ms(idx[n1]), "p": round(float(df[col].iloc[n1]), 2)}, {"t": last_t, "p": lv["breakout"]}]})
    elif g["kind"] == "lines":
        s = g["start"]; n = len(df)
        for key, role in (("up", "upper_line"), ("lo", "lower_line")):
            ln = g[key]
            prims.append({"type": "trendline", "role": role, "points": [{"t": ts_ms(idx[s]), "p": round(ln["slope"] * s + ln["intercept"], 2)}, {"t": last_t, "p": round(ln["slope"] * (n - 1) + ln["intercept"], 2)}]})
    elif g["kind"] == "flag":
        prims.append({"type": "polyline", "role": "pole", "points": [{"t": ts_ms(idx[g["i"]]), "p": round(float(df.Close.iloc[g["i"]]), 2)}, {"t": ts_ms(idx[g["j"]]), "p": round(float(df.Close.iloc[g["j"]]), 2)}]})
        prims.append({"type": "box", "role": "flag", "t1": ts_ms(idx[g["j"] + 1]), "p1": round(g["hi"], 2), "t2": last_t, "p2": round(g["lo"], 2)})
    elif g["kind"] == "channel":
        n = len(df); ln = g["line"]
        prims.append({"type": "trendline", "role": "broken_line", "points": [{"t": ts_ms(idx[ln["x0"]]), "p": round(ln["y0"], 2)}, {"t": last_t, "p": round(ln["y0"] + ln["slope"] * (n - 1 - ln["x0"]), 2)}]})
        if g.get("other"):
            o = g["other"]
            prims.append({"type": "trendline", "role": "channel_line", "points": [{"t": ts_ms(idx[o["x0"]]), "p": round(o["y0"], 2)}, {"t": last_t, "p": round(o["y0"] + o["slope"] * (n - 1 - o["x0"]), 2)}]})
        prims.append({"type": "label", "role": "annotation", "t": ts_ms(idx[g["brk_i"]]), "p": round(float(df.Low.iloc[g["brk_i"]]) * 0.985, 2), "text": "Breakout"})
    elif g["kind"] == "rect":
        prims.append({"type": "box", "role": "range", "t1": ts_ms(idx[g["start"]]), "p1": round(g["top"], 2), "t2": last_t, "p2": round(g["bot"], 2)})
    for role in ("breakout", "target", "stop", "breakout_up", "breakout_down", "target_up", "target_down"):
        if role in lv:
            prims.append({"type": "hline", "role": role, "price": lv[role], "from": ts_ms(idx[max(0, cand["anchors"][0]["i"])]), "to": last_t})
    return {"schema": "dalal-pulse/ta-view/v0", "symbol": view["symbol"], "interval": view["interval"], "as_of": view["as_of"], "pattern": cand["pattern"],
            "status": cand["status"], "view": view["view"], "levels": lv, "primitives": prims}

def overlay_chart(df, geo, view, path, dark=True):
    st, bg, fg = style(dark)
    adds = [mpf.make_addplot(df[k], color=c, width=0.9, alpha=0.8) for k, c in (("EMA20", "#1e88e5"), ("EMA50", "#fb8c00")) if k in df]
    hl = [p for p in geo["primitives"] if p["type"] == "hline"]
    colors = {"breakout": "#2962ff", "target": "#26a69a", "stop": "#ef5350", "breakout_up": "#2962ff", "breakout_down": "#2962ff", "target_up": "#26a69a", "target_down": "#ef5350"}
    fig, axes = mpf.plot(df, type="candle", style=st, volume=True, addplot=adds, returnfig=True, figsize=(16, 9), tight_layout=True, xrotation=0, datetime_format="%b %y")
    ax = axes[0]; n = len(df); pos = {ts: i for i, ts in enumerate(df.index)}
    lo_y = float(df.Low.min()); hi_y = max(float(df.High.max()), max([h["price"] for h in hl], default=0))
    ax.set_ylim(min(lo_y, min([h["price"] for h in hl], default=lo_y)) * 0.985, hi_y * 1.015); ax.set_xlim(-2, n + 30)
    def X(t): return pos[pd.Timestamp(datetime.fromtimestamp(t / 1000, IST).date())]
    for h in hl:
        ax.plot([X(h["from"]), n + 28], [h["price"], h["price"]], color=colors[h["role"]], ls="--", lw=1.2, zorder=4)
    for p in geo["primitives"]:
        if p["type"] == "curve":
            xs = [X(q["t"]) for q in p["points"]]; ys = [q["p"] for q in p["points"]]
            xx = np.linspace(xs[0], xs[-1], 200); yy = np.polyval(np.polyfit(xs, ys, 2), xx)
            ax.plot(xx, yy, color="#00bcd4", lw=2.6, zorder=5); ax.fill_between(xx, yy, geo["levels"].get("breakout", yy.max()), color="#00bcd4", alpha=0.07)
        elif p["type"] in ("polyline", "trendline"):
            ax.plot([X(q["t"]) for q in p["points"]], [q["p"] for q in p["points"]], color="#ffb74d" if p["role"] != "neckline" else "#2962ff", lw=2.2, zorder=5)
        elif p["type"] == "box":
            x1, x2 = X(p["t1"]), X(p["t2"]); ax.add_patch(plt.Rectangle((x1, min(p["p1"], p["p2"])), x2 - x1, abs(p["p1"] - p["p2"]), fill=True, alpha=0.12, color="#ffb74d", ec="#ffb74d", lw=1.5, zorder=4))
        elif p["type"] == "label":
            ax.annotate(p["text"], (X(p["t"]), p["p"]), color=fg, fontsize=11, fontweight="bold", ha="center", zorder=6)
    for h in hl:
        ax.annotate(f"{h['role'].replace('_', ' ').title()} {h['price']:,.0f}", (n - 1, h["price"]), xytext=(4, 0), textcoords="offset points", color=colors[h["role"]], fontsize=9, va="center")
    ax.set_title(f"{geo['symbol']} · {geo['interval']} · {geo['pattern'].replace('_', ' ')} ({geo['status']}) · view: {geo['view'].upper()} · as of {geo['as_of']}", color=fg, fontsize=12, loc="left")
    fig.savefig(path, dpi=100, facecolor=bg); plt.close(fig)

def pine_ts(t_ms):
    d = datetime.fromtimestamp(t_ms / 1000, IST)
    return f'timestamp("Asia/Kolkata", {d.year}, {d.month}, {d.day}, {d.hour}, {d.minute})'

def to_pine(geo, reason):
    sym = geo["symbol"].split(":")[1]
    out = ["//@version=6", f'indicator("Dalal Pulse · {sym} {geo["interval"]} · {geo["pattern"].replace("_", " ").title()} · {geo["as_of"]}", overlay=true, max_lines_count=50, max_labels_count=50, max_polylines_count=10, max_boxes_count=10)',
           f"// View: {geo['view'].upper()} · status {geo['status']} · levels {geo['levels']}", "var bool drawn = false", "if barstate.islast and not drawn", "    drawn := true"]
    colors = {"breakout": "color.blue", "target": "color.green", "stop": "color.red", "breakout_up": "color.blue", "breakout_down": "color.blue", "target_up": "color.green", "target_down": "color.red"}
    k = 0
    for p in geo["primitives"]:
        k += 1
        if p["type"] in ("curve", "polyline"):
            out.append(f"    pts{k} = array.new<chart.point>()")
            for q in p["points"]: out.append(f"    array.push(pts{k}, chart.point.from_time({pine_ts(q['t'])}, {q['p']}))")
            out.append(f"    polyline.new(pts{k}, curved={'true' if p['type'] == 'curve' else 'false'}, xloc=xloc.bar_time, line_color={'color.aqua' if p['type'] == 'curve' else 'color.orange'}, line_width=2)")
        elif p["type"] == "trendline":
            a, b = p["points"]
            out.append(f"    line.new({pine_ts(a['t'])}, {a['p']}, {pine_ts(b['t'])}, {b['p']}, xloc=xloc.bar_time, extend=extend.right, color=color.orange, width=2)")
        elif p["type"] == "box":
            out.append(f"    box.new(chart.point.from_time({pine_ts(p['t1'])}, {p['p1']}), chart.point.from_time({pine_ts(p['t2'])}, {p['p2']}), xloc=xloc.bar_time, border_color=color.orange, bgcolor=color.new(color.orange, 85))")
        elif p["type"] == "hline":
            c = colors[p["role"]]
            out.append(f"    line.new({pine_ts(p['from'])}, {p['price']}, {pine_ts(p['to'])}, {p['price']}, xloc=xloc.bar_time, extend=extend.right, color={c}, style=line.style_dashed)")
            out.append(f"    label.new({pine_ts(p['to'])}, {p['price']}, \"{p['role'].replace('_', ' ').title()} {p['price']}\", xloc=xloc.bar_time, style=label.style_label_left, color=color.new({c}, 20), textcolor=color.white, size=size.small)")
        elif p["type"] == "label":
            out.append(f"    label.new({pine_ts(p['t'])}, {p['p']}, \"{p['text']}\", xloc=xloc.bar_time, style=label.style_label_up, color=color.new(color.gray, 30), textcolor=color.white)")
    out.append(""); out.append("// Reason: " + reason.replace("\n", " "))
    return "\n".join(out)

# ----------------------------------------------------------------------------- 8. checker
NUM = re.compile(r"(?<![A-Za-z])[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![A-Za-z])[-+]?\d+(?:\.\d+)?")
def pack_numbers(pack):
    vals = set()
    def walk(o):
        if isinstance(o, dict):
            for v in o.values(): walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o: walk(v)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            vals.add(float(o))
        elif isinstance(o, str):
            for m in NUM.findall(o):
                try: vals.add(float(m.replace(",", "")))
                except ValueError: pass
    walk(pack); return vals

def check_sample(sample, pack):
    """Every cited fact id must exist; every number in the prose must be in the pack (0.6% or ±0.05 absolute)."""
    ids = {f["id"] for f in pack["facts"]} | {c["id"] for c in pack["candidates"]} | {p["id"] for p in pack["pivots"]}
    vals = pack_numbers(pack); problems = []
    cited = set()
    for r in sample.get("reasons", []):
        for e in r.get("evidence", []):
            cited.add(e)
            if e not in ids: problems.append(f"unknown evidence id {e}")
        for m in NUM.findall(r.get("text", "")):
            x = float(m.replace(",", ""))
            if x in (14, 20, 50, 200, 10, 40, 52): continue  # indicator parameters
            if not any(abs(abs(x) - abs(v)) <= max(0.001 * abs(v), 0.5) for v in vals): problems.append(f"number {m} not in evidence pack")
    for k in ("breakout", "target", "stop", "invalidation"):
        v = sample.get("levels", {}).get(k)
        if v is not None and not any(abs(float(v) - p) <= max(0.001 * abs(p), 0.5) for p in vals): problems.append(f"level {k}={v} not in evidence pack")
    if sample.get("pattern_id") and sample["pattern_id"] not in {c["id"] for c in pack["candidates"]} and sample["pattern_id"] != "none":
        problems.append(f"pattern_id {sample['pattern_id']} not a candidate")
    return problems, cited

def consensus(samples):
    views = [s["view"] for s in samples]; setups = [s["setup"] for s in samples]; pids = [s.get("pattern_id") or "none" for s in samples]
    unanimous = len(set(views)) == 1 and len(set(setups)) == 1
    return {"unanimous": unanimous, "views": views, "setups": setups, "pattern_ids": pids,
            "final_view": views[0] if unanimous else "neutral", "final_setup": setups[0] if len(set(setups)) == 1 else "conflicting"}

# (CLI removed; see pipeline.py)
