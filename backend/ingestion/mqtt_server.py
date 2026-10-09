import asyncio
import json
import logging
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
from sqlalchemy.orm import Session

from database.session import SessionLocal
from database.models import Reading, Node, Device
from positioning.triangulator import PositioningFleet

logger = logging.getLogger(__name__)

class MQTTServer:
    def __init__(self, broker_host: str = "localhost", broker_port: int = 1883, fleet: PositioningFleet = None):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.fleet = fleet
        self.client = mqtt.Client(client_id="aura_backend", protocol=mqtt.MQTTv311)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            self.client.subscribe("flowtrace/nodes/+/readings")
        else:
            logger.error(f"Failed to connect, return code {rc}")

    def on_disconnect(self, client, userdata, rc):
        logger.warning("Disconnected from MQTT broker")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            self.process_reading(payload)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON payload on {msg.topic}: {msg.payload}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def process_reading(self, data: dict):
        # Expected format: {"node_id": "NODE_A", "device_id": "TAG_1", "rssi": -65, "timestamp": "...", "battery_pct": 95}
        node_id_str = data.get("node_id")
        device_id_str = data.get("device_id")
        rssi = data.get("rssi")
        
        if not all([node_id_str, device_id_str, rssi]):
            logger.warning(f"Incomplete reading data: {data}")
            return
            
        timestamp_str = data.get("timestamp")
        try:
            if timestamp_str:
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                dt = datetime.now(timezone.utc)
        except ValueError:
            dt = datetime.now(timezone.utc)
            
        if self.fleet:
            self.fleet.ingest_reading(node_id_str, device_id_str, rssi, dt.timestamp())

        with SessionLocal() as db:
            node = db.query(Node).filter(Node.node_id == node_id_str).first()
            if not node:
                # Optionally auto-create node or ignore
                logger.warning(f"Unknown node ID: {node_id_str}")
                return
                
            device = db.query(Device).filter(Device.device_id == device_id_str).first()
            if not device:
                device = Device(device_id=device_id_str, first_seen=dt, last_seen=dt)
                db.add(device)
                db.commit()
                db.refresh(device)
            else:
                device.last_seen = dt
                
            reading = Reading(
                node_id=node.id,
                device_id=device.id,
                rssi=rssi,
                timestamp=dt,
                battery_pct=data.get("battery_pct")
            )
            db.add(reading)
            db.commit()

    def start(self):
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Could not start MQTT client: {e}")

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
