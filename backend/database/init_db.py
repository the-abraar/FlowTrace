"""
database/init_db.py
───────────────────
Initialises the SQLite database — creates all tables and seeds a set of
test BLE scanner nodes arranged around a 10 m × 10 m demo room.

Usage (standalone)::

    python -m backend.database.init_db

or called from application startup::

    from backend.database.init_db import init_db
    await init_db()
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database.models import Base, Node
from backend.database.session import AsyncSessionLocal, engine

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Seed data — 9 nodes covering a 10 m × 10 m room in a 3 × 3 grid
# ──────────────────────────────────────────────────────────────────────────────

SEED_NODES: list[dict] = [
    # Corners
    {"id": "node-NW", "name": "Node North-West",  "x_pos": 0.0,  "y_pos": 10.0, "floor": 0},
    {"id": "node-NE", "name": "Node North-East",  "x_pos": 10.0, "y_pos": 10.0, "floor": 0},
    {"id": "node-SE", "name": "Node South-East",  "x_pos": 10.0, "y_pos": 0.0,  "floor": 0},
    {"id": "node-SW", "name": "Node South-West",  "x_pos": 0.0,  "y_pos": 0.0,  "floor": 0},
    # Edge midpoints
    {"id": "node-N",  "name": "Node North-Mid",   "x_pos": 5.0,  "y_pos": 10.0, "floor": 0},
    {"id": "node-S",  "name": "Node South-Mid",   "x_pos": 5.0,  "y_pos": 0.0,  "floor": 0},
    {"id": "node-E",  "name": "Node East-Mid",    "x_pos": 10.0, "y_pos": 5.0,  "floor": 0},
    {"id": "node-W",  "name": "Node West-Mid",    "x_pos": 0.0,  "y_pos": 5.0,  "floor": 0},
    # Centre
    {"id": "node-C",  "name": "Node Centre",      "x_pos": 5.0,  "y_pos": 5.0,  "floor": 0},
]


async def _seed_nodes(session: AsyncSession) -> None:
    """Insert seed nodes if they do not already exist."""
    for data in SEED_NODES:
        result = await session.execute(select(Node).where(Node.id == data["id"]))
        existing = result.scalar_one_or_none()
        if existing is None:
            node = Node(
                id=data["id"],
                name=data["name"],
                x_pos=data["x_pos"],
                y_pos=data["y_pos"],
                floor=data["floor"],
                venue_id=settings.VENUE_ID,
                active=True,
                created_at=datetime.utcnow(),
            )
            session.add(node)
            logger.info("Seeded node: %s @ (%.1f, %.1f)", node.id, node.x_pos, node.y_pos)
        else:
            logger.debug("Node %s already exists — skipping.", data["id"])

    await session.commit()


async def init_db() -> None:
    """
    Create all database tables and seed demo data.

    Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS semantics
    and skips rows that already exist.
    """
    logger.info("Initialising database at: %s", settings.DATABASE_URL)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("All tables created / verified.")

    # Seed nodes
    async with AsyncSessionLocal() as session:
        await _seed_nodes(session)

    logger.info("Database initialisation complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(init_db())
