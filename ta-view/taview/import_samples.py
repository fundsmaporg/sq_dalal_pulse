"""Import externally produced model samples (e.g. from a batch job or an evaluation run) for stored views.
python -m taview.import_samples samples.json   where samples.json = {"NSE:BSE": {"swing": [sample, sample, sample]}, ...}
Each sample must match reasoner.SCHEMA. The samples go through the same checker and unanimity gate as live calls."""
from __future__ import annotations
import json, os, sys
import pandas as pd
from .config import Settings
from .providers import make_provider
from .store import Store
from .pipeline import compute, assemble
from .reasoner import reason


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print(__doc__); return 2
    data = json.load(open(argv[0]))
    label = argv[1] if len(argv) > 1 else None
    settings = Settings(); provider = make_provider(settings); store = Store(settings.db_path)
    for symbol, by_h in data.items():
        for horizon, samples in by_h.items():
            bars = provider.daily(symbol, years=6 if horizon == "long" else 3)
            out_dir = os.path.join(settings.views_dir, symbol.replace(":", "_"), horizon)
            computed = compute(symbol, horizon, bars, out_dir, provenance=f"{provider.name} provider")
            reasoned = reason(computed["pack"], computed["images"], settings, samples=samples)
            if label:
                reasoned["reasoner"] = label
            payload = assemble(symbol, horizon, computed, reasoned, bars, settings)
            json.dump(payload, open(os.path.join(out_dir, "view.json"), "w"), default=str)
            store.put(payload)
            print(f"{symbol:16s} {horizon:7s} {payload['view']:8s} {payload['setup']:10s} unanimous={payload['consensus']['unanimous']} checker={[s['checker'] for s in payload['samples']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
