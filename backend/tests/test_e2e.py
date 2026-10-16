"""Ingest (firmware batch format) -> position loop -> /ws + REST, on sqlite."""
import os
import sys
import tempfile
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/t.db"

from fastapi.testclient import TestClient
from main import app, fleet


def test_ingest_to_position():
    with TestClient(app, headers={"x-api-key": "test-ingest"}) as c, c.websocket_connect("/ws") as ws:
        # firmware shape: node_id once per batch; one POST per node
        for node, rssi in [("node-SW", -72), ("node-SE", -77), ("node-NW", -77)]:
            r = c.post("/api/v1/readings", json={"node_id": node, "fw_version": "1.0.0", "readings": [
                {"device_id": "TAG_1", "mac": "AA:BB:CC:DD:EE:FF", "rssi": rssi, "batt_mv": 3800, "ts_ms": 1}]})
            assert r.status_code == 200 and r.json()["inserted"] == 1

        r = c.post("/api/v1/readings", json={"node_id": "nope", "readings": [{"device_id": "TAG_1", "rssi": -70}]})
        assert r.json()["unknown_nodes"] == ["nope"] and r.json()["inserted"] == 0

        # ws.receive_json() has no timeout and the loop only broadcasts once a position exists, so a missing
        # position used to hang CI for hours. Wait for one (bounded), then the next 2 s tick is sure to send.
        deadline = time.monotonic() + 10
        while not fleet.get_all_positions().get("TAG_1") and time.monotonic() < deadline:
            time.sleep(0.1)
        assert fleet.get_all_positions().get("TAG_1"), f"no position for TAG_1 after 10 s; fleet holds {list(fleet._rssi)}"
        msg = ws.receive_json()  # position loop ticks every 2 s
        pos = next(p for p in msg["data"] if p["device_id"] == "TAG_1")  # other test modules may share the fleet
        assert msg["type"] == "positions"
        assert abs(pos["x"] - 3) < 2 and abs(pos["y"] - 3) < 2  # tag simulated at (3,3)
        assert c.get("/api/v1/devices").status_code == 200
