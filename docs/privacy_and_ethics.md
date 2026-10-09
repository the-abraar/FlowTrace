# Privacy & Ethics Framework

Project FlowTrace is designed with **Privacy by Default**. Tracking physical movement requires strict ethical boundaries to maintain user trust and comply with local data protection laws.

## Core Principles

1.  **Passive Anonymity ("Shadow Profiles")**
    *   We track *devices*, not *identities*. A BLE wristband or phone MAC address is recorded as a generic ID (e.g., `Shadow_742`).
    *   We DO NOT collect names, phone numbers, or emails unless the user explicitly opts in via a loyalty program.

2.  **No Persistent Cross-Venue Tracking**
    *   MAC addresses from smartphones are hashed with a daily rotating salt. A user visiting on Monday cannot be linked to their visit on Wednesday without their consent.

3.  **Data Minimization**
    *   We only store the data needed to generate the insight. Once a session ends, raw RSSI readings are aggregated into high-level metrics (e.g., "spent 5 mins in VR zone") and the raw tracking data is purged after 30 days.

## Compliance
*   Venue operators must display clear signage at entry points indicating that anonymous foot-traffic analytics are in use to improve the experience.
*   Staff handling the "Agentic Action" tablets must be trained not to assume personal knowledge of a visitor unless they are a registered loyalty member.
