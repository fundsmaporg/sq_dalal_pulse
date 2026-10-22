"""SQLite store for views. One row per (symbol, horizon, as_of); the newest row is served.
Stored verbatim: evidence pack, geometry, samples, consensus, card and provenance, so a view can be replayed."""
from __future__ import annotations
import json, os, sqlite3, time


class Store:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS views (
                id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, horizon TEXT NOT NULL, as_of TEXT NOT NULL,
                created_at REAL NOT NULL, reasoner TEXT NOT NULL, view TEXT NOT NULL, setup TEXT NOT NULL, payload TEXT NOT NULL)""")
            c.execute("CREATE INDEX IF NOT EXISTS ix_views ON views(symbol, horizon, created_at)")

    def _conn(self):
        return sqlite3.connect(self.path)

    def put(self, payload: dict) -> int:
        with self._conn() as c:
            cur = c.execute("INSERT INTO views(symbol, horizon, as_of, created_at, reasoner, view, setup, payload) VALUES (?,?,?,?,?,?,?,?)",
                            (payload["symbol"], payload["horizon"], payload["as_of"], time.time(), payload.get("reasoner", "?"),
                             payload["view"], payload["setup"], json.dumps(payload, default=str)))
            return cur.lastrowid

    def latest(self, symbol: str, horizon: str, max_age_hours: float | None = None) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT payload, created_at FROM views WHERE symbol=? AND horizon=? ORDER BY created_at DESC LIMIT 1", (symbol, horizon)).fetchone()
        if not row:
            return None
        if max_age_hours is not None and time.time() - row[1] > max_age_hours * 3600:
            return None
        return json.loads(row[0])

    def count(self) -> int:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM views").fetchone()[0]

    def seed(self, path: str) -> int:
        """Load demo views from a JSON file (list of payloads) when the store is empty. Returns rows added."""
        if self.count() or not os.path.exists(path):
            return 0
        n = 0
        for payload in json.load(open(path)):
            self.put(payload); n += 1
        return n

    def export(self, path: str) -> int:
        """Write the latest payload per (symbol, horizon) to a JSON file (without the bars' full history to keep it small)."""
        rows = [self.latest(v["symbol"], v["horizon"]) for v in self.list()]
        json.dump(rows, open(path, "w"), default=str)
        return len(rows)

    def list(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT symbol, horizon, as_of, created_at, reasoner, view, setup FROM views ORDER BY symbol, horizon, created_at DESC").fetchall()
        seen, out = set(), []
        for r in rows:
            if (r[0], r[1]) in seen: continue
            seen.add((r[0], r[1]))
            out.append({"symbol": r[0], "horizon": r[1], "as_of": r[2], "created_at": r[3], "reasoner": r[4], "view": r[5], "setup": r[6]})
        return out
