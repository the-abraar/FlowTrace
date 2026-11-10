# FlowTrace: what this lab taught

FlowTrace was BLE venue analytics for game zones: ESP32 scanner nodes hear wristband tags, a Python backend turns signal strength into positions, zones and dwell times, and a Vite dashboard shows them. It is frozen until a game-zone operator agrees to a free one-day install and names a monthly price of at least BDT 5,000 (deadline 15 Jan 2027), otherwise it is archived with this file and the demo.

State on 2026-11-10: 56 commits on `main` (2026-10-09 to 2026-11-09), the backend, dashboard and firmware build and their tests pass, and **no node has ever been flashed or installed**. Every position this project has produced came from simulated readings. Sources below are this repo's `judge.md` (the audit log) unless another file is named.

## Numbers

| What | Value | Source |
|---|---|---|
| Commits on `main` | 56 | `git rev-list --count origin/main` at `2268ae5` |
| Readiness at first audit / after fixes | 8% / 20% | `judge.md` Verdict, Update 8 |
| Hardware BOM for the minimum demo (3 nodes, 10 tags) | ~17,140 BDT | `docs/hardware_bom.md` §8 |
| Spent on hardware | 0 BDT | nothing bought or flashed (`judge.md`, firmware update: "nothing has been flashed") |
| Firmware flash use (scanner / gateway / beacon) | 87% / 80% / 85% | `judge.md`, firmware update (arduino-cli, ESP32 core 2.0.17) |
| Samples per node per tag, as configured | ~1 every 5-10 s | `judge.md` blocker 4 (beacon 100 ms per 5 s, scanner 50% duty, 9 of 10 s) |
| Path-loss exponent: backend default vs own calibration doc | 2.0 vs 3.0-3.5 | `backend/config.py`, `docs/rssi_calibration.md` |
| Demo zone depth | 3 m | `backend/positioning/zone_detector.py` `VENUE_ZONES` |
| Replay: backend zone = scripted zone | 74.6% of 536 samples | `demo/data/summary.json` (simulated, see below) |
| Replay: position error median / p90 | 1.44 m / 2.83 m | `demo/data/summary.json` (simulated) |
| Replay: finished zone visits, backend vs script | 119 vs 42 | `demo/data/summary.json` (simulated) |
| Replay: bounce rate, backend vs script | 99.2% vs 85.7% | `demo/data/summary.json` (simulated) |
| Measured accuracy in a real room | none | no field test has been run |
| Operators asked | 0 | no LOI, pilot or interview recorded |

## 1. Physics first, software second

The product promise (zone dwell, bounce, A/B layout splits) depends on putting a tag in the right 3 m zone. The audit estimated 2-5 m of trilateration error in a crowded venue (an estimate, never measured here), and this design samples each tag about once every 5-10 s per node. The code also assumes free-space propagation (`n = 2.0`) while its own calibration doc says crowded venues are 3.0-3.5. None of that needed code to find out; it needed one afternoon with two ESP32s and a tape measure, and that afternoon never happened.

The replay in `demo/` shows the effect even without a crowd. The simulator's readings use `n = 2.2` with 4 dB noise; the backend inverts them with `n = 2.0`. On that clean, crowd-free simulation the backend put the tag in the scripted zone 74.6% of the time, with 1.44 m median and 2.83 m p90 position error. Worse, position jitter near zone edges split stays into short visits: the backend logged 119 finished zone visits where the script made 42, so its bounce rate read 99.2% against 85.7% for the scripted truth (zone changes have no hysteresis). A real room would be worse, not better. Lesson: measure the sensor in the target setting before building positioning, dashboards or AI on top of it. The audit's own fix was to drop trilateration for one-node-per-zone proximity.

## 2. Bugs were found only when something ran

"Build passes" and "tests pass" claims hid bugs that the first real run exposed:

- The triangulator had a sign error: a tag at (3, 3) came out at (-2.8, -2.8) (Update 3, first end-to-end test).
- The dashboard rendered a blank page, live and demo, since `InsightPanel` called `require('react')` in an ES module; "build passes" never caught it, a headless browser did (Update 12).
- After a backend drop, the store swapped real data for mock data within ~3 s while the banner still said OFFLINE (Update 12).
- The live map was drawn upside down: north nodes at the bottom (Update 13).
- The scanner's fixed 8 KB JSON buffer overflowed at ~85 of 100 readings, so the backend refused every batch with 422 and the firmware retried the same failing batch forever; NimBLE's `wantDuplicates` flag was inverted, giving one reading per tag per 10 s window (firmware update, host-checked with ArduinoJson).
- The simulator posted from node IDs the backend does not know, and the backend answered 200 `partial` and stored nothing (fixed in Update 16). The scanner firmware still defaults to `NODE_ID "NODE_A"` (`firmware/scanner/config.h`), which has the same effect on real hardware.
- CI hung for 3 h 49 min on TestClient shutdown (Updates 11-12).

Lesson: a smoke run (start it, send one reading, look at the screen) is worth more than another unit test, and should come first.

## 3. Security lessons

- Every endpoint, including the `/ws` stream of every tracked person's position, started unauthenticated (blocker 5, Update 6). Writes now need `INGEST_API_KEY` and fail closed; reads and `/ws` are still open unless `READ_API_KEY` is set, and the backend says so at startup.
- Default passwords for the gateway OTA, web portal and hotspot were committed, and the MQTT broker allowed anonymous clients on a published port. All replaced by `CHANGE_ME` plus a build guard, env vars and broker auth (Update 15). Anything committed to a public repo should be treated as leaked and rotated.
- `VITE_READ_API_KEY` ships inside the dashboard's JS bundle (Update 10): a read key in a browser app is not a secret.
- The people tracked in a game zone are often children. The privacy doc promised salted IDs, aggregation and a 30-day purge that the code did not implement at first (blocker 6); a Device purge exists now, the legal review does not.

## 4. A pitch before an operator

Three different products were pitched before any operator was asked about one: BLE positioning for game zones, app-free pop-up analytics, and an RFID tap-to-ride system with no code (audit, "Major gaps"). The pitch copy claimed "100% of footfall, no app, no wristband", which the hardware cannot do (only FlowTrace tags are heard; phones randomise BLE MACs). The README prices tiers at ৳15,000-80,000+/month with no cost model, and `marketing/cold_emails.md` still says "already speaking with forward-thinking venues" and offers a case study that does not exist. Lesson: one operator conversation decides the wedge; pricing and copy come after it.

## 5. 17,140 BDT planned, 0 spent

The BOM for the smallest useful demo is about 17,140 BDT (3 ESP32 nodes, 10 nRF51822 wristbands). That was never spent, and no node was flashed, so 56 commits of software sit on an untested sensor. The BOM also does not fit the code: the recommended nRF51822 tags cannot run `beacon.ino` (ESP32-only), and the beacon's battery pin does not exist on the ESP32-C3 the README names (audit, "Hardware is not productized").

## What to do differently

1. Week 1: two nodes, one tag, a tape measure; publish the measured zone accuracy, good or bad.
2. In parallel: talk to five operators; pick one buyer and one job.
3. Only then write the backend, starting with a smoke run, not a feature list.
4. Treat every claim (copy, CV, cold email) as a test that needs a source before it ships.

## The demo

`demo/index.html` replays 5 minutes of the backend tracking 4 scripted tags on the `VENUE_ZONES` floor plan (north up), with the scripted truth drawn beside each position, dwell bars, and the backend's own bounce rate and A/B split. It is labelled as simulated on the page. Re-record with `demo/tools/record_replay.py` (usage in its docstring) against a local backend with a temp SQLite DB.
