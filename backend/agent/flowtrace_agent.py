"""
flowtrace_agent.py — The FlowTrace Agentic Engine

An LLM-powered agent that:
1. Observes visitor movement data (positions, zone dwell times, journey history)
2. Generates actionable insights (UPSELL, ALERT, RECOMMENDATION, ANOMALY)
3. Triggers real-time actions (notifications, staff alerts, discounts)

Uses LangChain with tool-calling to query the database and emit actions.
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


# ─── Insight data class ────────────────────────────────────────────────────────

@dataclass
class InsightReport:
    device_id: str
    insight_type: str       # UPSELL | ALERT | RECOMMENDATION | ANOMALY | GREETING
    title: str
    message: str
    suggested_action: str
    confidence: float       # 0.0–1.0
    context: dict


# ─── Prompts ──────────────────────────────────────────────────────────────────

AURA_SYSTEM_PROMPT = """You are FLOWTRACE, the invisible intelligence layer of BlankFrame Technologies.

You analyze anonymous visitor movement data from physical venues (game zones, malls, entertainment centers) and generate real-time actionable insights for venue operators.

Your core principles:
1. **Anonymity** — Visitors are identified only by tag IDs (e.g. FLOWTRACE_TAG_042). Never infer or speculate about personal identity.
2. **Specificity** — Always cite exact numbers. "Spent 8 minutes at VR Zone", not "spent time".
3. **Actionability** — Every insight must include a concrete, immediate action.
4. **Brevity** — Insights are read on a tablet by busy staff. Be crisp.

Insight types you can generate:
- **UPSELL**: Visitor is interested but hasn't converted. Suggest promotion.
- **ALERT**: Crowd bottleneck or operational issue needs attention.
- **RECOMMENDATION**: Long-term improvement for venue layout or operations.
- **ANOMALY**: Unusual pattern (e.g. someone near the exit for 10 minutes without leaving).
- **GREETING**: A returning visitor — personalize their experience.

You have access to tools to query movement data. Use them before generating insights.
Think step by step. Be data-driven. Output structured JSON."""

USER_ANALYSIS_PROMPT = """Analyze visitor {device_id}.

Use your tools to get their:
1. Full journey (zones visited, time in each)
2. Current zone and dwell time
3. Historical visit data

Then determine:
- What is their current behavioral state? (exploring, committed, hesitating, bored, frustrated)
- What is their most likely intent right now?
- What is the optimal intervention?

Output a JSON insight with fields: insight_type, title, message, suggested_action, confidence (0.0-1.0)"""

VENUE_SUMMARY_PROMPT = """Generate a comprehensive venue intelligence report.

Use your tools to analyze:
1. Current zone occupancy across all active visitors
2. Which zones have the most traffic vs. conversion
3. Any congestion hotspots
4. Visitors who are showing hesitation signals
5. Overall session health

Output a list of JSON insights — prioritized by urgency (ALERT first, then UPSELL, then RECOMMENDATION)."""


# ─── Tool definitions (injected with data access functions) ────────────────────

def create_aura_tools(data_provider):
    """
    Factory: creates LangChain tools bound to a data provider object.
    The data_provider must implement the methods used below.
    """

    @tool
    def get_user_journey(device_id: str) -> str:
        """
        Get the complete movement journey of a visitor for their current session.
        Returns: JSON with zone_dwell_times, journey (ordered list), top_zone,
                 total_dwell_seconds, visit_count.
        Args:
            device_id: The visitor's tag ID (e.g. "FLOWTRACE_TAG_042")
        """
        try:
            data = data_provider.get_device_journey(device_id)
            return json.dumps(data, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def get_zone_stats(zone_name: str) -> str:
        """
        Get real-time statistics for a specific venue zone.
        Returns: current_occupancy, total_dwell_seconds, avg_dwell, visitor_count.
        Args:
            zone_name: e.g. "VR_ZONE", "LASER_TAG", "FOOD_COURT", "EXIT"
        """
        try:
            data = data_provider.get_zone_stats(zone_name)
            return json.dumps(data, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def get_venue_summary() -> str:
        """
        Get a high-level summary of the entire venue right now.
        Returns: active_visitors, zone_occupancy dict, busiest_zone, insights_triggered_today.
        """
        try:
            data = data_provider.get_venue_summary()
            return json.dumps(data, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def get_device_history(device_id: str) -> str:
        """
        Look up a visitor's historical visit data (previous sessions).
        Returns: total_past_visits, favorite_zone, avg_session_length_minutes, last_visit_date.
        Args:
            device_id: The visitor's tag ID
        """
        try:
            data = data_provider.get_device_history(device_id)
            return json.dumps(data, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def trigger_notification(device_id: str, message: str, action_type: str) -> str:
        """
        Trigger a real-time notification or action for a specific visitor.
        This logs the action and emits it via WebSocket to the dashboard.
        Args:
            device_id: The visitor's tag ID
            message: The message to send to staff / display
            action_type: One of: DISCOUNT | STAFF_GREETING | QUEUE_TICKET | GENERAL
        Returns: Confirmation string
        """
        try:
            result = data_provider.trigger_notification(device_id, message, action_type)
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def get_hesitation_signals() -> str:
        """
        Find all visitors currently showing hesitation signals:
        - Spent > 2 min near a zone but haven't entered
        - Visited a zone briefly (< 30s) and left multiple times
        - Standing near the exit for > 5 minutes
        Returns: list of {device_id, zone, signal_type, dwell_seconds}
        """
        try:
            data = data_provider.get_hesitation_signals()
            return json.dumps(data, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    return [
        get_user_journey,
        get_zone_stats,
        get_venue_summary,
        get_device_history,
        trigger_notification,
        get_hesitation_signals,
    ]


# ─── Main Agent class ──────────────────────────────────────────────────────────

class FlowTraceAgent:
    """
    The FlowTrace Agentic Engine.
    Wraps a LangChain tool-calling agent with FlowTrace-specific tools and prompts.
    """

    def __init__(
        self,
        data_provider,
        model: str = "gpt-4o",
        temperature: float = 0.1,
    ):
        self.data_provider = data_provider
        self.tools = create_aura_tools(data_provider)

        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            timeout=30,
        )

        # Build the prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", AURA_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # Create LangChain tool-calling agent
        agent = create_tool_calling_agent(self.llm, self.tools, self.prompt)
        self.executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            max_iterations=6,
            handle_parsing_errors=True,
            return_intermediate_steps=False,
        )

    def _parse_insight(self, raw_output: str, device_id: str) -> InsightReport:
        """Extract structured insight from agent output."""
        # Try to parse JSON from output
        try:
            # Find JSON block in output
            start = raw_output.find("{")
            end = raw_output.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw_output[start:end])
                return InsightReport(
                    device_id=device_id,
                    insight_type=data.get("insight_type", "RECOMMENDATION"),
                    title=data.get("title", "Insight"),
                    message=data.get("message", raw_output),
                    suggested_action=data.get("suggested_action", "Review data"),
                    confidence=float(data.get("confidence", 0.7)),
                    context=data.get("context", {}),
                )
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: wrap raw output
        return InsightReport(
            device_id=device_id,
            insight_type="RECOMMENDATION",
            title="FlowTrace Analysis",
            message=raw_output,
            suggested_action="Review the insight and act accordingly",
            confidence=0.6,
            context={},
        )

    def analyze_user(self, device_id: str) -> InsightReport:
        """
        Run the agent on a specific visitor.
        Returns a structured InsightReport.
        """
        logger.info(f"Running FlowTrace agent for device: {device_id}")
        start = time.time()

        try:
            result = self.executor.invoke({
                "input": USER_ANALYSIS_PROMPT.format(device_id=device_id)
            })
            output = result.get("output", "")
        except Exception as e:
            logger.error(f"Agent failed for {device_id}: {e}")
            output = f"Analysis failed: {str(e)}"

        elapsed = time.time() - start
        logger.info(f"Agent completed for {device_id} in {elapsed:.1f}s")

        insight = self._parse_insight(output, device_id)
        return insight

    def analyze_venue(self) -> list[InsightReport]:
        """
        Run the agent for whole-venue analysis.
        Returns a list of InsightReports sorted by urgency.
        """
        logger.info("Running FlowTrace venue-wide agent analysis")

        try:
            result = self.executor.invoke({"input": VENUE_SUMMARY_PROMPT})
            output = result.get("output", "")
        except Exception as e:
            logger.error(f"Venue agent failed: {e}")
            return []

        # Try to parse array of insights
        insights = []
        try:
            start = output.find("[")
            end = output.rfind("]") + 1
            if start >= 0 and end > start:
                items = json.loads(output[start:end])
                for item in items:
                    insights.append(InsightReport(
                        device_id=item.get("device_id", "VENUE"),
                        insight_type=item.get("insight_type", "RECOMMENDATION"),
                        title=item.get("title", "Venue Insight"),
                        message=item.get("message", ""),
                        suggested_action=item.get("suggested_action", ""),
                        confidence=float(item.get("confidence", 0.7)),
                        context=item.get("context", {}),
                    ))
        except (json.JSONDecodeError, ValueError, KeyError):
            # Fallback: single insight
            insights.append(self._parse_insight(output, "VENUE"))

        # Sort: ALERT > ANOMALY > UPSELL > GREETING > RECOMMENDATION
        priority = {"ALERT": 0, "ANOMALY": 1, "UPSELL": 2, "GREETING": 3, "RECOMMENDATION": 4}
        insights.sort(key=lambda i: priority.get(i.insight_type, 99))
        return insights

    def generate_greeting(self, device_id: str, visit_count: int, favorite_zone: str) -> InsightReport:
        """Generate a personalized greeting for a returning visitor."""
        prompt = f"""
Visitor {device_id} has just entered the venue.
They have visited {visit_count} times before.
Their favorite zone is {favorite_zone}.

Generate a warm, personalized GREETING insight for the staff to act on.
Output JSON with: insight_type="GREETING", title, message, suggested_action, confidence.
"""
        try:
            result = self.executor.invoke({"input": prompt})
            return self._parse_insight(result.get("output", ""), device_id)
        except Exception as e:
            return InsightReport(
                device_id=device_id,
                insight_type="GREETING",
                title="Returning Visitor",
                message=f"Returning visitor with {visit_count} past visits. Favorite: {favorite_zone}",
                suggested_action=f"Greet them and offer a loyalty benefit at {favorite_zone}",
                confidence=0.9,
                context={},
            )
