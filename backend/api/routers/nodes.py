from auth import require_read
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.session import get_session
from database.models import Node, Reading

router = APIRouter(prefix="/api/v1/nodes", tags=["Nodes"], dependencies=[Depends(require_read)])

@router.get("")
async def list_nodes(db: AsyncSession = Depends(get_session)):
    return [n.to_dict() for n in (await db.scalars(select(Node))).all()]

@router.get("/{node_id}/readings")
async def get_node_readings(node_id: str, limit: int = Query(50, ge=1, le=1000), db: AsyncSession = Depends(get_session)):
    if await db.get(Node, node_id) is None:
        return {"error": "Node not found"}
    q = select(Reading).where(Reading.node_id == node_id).order_by(Reading.id.desc()).limit(limit)
    return [{"device_id": r.device_id, "rssi": r.rssi, "timestamp": r.timestamp} for r in (await db.scalars(q)).all()]
