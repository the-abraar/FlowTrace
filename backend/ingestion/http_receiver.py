from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import logging
from sqlalchemy.orm import Session
import time

from database.session import get_db
from database.models import Reading, Node, Device
# In a real app we'd inject the fleet instance via dependencies. We assume access via app state or import.

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/readings", tags=["Ingestion"])

class ReadingPayload(BaseModel):
    node_id: str
    device_id: str
    rssi: int
    timestamp: Optional[str] = None
    battery_pct: Optional[int] = None
    _true_x: Optional[float] = None  # for simulation
    _true_y: Optional[float] = None

class BatchReadingsPayload(BaseModel):
    readings: List[ReadingPayload]

@router.post("")
async def receive_readings(payload: BatchReadingsPayload, db: Session = Depends(get_db)):
    """Receive a batch of readings via HTTP POST."""
    
    # We will grab the fleet from the app state in main.py but for now just log
    from main import fleet # Lazy import to avoid circular dependency
    
    now = datetime.now(timezone.utc)
    
    # Cache to avoid repeated DB lookups in the same batch
    node_cache = {}
    device_cache = {}
    
    records = []
    for r in payload.readings:
        # Pass to fleet for real-time positioning
        ts = datetime.fromisoformat(r.timestamp.replace('Z', '+00:00')).timestamp() if r.timestamp else time.time()
        if fleet:
            fleet.ingest_reading(r.node_id, r.device_id, r.rssi, ts)
            
        # DB persistence logic
        node_id_str = r.node_id
        if node_id_str not in node_cache:
            node = db.query(Node).filter(Node.node_id == node_id_str).first()
            if node:
                node_cache[node_id_str] = node.id
            else:
                continue # Unknown node
                
        device_id_str = r.device_id
        if device_id_str not in device_cache:
            device = db.query(Device).filter(Device.device_id == device_id_str).first()
            if not device:
                device = Device(device_id=device_id_str, first_seen=now, last_seen=now)
                db.add(device)
                db.commit()
                db.refresh(device)
            else:
                device.last_seen = now
            device_cache[device_id_str] = device.id
            
        dt = datetime.fromisoformat(r.timestamp.replace('Z', '+00:00')) if r.timestamp else now
        records.append(Reading(
            node_id=node_cache[node_id_str],
            device_id=device_cache[device_id_str],
            rssi=r.rssi,
            timestamp=dt,
            battery_pct=r.battery_pct
        ))
        
    if records:
        db.add_all(records)
        db.commit()
        
    return {"status": "ok", "inserted": len(records)}
