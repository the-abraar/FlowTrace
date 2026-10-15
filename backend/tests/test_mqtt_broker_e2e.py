"""Real broker: publish a scanner batch over MQTT and see it stored once.
Opt-in: `docker compose up -d mosquitto`, then MQTT_E2E_BROKER=localhost:1883 pytest tests/test_mqtt_broker_e2e.py."""
import json
import os
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

BROKER = os.environ.get("MQTT_E2E_BROKER")
pytestmark = pytest.mark.skipif(not BROKER, reason="set MQTT_E2E_BROKER=host:port (docker compose up -d mosquitto)")


def test_mqtt_batch_stored_once(monkeypatch):
    import paho.mqtt.client as mqtt
    from fastapi.testclient import TestClient
    from config import settings
    from main import app

    host, port = BROKER.rsplit(":", 1)
    monkeypatch.setenv("MQTT_BROKER_HOST", host)
    monkeypatch.setenv("MQTT_BROKER_PORT", port)
    monkeypatch.setattr(settings, "MQTT_CLIENT_ID", f"flowtrace-e2e-{os.getpid()}")  # don't kick a running backend off
    dev = f"E2E_{time.time_ns()}"
    batch = json.dumps({"node_id": "node-C", "fw_version": "1.0.0", "readings": [
        {"device_id": dev, "mac": "AA:BB:CC:DD:EE:FF", "rssi": -61, "batt_mv": 3800, "ts_ms": 42}]})
    pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"flowtrace-e2e-pub-{os.getpid()}")
    pub.connect(host, int(port))
    pub.loop_start()

    def stored():
        return [r for r in c.get("/api/v1/nodes/node-C/readings?limit=1000").json() if r["device_id"] == dev]
    try:
        with TestClient(app) as c:
            for _ in range(20):  # the backend subscribes asynchronously: republish until stored (dedupe keeps one)
                pub.publish("flowtrace/nodes/node-C/readings", batch, qos=1).wait_for_publish(5)
                time.sleep(0.5)
                if stored():
                    break
            time.sleep(1.0)  # let any in-flight copy land
            rows = stored()
            assert len(rows) == 1 and rows[0]["rssi"] == -61
            assert dev in [d["id"] for d in c.get("/api/v1/devices").json()]
    finally:
        pub.loop_stop()
        pub.disconnect()
