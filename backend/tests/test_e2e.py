"""Ingest (firmware batch format) -> position loop -> /ws + REST, on sqlite."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/t.db"

from fastapi.testclient import TestClient
from main import app


def test_ingest_to_position():
    with TestClient(app, headers={"x-api-key": "test-ingest"}) as c, c.websocket_connect("/ws") as ws:
        # firmware shape: node_id once per batch; one POST per node
        for node, rssi in [("node-SW", -72), ("node-SE", -77), ("node-NW", -77)]:
            r = c.post("/api/v1/readings", json={"node_id": node, "fw_version": "1.0.0", "readings": [
                {"device_id": "TAG_1", "mac": "AA:BB:CC:DD:EE:FF", "rssi": rssi, "batt_mv": 3800, "ts_ms": 1}]})
            assert r.status_code == 200 and r.json()["inserted"] == 1

        r = c.post("/api/v1/readings", json={"node_id": "nope", "readings": [{"device_id": "TAG_1", "rssi": -70}]})
        assert r.json()["unknown_nodes"] == ["nope"] and r.json()["inserted"] == 0

        msg = ws.receive_json()  # position loop ticks every 2 s
        pos = msg["data"][0]
        assert msg["type"] == "positions" and pos["device_id"] == "TAG_1"
        assert abs(pos["x"] - 3) < 2 and abs(pos["y"] - 3) < 2  # tag simulated at (3,3)
        assert c.get("/api/v1/devices").status_code == 200
