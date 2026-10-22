"""Price provider interface. Every provider returns pandas DataFrames indexed by timestamp with
columns Open, High, Low, Close, Volume (floats; Volume int). Symbols are EXCHANGE:TRADINGSYMBOL."""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd


class ProviderError(Exception):
    """Base class for provider failures. `retryable` tells callers whether a retry makes sense."""
    def __init__(self, message: str, retryable: bool = False, status: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status = status


class UnknownSymbol(ProviderError):
    pass


class NotSupported(ProviderError):
    pass


@dataclass
class Quote:
    symbol: str
    ltp: float | None
    close: float | None
    age_seconds: int | None
    source: str | None
    unavailable: str | None = None


class PriceProvider:
    name = "base"

    def daily(self, symbol: str, years: int = 3) -> pd.DataFrame:
        raise NotImplementedError

    def intraday(self, symbol: str, interval: str = "5minute", days: int = 60) -> pd.DataFrame:
        raise NotSupported(f"{self.name} has no intraday data")

    def quotes(self, symbols: list[str]) -> dict[str, Quote]:
        raise NotSupported(f"{self.name} has no live quotes")


REQUIRED = ["Open", "High", "Low", "Close", "Volume"]


def normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Sort, de-duplicate and type-check a candle frame."""
    if df.empty:
        return pd.DataFrame(columns=REQUIRED)
    df = df[REQUIRED].copy()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    for c in ("Open", "High", "Low", "Close"):
        df[c] = df[c].astype(float)
    df["Volume"] = df["Volume"].fillna(0).astype("int64")
    return df.dropna()
