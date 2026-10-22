"""End-to-end through the API with the offline mirror provider and the deterministic reasoner (no network, no model key)."""
import os, shutil, pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    data = tmp_path_factory.mktemp("data")
    os.makedirs(data / "cache"); shutil.copy(os.path.join(ROOT, "tests", "fixtures", "NSE_BSE.csv"), data / "cache" / "NSE_BSE.csv")
    os.environ.update({"TAVIEW_DATA_DIR": str(data), "TAVIEW_OFFLINE": "1", "TAVIEW_REASONER": "fallback", "PRICE_PROVIDER": "eod2"})
    import importlib, taview.api as api
    importlib.reload(api)
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def test_health_and_symbols(client):
    assert client.get("/api/health").json()["provider"] == "eod2"
    j = client.get("/api/symbols").json()
    assert any(s["symbol"] == "NSE:BSE" for s in j["symbols"]) and j["horizons"] == ["swing", "medium", "long"]


def test_view_swing_bse(client):
    r = client.get("/api/view", params={"symbol": "bse", "horizon": "swing"})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["symbol"] == "NSE:BSE" and v["view"] in ("bullish", "bearish", "neutral") and v["setup"] in ("none", "forming", "confirmed", "failed", "conflicting")
    assert len(v["bars"]) > 200 and v["facts"] and v["reasons"]
    assert all(not s["checker"] for s in v["samples"]), v["samples"]
    if v["geometry"]:
        assert v["pine"].startswith("//@version=6") and all("d" in q for p in v["geometry"]["primitives"] for q in p.get("points", []))


def test_view_is_cached_and_listed(client):
    a = client.get("/api/view", params={"symbol": "NSE:BSE", "horizon": "swing"}).json()
    b = client.get("/api/view", params={"symbol": "NSE:BSE", "horizon": "swing"}).json()
    assert a["generated_at"] == b["generated_at"]
    assert any(x["symbol"] == "NSE:BSE" for x in client.get("/api/views").json()["views"])


def test_unknown_symbol_offline(client):
    assert client.get("/api/view", params={"symbol": "NSE:NOTREAL"}).status_code == 404


def test_bad_horizon(client):
    assert client.get("/api/view", params={"symbol": "NSE:BSE", "horizon": "weekly"}).status_code == 400


def test_ui_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Technical view" in r.text
