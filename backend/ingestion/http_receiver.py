from fastapi import APIRouter, Depends, HTTPException
from auth import require_ingest
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session
from database.models import Reading, Node, Device
# In a real app we'd inject the fleet instance via dependencies. We assume access via app state or import.

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/readings", tags=["Ingestion"])

class ReadingPayload(BaseModel):
    node_id: Optional[str] = None  # may be inherited from the batch (firmware sends it once per batch)
    device_id: str
    rssi: int
    timestamp: Optional[str] = None
    battery_pct: Optional[int] = None
    batt_mv: Optional[int] = None  # firmware field; ts_ms/mac are ignored (device uptime, not wall clock)

class BatchReadingsPayload(BaseModel):
    node_id: Optional[str] = None
    readings: List[ReadingPayload]

async def persist_reading(db, node_id, device_id, rssi, dt, battery_pct=None) -> bool:
    """Insert one reading; creates the device on first sight. False if node unknown."""
    if await db.get(Node, node_id) is None:
        logger.warning("Unknown node ID: %s", node_id)
        return False
    device = await db.get(Device, device_id)
    if device is None:
        db.add(Device(id=device_id, first_seen=dt, last_seen=dt))
        await db.flush()
    else:
        device.last_seen = dt
    db.add(Reading(node_id=node_id, device_id=device_id, rssi=rssi, timestamp=dt, battery_pct=battery_pct))
    await db.flush()
    return True


def parse_readings(data) -> list[tuple]:
    """Scanner batch ({node_id, readings:[...]}) or one flat reading -> [(node_id, device_id, rssi, dt, battery_pct)].
    Raises ValueError (pydantic's is one) on bad shape or missing node_id."""
    if isinstance(data, dict) and "readings" not in data:
        data = {"readings": [data]}
    payload = BatchReadingsPayload.model_validate(data)
    out = []
    for r in payload.readings:
        node_id = r.node_id or payload.node_id
        if not node_id:
            raise ValueError("node_id missing (per reading or per batch)")
        dt = datetime.fromisoformat(r.timestamp.replace("Z", "+00:00")) if r.timestamp else datetime.now(timezone.utc)
        out.append((node_id, r.device_id, r.rssi, dt, r.battery_pct))
    return out


@router.post("", dependencies=[Depends(require_ingest)])
async def receive_readings(payload: BatchReadingsPayload, db: AsyncSession = Depends(get_session)):
    """Receive a batch of readings via HTTP POST."""
    from main import fleet  # lazy: avoids circular import

    try:
        rows = parse_readings(payload.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))
    inserted, unknown = 0, set()
    for node_id, device_id, rssi, dt, batt in rows:
        if not fleet.has_capacity(device_id):  # device cap: no Device row either
            continue
        if await persist_reading(db, node_id, device_id, rssi, dt, batt):
            fleet.ingest_reading(node_id, device_id, rssi, dt.timestamp())
            inserted += 1
        else:
            unknown.add(node_id)
    return {"status": "partial" if unknown else "ok", "inserted": inserted, "unknown_nodes": sorted(unknown)}
