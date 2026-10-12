import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/i.db"
os.environ["OPENAI_API_KEY"] = ""

import asyncio
from fastapi.testclient import TestClient
import main
from agent.service import InsightService, build_service
from positioning.zone_detector import ZoneDetector


class FakeAgent:  # stands in for the LLM-backed FlowTraceAgent
    def analyze_venue(self):
        from dataclasses import dataclass
        @dataclass
        class R:
            device_id: str = "VENUE"; insight_type: str = "ALERT"; title: str = "t"
            message: str = "m"; suggested_action: str = "a"; confidence: float = 0.9; context: dict = None
        return [R()]


def test_disabled_returns_503():
    assert not build_service("", ZoneDetector()).enabled
    with TestClient(main.app) as c:
        r = c.get("/api/v1/insights")
        assert r.status_code == 503 and "OPENAI_API_KEY" in r.json()["detail"]


def test_enabled_returns_latest_report():
    svc = InsightService(FakeAgent())
    asyncio.run(svc.run_once())
    main.insights = svc
    c = TestClient(main.app)  # no lifespan: keep our injected service
    r = c.get("/api/v1/insights")
    assert r.status_code == 200 and r.json()["insights"][0]["insight_type"] == "ALERT"
