import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from database.models import AgentInsight, Base, Device, Reading
from database.retention import purge_stale_devices
from positioning.triangulator import PositionEngine, rssi_to_distance


def test_purge_stale_devices():
    async def run():
        eng = create_async_engine(f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/p.db")
        async with eng.begin() as c:
            await c.run_sync(Base.metadata.create_all)
        now = datetime.now(timezone.utc)
        async with async_sessionmaker(eng)() as db:
            db.add_all([Device(id="old", last_seen=now - timedelta(days=31)), Device(id="new", last_seen=now - timedelta(days=1))])
            await db.flush()
            db.add_all([Reading(node_id="n", device_id=d, rssi=-60, timestamp=now) for d in ("old", "new")]
                       + [AgentInsight(device_id="old", insight_type="ALERT", message="m")])
            await db.commit()
            assert await purge_stale_devices(db, 30) == 1
            await db.commit()
            assert (await db.scalars(select(Device.id))).all() == ["new"]
            assert (await db.scalars(select(Reading.device_id))).all() == ["new"]
            assert (await db.scalars(select(AgentInsight.device_id))).all() == [None]  # insight kept, link cleared
        await eng.dispose()
    asyncio.run(run())


def test_position_engine_uses_calibration(tmp_path, monkeypatch):
    cal = tmp_path / "cal.json"
    cal.write_text(json.dumps({"a": {"tx_power": -40, "n": 2}}))
    monkeypatch.setenv("RSSI_CALIBRATION_JSON", str(cal))
    e = PositionEngine()  # same default construction as the module-level position_engine
    assert e.distance("a", -60) == pytest.approx(10.0)
    assert e.distance("b", -60) == rssi_to_distance(-60)  # uncalibrated node: settings defaults
