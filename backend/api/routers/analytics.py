from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])

@router.get("/summary")
def get_venue_summary():
    # In a real app we query the VenueZoneAnalytics global
    from main import zone_analytics
    return {
        "heatmap": zone_analytics.get_heatmap_data(),
        "occupancy": zone_analytics.get_current_occupancy()
    }
