import asyncio
import json
import logging
import paho.mqtt.client as mqtt

from config import settings
from database.session import AsyncSessionLocal
from ingestion.http_receiver import persist_reading, parse_readings
from positioning.triangulator import PositioningFleet

logger = logging.getLogger(__name__)

class MQTTServer:
    def __init__(self, broker_host: str = "localhost", broker_port: int = 1883, fleet: PositioningFleet = None):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.fleet = fleet
        self.loop = None
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="aura_backend", protocol=mqtt.MQTTv311)
        if settings.MQTT_USERNAME:
            self.client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD or None)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if not rc.is_failure:
            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            self.client.subscribe("flowtrace/nodes/+/readings")
        else:
            logger.error(f"Failed to connect, return code {rc}")

    def on_disconnect(self, client, userdata, flags, rc, properties=None):
        logger.warning("Disconnected from MQTT broker")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            parts = msg.topic.split("/")  # flowtrace/nodes/<id>/readings
            if len(parts) != 4 or not parts[2]:
                logger.warning("Unexpected MQTT topic %s", msg.topic)
                return
            self.process_reading(payload, topic_node=parts[2])
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON payload on {msg.topic}: {msg.payload}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def process_reading(self, data: dict, topic_node: str | None = None):
        # Scanner batch {"node_id", "readings": [...]} or one flat reading; parsing shared with HTTP.
        if topic_node is not None and isinstance(data, dict):
            data = {**data, "node_id": data.get("node_id") or topic_node}  # topic is the node identity
        try:
            rows = parse_readings(data)
        except ValueError as e:
            logger.warning("Bad reading payload (%s): %s", e, data)
            return
        if topic_node is not None:
            if any(r[0] != topic_node for r in rows):
                logger.warning("Node ID in payload does not match topic node %s: dropped", topic_node)
                return
        if self.fleet:
            rows = [r for r in rows if self.fleet.has_capacity(r[1])] if hasattr(self.fleet, "has_capacity") else rows
            for node_id, device_id, rssi, dt, _ in rows:
                self.fleet.ingest_reading(node_id, device_id, rssi, dt.timestamp())
        if self.loop:  # paho runs in its own thread; DB is async on the app loop
            asyncio.run_coroutine_threadsafe(self._persist(rows), self.loop)

    async def _persist(self, rows):
        unknown = set()
        async with AsyncSessionLocal() as db:
            for node_id, device_id, rssi, dt, batt in rows:
                if not await persist_reading(db, node_id, device_id, rssi, dt, batt):
                    unknown.add(node_id)
            await db.commit()
        if unknown:
            logger.warning("Dropped readings from unknown nodes: %s", sorted(unknown))

    def start(self):
        self.loop = asyncio.get_running_loop()
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Could not start MQTT client: {e}")

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
