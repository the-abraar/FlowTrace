from auth import require_read
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.session import get_session
from database.models import Device

router = APIRouter(prefix="/api/v1/devices", tags=["Devices"], dependencies=[Depends(require_read)])

@router.get("")
async def list_devices(db: AsyncSession = Depends(get_session)):
    devices = (await db.scalars(select(Device).where(Device.is_active.is_(True)))).all()
    return [{"id": d.id, "label": d.label, "first_seen": d.first_seen, "last_seen": d.last_seen} for d in devices]

@router.get("/{device_id}/journey")
async def get_device_journey(device_id: str, db: AsyncSession = Depends(get_session)):
    if await db.get(Device, device_id) is None:
        return {"error": "Device not found"}
    # Mock return for MVP
    return {"device_id": device_id, "journey": []}
