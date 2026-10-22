"""Public NSE end-of-day mirror (eod2_data on GitHub): daily candles adjusted for bonuses and splits.
Prototype data only: it is a community mirror of NSE bhavcopy, updated roughly weekly, and not a licensed feed.
Cached on disk so repeated runs and tests never hit the network."""
from __future__ import annotations
import io, os, time
import httpx
import pandas as pd
from .base import PriceProvider, UnknownSymbol, ProviderError, normalise

RAW = "https://raw.githubusercontent.com/BennyThadikaran/eod2_data/main/daily/{sym}.csv"


class Eod2Provider(PriceProvider):
    name = "eod2"

    def __init__(self, cache_dir: str, ttl_hours: float = 12, timeout: float = 30, offline: bool = False):
        self.cache_dir = cache_dir
        self.ttl = ttl_hours * 3600
        self.timeout = timeout
        self.offline = offline
        os.makedirs(cache_dir, exist_ok=True)

    def _path(self, symbol: str) -> str:
        return os.path.join(self.cache_dir, symbol.replace(":", "_").upper() + ".csv")

    def _fetch(self, symbol: str) -> str:
        exch, _, ts = symbol.partition(":")
        if exch.upper() != "NSE" or not ts:
            raise UnknownSymbol(f"{symbol}: the mirror only carries NSE symbols as NSE:TRADINGSYMBOL")
        url = RAW.format(sym=ts.lower())
        try:
            r = httpx.get(url, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise ProviderError(f"mirror fetch failed: {e}", retryable=True) from e
        if r.status_code == 404:
            raise UnknownSymbol(f"{symbol}: not in the mirror")
        if r.status_code != 200:
            raise ProviderError(f"mirror returned {r.status_code}", retryable=r.status_code >= 500, status=r.status_code)
        return r.text

    def daily(self, symbol: str, years: int = 3) -> pd.DataFrame:
        path = self._path(symbol)
        fresh = os.path.exists(path) and (time.time() - os.path.getmtime(path) < self.ttl)
        if not fresh and not self.offline:
            text = self._fetch(symbol)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        elif not os.path.exists(path):
            raise UnknownSymbol(f"{symbol}: not cached and provider is offline")
        df = pd.read_csv(path)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        df = normalise(df)
        if years:
            df = df[df.index >= df.index[-1] - pd.Timedelta(days=int(365.25 * years))]
        return df
