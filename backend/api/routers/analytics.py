from fastapi import Depends
from auth import require_read
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"], dependencies=[Depends(require_read)])

@router.get("/summary")
def get_venue_summary():
    # In a real app we query the ZoneDetector global
    from main import zone_analytics
    return {
        "zones": zone_analytics.get_zone_stats()
    }
