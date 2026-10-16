# FlowTrace Launch-Readiness Judgement

> **Current go-to-market score: 20%.** The verdict below is the original 2026-10-12 audit. See *Update 8* at the bottom for the current score, gaps and next steps, and `../GO_TO_MARKET_SCORECARD.md`.

Audited 2026-10-12, at commit `67b943c`. I read every source, config, doc and marketing file. Nothing was modified, and no code was executed: the findings come from reading the code, and every one cites a file and line.

---

## Verdict

**Readiness: about 8%.** FlowTrace is a scaffold with strong docs and marketing, but almost none of it works end to end:

- **The backend crashes on startup.** It imports classes that do not exist.
- **The dashboard crashes on load.** It uses a default import that does not exist.
- **The firmware cannot talk to the backend.** Payload shape, port and MQTT topics all disagree.
- **The AI agent is never started.**
- **There are no tests, and no RSSI accuracy measurements exist.**
- **The demo numbers are fake.** Without a backend, the dashboard silently shows mock data (`flowtraceStore.js:157,189`) and hardcoded values (`StatsBar.jsx:11-13`, `PopUpDashboard.jsx:9-10`, `NodeHealth.jsx:6-12`). A demo today would present invented figures as live.

The product side is weaker than the code:

- **Three different products are being sold:**
  - BLE positioning for game zones (`docs/pitch_deck.md`).
  - App-free pop-up analytics for D2C brands (`marketing/online_brand_strategy.md`).
  - An RFID tap-to-ride cashless system (`marketing/bashundhara_pitch.html`). No code exists for it.
- **The core promise is technically false.** "No app, no wristband, 100% of footfall, just walk" does not hold: the system only detects FlowTrace-flashed tags. Phones cannot be tracked reliably because of MAC randomization and iOS background limits.
- **Nothing is validated:** no customer, no accuracy number, no legal review, no billing, no multi-venue support.

This is a 30-day demo project that has not passed its own Day-11 milestone ("Backend Server Running, Ingesting Real Node Data").

---

## Critical blockers (ranked)

### 1. The backend cannot start
- **Evidence:**
  - `backend/main.py:10-11` imports `PositioningFleet` and `VenueZoneAnalytics`. Neither class exists. `triangulator.py` defines `PositionEngine`; `zone_detector.py` defines `ZoneDetector`.
  - `ingestion/mqtt_server.py:8` imports `SessionLocal`, and `http_receiver.py:9` plus all three routers import `get_db`. `database/session.py` defines neither; it only has `AsyncSessionLocal` and `get_session`.
  - `session.py:9`, `triangulator.py:31` and `init_db.py:26-28` import `backend.config`, while `main.py` uses `database.*`. Run from `backend/` (as the README and Dockerfile do), `backend.` cannot be found; run from the repo root, `database.` cannot be found.
  - The code mixes a sync ORM with an async engine. `main.py:29` calls `create_all(bind=async_engine)`, and the routers and ingestion use `db.query(...)` on an async session.
  - Column names do not match the model. `Node.node_id` and `Device.device_id` are used in `http_receiver.py:52,60,62`, `mqtt_server.py:66,72,74`, `nodes.py:15` and `devices.py:15`, but the model only has `id` (`models.py:69,118`).
  - `fleet.ingest_reading` and `fleet.get_all_positions` do not exist anywhere.
  - `mqtt_server.py:19` calls `mqtt.Client(client_id=...)` without the `callback_api_version` argument that paho-mqtt 2.x (pinned at `requirements.txt:10`) requires.
  - `docker-compose.yml:12` sets `DATABASE_URL=sqlite:///` (sync driver) for an async engine.
- **Why it blocks launch:** nothing runs, so nothing can be demoed, piloted or sold.
- **Fix:**
  1. Pick one import root: run the app as the `backend` package from the repo root, with `uvicorn backend.main:app`.
  2. Pick sync SQLAlchemy plus `psycopg` or `sqlite`. It is simpler, and the readings path is not I/O-bound at pilot scale. Delete the async session.
  3. Write a `PositioningFleet` that wraps `PositionEngine`. It needs `configure_nodes`, `ingest_reading` (a per-device, per-node RSSI window) and `get_all_positions`.
  4. Rename `ZoneDetector` usage to match.
  5. Fix the column names.
  6. Add `CallbackAPIVersion.VERSION2`.
  7. Add a CI job that runs `python -c "import backend.main"` plus a `/health` smoke test, so this class of break cannot ship again.

### 2. The firmware, gateway and backend use incompatible data contracts
- **Evidence:**
  - **Payload shape:**
    - The scanner posts `{node_id, fw_version, readings:[{device_id, mac, rssi, batt_mv, ts_ms}]}` (`scanner.ino:293-316`).
    - The backend expects `readings:[{node_id, device_id, rssi, timestamp ISO, battery_pct}]` (`http_receiver.py:17-27`). Every real upload returns 422.
  - **Port:** firmware posts to port `8080` (`scanner/config.h:43`, `gateway/config.h:69`); the backend listens on `8000` (`run.py:10`).
  - **MQTT topics:**
    - Scanners do not use MQTT at all.
    - The gateway subscribes to `flowtrace/readings/#` (`gateway/config.h:54`).
    - The backend subscribes to `flowtrace/nodes/+/readings` (`mqtt_server.py:27`).
  - **Timestamps:** `ts_ms` is `millis()` since boot, and there is no NTP, so nodes have no common clock to align readings for trilateration.
  - **Beacon name filter:** the beacon advertises the name `AURA_FLOWTRACE_TAG_001` (`beacon.ino:126,~283`), but the scanner only matches names starting with `FLOWTRACE` (`scanner/config.h:58`). Tags are only accepted through the iBeacon UUID fallback.
  - **Duplicate identities:** `deviceId` becomes the name when a scan response was received and the MAC otherwise (`scanner.ino:187-192`). One tag shows up as two devices.
  - **Shared major/minor:** every tag ships with major/minor `0x0001/0x0001` (`beacon/config.h:23-24`).
  - **Foreign beacons:** the UUID `f7826da6-…` is Kontakt.io's default, so any Kontakt beacons in a mall would be ingested as visitors.
  - **Unknown node IDs:** seeded node IDs are `node-NW…` (`init_db.py:38-48`), but the simulator and `main.py` use `NODE_A…`. `http_receiver.py:56` silently drops readings from unknown nodes, so nothing is persisted even from the simulator.
- **Why it blocks launch:** real hardware data never reaches positioning.
- **Fix:**
  1. Write one versioned schema (`schemas/reading.v1.json`) and generate or validate both sides against it.
  2. Make the backend accept the scanner's batch shape: node_id at batch level, and a server receive time as the clock, with `ts_ms` kept as a relative offset.
  3. Encode tag ID in iBeacon major/minor, unique per tag, and identify tags by that instead of the name or MAC.
  4. Generate a FlowTrace-owned UUID.
  5. Add node auto-registration with "pending" status.
  6. Delete either MQTT or HTTP; keep HTTP for v1. Delete `gateway.ino` until it is needed.
  7. Add a contract test that replays a captured scanner payload against the API.

### 3. "No app, no friction, 100% of footfall" is false, and the product depends on it
- **Evidence:**
  - The scanner only accepts FlowTrace-named or FlowTrace-UUID tags (`scanner.ino:150-180`).
  - Marketing still claims "captures 100% of visitor footfall passively", "no apps", and also mentions "existing smartphone BLE signals" (`cold_emails.md:8`, `landing_page.md:9-15`, `pitch_deck.md:13`, `online_brand_strategy.md`).
  - Modern phones rotate BLE MACs every ~15 minutes, and iOS barely advertises when backgrounded. Phone-based tracking cannot produce stable sessions or dwell times, and cannot deliver to "100%".
  - The D2C pop-up segment will not hand out and collect wristbands at a 1–3 day booth.
- **Why it blocks launch:** the main selling claim cannot be delivered. That means misleading sales, failed pilots and legal exposure.
- **Fix:**
  1. Restrict v1 to venues that already issue a wearable or token at paid entry: game zones and play centers. There the tag is the entry band.
  2. Rewrite all copy to "tag-based visitor analytics".
  3. For pop-ups, either drop the segment or swap the sensor for an overhead people-counter or an edge-CV anonymous counter. Do not sell BLE there.
  4. Add tag-logistics SOPs: issue at entry, collect at exit, charge overnight, sanitize, count losses. Price in tag loss.

### 4. Positioning accuracy is unmeasured and almost certainly too poor for the zone model
- **Evidence:**
  - **Sampling:** the beacon advertises 100 ms per 5 s (`beacon/config.h:41-52`). The scanner listens with a 50% duty cycle (`scanner/config.h:70-71`), only for 9 of every 10 s, and stops scanning while uploading (`scanner.ino:439-457`). That gives roughly one sample per node every 5–10 s.
  - **Assumed propagation:** the backend assumes free-space path loss, `n=2.0` (`config.py:60`), even though its own doc says crowded venues are 3.0–3.5 (`rssi_calibration.md`).
  - **Single venue parameters:** there is one TxPower and one `n` for the whole venue, with no per-node calibration.
  - **Kalman timing:** the Kalman filter uses processing wall-clock time, not reading time (`triangulator.py:126`).
  - **Two-anchor case:** with only 2 anchors, the code interpolates along a line and still returns a position (`triangulator.py:214-221`).
  - **Demo zone size:** demo zones are 3 m deep (`zone_detector.py:92-129`). Typical crowded-venue RSSI trilateration error is 2–5 m, so zone assignment would be close to a coin flip at boundaries.
  - **No accuracy data:** the sprint's accuracy deliverables (`docs/accuracy_baseline.md`, `/data/calibration/*`, `docs/evidence/day09_heatmap.png`) do not exist.
  - **Simulator mismatch:** the simulator uses `n=2.2`, 4 dB noise, and zones that differ from the backend's (`simulate.py:28-38` vs `zone_detector.py`), so simulated success proves nothing.
- **Why it blocks launch:** every insight, heatmap and AI recommendation sits on top of these positions. Wrong zones lead to wrong insights and a lost customer.
- **Fix:**
  1. Drop trilateration for v1. Use zone-level proximity instead: one node per zone, assign the zone by strongest median RSSI over a 5–10 s window, with hysteresis and per-node RSSI offset calibration.
  2. Raise the tag rate to 1–2 Hz continuous advertising on nRF52 tags, and scan at 100% duty (`window == interval`, continuous scan, upload from a separate task).
  3. Build a ground-truth harness: walk a scripted route with a logged timeline, and compute zone accuracy and confusion matrix.
  4. Set a launch gate of at least 90% zone accuracy at the target crowd density.
  5. Publish only the measured number.

### 5. No security at any layer
- **Evidence:**
  - No auth on any API or WebSocket route (`main.py:94-108`).
  - CORS is `*` with credentials (`main.py:86-92`).
  - Ingestion is unauthenticated, so anyone on the LAN can inject or spoof visitors.
  - Mosquitto has `allow_anonymous true` with ports 1883 and 9001 exposed (`docker/mosquitto.conf`, `docker-compose.yml:38-40`).
  - Hardcoded credentials:
    - OTA `aura_ota_secret` (`gateway/config.h:80`) and portal `admin/aura2024` (`gateway/config.h:90-91`).
    - Hotspot passphrase in git (`deployment/popup_hotspot.sh:59`).
    - WiFi creds compiled into firmware.
  - All traffic is plaintext HTTP.
  - The positions WebSocket broadcasts every tracked person's location to any client.
- **Why it blocks launch:** live location data of visitors (often children) is exposed on the venue network. One incident ends the company.
- **Fix:**
  1. Per-node API keys, an HMAC header checked at ingestion.
  2. Dashboard login with sessions or JWT, plus per-venue RBAC.
  3. Authenticated WebSocket.
  4. CORS allowlist from config, which already exists at `config.py:45` but is unused.
  5. Remove MQTT, or enable auth and ACLs on it.
  6. Move secrets to provisioning: a WiFi/key captive portal on first boot, and NVS storage.
  7. TLS via a reverse proxy (Caddy) on the edge box.
  8. Rotate the leaked passwords.

### 6. Privacy and legal compliance are claimed but not implemented
- **Evidence:**
  - `docs/privacy_and_ethics.md` promises daily-salted MAC hashing, aggregation after sessions, and a 30-day purge. None of it exists:
    - Raw device IDs and MACs are stored (`models.py:118`).
    - There is no retention job.
    - `UserSession` is never written.
  - The agent is built to "personalize returning visitors" (`flowtrace_agent.py:57,330`), which contradicts "no cross-visit linking".
  - The Bashundhara pitch sells demographic profiling ("Males, 18-24") and data capture tied to phone or email.
  - Game zones mean minors.
  - Visitor movement data is sent to OpenAI (US), which is a cross-border transfer.
  - There is no DPIA, privacy notice, consent flow or DPA template.
  - Bangladesh's data-protection regime (the PDP Ordinance 2025, replacing the draft PDP Act) and BTRC radio-equipment type approval or import NOC have not been assessed.
- **Why it blocks launch:** a venue's legal team will block the pilot, or a regulator or press story will. Tracking children's locations is the worst case.
- **Fix:**
  1. Get a written legal memo from Bangladeshi counsel covering PDP, BTRC type approval for 2.4 GHz devices, and minors' data.
  2. Implement the doc as code:
     - Rotate the tag-to-session ID at entry.
     - Hash with a daily salt.
     - Run a nightly job that rolls readings up into aggregates and deletes raw readings older than N days.
     - No PII fields in the schema.
  3. Strip device IDs before any LLM call; send aggregates only.
  4. Prepare a signage template, a venue DPA and a parental notice.
  5. Turn "returning visitor" features off by default.

### 7. The "Agentic Action" core feature does not exist
- **Evidence:**
  - `FlowTraceAgent` is never instantiated or imported outside its own file.
  - There is no `data_provider` implementation.
  - `AGENT_ANALYSIS_INTERVAL_SECONDS` is unused.
  - `AgentInsight` rows are never written.
  - The WebSocket never sends `type: 'insight'`.
  - The dashboard expects REST endpoints that do not exist:
    - `/analytics/zones`, `/stats/venue`, `/insights`, `/devices/{id}/trail`, `/nodes/{id}/history` (`useFlowTraceData.js:15,34,45,61,72`).
    - The real routes are `/api/v1/...`, with no `/v1` in the dashboard calls.
  - `trigger_notification` has no delivery channel. There is no way to "send a discount" to a wristband wearer.
  - `prompts.py` holds a second, unused prompt set with different insight types than the agent and the UI.
  - Running a tool-calling GPT-4o agent with up to 6 iterations per device every 30 s has unbounded cost.
- **Why it blocks launch:** the README's step 3, "Understands", and step 4, "Acts", are the differentiators, and both are absent.
- **Fix:**
  1. v1: deterministic rules compute the metrics (dwell, bounce under 60 s, congestion over threshold, zone pairings). Store them as insights.
  2. Run one batched LLM call per 15 min or per day that turns the aggregates into a plain-language report. Use structured output, aggregates only, and a daily cost cap.
  3. Deliver actions to staff, not visitors: a tablet view or WhatsApp/SMS staff alerts.
  4. Delete the per-visitor agent and the duplicate prompts.

### 8. The dashboard crashes on load and its numbers are fake
- **Evidence:**
  - `App.jsx:7` does `import useWebSocket from './hooks/useWebSocket'`, but the hook only has a named export (`useWebSocket.js:10`). This is an ES module error, so the app renders a blank page.
  - The WebSocket URL is `/ws/dashboard` (`flowtraceStore.js:155`), but the backend serves `/ws` (`main.py:100`). URLs are hardcoded to `localhost`, so the dashboard breaks on any other device.
  - It silently falls back to random mock data.
  - These values are hardcoded:
    - The "System Active" badge (`App.jsx:28-31`).
    - Stats (`StatsBar.jsx:11-13`).
    - Bounce rate and A/B results (`PopUpDashboard.jsx:9-10,44-50`).
    - Node health (`NodeHealth.jsx:6-12`).
  - `GhostTrail` and `ZoneHeatmap` are never mounted, and `ZoneHeatmap` is a placeholder.
- **Why it blocks launch:** the operator-facing product does not exist. Fake numbers in a customer demo are a credibility and legal risk.
- **Fix:**
  1. Fix the import.
  2. Derive the API and WebSocket base from `location`.
  3. Remove the mock fallback from production builds; put it behind `?demo=1` with a visible "DEMO DATA" banner.
  4. Wire every tile to a real endpoint.
  5. Mount the zone heatmap and ghost trail, or delete them.

### 9. There is no working deploy path
- **Evidence:**
  - `dashboard/Dockerfile` does not exist, but compose builds it (`docker-compose.yml:23-26`).
  - `docker-compose.popup.yml:22-24,10` builds from a root `Dockerfile` and mounts `./mosquitto.conf`. Neither exists.
  - `docker-compose.popup.yml:29-30` uses `MQTT_BROKER/MQTT_PORT`, but the code reads `MQTT_BROKER_HOST/PORT`.
  - The backend Dockerfile runs `init_db.py` at build time (`Dockerfile:10`); the import roots are broken (blocker 1).
  - The DB lives at `./flowtrace.db`, but the volume mounts `/app/data` (`docker-compose.yml:12,17`), so data is lost on container rebuild.
  - `run.py:10` runs `reload=True` in production.
  - There is no backup, monitoring, log shipping, remote access or update mechanism for edge Pis.
  - Scanner nodes have no OTA; only the gateway does.
  - `flowtrace.service` uses the deprecated `docker-compose` v1.
- **Why it blocks launch:** you cannot install at a customer site, or keep a site running.
- **Fix:**
  1. Ship one compose file with a backend image, a static dashboard served by Caddy (with TLS), and a named volume for the DB.
  2. CI builds multi-arch images (arm64 for Pi) and pushes them to GHCR.
  3. Pis pull pinned tags.
  4. Add Tailscale or similar for remote support.
  5. Add healthchecks and node heartbeat alerts to staff.
  6. Run a nightly DB backup off-device.
  7. Add scanner OTA by HTTP pull from the edge box.

### 10. Zero tests
- **Evidence:** there are no test files anywhere. The sprint's `tests/integration/day20_checklist.md` and `/demo/agent_test_prompts.py` do not exist.
- **Why it blocks launch:** blockers 1, 2 and 8 would each have been caught by a single smoke test.
- **Fix, in this order:**
  1. API smoke test: app imports, `/health`, and a POST of a recorded scanner payload persists rows.
  2. Unit tests for `rssi_to_distance`, zone assignment and dwell.
  3. Simulator-driven E2E with zone-accuracy assertions.
  4. Dashboard `vite build` in CI.
  5. Firmware compile in CI with `arduino-cli`.
  6. Gate merges on all of these.

---

## Major gaps

- **No ICP or wedge.** Three conflicting products are on offer: a BLE venue tracker, D2C pop-up analytics, and an RFID cashless tap-to-ride system for Bashundhara Playzone. The latest pitch (`bashundhara_pitch.html`) sells something with no code at all: RFID readers on 70 rides, ride activation, end-of-visit billing, a kiosk and accounts.
  - **Fix:** run 10 operator interviews, then pick one segment and one buying job. If Playzone wants RFID cashless, that is a different and arguably easier product with a clearer ROI (labor and coin handling), and RFID taps give ride analytics without RSSI.
- **No validation.**
  - No LOI, no pilot, no willingness-to-pay data.
  - Cold emails reference a nonexistent "case study" and "already speaking with venues" (`cold_emails.md:31,45`). Remove the claims.
  - Get one signed paid pilot with written success metrics before building more.
- **Unit economics are unproven.**
  - ৳15k–80k per month (`README.md:164-166`) has no basis.
  - Tag cost, loss, charging labor, install time, support visits and LLM spend are not modeled.
  - Build a per-venue P&L sheet and price from it.
- **No multi-venue or self-serve configuration.**
  - Zones are Python constants (`zone_detector.py:92`).
  - Node positions are hardcoded in `main.py:33-39` and conflict with `init_db.py`.
  - Nodes and devices have no `venue_id` scoping.
  - **Fix:** add `venues`, `zones` and `nodes` tables, a floor-plan upload with a zone-polygon editor, and tenant scoping on every query.
- **No billing or accounts.** There are no users, orgs, subscription or invoicing. For a B2B pilot, manual invoicing is fine; add accounts and RBAC before a second customer.
- **Data growth is unbounded.**
  - One `Reading` row per advertisement, in SQLite, with no retention.
  - At 500 tags × 5 nodes × 1 Hz, that is about 200M rows per day.
  - **Fix:** keep raw readings in a ring buffer in memory or Redis, persist only position or zone events at 1 Hz per device, roll up daily, and use Postgres beyond one venue.
- **Concurrency bugs.**
  - The paho thread mutates the fleet while the asyncio loop reads it, with no lock.
  - `active_websockets` raises on send to a dead socket. `main.py:77-78` aborts the broadcast to every client after one failure, and dead sockets are never removed.
  - The HTTP handler is `async` but does blocking DB I/O, which stalls the event loop.
- **Hardware is not productized.**
  - `enclosures/` and root `database/` are empty.
  - The recommended nRF51822 tags (`hardware_bom.md:94-115`) cannot run `beacon.ino` (ESP32-only), and the scanner will not recognize them unless they are reconfigured to the UUID.
  - The ESP32 beacon is too large and power-hungry for a wristband: GPIO34 battery pin (`beacon/config.h:60`) does not exist on the ESP32-C3 named in the README.
  - Scanners run on mains USB with no power-loss handling, and are provisioned by recompiling per node.
  - **Fix:** standardize on an off-the-shelf nRF52 iBeacon band with a configurable UUID and major/minor, add a provisioning CLI, and use a fixed enclosure with a PoE or USB-C PSU.
- **The LLM vendor is hard-wired.** OpenAI is the only option, with no offline fallback, even though the target is offline edge Pis with no internet (`deployment_guide.md`). The rules-first design from blocker 7 removes this dependency.
- **Docs drift.**
  - README commands are wrong (`python init_db.py`, while the file is at `database/init_db.py`).
  - The architecture lists Redis, LangChain flows and `shadow_profiles`, none of which exist.
  - The banner prints "AURA" (`setup.sh:15-20`).
  - Names mix `AURA`, `FlowTrace` and `BlankFrame`.

---

## Launch path (ordered)

1. **Week 0, pick the wedge.**
   - Do 10 operator interviews: game zones and play centers with paid entry.
   - Choose BLE zone analytics or RFID tap analytics.
   - Get one LOI for a paid 30-day pilot with 3 written success metrics.
   - Kill the D2C pop-up track, or move it to a different sensor.
   - Rewrite all marketing copy so nothing claims phone tracking or 100% coverage.
2. **Week 0, legal.** Get counsel's memo on PDP, BTRC and minors. Then write a DPA template, signage and a retention policy. Do not deploy in front of the public before this.
3. **Week 1, make it run.**
   - Fix blocker 1 (imports, sync DB, missing classes, columns).
   - Fix blocker 8 (dashboard import and URLs, real endpoints, gated mock mode).
   - Add CI with an import, build and smoke test (blocker 10, step 1).
4. **Week 1–2, one data contract.**
   - Write the versioned schema, align the scanner, backend and simulator, and use major/minor tag IDs with an owned UUID.
   - Drop MQTT and the gateway for v1.
   - Add a contract test using a real captured payload.
5. **Week 2–3, prove accuracy.**
   - Switch to zone proximity: one node per zone, continuous scanning, 1–2 Hz nRF52 tags.
   - Build the ground-truth harness and measure in a real venue at real crowd density.
   - Gate: at least 90% zone accuracy. If it fails, change sensing (more nodes, or RFID taps) before writing more software.
6. **Week 3, security and privacy as code.**
   - Node keys, dashboard auth, authenticated WebSocket, CORS allowlist and TLS.
   - Rotate all leaked secrets.
   - Rotating salted session IDs, a nightly rollup and purge, and no IDs sent to the LLM.
7. **Week 3–4, insights v1.**
   - Rule-based metrics (dwell, bounce, congestion, pairings) stored as insights.
   - One daily or 15-minute batched LLM summary with a cost cap.
   - Staff alerts via tablet or WhatsApp. No visitor-facing actions.
8. **Week 4, deployable edge box.**
   - Single compose file, arm64 images, persistent volume, Caddy TLS, remote access, healthchecks and node-offline alerts, backups, and scanner OTA.
   - Write the install SOP and tag-logistics SOP.
9. **Week 5–8, paid pilot.**
   - Deploy at the LOI venue and run a weekly report review with the operator.
   - Track the success metrics, tag loss and support hours.
10. **After the pilot.** If the metrics are met, add multi-venue tables and the zone editor, accounts and RBAC, Postgres, and billing. Then price from the real per-venue P&L and approach venue 2.


---

## Progress log (2026-10-12, Claude session)

**Done:** nothing changed in this session. No edits made.

**Next, in value order:**
1. Blocker 1: pick one import root and fix the missing classes (`PositioningFleet` -> `PositionEngine`, `VenueZoneAnalytics` -> `ZoneDetector`), `SessionLocal`/`get_db` vs `AsyncSessionLocal`/`get_session`, `node_id`/`device_id` vs `id`, the paho-mqtt 2.x `callback_api_version`, and the sync `DATABASE_URL`.
2. Fix the dashboard default import, then align the firmware payload, port and MQTT topics with the backend.
3. Mark mock data as mock in the UI, and remove the "no app, 100% footfall" claim from the pitch.


### Update 2 (supersedes "nothing changed" above; agent-made, not reviewed by a human)

**Done (agent ran it):** backend starts under uvicorn from `backend/`; `/health` OK; POST of 3 readings to `/api/v1/readings` returned `inserted: 3`; devices, node-readings and analytics GETs return data; `npm run build` passes. Changes: one import root, `PositioningFleet` added to `triangulator.py`, `ZoneDetector` wired in `main.py`, shared async `persist_reading`, routers converted to async, paho `CallbackAPIVersion.VERSION2`, `sqlite+aiosqlite` in docker-compose, `greenlet` added, dashboard named import of `useWebSocket`, default WS URL `/ws`. Marketing: "100% of footfall" and "no wristband" reworded; "DEMO DATA" labels added to `StatsBar.jsx`, `NodeHealth.jsx`, `PopUpDashboard.jsx`.

**Still broken / unchecked:**
1. `requirements.txt` does not install on Python 3.11: `langchain-community` needs numpy<2 but numpy 2.1.3 is pinned; scipy fails to build on 3.14. The agent tested with the langchain and openai lines excluded.
2. Firmware payload shape, port 8080 and MQTT topics still disagree with the backend. The scanner's batch format gets a 422, and unknown node IDs are dropped.
3. MQTT untested (no broker). Agent code still has `backend.` imports, unchecked. No position was ever seen coming out of the position loop; the WebSocket path is unchecked.
4. No tests or CI for any of this.
5. Marketing: `docs/`, `pitch_deck.md` and the strategy doc may still claim phone tracking and "no wristband".


### Update 3 (agent-made; results are the agents' own reports unless stated)

**Done:** `requirements.txt` now installs on Python 3.11 (numpy 1.26.4, scipy 1.13.1; langchain and openai moved to `requirements-agent.txt`; `pip check` clean). Both firmware `config.h` files use port 8000; the gateway subscribes to `flowtrace/nodes/+/readings`. `http_receiver.py` accepts the scanner batch format. Unknown nodes return `status: "partial"` with `unknown_nodes` instead of being dropped silently. No `backend.` imports remain in `backend/agent`. **Real bug fixed:** wrong sign in the triangulator (a tag at (3,3) came out at (-2.8,-2.8)). `backend/tests/test_e2e.py` passes (`1 passed`, ~8 s): firmware-shape POST from 3 nodes, `/ws` position near (3,3), `GET /api/v1/devices`. "How to run" added to `backend/README.md`.

**Still open:** MQTT untested (no broker), and `mqtt_server.process_reading` still handles only flat payloads, not the scanner batch. Firmware `.ino` and `.h` changes not compiled. Positions are not clamped to the room. RSSI accuracy measurement (a core claim) still does not exist. Docs outside `config.h` that mention the MQTT topic were not checked. The pitch deck and strategy doc may still claim phone tracking.


### Update 4 (agent-made; agents' own reports, not yet independently re-run)

**Done (pytest: 3 passed):** `parse_readings()` in `http_receiver.py` shared by the HTTP route and `MQTTServer.process_reading` (scanner batch or flat reading; unknown nodes logged; bad payloads rejected). `tests/test_mqtt_and_bounds.py` calls `on_message` with a fake message, no broker. Optional `VENUE_WIDTH_M` and `VENUE_HEIGHT_M` in `config.py`; positions clamp to them when set. `docs/30_day_sprint.md` 8080 -> 8000. `docs/pitch_deck.md` and `marketing/online_brand_strategy.md` reworded: only opt-in FlowTrace tags are detected.

**Still open:** MQTT against a real broker; docs say WebSocket `/ws/positions` but the backend serves `/ws`; `marketing/bashundhara_pitch.html` not searched for phone claims; RFID tap-to-ride has no code; firmware not compiled; no RSSI accuracy data.


### Update 5 (agent-made, round 6; agents' own reports unless marked)

**Done (agent runs: backend pytest 7 passed; `npm run build` OK; tools tests 2 passed):** dashboard store has `connection` = connected / demo / offline; demo data only after a failed connect; sticky `ConnectionBanner.jsx`; when connected, a 5 s poll of `/api/v1/nodes`, `/devices`, `/analytics/summary`, `/insights` feeds `StatsBar`, `NodeHealth`, `PopUpDashboard`. `backend/agent/service.py` starts the AI agent only if `OPENAI_API_KEY` is set; `GET /api/v1/insights` returns the latest report or 503. New tests for insights (LLM mocked), bad-payload 422, partial unknown nodes, duplicate batch, 2-zone detector. RSSI tooling: `tools/calibrate_rssi.py`, `tools/evaluate_accuracy.py`, `tools/synth.py`, tests, `docs/field_test_protocol.md`. `PositioningFleet` reads optional `RSSI_CALIBRATION_JSON`.

**Still open:** no real RSSI measurements exist, so the accuracy claim is unproven; the protocol's accuracy thresholds are the agent's own judgement and need owner sign-off. Pop-up bounce rate and A/B show "n/a" live (no endpoint). Duplicate batches are inserted twice (no dedupe). Hesitation signals and notifications in the agent adapter are stubs. Real LLM path and the dashboard in a browser unchecked. Dashboard has no test runner. One agent reported `pip install -r requirements.txt` failing in its environment, while the independent verification install passed; re-check. RFID tap-to-ride still has no code. MQTT against a real broker untested. Firmware not compiled.


### Update 6 (agent-made: independent verification, security review, fixes; agents' own reports unless marked)

**Independent re-run (fresh venvs) confirmed:** backend 7 tests, tools 2, dashboard build. **Python version:** `requirements.txt` installs only on Python 3.11 or 3.12. On Python 3.14, `scipy==1.13.1` has no wheel and the build fails (no Fortran compiler). Use `python3.11 -m venv` (check the Dockerfile pin too; not checked).

**Security review found (fixed, 11 tests pass in a fresh 3.11 venv):** every endpoint was unauthenticated; node-readings `limit` was unbounded; each new device ID grew memory forever; MQTT trusted the payload's node ID. Fixes: `INGEST_API_KEY` (header `X-API-Key`) guards POST `/readings`; if unset, writes return 503 unless `DEBUG` or `DEV=1`, with a loud startup warning; optional `READ_API_KEY` guards all GET routes, `/insights` and `/ws` (header or `?key=`), open if unset; constant-time compare; `limit` capped at 1000; idle devices evicted after `DEVICE_TTL_SECONDS` (600) and tracked devices capped at `MAX_TRACKED_DEVICES` (5000); MQTT takes the node ID from the topic, drops mismatches, and uses `MQTT_USERNAME` and `MQTT_PASSWORD`.

**ACTION NEEDED (breaking):** the firmware does not send `X-API-Key`, so with `INGEST_API_KEY` unset the backend now rejects firmware POSTs (503) outside debug. Add the key header to the firmware HTTP code and `config.h`, and set `INGEST_API_KEY` in production. The dashboard needs the read key via a Vite env if `READ_API_KEY` is set (dashboard code not changed). **Still open:** existing Device DB rows are never purged; the `/ws` test uses a broad `except`.


**Correction to Update 6 (firmware):** `firmware/scanner` and `firmware/gateway` now send `X-API-Key` (new `API_KEY` define in each `config.h`, placeholder `"CHANGE_ME"`; it must equal the backend's `INGEST_API_KEY`). **Not compiled or flashed**, so treat it as untested. `backend/README.md` now states the Python 3.11/3.12 requirement.


---

## Update 8: go-to-market scoring (2026-10-12)

**Score: 20% (was 8%).** Stage: Software prototype, hardware unvalidated.

**Cap:** 20: the core accuracy claim is unmeasured, the firmware has never been compiled, and there is no customer.

**Dimension scores (0-10):** Product 4, Quality 5, Security 5, Legal 2, Market 1, Ops 2, Honesty 5. Rubric and the other five projects: `../GO_TO_MARKET_SCORECARD.md`.

**Basis and limits:** my judgement from this file's audit, the agents' reports, and independent re-runs of tests and builds. No real-device, real-user or real-host testing has happened, and nothing is committed. Agent-written code has had no human review. Treat the score as +/- 10 points.

### Gaps and flaws, ranked

1. **Accuracy is unproven.** No RSSI measurements exist. The calibration and evaluation tools and the field protocol exist, but the protocol's accuracy thresholds are an agent's own judgement and need your sign-off.
2. **Three different products are being sold** (BLE game-zone positioning, app-free pop-up analytics, RFID tap-to-ride). RFID has no code at all.
3. **Firmware never compiled or flashed.** It now sends an `X-API-Key`; nobody has run it against the backend.
4. **MQTT path never run against a real broker.** The Docker stack has not been run.
5. **Auth defaults:** without `INGEST_API_KEY` writes return 503 outside debug (by design); `READ_API_KEY` is optional so reads and `/ws` are open if unset; the dashboard has no way to send a read key yet.
6. **Privacy and law.** BLE tracking of people has no legal or privacy review; phones are not reliably trackable (MAC randomization, iOS background limits), and some docs and `marketing/bashundhara_pitch.html` may still imply otherwise.
7. **Gaps in the product:** duplicate batches are inserted twice; pop-up bounce rate and A/B show n/a live; node health is only an active flag; the AI agent's hesitation signals and notifications are stubs; existing Device rows are never purged.
8. Needs Python 3.11 or 3.12; a plain install fails on 3.14.

### What to do next, in order

1. **You:** decide ONE product and one first customer segment. Delete or park the other two.
2. **You:** buy or borrow 4-6 nodes, compile and flash the firmware, set `API_KEY` and `INGEST_API_KEY`, and run the backend against real nodes. Fix what breaks.
3. **You:** run `docs/field_test_protocol.md`; review and sign off its thresholds; use `tools/calibrate_rssi.py` and `tools/evaluate_accuracy.py`; publish the real accuracy number, good or bad.
4. **Code:** add MQTT broker to the compose stack and run an end-to-end test; dedupe batches by node and timestamp; wire a dashboard read key.
5. **You:** legal and privacy review of tag-based tracking in a public venue, and a consent signage plan.
6. **You:** talk to 3 venue operators about what they would pay for; only then build billing or multi-venue support.
7. **Code:** make the module-level `position_engine` use calibration parameters; purge old Device rows.

### Update 9 (2026-10-12, stopped at the 70% usage ceiling)

**Done this round:** retro guardrails (`scripts/check.sh`, pre-commit hook `.githooks/pre-commit`, CI workflow, `AGENTS.md`, `CODING_STANDARDS.md`); orphaned worktrees removed (Suggest.Bike); all work committed and pushed to `origin/main`. Usage mirror `../usage.md` is live (status line writes the 5-hour and 7-day percentages); read it before starting a round.

**I was in the middle of:** nothing half-done. The last action was this log. No uncommitted work remains apart from this file.

**Not verified:** the GitHub CI workflows have never run; the pre-commit hook has never blocked a real commit; no real-device, real-user or real-host testing.
**Next, first:** buy nodes, compile and flash firmware with `API_KEY` and `INGEST_API_KEY` set, run the field protocol; decide ONE product (Update 8).

### Update 10 (2026-10-15, agent round)

**Done (code items 4 and 7 of "What to do next"; commit 7907155):**
- **MQTT, run for real:** the compose stack already had `eclipse-mosquitto:2.0`. New opt-in test `backend/tests/test_mqtt_broker_e2e.py` (`MQTT_E2E_BROKER=localhost:1883`) starts the backend in-process, publishes a firmware-shaped batch to the compose broker, and finds it stored exactly once: passed. Also ran the compose `mosquitto` + `backend` containers (backend on host port 8010, because 8000 was taken): the container connected to `mosquitto:1883`, and 3 publishes of one batch gave 1 stored row. check.sh skips the broker test (no broker in CI).
- **Dedupe:** readings store the node's `ts_ms`; unique (node, device, `ts_ms`); a retried batch returns `duplicates: N`. Readings without `ts_ms` are not deduped. `init_db` upgrades older DBs (checked on a hand-made old table).
- **Dashboard read key:** `VITE_READ_API_KEY` is sent as `X-API-Key` and as `?key=` on `/ws`. The key ships in the JS bundle. Build passes; not run in a browser.
- **Calibration:** `PositionEngine` loads `RSSI_CALIBRATION_JSON`, so the module-level `position_engine` uses it too (it is still unused by app code).
- **Purge:** Device rows unseen for `DEVICE_RETENTION_DAYS` (30) are deleted hourly with their readings, positions and sessions.
- **Test bug found:** in reverse order the backend tests wrote to the real `backend/flowtrace.db`. Fixed in conftest. That local DB may contain test rows.

**Still open:** the compose `dashboard` service has no Dockerfile, so a plain `docker compose up` fails; `ts_ms` resets on node reboot (rare false duplicate); upsert is SQLite-only; `dashboard/src/hooks/useFlowTraceData.js` is unused and sends no key. All Update 8 "You" items remain.

### Update 11 (2026-10-16, agent round)

- **CI hang:** the last two `check` runs never finished (one held the runner 3 h 49 min before I cancelled it). The log stops at "backend tests"; the same suite passes here in 3 s in both orders, so the cause is CI-only and still unknown. The likely spot is `tests/test_e2e.py`, whose `ws.receive_json()` has no timeout and waits for a broadcast that only comes once the fleet holds a position. Changes: that test now waits at most 10 s for TAG_1's position and fails with what the fleet holds; `backend/pytest.ini` sets `faulthandler_timeout = 60` (any blocked test dumps every thread's stack); the workflow job has `timeout-minutes: 20`. The next CI run should either pass or show where it blocks. Pushing the workflow file needs a token with the `workflow` scope.
- **Docker:** `dashboard/Dockerfile` added (Node build, nginx on :3000; `VITE_READ_API_KEY` is a build arg, since Vite bakes it in) plus `.dockerignore`; compose passes `READ_API_KEY` as that arg and drops the unused runtime `VITE_API_URL`. Not built: Docker Desktop did not start on this Mac. `npm run build` passes.
- Deleted the unused `dashboard/src/hooks/useFlowTraceData.js` (Update 10 "Still open").
- Proof: `scripts/check.sh` passes all 9 steps locally.

