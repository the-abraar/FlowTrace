"""Delete Device rows not seen for a while, with everything keyed to them (privacy and DB growth)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update

from database.models import AgentInsight, Device, Position, Reading, UserSession


async def purge_stale_devices(db, max_age_days: float) -> int:
    """Delete devices whose last_seen is older than max_age_days; returns how many. Caller commits."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    stale = select(Device.id).where(Device.last_seen < cutoff)
    # Bulk deletes skip ORM cascades and SQLite FKs are off, so children are handled explicitly.
    sessions = select(UserSession.id).where(UserSession.device_id.in_(stale))
    await db.execute(update(AgentInsight).where(AgentInsight.session_id.in_(sessions)).values(session_id=None))
    await db.execute(update(AgentInsight).where(AgentInsight.device_id.in_(stale)).values(device_id=None))
    for model in (Reading, Position, UserSession):
        await db.execute(delete(model).where(model.device_id.in_(stale)))
    return (await db.execute(delete(Device).where(Device.last_seen < cutoff))).rowcount
