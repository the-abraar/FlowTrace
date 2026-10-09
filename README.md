# 🌐 Project FlowTrace — BlankFrame Technologies

> **"The Invisible Intelligence Layer"**  
> A Local Positioning System (LPS) + Agentic Analytics Engine for physical venues.

[![Status](https://img.shields.io/badge/Status-30--Day%20Sprint-orange)]()
[![Stack](https://img.shields.io/badge/Stack-ESP32%20%2B%20Python%20%2B%20LLM-blue)]()
[![Target](https://img.shields.io/badge/Target-Game%20Zones%20%2F%20Malls-purple)]()

---

## What is FlowTrace?

FlowTrace is a passive, friction-free system that:
1. **Detects** visitor movement using BLE signals from ESP32 nodes hidden in a venue
2. **Triangulates** their position in real time using RSSI-based ranging
3. **Understands** their intent using an LLM-powered agentic engine
4. **Acts** — triggering notifications, discounts, crowd alerts automatically

**No app required. No QR codes. Just walk.**

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        VENUE FLOOR                              │
│                                                                 │
│  [BLE Tag / Wristband]  ──RSSI──►  [Scanner Node A]            │
│          │                         [Scanner Node B]  ──WiFi──► │
│          └────────────────────────► [Scanner Node C]            │
└─────────────────────────────────────────────────────────────────┘
                                              │
                                     HTTP POST / MQTT
                                              │
                              ┌───────────────▼──────────────┐
                              │      FLOWTRACE BACKEND SERVER      │
                              │  ┌─────────┐ ┌────────────┐  │
                              │  │Ingestor │ │Triangulator│  │
                              │  └────┬────┘ └─────┬──────┘  │
                              │       │             │         │
                              │  ┌────▼─────────────▼──────┐ │
                              │  │     SQLite Database      │ │
                              │  └────────────┬─────────────┘ │
                              │               │               │
                              │  ┌────────────▼─────────────┐ │
                              │  │    FLOWTRACE AGENT (LangChain) │ │
                              │  │  "User is hesitating at   │ │
                              │  │   VR zone. Send discount."│ │
                              │  └────────────┬─────────────┘ │
                              └───────────────┼───────────────┘
                                              │ WebSocket
                              ┌───────────────▼──────────────┐
                              │     FLOWTRACE DASHBOARD (React)    │
                              │  Live Map | Ghost Trails      │
                              │  Insights | Zone Heatmap      │
                              └──────────────────────────────┘
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- Arduino IDE 2.x (for firmware)
- ESP32 boards ×3 minimum (scanner nodes)
- ESP32 or nRF51822 (for BLE tags/beacons)

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your OPENAI_API_KEY
python init_db.py
python run.py
```

### 2. Dashboard

```bash
cd dashboard
npm install
npm run dev
# Open http://localhost:5173
```

### 3. Firmware

See [`firmware/README.md`](firmware/README.md) for flashing instructions.

---

## Project Structure

```
flowtrace/
├── firmware/
│   ├── beacon/          # BLE beacon (wristband/tag firmware)
│   ├── scanner/         # BLE scanner nodes (deployed in venue)
│   └── gateway/         # WiFi gateway with OTA + web config
│
├── backend/
│   ├── ingestion/       # MQTT + HTTP data receivers
│   ├── database/        # SQLAlchemy models + migrations
│   ├── positioning/     # Triangulation + Kalman filter + Zone detection
│   ├── agent/           # LangChain agentic engine
│   └── api/             # FastAPI REST API + WebSocket
│
├── dashboard/           # React + Vite + D3 real-time UI
│
├── docs/
│   ├── 30_day_sprint.md        # Day-by-day execution plan
│   ├── hardware_bom.md         # Bill of materials (BDT prices)
│   ├── venue_mapping_guide.md  # How to set up in a new venue
│   ├── pitch_deck.md           # Bashundhara Group pitch content
│   ├── deployment_guide.md     # Production deployment
│   ├── rssi_calibration.md     # RSSI tuning deep dive
│   └── privacy_and_ethics.md   # Data ethics framework
│
├── scripts/
│   ├── setup.sh         # One-command environment setup
│   └── simulate.py      # Simulates BLE readings for testing
│
└── enclosures/
    └── node_enclosure/  # 3D print files for hidden node housing
```

---

## The 30-Day MVP Goal

By Day 30, you will have:
- ✅ 3–5 live scanner nodes deployed in a test room
- ✅ Real-time position estimation on a live map
- ✅ Ghost Trail visualization of any visitor's path
- ✅ LLM agent generating actionable insights automatically
- ✅ A working demo for the Bashundhara Group pitch

---

## Key Concepts

| Term | Meaning |
|------|---------|
| **Frame Node** | An ESP32 scanner hidden in the venue |
| **FlowTrace Tag** | The BLE beacon given to a visitor (wristband or phone) |
| **Shadow Profile** | Anonymous movement record for one visitor session |
| **Ghost Trail** | Visualization of a visitor's historical path |
| **Agentic Action** | An automated response triggered by the AI agent |

---

## Business Model

| Tier | Price (BDT/month) | Nodes | Users | Features |
|------|-------------------|-------|-------|---------|
| Starter | ৳15,000 | 5 | 200/day | Live map, basic insights |
| Growth | ৳35,000 | 15 | 1000/day | + Ghost trails, agent alerts |
| Enterprise | ৳80,000+ | Unlimited | Unlimited | + Custom AI, API access |

**Hardware installation fee:** ৳25,000–৳60,000 one-time (covers nodes + setup)

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Sensor nodes | ESP32 (Arduino C++) |
| BLE tags | ESP32-C3 / nRF51822 wristbands |
| Backend | Python 3.11, FastAPI, asyncio |
| Database | SQLite (dev) → PostgreSQL (prod) |
| Positioning | Log-distance RSSI + Kalman filter + WLS triangulation |
| AI Agent | LangChain + GPT-4o |
| Dashboard | React 18, Vite, TailwindCSS, D3.js |
| Deployment | Docker Compose on Raspberry Pi 4 / VPS |

---

## Status

| Phase | Status |
|-------|--------|
| Phase 1: Hardware & Firmware | 🟡 In Development |
| Phase 2: Backend + Agent | 🟡 In Development |
| Phase 3: Dashboard | 🟡 In Development |
| Phase 4: Demo Prep | ⏳ Pending |

---

*BlankFrame Technologies — "The frame no one sees, the intelligence everyone feels."*
