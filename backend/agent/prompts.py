"""
agent/prompts.py
────────────────
All LangChain prompt templates used by the FlowTrace AI agent.

Templates
─────────
- SYSTEM_PROMPT          — base identity/persona for the agent
- USER_JOURNEY_PROMPT    — single-user behavioural analysis
- VENUE_SUMMARY_PROMPT   — whole-venue aggregate analysis
- CROWD_CONTROL_PROMPT   — congestion / intervention prompt
"""

from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate

# ──────────────────────────────────────────────────────────────────────────────
# System / Persona
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are FlowTrace, an invisible venue intelligence system embedded in a BLE-based \
local positioning platform. You analyse visitor movement data in real time and generate \
actionable insights for venue managers.

Your principles:
- Be specific and data-driven — always reference exact zone names, dwell times, and device IDs.
- Suggest real-time interventions that staff can act on immediately.
- Classify every insight as one of: UPSELL, ALERT, RECOMMENDATION, ANOMALY, QUEUE_ABANDONMENT, BOUNCE_RATE, or A_B_LAYOUT_TEST.
- Trigger QUEUE_ABANDONMENT if a visitor dwells near an attraction for a long time but leaves without entering the 'active' zone.
- Trigger BOUNCE_RATE if a visitor enters a pop-up zone and leaves in under 60 seconds.
- Trigger A_B_LAYOUT_TEST to compare traffic and dwell times between two distinct layout areas (e.g. "Front Table" vs "Back Wall").
- Keep messages concise (≤ 3 sentences) unless instructed otherwise.
- Never fabricate data — if information is unavailable, say so explicitly.
- Output structured JSON when a schema is requested.

Current venue: {venue_name}
Current UTC time: {current_time}
"""

# ──────────────────────────────────────────────────────────────────────────────
# Individual user journey analysis
# ──────────────────────────────────────────────────────────────────────────────

USER_JOURNEY_PROMPT_TEMPLATE = """Analyse the following visitor journey and generate an insight.

Device ID: {device_id}
Session start: {session_start}
Time in venue: {time_in_venue_minutes:.1f} minutes

Zone visit history:
{zone_history}

Zone dwell totals (seconds):
{dwell_totals}

Current zone: {current_zone}

Based on this data:
1. Identify the visitor's likely interest or behaviour pattern.
2. Decide the best insight type (UPSELL / ALERT / RECOMMENDATION / ANOMALY / QUEUE_ABANDONMENT / BOUNCE_RATE / A_B_LAYOUT_TEST).
3. Suggest a concrete action the venue team should take right now.

Return a JSON object with this exact schema:
{{
  "device_id": "{device_id}",
  "insight_type": "<UPSELL|ALERT|RECOMMENDATION|ANOMALY|QUEUE_ABANDONMENT|BOUNCE_RATE|A_B_LAYOUT_TEST>",
  "message": "<concise insight text>",
  "confidence": <0.0–1.0>,
  "suggested_action": "<actionable step for staff>"
}}
"""

USER_JOURNEY_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
        ("human", USER_JOURNEY_PROMPT_TEMPLATE),
    ]
)

# ──────────────────────────────────────────────────────────────────────────────
# Venue-wide summary analysis
# ──────────────────────────────────────────────────────────────────────────────

VENUE_SUMMARY_PROMPT_TEMPLATE = """Analyse the following venue-wide statistics and generate a summary insight.

Total active devices: {total_devices}
Average time in venue: {avg_time_minutes:.1f} minutes

Zone occupancy right now:
{zone_occupancy}

Top dwell zones (by average dwell time):
{top_dwell_zones}

Recent anomalies (last 30 minutes):
{recent_anomalies}

Based on this snapshot:
1. Identify the most important issue or opportunity for the venue manager.
2. Suggest one immediate operational action.

Return a JSON object:
{{
  "insight_type": "<UPSELL|ALERT|RECOMMENDATION|ANOMALY|QUEUE_ABANDONMENT|BOUNCE_RATE|A_B_LAYOUT_TEST>",
  "message": "<concise insight text>",
  "confidence": <0.0–1.0>,
  "suggested_action": "<actionable step for staff>"
}}
"""

VENUE_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
        ("human", VENUE_SUMMARY_PROMPT_TEMPLATE),
    ]
)

# ──────────────────────────────────────────────────────────────────────────────
# Crowd control / congestion prompt
# ──────────────────────────────────────────────────────────────────────────────

CROWD_CONTROL_PROMPT_TEMPLATE = """A congestion event has been detected.

Zone: {zone_name} ({zone_label})
Current occupancy: {occupancy} devices
Occupancy threshold: {threshold} devices
Average dwell time in zone: {avg_dwell:.1f} seconds

Suggest an immediate intervention to reduce congestion and improve visitor flow.

Return a JSON object:
{{
  "insight_type": "ALERT",
  "message": "<concise alert text>",
  "confidence": <0.0–1.0>,
  "suggested_action": "<specific crowd-control action for staff>"
}}
"""

CROWD_CONTROL_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
        ("human", CROWD_CONTROL_PROMPT_TEMPLATE),
    ]
)
