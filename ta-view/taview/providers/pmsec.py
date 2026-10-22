"""Client for the PMSEC price service (service-to-service endpoints /internal/ltp and /internal/history).

Implements the rules from the service documentation:
- X-Internal-Key header on every request; key comes from the environment, never from code.
- history: one symbol per call, windows split to the per-interval maximum span, candles after `to`
  dropped (known issue with date-only `to`), 503 busy -> wait retry_after_ms, 429 -> back off >= 5 s,
  502 -> one retry, 400/401/403/404 never retried.
- cache-friendly bulk windows: `daily_bulk_window()` ends two days back so the finished window is cached
  for 7 days; the last two sessions come from a separate small call or from /internal/ltp `close`.
- ltp: batches of at most 200 symbols; a symbol is either priced or unavailable, never guessed.
The service is reachable only from an allowlisted private IP inside the VPC."""
from __future__ import annotations
import os, time
from datetime import date, datetime, timedelta
import httpx
import pandas as pd
from .base import PriceProvider, ProviderError, UnknownSymbol, Quote, normalise

MAX_SPAN_DAYS = {"minute": 60, "3minute": 100, "5minute": 100, "10minute": 100, "15minute": 200, "30minute": 200, "60minute": 400, "day": 2000}


class PmsecProvider(PriceProvider):
    name = "pmsec"

    def __init__(self, base_url: str | None = None, key: str | None = None, timeout_ltp: float = 15, timeout_history: float = 35,
                 sleep=time.sleep, client: httpx.Client | None = None):
        self.base = (base_url or os.environ.get("PRICE_SERVICE_URL", "http://172.31.19.132:8766")).rstrip("/")
        self.key = key or os.environ.get("PRICE_INTERNAL_KEY")
        if not self.key:
            raise ProviderError("PRICE_INTERNAL_KEY is not set")
        self.timeout_ltp, self.timeout_history, self.sleep = timeout_ltp, timeout_history, sleep
        self.client = client or httpx.Client()

    # ------------------------------------------------------------------ low level
    def _get(self, path: str, params: dict, timeout: float, attempts: int = 4) -> dict:
        last = None
        for attempt in range(attempts):
            try:
                r = self.client.get(self.base + path, params=params, headers={"X-Internal-Key": self.key}, timeout=timeout)
            except httpx.HTTPError as e:
                last = ProviderError(f"network error: {e}", retryable=True)
                self.sleep(1.0 * (attempt + 1)); continue
            if r.status_code == 200:
                return r.json()
            body = {}
            try: body = r.json()
            except ValueError: pass
            code = body.get("error") or body.get("detail") or r.text[:80]
            if r.status_code == 503 and code == "busy":
                self.sleep((body.get("retry_after_ms") or int(float(r.headers.get("Retry-After", "1")) * 1000)) / 1000.0); last = ProviderError("busy", True, 503); continue
            if r.status_code == 429:
                self.sleep(5.0); last = ProviderError("rate_limited", True, 429); continue
            if r.status_code == 502:
                if attempt == 0:
                    self.sleep(2.0); last = ProviderError("upstream_error", True, 502); continue
                raise ProviderError("upstream_error (window too long or provider down)", retryable=True, status=502)
            if r.status_code == 404:
                raise UnknownSymbol(f"{params.get('symbol') or params.get('symbols')}: unknown_symbol")
            if r.status_code in (400, 401, 403):
                raise ProviderError(f"{r.status_code} {code}", retryable=False, status=r.status_code)
            if r.status_code == 503:
                raise ProviderError(f"503 {code}", retryable=False, status=503)
            last = ProviderError(f"{r.status_code} {code}", retryable=True, status=r.status_code)
        raise last or ProviderError("request failed")

    # ------------------------------------------------------------------ history
    @staticmethod
    def split_windows(start: date, end: date, interval: str):
        span = MAX_SPAN_DAYS[interval]
        cur = start
        while cur <= end:
            stop = min(end, cur + timedelta(days=span - 1))
            yield cur, stop
            cur = stop + timedelta(days=1)

    @staticmethod
    def daily_bulk_window(years: int, today: date | None = None) -> tuple[date, date, date]:
        """(from, to_for_bulk, to_for_tail): the bulk window ends two days back so it is cached for 7 days."""
        today = today or date.today()
        return today - timedelta(days=int(365.25 * years)), today - timedelta(days=2), today

    def history(self, symbol: str, interval: str, start: date, end: date) -> pd.DataFrame:
        if interval not in MAX_SPAN_DAYS:
            raise ProviderError(f"unsupported interval {interval}")
        frames = []
        for a, b in self.split_windows(start, end, interval):
            data = self._get("/internal/history", {"symbol": symbol, "interval": interval, "from": a.isoformat(), "to": b.isoformat()}, self.timeout_history)
            rows = data.get("candles") or []
            if rows:
                df = pd.DataFrame(rows)
                df["t"] = pd.to_datetime(df["t"].str.replace(r"([+-]\d\d)(\d\d)$", r"\1:\2", regex=True))
                df = df.set_index("t").rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
                df.index = df.index.tz_localize(None)
                df = df[df.index.normalize() <= pd.Timestamp(b)]   # known issue: date-only `to` may include the next day
                frames.append(df)
        if not frames:
            return normalise(pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"]))
        return normalise(pd.concat(frames))

    def daily(self, symbol: str, years: int = 3) -> pd.DataFrame:
        start, bulk_to, today = self.daily_bulk_window(years)
        bulk = self.history(symbol, "day", start, bulk_to)
        tail = self.history(symbol, "day", bulk_to + timedelta(days=1), today)
        df = normalise(pd.concat([bulk, tail])) if not tail.empty else bulk
        df.index = df.index.normalize()
        return df

    def intraday(self, symbol: str, interval: str = "5minute", days: int = 60) -> pd.DataFrame:
        today = date.today()
        return self.history(symbol, interval, today - timedelta(days=days), today)

    # ------------------------------------------------------------------ quotes
    def quotes(self, symbols: list[str]) -> dict[str, Quote]:
        out: dict[str, Quote] = {}
        for i in range(0, len(symbols), 200):
            batch = symbols[i:i + 200]
            data = self._get("/internal/ltp", {"symbols": ",".join(batch)}, self.timeout_ltp)
            for s, q in (data.get("quotes") or {}).items():
                out[s] = Quote(s, q.get("ltp"), q.get("close"), q.get("age_seconds"), q.get("source"))
            for s, reason in (data.get("unavailable") or {}).items():
                out[s] = Quote(s, None, None, None, None, unavailable=reason)
        return out
