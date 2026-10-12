import os
import sys
import types
import json
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingestion.mqtt_server import MQTTServer
from positioning.triangulator import PositioningFleet


class Spy:
    def __init__(self): self.calls = []
    def ingest_reading(self, *a): self.calls.append(a)


def _msg(d): return types.SimpleNamespace(topic="flowtrace/nodes/n1/readings", payload=json.dumps(d).encode())


def test_mqtt_scanner_batch_and_flat():
    spy = Spy(); s = MQTTServer(fleet=spy)  # loop is None: no DB, no broker
    s.on_message(None, None, _msg({"node_id": "n1", "readings": [
        {"device_id": "T1", "rssi": -70, "mac": "x", "ts_ms": 1}, {"device_id": "T2", "rssi": -60}]}))
    s.on_message(None, None, _msg({"node_id": "n2", "device_id": "T3", "rssi": -50}))  # topic says n1: rejected
    s.on_message(None, None, _msg({"readings": [{"device_id": "T4", "rssi": -50}]}))  # no node_id: taken from topic
    assert [c[:3] for c in spy.calls] == [("n1", "T1", -70), ("n1", "T2", -60), ("n1", "T4", -50)]


def test_positions_clamped_to_bounds():
    f = PositioningFleet(bounds=(2.0, 2.0))
    f.configure_nodes([{"node_id": "a", "x": 0, "y": 0}, {"node_id": "b", "x": 10, "y": 0}, {"node_id": "c", "x": 0, "y": 10}])
    t = time.time()
    for n, r in [("a", -90), ("b", -50), ("c", -50)]:  # raw estimate lands outside the room
        f.ingest_reading(n, "T", r, t)
    p = f.get_all_positions()["T"]
    assert 0 <= p.x <= 2 and 0 <= p.y <= 2


def test_fleet_ttl_eviction_and_cap():
    now = [1000.0]
    f = PositioningFleet(ttl_s=600, max_devices=2, clock=lambda: now[0])
    f.configure_nodes([{"node_id": "a", "x": 0, "y": 0}])
    for d in ("D1", "D2", "D3"):
        f.ingest_reading("a", d, -60, now[0])
    assert set(f._rssi) == {"D1", "D2"} and f.rejected == 1
    now[0] += 300; f.ingest_reading("a", "D2", -60, now[0])
    now[0] += 400; f.evict_idle()  # D1 idle 700s, D2 idle 400s
    assert set(f._rssi) == {"D2"}
    f.ingest_reading("a", "D3", -60, now[0])  # room freed
    assert set(f._rssi) == {"D2", "D3"}


def test_mqtt_credentials_applied(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "MQTT_USERNAME", "u"); monkeypatch.setattr(settings, "MQTT_PASSWORD", "p")
    assert MQTTServer(fleet=None).client._username == b"u"
