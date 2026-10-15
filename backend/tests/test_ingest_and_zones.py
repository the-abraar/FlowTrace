import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/x.db"

from fastapi.testclient import TestClient
from main import app
from positioning.zone_detector import ZoneDetector, Zone


def test_http_edge_cases():
    with TestClient(app, headers={"x-api-key": "test-ingest"}) as c:
        # bad payloads -> 422
        assert c.post("/api/v1/readings", json={"readings": "x"}).status_code == 422
        assert c.post("/api/v1/readings", json={"readings": [{"device_id": "T", "rssi": -60}]}).status_code == 422  # no node_id
        # unknown node -> partial; known -> ok
        r = c.post("/api/v1/readings", json={"readings": [
            {"node_id": "ghost", "device_id": "T", "rssi": -60},
            {"node_id": "node-SW", "device_id": "T", "rssi": -60}]}).json()
        assert r == {"status": "partial", "inserted": 1, "duplicates": 0, "unknown_nodes": ["ghost"]}
        # retried batch: (node, device, ts_ms) already stored -> counted as duplicates, not inserted again
        b = {"node_id": "node-SW", "readings": [{"device_id": "DUP", "rssi": -50, "ts_ms": 7}, {"device_id": "DUP", "rssi": -51, "ts_ms": 8}]}
        assert c.post("/api/v1/readings", json=b).json() == {"status": "ok", "inserted": 2, "duplicates": 0, "unknown_nodes": []}
        assert c.post("/api/v1/readings", json=b).json() == {"status": "ok", "inserted": 0, "duplicates": 2, "unknown_nodes": []}
        other = {"node_id": "node-SE", "readings": [{"device_id": "DUP", "rssi": -50, "ts_ms": 7}]}  # same ts_ms, other node
        assert c.post("/api/v1/readings", json=other).json()["inserted"] == 1
        no_ts = {"node_id": "node-SW", "readings": [{"device_id": "DUP", "rssi": -50}]}  # no node timestamp: no dedupe key
        assert c.post("/api/v1/readings", json=no_ts).json()["inserted"] == 1
        assert c.post("/api/v1/readings", json=no_ts).json()["inserted"] == 1
        sw = [x for x in c.get("/api/v1/nodes/node-SW/readings").json() if x["device_id"] == "DUP"]
        assert sorted(x["rssi"] for x in sw) == [-51, -50, -50, -50]
        assert [d["id"] for d in c.get("/api/v1/devices").json()].count("DUP") == 1  # device row not duplicated


def test_zone_detector_two_zones():
    zd = ZoneDetector([Zone("LEFT", "L", ((0, 0), (5, 0), (5, 10), (0, 10))),
                       Zone("RIGHT", "R", ((5, 0), (10, 0), (10, 10), (5, 10)))])
    assert zd.update("d", 2, 5) == "LEFT"
    assert zd.update("d", 8, 5) == "RIGHT"
    assert zd.point_in_zone(20, 20) is None and zd.update("d", 20, 20) is None
    assert [v["zone"] for v in zd.get_device_journey("d")] == ["LEFT", "RIGHT"]
