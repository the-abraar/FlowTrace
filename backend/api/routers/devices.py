from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import Device

router = APIRouter(prefix="/api/v1/devices", tags=["Devices"])

@router.get("")
def list_devices(db: Session = Depends(get_db)):
    devices = db.query(Device).filter(Device.is_active == True).all()
    return devices

@router.get("/{device_id}/journey")
def get_device_journey(device_id: str, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        return {"error": "Device not found"}
    # Mock return for MVP
    return {"device_id": device.device_id, "journey": []}
