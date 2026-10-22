"""The price-service client against a fake HTTP transport (no network)."""
import json
from datetime import date
import httpx, pytest
from taview.providers.pmsec import PmsecProvider, MAX_SPAN_DAYS
from taview.providers.base import ProviderError, UnknownSymbol


def make(handler, sleeps):
    transport = httpx.MockTransport(handler)
    return PmsecProvider(base_url="http://price.test:8766", key="k", sleep=lambda s: sleeps.append(s), client=httpx.Client(transport=transport))


def candles(dates):
    return {"symbol": "NSE:BSE", "interval": "day", "hasOi": False, "candles": [{"t": f"{d}T00:00:00+0530", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10} for d in dates]}


def test_key_header_and_window_split():
    seen = []
    def handler(req):
        seen.append((req.headers.get("X-Internal-Key"), dict(req.url.params)))
        return httpx.Response(200, json=candles([]))
    p = make(handler, [])
    p.history("NSE:BSE", "day", date(2015, 1, 1), date(2026, 10, 13))
    assert all(k == "k" for k, _ in seen)
    assert len(seen) > 1 and all((date.fromisoformat(q["to"]) - date.fromisoformat(q["from"])).days < MAX_SPAN_DAYS["day"] for _, q in seen)


def test_known_issue_drops_candle_after_to():
    def handler(req):
        return httpx.Response(200, json=candles(["2026-10-12", "2026-10-13", "2026-10-14"]))
    df = make(handler, []).history("NSE:BSE", "day", date(2026, 10, 1), date(2026, 10, 13))
    assert [str(d.date()) for d in df.index] == ["2026-10-12", "2026-10-13"]


def test_busy_then_ok_waits_retry_after():
    calls = {"n": 0}
    def handler(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={"error": "busy", "retry_after_ms": 1500})
        return httpx.Response(200, json=candles(["2026-10-13"]))
    sleeps = []
    df = make(handler, sleeps).history("NSE:BSE", "day", date(2026, 10, 1), date(2026, 10, 13))
    assert len(df) == 1 and sleeps == [1.5]


def test_rate_limited_backs_off_five_seconds():
    calls = {"n": 0}
    def handler(req):
        calls["n"] += 1
        return httpx.Response(429, json={"error": "rate_limited"}) if calls["n"] == 1 else httpx.Response(200, json=candles([]))
    sleeps = []
    make(handler, sleeps).history("NSE:BSE", "day", date(2026, 10, 1), date(2026, 10, 13))
    assert sleeps and sleeps[0] >= 5


def test_unknown_symbol_and_bad_request_do_not_retry():
    calls = {"n": 0}
    def handler(req):
        calls["n"] += 1
        return httpx.Response(404, json={"error": "unknown_symbol"})
    with pytest.raises(UnknownSymbol):
        make(handler, []).history("NSE:NOPE", "day", date(2026, 10, 1), date(2026, 10, 13))
    assert calls["n"] == 1
    calls["n"] = 0
    def handler2(req):
        calls["n"] += 1
        return httpx.Response(401, json={"error": "unauthorized"})
    with pytest.raises(ProviderError) as e:
        make(handler2, []).history("NSE:BSE", "day", date(2026, 10, 1), date(2026, 10, 13))
    assert not e.value.retryable and calls["n"] == 1


def test_bulk_window_ends_two_days_back():
    start, bulk_to, today = PmsecProvider.daily_bulk_window(3, today=date(2026, 10, 22))
    assert bulk_to == date(2026, 10, 20) and today == date(2026, 10, 22) and start.year == 2023


def test_quotes_batches_and_unavailable():
    seen = []
    def handler(req):
        seen.append(req.url.params["symbols"].count(",") + 1)
        return httpx.Response(200, json={"quotes": {"NSE:A": {"ltp": 1, "close": 2, "ts": 0, "age_seconds": 0, "source": "feed"}}, "unavailable": {"NSE:ZZ": "stale"}})
    q = make(handler, []).quotes([f"NSE:S{i}" for i in range(450)])
    assert seen == [200, 200, 50] and q["NSE:ZZ"].unavailable == "stale" and q["NSE:A"].ltp == 1
