from fastapi import Depends
from auth import require_read
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"], dependencies=[Depends(require_read)])

@router.get("/zones")
def get_zones():
    # zone layout the detector actually uses (read auth via the router dependency); the dashboard draws these
    from main import zone_analytics
    return [{"name": z.name, "label": z.label, "color": z.color, "polygon": z.polygon} for z in zone_analytics._zones]

@router.get("/summary")
def get_venue_summary():
    from config import settings
    from main import zone_analytics
    zones = zone_analytics.get_zone_stats()
    return {"zones": zones, "bounce_rate": zone_analytics.bounce_rate(), "ab_test": ab_split(zones, settings.AB_TEST_ZONES)}


def ab_split(zones: dict[str, dict], pair: str) -> dict | None:
    """Visit share of two zones (named in *pair* 'A,B', else the two most-visited); None until either has visits."""
    names = [n.strip() for n in pair.split(",") if n.strip()]
    if not names:
        names = sorted(zones, key=lambda n: zones[n]["total_visits"], reverse=True)[:2]
    if len(names) != 2 or not all(n in zones for n in names):
        return None  # misconfigured AB_TEST_ZONES shows n/a rather than a split of zones nobody chose
    a, b = (zones[n]["total_visits"] for n in names)
    if a + b == 0:
        return None
    return {"a": zones[names[0]]["label"], "b": zones[names[1]]["label"], "a_share": round(a / (a + b), 3), "b_share": round(b / (a + b), 3)}
