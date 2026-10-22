"""Settings from environment variables (see .env.example)."""
from __future__ import annotations
import os
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass
class Settings:
    provider: str = field(default_factory=lambda: _env("PRICE_PROVIDER", "eod2"))          # eod2 | pmsec
    offline: bool = field(default_factory=lambda: _env("TAVIEW_OFFLINE", "0") == "1")      # eod2 only: never fetch
    data_dir: str = field(default_factory=lambda: _env("TAVIEW_DATA_DIR", os.path.join(ROOT, "data")))
    model: str = field(default_factory=lambda: _env("TAVIEW_MODEL", "claude-opus-5-5"))
    samples: int = field(default_factory=lambda: int(_env("TAVIEW_SAMPLES", "3")))
    reasoner: str = field(default_factory=lambda: _env("TAVIEW_REASONER", "auto"))         # auto | claude | fallback
    fallbacks: bool = field(default_factory=lambda: _env("TAVIEW_FALLBACKS", "0") == "1")  # server-side refusal fallbacks (beta)
    view_ttl_hours: float = field(default_factory=lambda: float(_env("TAVIEW_VIEW_TTL_HOURS", "20")))

    @property
    def cache_dir(self) -> str:
        return os.path.join(self.data_dir, "cache")

    @property
    def views_dir(self) -> str:
        return os.path.join(self.data_dir, "views")

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, "taview.sqlite")

    @property
    def anthropic_key(self) -> str | None:
        return os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
