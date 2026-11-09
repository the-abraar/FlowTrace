"""scripts/simulate.py must post data the backend accepts: seeded node IDs, X-API-Key, and fail loudly otherwise."""
import asyncio
import importlib.util
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.init_db import SEED_NODES, init_db
from main import app

_spec = importlib.util.spec_from_file_location(
    "simulate", os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "simulate.py"))
sim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sim)


def _client(**headers):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", headers=headers)


def test_nodes_match_seed():
    assert sim.NODES == {n["id"]: {"x": n["x_pos"], "y": n["y_pos"]} for n in SEED_NODES}


def test_api_key_header_from_env(monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "k1")
    assert sim.auth_headers() == {"X-API-Key": "k1"}
    monkeypatch.delenv("INGEST_API_KEY")
    assert sim.auth_headers() == {}


def test_one_tick_lists_devices():
    async def run():
        await init_db()
        user = sim.SimulatedUser("SIM_TAG_001")
        async with _client(**sim.auth_headers()) as c:
            await sim.post_readings(c, "", user.get_readings())
            ids = {d["id"] for d in (await c.get("/api/v1/devices")).json()}
        assert "SIM_TAG_001" in ids
    asyncio.run(run())


def test_rejected_and_partial_are_errors():
    async def run():
        await init_db()
        reading = sim.SimulatedUser("SIM_TAG_002").get_readings()[0]
        async with _client(**{"X-API-Key": "wrong"}) as c:
            with pytest.raises(sim.SimulatorError, match="401"):
                await sim.post_readings(c, "", [reading])
        async with _client(**sim.auth_headers()) as c:
            with pytest.raises(sim.SimulatorError, match="NODE_X"):
                await sim.post_readings(c, "", [dict(reading, node_id="NODE_X")])
    asyncio.run(run())
