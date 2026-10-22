"""Nightly precompute: python -m taview.batch --symbols NSE:BSE,NSE:RELIANCE --horizons swing,medium,long
Runs the full pipeline per (symbol, horizon) and stores the result. Respects the provider's budget by running serially."""
from __future__ import annotations
import argparse, sys, time, traceback
from .config import Settings
from .providers import make_provider
from .store import Store
from .pipeline import build_view, COMPANY


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=",".join(COMPANY), help="comma-separated EXCHANGE:SYMBOL list")
    ap.add_argument("--horizons", default="swing,medium,long")
    ap.add_argument("--sleep", type=float, default=1.0, help="seconds between symbols (provider budget)")
    a = ap.parse_args(argv)
    settings = Settings(); provider = make_provider(settings); store = Store(settings.db_path)
    ok = fail = 0
    for sym in [s.strip().upper() for s in a.symbols.split(",") if s.strip()]:
        for h in [x.strip() for x in a.horizons.split(",") if x.strip()]:
            t0 = time.time()
            try:
                payload = build_view(sym, h, provider, settings); store.put(payload); ok += 1
                print(f"{sym:16s} {h:7s} {payload['view']:8s} {payload['setup']:10s} {payload['reasoner']:32s} {time.time() - t0:5.1f}s")
            except Exception as e:
                fail += 1; print(f"{sym:16s} {h:7s} FAILED {e}"); traceback.print_exc(limit=1, file=sys.stderr)
            time.sleep(a.sleep)
    print(f"done: {ok} ok, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
