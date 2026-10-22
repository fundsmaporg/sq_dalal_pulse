import math
import numpy as np, pandas as pd, pytest
from taview import engine as E


def synth_cup(n=200, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end="2026-10-13", periods=n)
    base = np.zeros(n); rim = 1000.0
    for i in range(n):
        if i < 55: base[i] = 880 + (rim - 880) * (i / 55) ** 0.9
        elif i < 145: base[i] = rim - 110 * math.sin(math.pi * (i - 55) / 90.0) ** 1.1
        elif i < 170: base[i] = rim - 35 * math.sin(math.pi * (i - 145) / 25.0) ** 0.8 - 2
        else: base[i] = rim + 48 * ((i - 170) / 29.0) ** 0.7
    close = base + rng.normal(0, 4, n); open_ = np.concatenate([[close[0] - 3], close[:-1]]) + rng.normal(0, 2.5, n)
    hi = np.maximum(open_, close) + np.abs(rng.normal(0, 4, n)); lo = np.minimum(open_, close) - np.abs(rng.normal(0, 4, n))
    vol = rng.integers(8_000_000, 14_000_000, n).astype(float); vol[170:] *= 1.8
    df = pd.DataFrame({"Open": open_, "High": hi, "Low": lo, "Close": close, "Volume": vol}, index=idx)
    df, _ = E.features(df)
    return df


def random_walk(n=250, seed=1, s0=1000, vol=0.013):
    rng = np.random.default_rng(seed)
    close = s0 * np.exp(np.cumsum(rng.normal(0, vol, n)))
    open_ = np.concatenate([[close[0]], close[:-1]]) * (1 + rng.normal(0, 0.004, n))
    hi = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.005, n))); lo = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.005, n)))
    df = pd.DataFrame({"Open": open_, "High": hi, "Low": lo, "Close": close, "Volume": 1e7}, index=pd.bdate_range(end="2026-10-13", periods=n))
    df, _ = E.features(df)
    return df


def test_cup_and_handle_detected_and_confirmed():
    df = synth_cup(); piv = E.pivots(df, 5)
    c = E.det_cup_and_handle(df, piv, 5)
    assert c, "cup and handle not detected on the designed series"
    best = max(c, key=lambda x: x["score"])
    assert best["status"] == "breakout_confirmed" or best["status"] == "confirmed"
    assert 8 <= best["components"]["cup_depth_pct"] <= 40
    assert best["levels"]["target"] > best["levels"]["breakout"] > best["levels"]["stop"]


def test_pivots_are_causal():
    df = synth_cup(); piv = E.pivots(df, 5)
    assert all(p["i"] <= len(df) - 1 - 5 for p in piv), "a pivot was reported before it could be confirmed"
    types = [p["type"] for p in piv]
    assert all(a != b for a, b in zip(types, types[1:])), "pivots must alternate H/L"


def test_double_top_requires_no_higher_high_between():
    df = random_walk(seed=3); piv = E.pivots(df, 5)
    for c in E.det_double(df, piv, 5):
        i, j = c["anchors"][0]["i"], c["anchors"][2]["i"]
        if c["pattern"] == "double_top":
            assert df.High.values[i:j + 1].max() <= max(df.High.values[i], df.High.values[j]) * 1.005


def test_false_positive_rate_on_noise_is_bounded():
    hits = 0; N = 60
    for s in range(N):
        df = random_walk(seed=100 + s); piv = E.pivots(df, 5); atr = float(df.ATR14.iloc[-1])
        tls = E.trendlines(piv, df, atr)
        if E.run_detectors(df, piv, 5, atr, tls): hits += 1
    assert hits / N < 0.5, f"detector fired on {hits}/{N} random walks"


def test_checker_flags_numbers_not_in_pack():
    pack = {"facts": [{"id": "F1", "text": "Last close 3375.4 on 2026-10-13", "value": 3375.4}], "candidates": [], "pivots": []}
    ok, _ = E.check_sample({"reasons": [{"text": "Close 3375.4 holds", "evidence": ["F1"]}], "levels": {}}, pack)
    bad, _ = E.check_sample({"reasons": [{"text": "Close 3390 holds", "evidence": ["F1", "F9"]}], "levels": {"stop": 3100}}, pack)
    assert ok == []
    assert any("3390" in p for p in bad) and any("F9" in p for p in bad) and any("stop" in p for p in bad)


def test_checker_is_sign_agnostic():
    pack = {"facts": [{"id": "F6", "text": "close is -24.09% from the 52-week high", "value": -24.09}], "candidates": [], "pivots": []}
    problems, _ = E.check_sample({"reasons": [{"text": "a 24.09% drop", "evidence": ["F6"]}], "levels": {}}, pack)
    assert problems == []


def test_consensus_gate():
    s = [{"view": "bullish", "setup": "confirmed", "pattern_id": "C1"}] * 3
    assert E.consensus(s)["final_view"] == "bullish"
    s2 = s[:2] + [{"view": "neutral", "setup": "confirmed", "pattern_id": "C1"}]
    assert E.consensus(s2)["final_view"] == "neutral" and not E.consensus(s2)["unanimous"]
