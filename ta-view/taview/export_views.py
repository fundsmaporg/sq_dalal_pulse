"""Export the latest stored views to data/demo_views.json (what a fresh install seeds from)."""
import os, sys
from .config import Settings
from .store import Store

if __name__ == "__main__":
    s = Settings(); st = Store(s.db_path)
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(s.data_dir, "demo_views.json")
    print(f"exported {st.export(out)} views to {out}")
