import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import logging

from database.session import engine
from database.models import Base
from positioning.triangulator import PositioningFleet
from positioning.zone_detector import VenueZoneAnalytics
from ingestion.mqtt_server import MQTTServer
from api.routers import nodes, devices, analytics
from ingestion import http_receiver

logger = logging.getLogger(__name__)

# Global state instances
fleet = PositioningFleet()
zone_analytics = VenueZoneAnalytics()
mqtt_server = None
active_websockets = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting FlowTrace Backend...")
    # Initialize DB tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    # Configure Fleet with dummy/db node positions
    # In a real app we'd load this from DB
    fleet.configure_nodes([
        {"node_id": "NODE_A", "x": 0.5, "y": 0.5},
        {"node_id": "NODE_B", "x": 9.5, "y": 0.5},
        {"node_id": "NODE_C", "x": 5.0, "y": 9.5},
        {"node_id": "NODE_D", "x": 0.5, "y": 9.5},
        {"node_id": "NODE_E", "x": 9.5, "y": 9.5},
    ])
    
    # Start MQTT server
    mqtt_broker = os.getenv("MQTT_BROKER_HOST", "localhost")
    port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    global mqtt_server
    mqtt_server = MQTTServer(broker_host=mqtt_broker, broker_port=port, fleet=fleet)
    mqtt_server.start()
    
    # Background task for position engine
    task = asyncio.create_task(position_loop())
    
    yield
    
    # Shutdown
    logger.info("Shutting down FlowTrace Backend...")
    task.cancel()
    if mqtt_server:
        mqtt_server.stop()

async def position_loop():
    while True:
        try:
            positions = fleet.get_all_positions()
            
            # Send updates to WS clients
            update_msg = {"type": "positions", "data": []}
            for device_id, pos in positions.items():
                if pos:
                    update_msg["data"].append({
                        "device_id": device_id,
                        "x": pos.x,
                        "y": pos.y,
                        "confidence": pos.confidence,
                        "zone": zone_analytics.update_device(device_id, pos.x, pos.y)
                    })
            
            if update_msg["data"]:
                for ws in active_websockets:
                    await ws.send_json(update_msg)
        except Exception as e:
            logger.error(f"Error in position loop: {e}")
            
        await asyncio.sleep(2.0)

app = FastAPI(title="FlowTrace Backend API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(http_receiver.router)
app.include_router(nodes.router)
app.include_router(devices.router)
app.include_router(analytics.router)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        active_websockets.remove(websocket)

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}
