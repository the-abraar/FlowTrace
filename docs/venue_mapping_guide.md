# Project FlowTrace — Venue Mapping Guide
**BlankFrame Technologies** | Field Operations Reference  
**Version:** 1.0

> [!NOTE]
> This guide is for the technician performing an FlowTrace installation at a new venue. Complete every section in order — skipping steps results in poor position accuracy and difficult-to-debug failures.

---

## 1. Pre-Site Survey Checklist

Before visiting the venue, gather:
- [ ] Architectural floor plan (PDF or CAD) — request from venue management
- [ ] WiFi network access (SSID + password for IoT VLAN, or request one be created)
- [ ] Power outlet locations (for scanner node placement planning)
- [ ] Venue manager contact for escort during installation
- [ ] Tape measure (10m minimum), laser distance meter if available
- [ ] Laptop with FlowTrace CLI installed
- [ ] 1× scanner node + 1× beacon tag for on-site signal testing
- [ ] FlowTrace Venue Mapping Worksheet (printed, `/docs/templates/venue_mapping_worksheet.pdf`)

---

## 2. Floor Plan Measurement Techniques

### 2.1 If You Have an Architectural Plan

1. Identify scale: Look for the scale bar on the plan (e.g., 1:100 means 1cm = 1m).
2. Measure reference walls with tape measure on-site. Correct any discrepancies (plans are often slightly wrong after renovation).
3. Scan/photograph the plan at high resolution (≥300 DPI).
4. Import into FlowTrace Dashboard → Venue Setup → Upload Floor Plan.
5. Set scale: Click two known points (e.g., room corners), enter real-world distance.

### 2.2 Manual Measurement (No Plan Available)

Use the **Baseline-and-Offset** method:

```
Step 1: Establish a baseline along the longest wall.
         Mark every 1m with tape.

Step 2: From each 1m mark, measure perpendicular distance
         to the opposite wall.

Step 3: Record all openings (doors, archways) with:
         - Position along baseline (m from corner)
         - Width (m)
         - Height (m)

Step 4: For irregular shapes, triangulate from two known points.
```

Sketch on graph paper. Each grid square = 1m × 1m.

**Minimum measurements required:**
- Overall length and width of space
- Column/pillar positions (x, y from corner reference)
- Height of space at multiple points (for 3D node placement)
- Structural wall thickness (relevant for signal planning)

### 2.3 Laser Distance Meter Method (Fastest)

With a Bosch GLM 40 or equivalent:
1. Place device at one corner, shoot to opposite wall: record **L1**
2. Rotate 90°, shoot to adjacent wall: record **W1**
3. For non-rectangular spaces: shoot diagonals, use Pythagoras to verify
4. Accuracy: ±2mm at 40m

Total time for a 500m² space: ~45 minutes including recording.

---

## 3. Node Placement Strategy

### 3.1 Core Principle: Minimize Dead Zones

A dead zone is any area in the venue where a tag is visible to fewer than 3 nodes. **Triangulation requires a minimum of 3 nodes.** With only 2 nodes visible, position can only be estimated on a circle (2D), not a point. With 1 or 0 nodes, positioning fails entirely.

Coverage rule of thumb:
- **Reliable BLE range indoors:** 10–15m (with clear line of sight)
- **Practical coverage per node:** ~8m radius in a furnished indoor environment
- **Overlap required:** Adjacent node coverage areas must overlap by ≥ 3m

### 3.2 Optimal Configurations

**3-Node Configuration (Minimum — ≤ 100m² space)**

```
         [N1]
        /     \
      8m       8m
      /    ●    \          ● = monitored area
   [N2]────────[N3]
         8m

Coverage: ~27m² "sweet spot" in triangle center
Gaps: Corners of room may have 1–2 node coverage only
```

**5-Node Configuration (Recommended — 100m²–400m² space)**

```
[N1]─────────────────[N2]
 │    .           .   │
 │      .       .     │
 │        [N5]        │
 │      .       .     │
 │    .           .   │
[N3]─────────────────[N4]

Node spacing: 8–12m
Coverage: ~350m² with good accuracy throughout
Dead zones: < 5% of floor area (usually in corners)
```

**L-Shaped Venue (Mall Corridor)**

```
[N1]──[N2]──[N3]
              │
             [N4]
              │
             [N5]──[N6]

Spacing: 8m between adjacent nodes
Corridor width: Nodes on one side if < 5m wide
               Nodes on both sides if > 5m wide
```

**Multi-Zone (Bashundhara Retail Floor)**

```
Zone A (Food Court)         Zone B (Game Zone)
[N1]────[N2]               [N5]────[N6]
  │          │               │          │
  │    A     │ ←── corridor ──→    B    │
  │          │               │          │
[N3]────[N4]               [N7]────[N8]

Add [N_border] at zone transition points
```

### 3.3 Node Height

Mount nodes at **2.0m–2.5m** above floor level. This is:
- **Above average human head** (reduces body shadowing)
- **Below suspended ceiling** (stays in same open space as tags)
- **Accessible for maintenance** (stepladder, not scissor lift)

Never mount higher than 3m — the increasing angle to a wristband tag creates unpredictable RSSI patterns due to antenna polarization mismatch.

### 3.4 Node Orientation

Mount with ESP32 PCB **horizontal** (flat, face-down) when possible. The PCB trace antenna radiates omnidirectionally in the horizontal plane — correct orientation maximizes coverage area and minimizes ceiling/floor interference.

---

## 4. Dead Zone Identification

### 4.1 Survey Method

After placing nodes (but before enclosing them), perform a walk survey:

```bash
# Start the dead zone survey tool
flowtrace-cli survey --venue venue_01 --output data/surveys/survey_01.json

# Walk slowly (1 step per 2 seconds) along a grid pattern
# The tool will log node count and RSSI per position
# Mark positions where fewer than 3 nodes are visible
```

Visualize results:
```bash
flowtrace-cli survey visualize --input data/surveys/survey_01.json --output docs/survey_01_heatmap.png
```

### 4.2 Coverage Heatmap Interpretation

The heatmap uses this color scale:

| Color | Meaning | Action |
|-------|---------|--------|
| 🟢 Green | ≥ 4 nodes visible, RSSI > -75 dBm | Excellent — no action |
| 🟡 Yellow | 3 nodes visible, RSSI -75 to -85 dBm | Acceptable — monitor |
| 🟠 Orange | 2 nodes visible | Position estimation will fail here |
| 🔴 Red | 0–1 nodes visible | Dead zone — add node or accept exclusion |

### 4.3 Dead Zone Mitigation

Options in order of preference:
1. **Reposition an existing node** closer to the dead zone
2. **Add a relay node** (scanner-only, no battery backup needed if power available)
3. **Accept and document** the dead zone, add it to the "exclusion zones" in the venue configuration (positions estimated in these areas will be flagged with low confidence)

Acceptable dead zone coverage for demo: < 10% of monitored floor area.

---

## 5. Environmental RSSI Interference Factors

### 5.1 Building Material Attenuation

The following values are additional attenuation (dB) beyond free-space path loss per material layer:

| Material | Attenuation (dB) | Notes |
|----------|-----------------|-------|
| Glass (single pane) | 2–3 dB | Minimal impact |
| Drywall / plasterboard | 3–5 dB | Standard office wall |
| Concrete wall (20cm) | 10–15 dB | Significant — plan around |
| Brick wall (25cm) | 8–12 dB | Significant |
| Reinforced concrete | 15–20 dB | Near-impassable for BLE |
| Metal shelving unit | 5–15 dB | Variable — depends on fill |
| Glass storefront (multi-pane) | 6–10 dB | Common in malls |
| Water (aquarium, pipes) | 10–20 dB | Highest attenuation per cm |

**Practical implication:** In a venue with concrete columns (common in Bangladeshi commercial buildings), place nodes so that the primary path between node and coverage area does NOT pass through a concrete column. A 20cm concrete column can reduce effective range by 50%.

### 5.2 Human Body Absorption

At 2.4 GHz, the human body absorbs approximately **3–6 dB** of BLE signal per body in the direct path between node and tag.

Crowd density impact:
| Density | People/m² | Expected Additional Attenuation |
|---------|-----------|--------------------------------|
| Sparse | < 0.1 | 0–3 dB |
| Moderate | 0.1–0.5 | 3–8 dB |
| Crowded (market) | 0.5–2.0 | 8–15 dB |
| Very crowded (event) | > 2.0 | 15–20 dB |

**Calibrate with a crowd present.** A calibration done in an empty venue at 9 AM will give incorrect models for a busy Saturday afternoon. Perform at least one calibration session during peak hours.

### 5.3 WiFi Interference

BLE and WiFi both operate on 2.4 GHz. WiFi uses channels 1–13 (22 MHz wide each). BLE uses 40 channels of 2 MHz each.

**Problem:** High-density WiFi deployments (shopping malls often have 10+ access points per floor) cause channel overlap with BLE, adding noise floor to RSSI readings.

**Mitigation:**
- Check 2.4 GHz channel utilization: use WiFi Analyzer app (Android) or `airport -s` (macOS) on-site
- If channels 6 and 11 are heavily loaded (>-60 dBm from multiple APs), RSSI variance will be high
- Solution: Increase BLE advertisement interval (500ms → 200ms) to get more readings per second, average more aggressively in Kalman filter
- Long-term: Request venue IT to configure IoT VLAN on 5 GHz only for FlowTrace infrastructure

### 5.4 Metal Shelving and Fixtures

Metal creates two problems:
1. **Absorption:** Direct path through metal attenuates severely
2. **Reflection:** Indirect reflections arrive at the node with delay and phase shift, causing multipath interference

**Game zone specific:** Arcade machine cabinets are large metal boxes. If a tag is directly behind an arcade cabinet relative to a node, expect RSSI errors of ±10 dBm (≈ ±2 meters position error).

**Mitigation:** Place nodes above and slightly behind the main row of machines, so there is always a partial line-of-sight path to the carrying height (chest/wrist level).

---

## 6. Calibration Walkthrough Procedure

> [!IMPORTANT]
> Perform calibration **after** nodes are permanently mounted. Calibration is valid only for the exact node positions recorded. If a node is moved even 20cm, recalibrate.

### 6.1 Pre-Calibration Setup

```bash
# Set up venue configuration
flowtrace-cli venue create \
  --id venue_bashundhara_g1 \
  --name "Bashundhara City Game Zone — Ground Floor" \
  --width_m 45.0 \
  --height_m 22.0

# Register node positions (in meters from SW corner of venue)
flowtrace-cli node register --venue venue_bashundhara_g1 --id NODE_001 --x 2.0 --y 2.0 --z 2.3
flowtrace-cli node register --venue venue_bashundhara_g1 --id NODE_002 --x 43.0 --y 2.0 --z 2.3
flowtrace-cli node register --venue venue_bashundhara_g1 --id NODE_003 --x 2.0 --y 20.0 --z 2.3
flowtrace-cli node register --venue venue_bashundhara_g1 --id NODE_004 --x 43.0 --y 20.0 --z 2.3
flowtrace-cli node register --venue venue_bashundhara_g1 --id NODE_005 --x 22.5 --y 11.0 --z 2.3
```

### 6.2 TxPower Reference Measurement

At each node, place the calibration tag at exactly **1.00 meter** horizontally (use tape measure). Record 200 RSSI samples:

```bash
flowtrace-cli calibrate txpower \
  --node NODE_001 \
  --tag TAG_CALIB \
  --distance_m 1.0 \
  --samples 200 \
  --output data/calibration/venue_b_txpower.json
```

Repeat for all 5 nodes. Expected TxPower range: -40 dBm to -50 dBm depending on ESP32 batch and antenna.

### 6.3 Path Loss Exponent Measurement

Walk the calibration path — a pre-defined set of 15 known positions across the venue:

```bash
# Start calibration walk
flowtrace-cli calibrate walk \
  --venue venue_bashundhara_g1 \
  --tag TAG_CALIB \
  --ground_truth data/calibration/walk_path.json \
  --output data/calibration/venue_b_walk.json

# walk_path.json specifies: [{x: 2.0, y: 5.0, dwell_seconds: 30}, ...]
# Stand at each point for the specified duration
```

After the walk (approximately 8 minutes), compute the model:

```bash
flowtrace-cli calibrate compute \
  --venue venue_bashundhara_g1 \
  --txpower data/calibration/venue_b_txpower.json \
  --walk data/calibration/venue_b_walk.json \
  --output data/calibration/venue_b_model.json
```

Review output:
```json
{
  "venue_id": "venue_bashundhara_g1",
  "path_loss_exponent": 3.1,
  "tx_power_dbm": -44,
  "r_squared": 0.88,
  "calibrated_at": "2026-10-20T11:30:00Z",
  "calibrated_by": "field_tech_01",
  "nodes_calibrated": ["NODE_001", "NODE_002", "NODE_003", "NODE_004", "NODE_005"]
}
```

**Minimum acceptable R² = 0.80.** If R² < 0.80, check for node connectivity issues or repeat measurements during lower-traffic hours.

### 6.4 Zone Definition

After calibration, define logical zones as polygons:

```bash
flowtrace-cli zone create \
  --venue venue_bashundhara_g1 \
  --id ZONE_ARCADE \
  --name "Arcade Zone" \
  --polygon "[[5,3],[20,3],[20,18],[5,18]]"  # meters from venue origin

flowtrace-cli zone create \
  --venue venue_bashundhara_g1 \
  --id ZONE_FOOD \
  --name "Food Counter" \
  --polygon "[[22,3],[43,3],[43,10],[22,10]]"

flowtrace-cli zone create \
  --venue venue_bashundhara_g1 \
  --id ZONE_ENTRANCE \
  --name "Entrance / Lobby" \
  --polygon "[[0,0],[45,0],[45,3],[0,3]]"
```

### 6.5 Calibration Verification

After applying the calibration model, verify with a blind test walk:

```bash
flowtrace-cli verify \
  --venue venue_bashundhara_g1 \
  --tag TAG_CALIB \
  --ground_truth data/calibration/blind_test_path.json \
  --output reports/calibration_verification.md
```

Acceptable result: Mean position error ≤ 2.0m, 90th percentile ≤ 3.5m in a furnished venue.

---

## 7. Bashundhara City — Specific Deployment Notes

**Venue:** Bashundhara City Shopping Complex, Panthapath, Dhaka  
**Target Floor:** 6th or 7th floor (Game Zone / entertainment level)

### Known Environmental Factors

| Factor | Impact | Mitigation |
|--------|--------|------------|
| Reinforced concrete slab between floors | Minimal (vertical not horizontal concern) | N/A |
| Central HVAC ducts (metal, ~0.5m diameter) | ±4 dBm where duct runs between node and tag | Avoid placing nodes directly adjacent to HVAC runs |
| Marble flooring | Strong reflection of BLE upward | Kalman filter smoothing, higher R in measurement noise |
| Glass storefronts (elevator lobby) | 6 dB attenuation | Place node on game zone side of glass |
| Crowded Fridays (Jumu'ah + market day) | +10 dB body attenuation vs weekday morning | Apply crowd-correction factor: add 1.2× multiplier to path loss exponent from 2pm–6pm Fri/Sat |
| Security camera system (2.4 GHz wireless) | +2–5 dBm noise floor | Check channel usage; request venue IT to switch cams to 5GHz |

### Recommended Node Placement — Bashundhara Game Zone (Approximate)

Assuming a roughly 40m × 20m game zone:
- **NODE_001:** Above entrance archway, center, height 2.3m — covers entry zone and first 10m
- **NODE_002:** Back-left corner above wall-mounted game machine, height 2.2m
- **NODE_003:** Back-right corner above prize counter, height 2.2m
- **NODE_004:** Center-left, above ticket dispenser column, height 2.3m
- **NODE_005:** Center-right, above food counter entrance, height 2.3m

Estimated dead zones: < 8% (mainly directly behind the VR booth metal enclosure).

### Wiring and Power at Bashundhara

Power outlets in Bangladeshi commercial venues are typically:
- 220V, 50Hz AC, type C or type D sockets
- Located every 5–8m on the perimeter walls
- Managed by building electrician (permission required to run extension cables)

**Recommended power setup:**
- Use 5V/2A USB adapters plugged into existing outlets
- Run USB cables (micro-USB, 3m length) to node mounting positions
- For positions far from outlets: use a 6-outlet power strip + single longer AC extension to the nearest socket
- Label all power strips: `FLOWTRACE SYSTEM — DO NOT UNPLUG`

> [!CAUTION]
> Bangladeshi commercial buildings experience frequent voltage fluctuations (160V–260V swings common). Use a USB adapter with wide input range (100V–240V, which all modern USB adapters support) and optionally add an inline voltage protector for the Raspberry Pi server.

---

## 8. Togi Fun World — Specific Deployment Notes

**Venue:** Togi Fun World (Toy/Game Venue), Mirpur or Dhanmondi location  
*(Verify current location — Togi operates multiple venues)*

### Known Environmental Factors

| Factor | Impact | Mitigation |
|--------|--------|------------|
| Play equipment (plastic slides, foam pits) | Low attenuation — plastic is transparent to BLE | Favorable |
| Chain-link / net barriers | Mild scattering (2–4 dB) | Position nodes to see over, not through, barriers |
| Ceiling height (typically 4–6m) | Longer vertical distance to tags | Lower mounting height to 2.0m to maintain RSSI levels |
| Children's height (tags at waist/wrist, ~0.8m AGL) | Higher angle from low-mounted tag to high node | Mount nodes at 2.0m, not 2.5m |
| Noise (play venue) | No RF impact but voice comms difficult | Bring printed checklists |
| Parent clustering near entrance | Creates RSSI shadow for exit-zone node | Add extra node at entrance |

### Togi-Specific Zone Suggestions

| Zone ID | Name | Description |
|---------|------|-------------|
| ZONE_TODDLER | Toddler Area | Soft play, ball pit — typically 0–3 yr |
| ZONE_JUNIOR | Junior Activity | Slides, climbing — 4–8 yr |
| ZONE_ARCADE | Arcade Section | Token-operated machines — 8–15 yr |
| ZONE_CANTEEN | Canteen | Food, parent waiting area |
| ZONE_ENTRANCE | Entrance / Checkout | Ticket desk, entry/exit |

**Business insight value:** Togi can use dwell time in ZONE_CANTEEN vs ZONE_ARCADE to optimize staffing and food preparation.

---

*Guide maintained by BlankFrame Technologies Field Operations. Last updated: Sprint Day 0.*
