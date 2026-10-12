"""Optional AI insights: runs FlowTraceAgent.analyze_venue() periodically, keeps the latest report.
No langchain import at module level, so core installs (requirements.txt) can import this."""
import asyncio
import dataclasses
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ZoneDataProvider:
    """Adapter giving the agent tools the data_provider interface, backed by ZoneDetector."""

    def __init__(self, zones):
        self.z = zones

    def get_device_journey(self, device_id):
        return self.z.get_device_journey(device_id)

    def get_device_history(self, device_id):
        return self.z.track_zone_dwell_time(device_id)

    def get_zone_stats(self, zone_name):
        return self.z.get_zone_stats().get(zone_name, {})

    def get_venue_summary(self):
        return self.z.get_zone_stats()

    def get_hesitation_signals(self):
        return []  # shortcut: no hesitation detector yet

    def trigger_notification(self, device_id, message, action_type):
        return {"sent": False, "reason": "notifications not implemented"}


class InsightService:
    def __init__(self, agent=None, interval_s: float = 300.0):
        self.agent, self.interval_s = agent, interval_s
        self.latest = None  # {"generated_at", "insights"}
        self._task = None

    @property
    def enabled(self) -> bool:
        return self.agent is not None

    async def run_once(self):
        reports = await asyncio.to_thread(self.agent.analyze_venue)
        self.latest = {"generated_at": datetime.now(timezone.utc).isoformat(),
                       "insights": [dataclasses.asdict(r) for r in reports]}

    async def _loop(self):
        while True:
            try:
                await self.run_once()
            except Exception as e:  # keep looping; LLM/network errors are transient
                logger.error("Insight run failed: %s", e)
            await asyncio.sleep(self.interval_s)

    def start(self):
        if self.enabled:
            self._task = asyncio.create_task(self._loop())

    def stop(self):
        if self._task:
            self._task.cancel()


def build_service(api_key: str, zones, model: str = "gpt-4o") -> InsightService:
    """Disabled service when no key or the optional deps are missing."""
    if not api_key:
        return InsightService()
    try:
        from agent.flowtrace_agent import FlowTraceAgent
        import os
        os.environ.setdefault("OPENAI_API_KEY", api_key)
        return InsightService(FlowTraceAgent(ZoneDataProvider(zones), model=model))
    except Exception as e:
        logger.warning("AI agent disabled (%s) - install requirements-agent.txt", e)
        return InsightService()
