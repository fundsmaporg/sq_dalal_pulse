from .base import PriceProvider, ProviderError, UnknownSymbol, NotSupported, Quote
from .eod2 import Eod2Provider
from .pmsec import PmsecProvider


def make_provider(settings) -> PriceProvider:
    if settings.provider == "pmsec":
        return PmsecProvider()
    return Eod2Provider(settings.cache_dir, offline=settings.offline)
