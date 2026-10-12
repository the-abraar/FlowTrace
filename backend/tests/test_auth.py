import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/a.db"
from fastapi.testclient import TestClient
from main import app

B = {"node_id": "node-SW", "readings": [{"device_id": "D", "rssi": -50}]}


def test_ingest_key_and_unset(monkeypatch):
    with TestClient(app) as c:
        assert c.post("/api/v1/readings", json=B).status_code == 401
        assert c.post("/api/v1/readings", json=B, headers={"x-api-key": "bad"}).status_code == 401
        assert c.post("/api/v1/readings", json=B, headers={"x-api-key": "test-ingest"}).status_code == 200
        monkeypatch.delenv("INGEST_API_KEY")
        assert c.post("/api/v1/readings", json=B).status_code == 503  # unset, not DEBUG: refused
        monkeypatch.setenv("DEBUG", "1")
        assert c.post("/api/v1/readings", json=B).status_code == 200  # dev: open


def test_read_key_and_limit(monkeypatch):
    with TestClient(app) as c:
        assert c.get("/api/v1/nodes").status_code == 200  # READ_API_KEY unset: open
        monkeypatch.setenv("READ_API_KEY", "rk")
        assert c.get("/api/v1/nodes").status_code == 401
        assert c.get("/api/v1/nodes?key=rk").status_code == 200
        h = {"x-api-key": "rk"}
        assert c.get("/api/v1/nodes/node-SW/readings?limit=1001", headers=h).status_code == 422
        assert c.get("/api/v1/nodes/node-SW/readings?limit=0", headers=h).status_code == 422
        assert c.get("/api/v1/nodes/node-SW/readings?limit=1000", headers=h).status_code == 200
        try:
            with c.websocket_connect("/ws"):
                assert False, "ws should be refused"
        except Exception:
            pass
        with c.websocket_connect("/ws?key=rk"):
            pass
