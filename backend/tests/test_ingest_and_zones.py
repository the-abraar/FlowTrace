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
        assert r == {"status": "partial", "inserted": 1, "unknown_nodes": ["ghost"]}
        # duplicate batch: no dedupe today, both inserted and nothing crashes (documents behaviour)
        b = {"node_id": "node-SW", "readings": [{"device_id": "D", "rssi": -50, "timestamp": "2026-01-01T00:00:00Z"}]}
        assert c.post("/api/v1/readings", json=b).json()["inserted"] == 1
        assert c.post("/api/v1/readings", json=b).json()["inserted"] == 1
        assert [d["id"] for d in c.get("/api/v1/devices").json()].count("D") == 1  # device row not duplicated


def test_zone_detector_two_zones():
    zd = ZoneDetector([Zone("LEFT", "L", ((0, 0), (5, 0), (5, 10), (0, 10))),
                       Zone("RIGHT", "R", ((5, 0), (10, 0), (10, 10), (5, 10)))])
    assert zd.update("d", 2, 5) == "LEFT"
    assert zd.update("d", 8, 5) == "RIGHT"
    assert zd.point_in_zone(20, 20) is None and zd.update("d", 20, 20) is None
    assert [v["zone"] for v in zd.get_device_journey("d")] == ["LEFT", "RIGHT"]
