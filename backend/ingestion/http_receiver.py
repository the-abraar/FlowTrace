from fastapi import APIRouter, Depends, HTTPException
from auth import require_ingest
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import logging
from sqlalchemy.dialects import postgresql, sqlite
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
    batt_mv: Optional[int] = None  # firmware field; mac is ignored
    ts_ms: Optional[int] = None  # node uptime (millis()), not wall clock: used only as the dedupe key

class BatchReadingsPayload(BaseModel):
    node_id: Optional[str] = None
    readings: List[ReadingPayload]

async def persist_reading(db, node_id, device_id, rssi, dt, battery_pct=None, ts_ms=None) -> str:
    """Insert one reading; creates the device on first sight. Returns "ok", "duplicate" (same node, device, ts_ms
    already stored: a retried batch) or "unknown" (node not registered)."""
    if await db.get(Node, node_id) is None:
        logger.warning("Unknown node ID: %s", node_id)
        return "unknown"
    device = await db.get(Device, device_id)
    if device is None:
        db.add(Device(id=device_id, first_seen=dt, last_seen=dt))
        await db.flush()
    else:
        device.last_seen = dt
    res = await db.execute(reading_insert(db.get_bind().dialect.name, node_id=node_id, device_id=device_id, rssi=rssi,
                                          timestamp=dt, battery_pct=battery_pct, ts_ms=ts_ms))
    return "ok" if res.rowcount else "duplicate"


# Dialects whose INSERT has ON CONFLICT DO NOTHING; the conflict is uq_reading_node_device_ts (NULL ts_ms never collides)
_INSERT = {"sqlite": sqlite.insert, "postgresql": postgresql.insert}


def reading_insert(dialect: str, **values):
    if dialect not in _INSERT:
        raise NotImplementedError(f"reading dedupe needs ON CONFLICT DO NOTHING; no support for {dialect!r}")
    return _INSERT[dialect](Reading).values(**values).on_conflict_do_nothing()


def parse_readings(data) -> list[tuple]:
    """Scanner batch ({node_id, readings:[...]}) or one flat reading -> [(node_id, device_id, rssi, dt, battery_pct, ts_ms)].
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
        out.append((node_id, r.device_id, r.rssi, dt, r.battery_pct, r.ts_ms))
    return out


@router.post("", dependencies=[Depends(require_ingest)])
async def receive_readings(payload: BatchReadingsPayload, db: AsyncSession = Depends(get_session)):
    """Receive a batch of readings via HTTP POST."""
    from main import fleet  # lazy: avoids circular import

    try:
        rows = parse_readings(payload.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))
    inserted, duplicates, unknown = 0, 0, set()
    for node_id, device_id, rssi, dt, batt, ts_ms in rows:
        if not fleet.has_capacity(device_id):  # device cap: no Device row either
            continue
        status = await persist_reading(db, node_id, device_id, rssi, dt, batt, ts_ms)
        if status == "ok":
            fleet.ingest_reading(node_id, device_id, rssi, dt.timestamp())
            inserted += 1
        elif status == "duplicate":
            duplicates += 1
        else:
            unknown.add(node_id)
    return {"status": "partial" if unknown else "ok", "inserted": inserted, "duplicates": duplicates,
            "unknown_nodes": sorted(unknown)}
