import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import logging
from config import settings
from auth import require_read, ws_allowed, warn_if_open

from database.init_db import init_db, SEED_NODES
from positioning.triangulator import PositioningFleet
from positioning.zone_detector import ZoneDetector
from ingestion.mqtt_server import MQTTServer
from api.routers import nodes, devices, analytics
from ingestion import http_receiver
from agent.service import InsightService, build_service

logger = logging.getLogger(__name__)

# Global state instances
fleet = PositioningFleet(
    bounds=(settings.VENUE_WIDTH_M, settings.VENUE_HEIGHT_M) if settings.VENUE_WIDTH_M and settings.VENUE_HEIGHT_M else None)
zone_analytics = ZoneDetector()
mqtt_server = None
insights = InsightService()  # replaced in lifespan if OPENAI_API_KEY is set
active_websockets = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting FlowTrace Backend...")
    warn_if_open()
    # Initialize DB tables if they don't exist
    await init_db()  # tables + seed nodes
    
    # Configure Fleet with dummy/db node positions
    # In a real app we'd load this from DB
    fleet.configure_nodes([{"node_id": n["id"], "x": n["x_pos"], "y": n["y_pos"]} for n in SEED_NODES])
    
    # Start MQTT server
    mqtt_broker = os.getenv("MQTT_BROKER_HOST", "localhost")
    port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    global mqtt_server
    mqtt_server = MQTTServer(broker_host=mqtt_broker, broker_port=port, fleet=fleet)
    mqtt_server.start()
    
    # Background task for position engine
    task = asyncio.create_task(position_loop())
    global insights
    insights = build_service(settings.OPENAI_API_KEY, zone_analytics, settings.OPENAI_MODEL)
    insights.start()
    
    yield
    
    # Shutdown
    logger.info("Shutting down FlowTrace Backend...")
    task.cancel()
    insights.stop()
    if mqtt_server:
        mqtt_server.stop()

async def position_loop():
    while True:
        try:
            fleet.evict_idle()
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
                        "zone": zone_analytics.update(device_id, pos.x, pos.y)
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
    if not ws_allowed(websocket):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep the socket open; client messages are ignored
    except WebSocketDisconnect:
        active_websockets.remove(websocket)

@app.get("/api/v1/insights", dependencies=[Depends(require_read)])
def get_insights():
    if not insights.enabled:
        raise HTTPException(503, "AI insights disabled: set OPENAI_API_KEY and install requirements-agent.txt")
    if insights.latest is None:
        raise HTTPException(503, "AI insights enabled but first report not generated yet")
    return insights.latest

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}
