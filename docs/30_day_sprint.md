# Project FlowTrace — 30-Day Sprint Plan
**BlankFrame Technologies** | Internal Execution Document  
**Sprint Start:** TBD | **Target Demo Date:** Day 30

---

## Overview

This sprint takes Project FlowTrace from zero hardware to a live, demoable Local Positioning System with an Agentic Analytics Engine. The sprint is divided into three phases:

| Phase | Days | Focus | Exit Criteria |
|-------|------|-------|---------------|
| **Phase 1: Sensing Layer** | 1–10 | Hardware, firmware, RSSI calibration, physical deployment | ≥80% accuracy in 5-node room test |
| **Phase 2: Software Layer** | 11–20 | Backend, triangulation, Shadow Profiles, LLM agent, dashboard | End-to-end pipeline working with real data |
| **Phase 3: Demo Prep** | 21–30 | Polish, stress test, pitch deck, recorded demo | Investor-ready live demo + video |

> [!IMPORTANT]
> Each day has a **hard deliverable**. If a deliverable is missed, block the next morning to recover before moving on. Do not skip calibration days — bad RSSI data poisons every layer above it.

---

## Phase 1: Sensing Layer (Days 1–10)

### Day 1 — Hardware Unboxing, Firmware Flash, BLE Scan Verification

**Goal:** Every ESP32 unit is flashed, powered, and scanning BLE advertisements.

**Morning (3h)**
- Unbox all ESP32 DevKit v1 units (minimum 5 scanner nodes + 10 beacon tags)
- Install toolchain on dev machine:
  ```bash
  # Install PlatformIO (recommended over Arduino IDE for this project)
  pip install platformio

  # Verify
  pio --version
  # Expected: PlatformIO Core 6.x.x
  ```
- Clone the FlowTrace firmware repository:
  ```bash
  git clone https://github.com/blankframe/flowtrace-firmware
  cd flowtrace-firmware
  ```

**Afternoon (4h)**
- Flash the `scanner_node` firmware to 5 ESP32 DevKit v1 units:
  ```bash
  pio run -e scanner_node -t upload --upload-port /dev/ttyUSB0
  ```
- Flash the `beacon_tag` firmware to 10 ESP32 WROOM-32 units:
  ```bash
  pio run -e beacon_tag -t upload --upload-port /dev/ttyUSB1
  ```
- Open serial monitor and confirm BLE scan output:
  ```
  [FLOWTRACE] Node ID: NODE_001 | MAC: AA:BB:CC:DD:EE:FF
  [SCAN] TAG_001 | RSSI: -62 dBm | Timestamp: 1728432000
  [SCAN] TAG_002 | RSSI: -78 dBm | Timestamp: 1728432001
  ```

**Evening (1h)**
- Label all hardware with masking tape + permanent marker (NODE_001–005, TAG_001–010)
- Charge all LiPo batteries via TP4056 modules
- Commit firmware version to git, tag as `v0.1.0-day1`

**Deliverable:** Serial output on all 5 nodes showing active BLE scans. Screenshot saved to `/docs/evidence/day01_scan_output.png`.

---

### Days 2–3 — RSSI-to-Distance Calibration

**Goal:** Establish a reliable distance estimation model for the specific venue environment (or office stand-in).

**Day 2 Morning — Reference Measurement**

Set up a straight-line test corridor (minimum 10 meters, unobstructed):

```
[NODE] ←──1m──→ [TAG] ←──1m──→ ... ←──1m──→ [10m mark]
```

At each 1-meter interval (1m, 2m, 3m, 4m, 5m, 6m, 7m, 8m, 9m, 10m), record **200 RSSI samples** from each node. This takes approximately 3–4 minutes per distance point.

Log format (CSV):
```
distance_m,node_id,tag_id,rssi_dbm,timestamp_unix
1.0,NODE_001,TAG_001,-42,1728432100
1.0,NODE_001,TAG_001,-44,1728432101
...
```

**Day 2 Afternoon — Model Fitting**

Apply the **Log-Distance Path Loss Model**:

```
RSSI(d) = TxPower - 10 * n * log10(d)
```

Where:
- `TxPower` = RSSI measured at exactly 1 meter (your empirical reference)
- `n` = Path Loss Exponent (2.0 for free space; 2.5–3.5 for indoor; 3.5–4.5 for obstructed)
- `d` = distance in meters

Run the curve-fitting script:
```bash
cd flowtrace-tools/calibration
python fit_path_loss.py \
  --input ../../data/calibration/day02_raw.csv \
  --output ../../data/calibration/day02_model.json
```

Expected output:
```json
{
  "tx_power_dbm": -42,
  "path_loss_exponent": 2.8,
  "r_squared": 0.91,
  "environment": "office_open_plan",
  "date": "2026-10-10"
}
```

**Day 3 — Environmental Variation Tests**

Repeat measurements in 3 different sub-environments within the office:
1. **Open corridor** (baseline, Day 2)
2. **Through one glass partition wall** (expect n ≈ 3.2)
3. **Through metal shelving / server rack** (expect n ≈ 4.0+)

Record a separate model JSON for each condition. The software layer will use the worst-case model for conservative distance estimates.

> [!WARNING]
> Human bodies absorb ~3–6 dB of BLE signal at 2.4 GHz. All calibration measurements must be done with a person holding the tag in a natural carrying position (chest height, pocket, wristband). Do not tape the tag to a tripod — it will give non-representative readings.

**Deliverable:** `/data/calibration/day03_models.json` with 3 environment profiles. R² > 0.85 for each.

---

### Days 4–5 — 3-Node Triangulation Test in Office

**Goal:** Triangulate a tag's position using 3 nodes and compare to known ground truth.

**Day 4 — Physical Setup**

Place 3 scanner nodes in an equilateral triangle configuration. For a 6m × 6m test area:

```
         NODE_001
           [N1]
          /     \
       6m/       \6m
        /    TAG   \
     [N2]----[N3]
    NODE_002  NODE_003
         ←6m→
```

Mount nodes at **2.2 meters height** (above head level to reduce body shadowing). Use zip ties on shelving or command strips on walls.

Power: USB power banks taped to shelf uprights.

**Day 4 Afternoon — Triangulation Algorithm**

Implement weighted centroid triangulation:
```python
def triangulate(rssi_readings, node_positions, path_loss_model):
    """
    rssi_readings: dict {node_id: rssi_dbm}
    node_positions: dict {node_id: (x_m, y_m)}
    Returns: (x_est, y_est) in meters
    """
    distances = {}
    for node_id, rssi in rssi_readings.items():
        d = distance_from_rssi(rssi, path_loss_model)
        distances[node_id] = d

    # Weighted centroid — weight = 1/distance²
    total_weight = 0
    x_weighted, y_weighted = 0, 0
    for node_id, d in distances.items():
        w = 1 / (d ** 2 + 0.01)  # epsilon prevents division by zero
        x, y = node_positions[node_id]
        x_weighted += w * x
        y_weighted += w * y
        total_weight += w

    return x_weighted / total_weight, y_weighted / total_weight
```

**Day 5 — Accuracy Measurement Grid**

Walk the tag to **20 known grid positions** (every 1m in a 4×5 grid within the triangle). For each position:
1. Stand still for 30 seconds (collect ~30 readings)
2. Record estimated position from algorithm
3. Measure error = Euclidean distance between estimated and true position

Target: **Mean position error < 1.5 meters** in office environment.

Fill in the accuracy table:
```
True (x,y) | Est (x,y) | Error (m)
(1, 1)     | (1.2, 0.9)| 0.22
(2, 1)     | (2.4, 1.3)| 0.50
...
```

**Deliverable:** Accuracy table saved as `/data/calibration/day05_accuracy_grid.csv`. Pass criterion: median error ≤ 1.5m.

---

### Days 6–7 — Enclosure Design and Fabrication

**Goal:** Scanner nodes are in weatherproof / presentable enclosures suitable for venue deployment.

**Day 6 — Design**

Option A — 3D Print (if printer available):
- Design in Tinkercad or Fusion 360
- Dimensions: 90mm × 60mm × 35mm (fits ESP32 DevKit + TP4056 + 18650 cell)
- Include M3 screw holes for wall mounting plate
- Ventilation slots on sides (ESP32 can reach 70°C under load)
- Export as `.stl` to `/hardware/enclosures/node_v1.stl`
- Print settings: PLA, 0.2mm layer height, 20% infill, 2 perimeters

Option B — Off-the-shelf ABS Junction Box (recommended for Day 30 demo):
- Purchase: **ABS Enclosure 100×68×50mm** from Patuatuly market (Shop row near Circuit House)
- Price: **BDT 80–120 per unit**
- Drill one 10mm hole for USB power cable entry
- Drill two 4mm holes for mounting screws
- Stick foam weatherstrip tape around lid seam

**Day 7 — Assembly**

Assemble all 5 scanner nodes:
1. Hot-glue ESP32 DevKit v1 to base of enclosure (USB port facing cable entry hole)
2. Solder TP4056 in parallel with USB input if battery backup desired
3. Thread USB cable through grommet
4. Secure lid with M3 screws
5. Affix white label: `FLOWTRACE NODE 001 | DO NOT REMOVE`

Test each assembled unit: power cycle 3 times, verify BLE scan output resumes within 5 seconds of power-on.

**Deliverable:** 5 enclosed, labeled, functioning scanner nodes. Photo to `/docs/evidence/day07_enclosures.jpg`.

---

### Days 8–9 — Full 5-Node Deployment in Test Room

**Goal:** Deploy all 5 nodes in a realistic room layout and measure real-world triangulation accuracy.

**Day 8 — Deployment**

Use a room ≥ 8m × 8m. Optimal 5-node layout:

```
[N1]────────────────[N2]
 │   .           .   │
 │     .       .     │
 │       [N5]        │
 │     .       .     │
 │   .           .   │
[N3]────────────────[N4]
```

- N1–N4: Corners at 2.2m height
- N5: Center at 2.2m height (dramatically improves accuracy in room center)
- All nodes networked via WiFi to the backend server (same LAN)
- Node spacing: ≤ 8m between adjacent nodes (BLE reliable up to ~15m indoor)

**Day 9 — Systematic Accuracy Test**

Test grid: 3m × 3m grid positions across the room (9+ test points).

For each position, collect 60-second dwell (1 reading/second = 60 samples), then compute:
- **Mean error** (meters)
- **90th percentile error** (meters)
- **Coverage gaps** (positions where < 3 nodes see the tag)

Expected benchmarks:
| Environment | Mean Error | 90th Pct Error |
|-------------|------------|----------------|
| Open office, 5 nodes | 0.8–1.2m | 2.0m |
| Furnished room | 1.2–2.0m | 3.0m |
| Mall corridor (future) | 1.5–2.5m | 3.5m |

**Deliverable:** Accuracy heatmap image at `/docs/evidence/day09_heatmap.png` (use matplotlib). Overall system coverage ≥ 90% of test area.

---

### Day 10 — Accuracy Baseline Documentation

**Goal:** Write the honest, quantified accuracy report that will anchor all future claims.

Document the following in `/docs/accuracy_baseline.md`:
- Hardware versions used
- Firmware version (git tag)
- Room dimensions and node coordinates
- Path loss model parameters (TxPower, n)
- Kalman filter settings used
- Full accuracy table (all grid positions)
- Known failure modes:
  - **Corner effect:** Accuracy degrades >2m near walls
  - **Crowding:** Each additional body in LOS adds ~2–4 dB attenuation
  - **Interference:** 2.4 GHz WiFi congestion can cause ±5 dBm RSSI swings
  - **Tag orientation:** Antenna polarization causes ±3 dB variation

Publish the accuracy number you will use in the pitch deck. Be conservative — use the **75th percentile error**, not the median.

**Deliverable:** `/docs/accuracy_baseline.md` committed and reviewed.

---

## Phase 2: Software Layer (Days 11–20)

### Day 11 — Backend Server Running, Ingesting Real Node Data

**Goal:** The FlowTrace backend server is receiving live RSSI readings from all 5 nodes.

**Server setup (Raspberry Pi 4 or local Docker):**
```bash
docker compose -f docker/compose.prod.yml up -d \
  flowtrace-api \
  flowtrace-db \
  flowtrace-timescale \
  flowtrace-redis
```

Verify node data ingestion:
```bash
# Watch live RSSI stream
docker logs -f flowtrace-api | grep "RSSI_INGEST"

# Check DB record count (should grow ~1/sec per tag per node)
psql $DATABASE_URL -c "SELECT count(*) FROM rssi_readings WHERE created_at > now() - interval '1 minute';"
```

Expected: ≥ 45 rows/minute (5 nodes × 10 tags × ~0.9 reads/sec).

**Deliverable:** Live data flowing. Dashboard metric: "Readings/min" counter > 0.

---

### Days 12–13 — Triangulation Algorithm Tuned to Real Data

**Goal:** The backend is computing real-time position estimates for all active tags.

**Day 12:** Port the Day 4 Python triangulation code to the backend service. Add:
- Kalman filter for position smoothing (reduce jitter from RSSI noise)
- Confidence score per position estimate (function of number of nodes in view + RSSI variance)
- Position published to Redis pub/sub channel `flowtrace:positions`

```python
# Kalman filter state: [x, y, vx, vy]
# Measurement: [x_est, y_est] from triangulation
# Process noise Q: tuned for walking speed (~1.5 m/s max)
# Measurement noise R: tuned to Day 9 accuracy benchmarks
```

**Day 13:** Real-data tuning session. Walk the room for 2 hours with tags, compare Kalman-filtered tracks to visual ground truth (record video simultaneously). Tune R matrix until track smoothness is acceptable without introducing > 2-second lag.

**Deliverable:** Tag positions update in Redis at ≥ 2 Hz, with Kalman-filtered tracks that don't jitter more than ±0.3m/update on a stationary tag.

---

### Days 14–15 — Shadow Profile Database + Session Tracking

**Goal:** Each tag/device has a persistent "Shadow Profile" that accumulates behavioral data across sessions.

**Shadow Profile Schema:**
```sql
CREATE TABLE shadow_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tag_id VARCHAR(32) NOT NULL UNIQUE,
    first_seen TIMESTAMPTZ NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL,
    total_sessions INTEGER DEFAULT 0,
    total_dwell_seconds INTEGER DEFAULT 0,
    zone_dwell_seconds JSONB DEFAULT '{}', -- {"zone_id": seconds}
    visit_frequency JSONB DEFAULT '[]',    -- [{"date": "...", "duration_s": ...}]
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tag_id VARCHAR(32) NOT NULL,
    entered_at TIMESTAMPTZ NOT NULL,
    exited_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    zones_visited TEXT[],
    path_geojson JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**Day 15:** Session detection logic:
- **Session Start:** Tag seen for the first time in > 10 minutes → new session
- **Zone Transition:** Tag centroid moves from one defined zone polygon to another → log zone_id + dwell time
- **Session End:** Tag not seen for > 5 minutes → close session, compute duration, update shadow profile

**Deliverable:** After a 30-minute walkabout with 3 tags, query shadow_profiles and see accurate total_dwell_seconds and zones_visited.

---

### Days 16–17 — LangChain Agent First Run

**Goal:** The FlowTrace Analytics Agent answers natural language questions about visitor behavior using real data.

**Day 16 — Agent Setup**

```python
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

tools = [
    get_zone_dwell_time,     # "How long do visitors spend in Zone A?"
    get_peak_hours,          # "When is the venue busiest?"
    get_ghost_trail,         # "Show the path of tag TAG_003 today"
    get_conversion_funnel,   # "How many visitors from Zone A go to Zone C?"
    get_session_count,       # "How many visitors today?"
    get_zone_heatmap_data,   # "Which zone is most visited?"
]

system_prompt = """You are FlowTrace, an intelligent venue analytics assistant for BlankFrame Technologies.
You help venue managers understand visitor behavior using real-time positioning data.
Always give specific numbers. When asked about a zone, name it by its configured label.
Never fabricate data — if you don't have enough data, say so clearly.
"""
```

**Day 17 — Test Prompts**

Run these 10 test prompts and log the responses:
1. "How many unique visitors have we had today?"
2. "What's the average dwell time in the food court?"
3. "Which zone is underperforming in foot traffic?"
4. "Show me the path of Tag 003 between 2pm and 4pm"
5. "When do visitors typically arrive and leave?"
6. "Which zone do most visitors go to first?"
7. "Is there a dead zone in the venue?"
8. "Compare today's foot traffic to yesterday"
9. "How many visitors spent more than 30 minutes here?"
10. "What's the busiest day of the week based on our data?"

Acceptable: Agent correctly uses tools for 8/10 prompts without hallucinating numbers.

**Deliverable:** Agent demo script at `/demo/agent_test_prompts.py` with logged outputs.

---

### Days 18–19 — Live Dashboard Map

**Goal:** A browser-accessible dashboard shows a live floor plan with moving tag dots and zone analytics.

**Tech stack:** Next.js + Leaflet.js (for floor plan overlay) + WebSocket for live position updates.

**Day 18 — Floor Plan Overlay**
- Export venue floor plan as PNG (scan paper plan or draw in Excalidraw)
- Geo-reference corners using pixel coordinates mapped to meter coordinates
- Overlay using Leaflet's `imageOverlay`

**Day 19 — Live Position Dots**
- WebSocket connection to backend: `ws://flowtrace-server:8080/ws/positions`
- Each connected client receives position updates at 2 Hz
- Render each active tag as a colored dot with tag label
- Ghost Trail: last 30 position updates drawn as fading polyline
- Zone overlays: polygon overlays with dwell time percentage label

Color coding:
- 🟢 Green dot: tag seen within last 3 seconds (active)
- 🟡 Yellow: seen 3–10 seconds ago
- 🔴 Red: seen > 10 seconds ago (stale / may have left)

**Deliverable:** Dashboard accessible at `http://localhost:3000`. Live demo with 3 walking tags shows smooth movement.

---

### Day 20 — End-to-End Integration Test

**Goal:** Full system smoke test from physical BLE scan to agent query.

**Test Protocol:**
1. Cold-start all 5 scanner nodes (power cycle)
2. Verify all nodes check in to backend within 60 seconds
3. Start session with 3 tags; walk a pre-defined path for 20 minutes
4. Verify dashboard shows correct positions throughout
5. After walk: query agent with "Describe what TAG_001 did today"
6. Verify shadow profiles updated correctly
7. Simulate node failure: unplug NODE_003, verify system degrades gracefully (not crash)
8. Re-plug NODE_003, verify it rejoins without restart

**Pass criteria:** All 8 steps pass without manual intervention.

**Deliverable:** Integration test checklist at `/tests/integration/day20_checklist.md` with pass/fail for each step.

---

## Phase 3: Demo Prep (Days 21–30)

### Days 21–22 — Full System Test with 3 Live Users

**Goal:** Three real people (not the dev) use the system naturally for 1 hour. Observe pain points.

- Give each person a wristband tag. Explain nothing about the system.
- Ask them to walk around the venue/test room naturally.
- Watch the dashboard in another room.
- Note: any tag loss events, position jumps, missed zone transitions.

After 1 hour, debrief with the three users:
- "Did you notice anything unusual?" (tests for BLE interference from wristband)
- "Were there areas you couldn't move freely?" (tests for cable/enclosure issues)

Fix all critical bugs found on Day 22.

**Deliverable:** Bug list at `/issues/day21_user_test.md`. All P0 (system-stopping) bugs fixed by end of Day 22.

---

### Days 23–24 — Ghost Trail Visualization Polish

**Goal:** The Ghost Trail feature is visually impressive enough to be the centerpiece of the demo.

Ghost Trail requirements:
- Smooth animation (60fps on demo laptop)
- Color gradient from blue (start of session) to red (most recent position)
- Opacity fade: older points more transparent
- Click on any trail point to see timestamp + zone label
- "Replay" button to animate the full session path at 10× speed
- Export trail as PNG for slide deck

Polish the Agent chat panel:
- Clean chat UI (dark mode, monospaced font for data outputs)
- Streaming responses (token-by-token display)
- Tool call indicators: "🔍 Querying zone dwell times..." while agent thinks

**Deliverable:** Screen recording of Ghost Trail replay at `/demo/ghost_trail_demo.mp4`.

---

### Days 25–26 — Pitch Deck Preparation

**Goal:** A complete, rehearsable pitch deck is ready.

- Build in Google Slides or Canva (brand colors: dark navy + electric cyan + white)
- Export as PDF to `/docs/pitch_deck_final.pdf`
- Export each slide as PNG for backup
- One-sentence speaker notes per slide (max 30 words each)
- Practice transitions — no slide should need more than 90 seconds

See `/docs/pitch_deck.md` for full slide-by-slide content.

**Deliverable:** Pitch deck exported as PDF, reviewed by at least one non-technical person for clarity.

---

### Days 27–28 — Rehearse Demo with Test Subject

**Goal:** Full demo rehearsal — pitch + live system — runs smoothly in ≤ 20 minutes.

**Demo script:**
1. (2 min) Pitch slides 1–6: problem, market, solution
2. (3 min) Live dashboard: show test subject walking in real time
3. (2 min) Ghost Trail replay of their session
4. (3 min) Agent queries: ask 3 impressive questions, get instant answers
5. (2 min) Pitch slides 8–12: business model, pricing, ask
6. (8 min) Q&A buffer

Day 27: First full rehearsal — record on phone. Watch back. Identify weak spots.  
Day 28: Second rehearsal with fixes. Aim for < 3 stumbles total.

**Deliverable:** Final rehearsal video saved at `/demo/rehearsal_day28.mp4`.

---

### Day 29 — Stress Test: 10 Simultaneous Users

**Goal:** System does not degrade with 10 active tags — the maximum expected demo load.

Start 10 tags simultaneously. Have 5 people each carry 2 tags (simulates max venue density for a small venue). Walk for 30 minutes.

Monitor:
```bash
# API response time (should be < 200ms p99)
watch -n 5 'curl -s http://localhost:8080/metrics | grep api_response_p99'

# DB write queue depth (should be < 500)
watch -n 5 'curl -s http://localhost:8080/metrics | grep db_queue_depth'

# WebSocket broadcast lag (should be < 500ms)
watch -n 5 'curl -s http://localhost:8080/metrics | grep ws_broadcast_lag_ms'
```

**Pass criteria:**
- API p99 latency < 200ms throughout
- No tag position loss for > 15 seconds in open areas
- Dashboard renders smoothly on demo laptop (≥ 30fps)
- Agent queries return in < 10 seconds even under load

**Deliverable:** Stress test metrics log at `/tests/stress/day29_results.json`.

---

### Day 30 — Final Demo + Video Recording

**Goal:** A professional, shareable demo video is recorded and the system is ready for a real investor or client meeting.

**Morning:**
- Full system cold-start (simulate as if setting up at a real venue)
- Run integration test checklist from Day 20
- Confirm all nodes are in clean enclosures, labeled, cabled neatly

**Afternoon — Record Demo Video:**
- Screen capture: OBS Studio or QuickTime
- Resolution: 1920×1080 minimum
- Audio: external mic or AirPods with good mic quality
- Duration: 3–5 minutes (not the full 20-minute pitch — a highlight reel)

**Video structure:**
1. (30s) Open with "This is FlowTrace by BlankFrame" — show the dashboard
2. (60s) Show someone walking — live position tracking
3. (45s) Ghost Trail replay
4. (45s) Ask 2 agent questions, show instant answers
5. (30s) Show the hardware (node enclosure, wristband)
6. (30s) Close with pricing tier and call to action

Upload to YouTube (unlisted) + save raw .mp4 locally.

**Deliverable:** Demo video published. Link posted in team Slack channel. System in "demo-ready" state on dedicated server or Raspberry Pi.

---

## Sprint Tracking Dashboard

| Day | Phase | Key Deliverable | Status |
|-----|-------|-----------------|--------|
| 1 | Sensing | All nodes scanning BLE | ⬜ |
| 2–3 | Sensing | Path loss models calibrated | ⬜ |
| 4–5 | Sensing | 3-node triangulation < 1.5m error | ⬜ |
| 6–7 | Sensing | 5 nodes in enclosures | ⬜ |
| 8–9 | Sensing | 5-node deployment, accuracy measured | ⬜ |
| 10 | Sensing | Accuracy baseline documented | ⬜ |
| 11 | Software | Backend ingesting live data | ⬜ |
| 12–13 | Software | Triangulation tuned to real data | ⬜ |
| 14–15 | Software | Shadow profiles + session tracking | ⬜ |
| 16–17 | Software | LangChain agent answering 8/10 prompts | ⬜ |
| 18–19 | Software | Live dashboard map working | ⬜ |
| 20 | Software | End-to-end integration test passes | ⬜ |
| 21–22 | Demo | 3-user test, P0 bugs fixed | ⬜ |
| 23–24 | Demo | Ghost Trail polished | ⬜ |
| 25–26 | Demo | Pitch deck final | ⬜ |
| 27–28 | Demo | Demo rehearsed x2 | ⬜ |
| 29 | Demo | Stress test: 10 users pass | ⬜ |
| 30 | Demo | Video recorded and published | ⬜ |

---

*Document maintained by BlankFrame Technologies Engineering. Last updated: Sprint Day 0.*
