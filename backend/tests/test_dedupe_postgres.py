"""Reading dedupe on Postgres. The live test needs a server and asyncpg:
PG_TEST_URL=postgresql+asyncpg://user:pw@host/db pytest tests/test_dedupe_postgres.py"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.dialects import postgresql

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingestion.http_receiver import persist_reading, reading_insert


def test_postgres_insert_skips_conflicts():
    stmt = reading_insert("postgresql", node_id="n", device_id="d", rssi=-50, ts_ms=7)
    assert "ON CONFLICT DO NOTHING" in str(stmt.compile(dialect=postgresql.dialect()))
    with pytest.raises(NotImplementedError):
        reading_insert("mysql", node_id="n")


@pytest.mark.skipif(not os.getenv("PG_TEST_URL"), reason="PG_TEST_URL not set")
def test_dedupe_on_live_postgres():
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from database.models import Base, Node

    async def run():
        engine = create_async_engine(os.environ["PG_TEST_URL"])
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with AsyncSession(engine) as db:  # rolled back at the end: leaves no rows
            node, dev, now = f"pg-{uuid.uuid4().hex[:8]}", f"D-{uuid.uuid4().hex[:8]}", datetime.now(timezone.utc)
            db.add(Node(id=node, name=node))
            await db.flush()
            assert await persist_reading(db, node, dev, -50, now, ts_ms=7) == "ok"
            assert await persist_reading(db, node, dev, -51, now, ts_ms=7) == "duplicate"
            assert await persist_reading(db, node, dev, -52, now, ts_ms=8) == "ok"
            assert await persist_reading(db, node, dev, -53, now) == "ok"  # no ts_ms: never deduped
            assert await persist_reading(db, node, dev, -53, now) == "ok"
            await db.rollback()
        await engine.dispose()

    asyncio.run(run())
