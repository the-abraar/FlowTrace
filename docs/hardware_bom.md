# Project FlowTrace — Hardware Bill of Materials
**BlankFrame Technologies** | Engineering Reference  
**Version:** 1.0 | **Target Configuration:** 3-Node Scanner + 10 Beacon Tags

> [!NOTE]
> All prices are in **Bangladeshi Taka (BDT)** and reflect observed market rates at **Patuatuly Electronics Market and Elephant Road, Dhaka** as of late 2025. Prices fluctuate ±15% with USD/BDT exchange rate and import availability. Always verify before purchasing.

---

## 1. Scanner Nodes (Fixed Infrastructure)

Scanner nodes are powered, wall-mounted units that continuously scan for BLE advertisements from beacon tags.

### 1.1 ESP32 DevKit v1 (Primary MCU — Scanner Nodes)

| Attribute | Specification |
|-----------|--------------|
| **Chip** | Espressif ESP32-D0WDQ6 (dual-core Xtensa LX6, 240 MHz) |
| **RAM** | 520 KB SRAM |
| **Flash** | 4 MB (some boards: 8 MB) |
| **WiFi** | 802.11 b/g/n 2.4 GHz |
| **Bluetooth** | BT 4.2 + BLE |
| **GPIO Pins** | 30 (18 usable on DevKit footprint) |
| **Operating Voltage** | 3.3V logic, 5V USB input |
| **Current Draw** | ~160 mA active WiFi + BLE scan |
| **USB-Serial** | CP2102 or CH340 (board variant dependent) |
| **Board Dimensions** | 55mm × 28mm |
| **Antenna** | PCB trace antenna (onboard) |

**Role in FlowTrace:** Runs BLE scanner firmware. Scans all 2.4 GHz BLE advertisements every 100ms, parses device MAC + RSSI, POSTs to backend API over WiFi.

| Item | Unit Price (BDT) | Qty (3-node setup) | Qty (Full 5-node) | Total (3-node) |
|------|------------------|--------------------|---------------------|----------------|
| ESP32 DevKit v1 | 450–550 | 3 | 5 | ~1,500 |

**Where to buy in Dhaka:**
- **Patuatuly Market (পাটুয়াটুলি):** Row of shops near the BRTC bus stop. Ask specifically for "ESP32 DevKit v1" — many shops stock both genuine Espressif and Ai-Thinker variants. Ai-Thinker is acceptable.
- **Elephant Road (হাতিরপুল):** Shops on the ground floor of Multiplan Centre carry ESP32 consistently.
- **Online:** Techshopbd.com, Roboticsbd.com (add ~BDT 100–200 for delivery)

> [!TIP]
> Buy 2 extra units as spares. ESP32 boards are occasionally DOA (~5% failure rate on budget batches). Test each with `pio run -e blink -t upload` before committing to production firmware.

---

### 1.2 Optional: ESP32-S3 DevKit (Upgrade Path)

For venues requiring longer BLE range or Matter/Thread support in future:

| Attribute | Specification |
|-----------|--------------|
| **Chip** | ESP32-S3 dual-core Xtensa LX7, 240 MHz |
| **BLE** | BLE 5.0 (vs 4.2 on standard ESP32) |
| **Range** | ~20% better indoor range vs ESP32 |
| **Price** | BDT 700–900 |

Not required for Day 30 demo. Useful for Phase 2 productization.

---

## 2. Beacon Tags (Mobile, Worn by Visitors)

Beacon tags are small, low-power devices worn by visitors (wristband, lanyard, or clipped to token). They broadcast BLE advertisements that scanner nodes detect.

### 2.1 Option A — ESP32 WROOM-32 as Beacon (DIY)

| Attribute | Specification |
|-----------|--------------|
| **Module** | ESP32-WROOM-32D (18.0mm × 20.0mm × 3.2mm) |
| **Chip** | ESP32-D0WD dual-core |
| **RAM** | 520 KB SRAM |
| **Flash** | 4 MB |
| **BLE TX Power** | -12 dBm to +9 dBm (configurable) |
| **Antenna** | PCB trace (integral to module) |
| **Operating Voltage** | 3.0V–3.6V |
| **Sleep Current** | 10 µA (deep sleep) |
| **Active BLE Adv Current** | ~80 mA @ 3.3V |
| **Dimensions** | 18mm × 25.5mm (module only) |

**Beacon firmware behavior:**
- Advertise BLE packet every 500ms (BDT optimal: 100–1000ms)
- Packet contains: Device UUID (32-bit, set at flash time) + Battery voltage
- Deep sleep 400ms between advertisements to extend battery life
- At 500ms interval + 80mA active + 10µA sleep: **avg current ≈ 40mA**, giving **~12.5 hours on 500mAh battery**

| Item | Unit Price (BDT) | Qty (10-tag setup) | Total |
|------|------------------|--------------------|-------|
| ESP32-WROOM-32 module (bare) | 380–450 | 10 | ~4,200 |

**Where to buy:** Patuatuly, same shops as DevKit. Ask for "WROOM-32 module" (the bare SMD module, not a full devkit). Soldering required.

---

### 2.2 Option B — nRF51822-Based BLE Wristband Tags (Recommended for Demo)

Pre-built BLE wristband tags based on Nordic Semiconductor nRF51822:

| Attribute | Specification |
|-----------|--------------|
| **Chip** | Nordic nRF51822 (ARM Cortex-M0, 16 MHz) |
| **BLE** | BLE 4.0 |
| **TX Power** | -20 dBm to +4 dBm |
| **Sleep Current** | 0.6 µA (System Off) |
| **Active Current** | ~15 mA during BLE advertisement |
| **Battery** | Integrated 100mAh LiPo |
| **Battery Life** | ~72 hours continuous BLE advertising at 1 Hz |
| **Form Factor** | Wristband (child-safe clasp, one-size silicone) |
| **IP Rating** | IP54 (sweat resistant) |
| **Programmable?** | Yes — SWD port accessible inside band |

**Why prefer this for demo:** Looks professional (wristband = familiar game zone experience). Pre-built → no soldering → faster Day 1 readiness. Children can wear them safely.

| Item | Unit Price (BDT) | Qty | Total |
|------|------------------|-----|-------|
| nRF51822 wristband tag (AliExpress via Dhaka forwarding agent) | 800–1,200 | 10 | ~10,000 |
| (Alternative) Generic iBeacon tag, CR2032 | 400–600 | 10 | ~5,000 |

> [!WARNING]
> Generic iBeacon tags (CR2032 powered) are convenient but have a fixed, non-configurable Device UUID on many cheap models. Verify you can set a custom UUID via the vendor app before purchasing 10 units.

**Where to buy in Dhaka:**
- Order via a Dhaka-based AliExpress forwarding agent (e.g., Chaldal Import, various agents in Dhanmondi)
- Lead time: 7–14 days
- Alternative: Check `technoshopbd.com` for iBeacon tags

---

## 3. Power Components

### 3.1 3.7V LiPo Battery — 500mAh (for DIY Beacons)

| Attribute | Specification |
|-----------|--------------|
| **Chemistry** | Lithium Polymer |
| **Nominal Voltage** | 3.7V |
| **Capacity** | 500mAh |
| **Max Discharge** | 1C (500mA) |
| **Dimensions** | ~60mm × 30mm × 5mm (varies by supplier) |
| **Connector** | JST PH 2.0mm (standard) |

Life estimate with ESP32 WROOM-32 beacon at 500ms advertisement interval: **~12 hours** (charge daily).

| Item | Unit Price (BDT) | Qty | Total |
|------|------------------|-----|-------|
| 3.7V 500mAh LiPo | 200–300 | 10 | ~2,500 |

**Where to buy:** Patuatuly — shops specializing in mobile phone batteries often carry bare LiPo cells. Specify "500mAh flat LiPo with JST connector." Also available at RC hobby shops near Gulshan.

---

### 3.2 TP4056 LiPo Charging Module

| Attribute | Specification |
|-----------|--------------|
| **IC** | TP4056 (with or without DW01A protection IC) |
| **Input** | 5V Micro-USB or USB-C (depending on board revision) |
| **Charge Current** | 1A (adjustable via R_prog resistor) |
| **Charge Voltage** | 4.2V |
| **Protection** | Overcharge, over-discharge, short-circuit (on models with DW01A) |
| **Efficiency** | Linear charger — heat dissipation at high current |
| **Indicators** | Red LED: charging, Blue LED: charge complete |

> [!IMPORTANT]
> Always purchase the **TP4056 + DW01A combo module** (has an extra protection IC chip visible on the board). Pure TP4056 boards without the protection IC will not disconnect the load when the battery is critically discharged, which destroys LiPo cells.

| Item | Unit Price (BDT) | Qty | Total |
|------|------------------|-----|-------|
| TP4056 + DW01A module (Micro-USB) | 25–40 | 15 | ~525 |

**Where to buy:** Patuatuly — every electronics component shop. Buy 15 (10 for beacons + 5 for scanner node backup power).

---

### 3.3 18650 Li-ion Cell (for Scanner Node Battery Backup)

For scanner nodes that need to stay online during power cuts:

| Attribute | Specification |
|-----------|--------------|
| **Chemistry** | Lithium Ion |
| **Nominal Voltage** | 3.7V |
| **Capacity** | 2,500–3,400mAh |
| **Recommended Brand** | Panasonic NCR18650B, Samsung 25R, or LG HG2 |
| **Warning** | Avoid unbranded cells claiming > 5000mAh — these are counterfeit |

| Item | Unit Price (BDT) | Qty | Total |
|------|------------------|-----|-------|
| 18650 cell (genuine Samsung 25R or Panasonic) | 350–500 | 5 | ~2,000 |

**Where to buy:** Patuatuly (laptop battery repair shops) or IDB Bhaban. Always test capacity with a hobby charger before trusting.

---

## 4. Indicators and Passives

### 4.1 RGB LEDs (Status Indicators on Scanner Nodes)

| Attribute | Specification |
|-----------|--------------|
| **Type** | Common cathode RGB LED, 5mm through-hole |
| **Forward Voltage** | Red: 2.0V, Green: 3.2V, Blue: 3.2V |
| **Forward Current** | 20mA max per channel |

**FlowTrace node status colors:**
- 🔵 Blue pulsing: Scanning, no backend connection
- 🟢 Green solid: Scanning, connected to backend
- 🟡 Yellow: Scanning, backend reachable but no tags seen
- 🔴 Red: Error / firmware crash

| Item | Unit Price (BDT) | Qty | Total |
|------|------------------|-----|-------|
| 5mm RGB LED (common cathode) | 5–8 each | 20 | ~140 |

### 4.2 Current-Limiting Resistors

For 3.3V GPIO driving RGB LED at ~5mA (dim but visible):
- R = (3.3V - 2.0V) / 0.005A = **260Ω** → use **270Ω** (red channel)
- R = (3.3V - 3.2V) / 0.005A = **20Ω** → use **22Ω** (green, blue channels)

| Item | Unit Price (BDT) | Qty | Total |
|------|------------------|-----|-------|
| Resistor pack 270Ω, 22Ω (100pcs each) | 30–50/pack | 2 packs | ~80 |

### 4.3 Decoupling Capacitors

100nF ceramic capacitors on every power rail near the ESP32 VCC pin.

| Item | Unit Price (BDT) | Qty | Total |
|------|------------------|-----|-------|
| 100nF ceramic capacitor (0.1µF) | 2–3 each | 30 | ~80 |

---

## 5. Enclosures

### 5.1 ABS Plastic Junction Box (Scanner Nodes)

| Attribute | Specification |
|-----------|--------------|
| **Material** | ABS plastic, grey or white |
| **Dimensions** | 100mm × 68mm × 50mm (fits ESP32 DevKit + TP4056 + 18650) |
| **IP Rating** | IP65 with proper sealing (gasket included on better models) |
| **Mounting** | External flanges with 4mm holes |
| **Available colors** | Grey, white (white preferred for aesthetics) |

| Item | Unit Price (BDT) | Qty | Total |
|------|------------------|-----|-------|
| ABS junction box 100×68×50mm | 80–130 | 5 | ~550 |

**Where to buy:** Patuatuly — shops selling electrical fittings (near the transformer and meter shops in the lower market rows). Also available in larger quantities from importers in Bangabazar area.

---

### 5.2 Wristband Tag Holder / Lanyard Case (DIY Beacons)

If using ESP32 WROOM-32 as DIY beacon (not pre-built wristband):

| Item | Unit Price (BDT) | Qty | Total |
|------|------------------|-----|-------|
| Clear ABS snap-fit case 35×55×12mm | 60–90 | 10 | ~750 |
| Breakaway lanyard (safety release) | 30–50 | 10 | ~400 |

---

## 6. Connectivity and Cabling

### 6.1 USB-A to Micro-USB Power Cables (1m)

For powering scanner nodes from wall adapters.

| Item | Unit Price (BDT) | Qty | Total |
|------|------------------|-----|-------|
| Micro-USB cable 1m | 80–120 | 5 | ~500 |
| 5V/2A USB wall adapter | 150–200 | 5 | ~875 |

### 6.2 Dupont Jumper Wires

For prototyping connections between ESP32 and LEDs / TP4056 modules.

| Item | Unit Price (BDT) | Qty | Total |
|------|------------------|-----|-------|
| Dupont wire pack (M-M, M-F, F-F, 40 pcs each) | 80–120/pack | 2 packs | ~200 |

### 6.3 Soldering Consumables

| Item | Unit Price (BDT) | Qty | Total |
|------|------------------|-----|-------|
| Rosin core solder (0.6mm, 100g) | 200–300 | 1 | ~250 |
| Flux paste | 100–150 | 1 | ~125 |

---

## 7. Development Tools (One-Time Purchases)

| Item | Price (BDT) | Notes |
|------|-------------|-------|
| Soldering iron (60W temperature-controlled) | 1,200–2,000 | TS-100 type preferred |
| USB-Serial adapter (CP2102) | 150–250 | For boards with CH340 issues |
| Digital multimeter | 500–1,500 | For continuity and voltage checks |
| Drill + 4mm + 10mm drill bits | 800–1,500 | For enclosure holes |
| Hot glue gun | 200–400 | For securing components in enclosure |
| Label maker or label printer | 1,500–3,000 | Professional labeling of nodes |

---

## 8. Complete BOM Cost Summary

### 3-Node Scanner + 10-Tag Setup (Minimum Viable Demo)

| Category | Item | Qty | Unit Price (BDT) | Total (BDT) |
|----------|------|-----|------------------|-------------|
| **Scanner Nodes** | ESP32 DevKit v1 | 3 | 500 | 1,500 |
| | ABS enclosure 100×68×50mm | 3 | 100 | 300 |
| | 18650 Li-ion cell | 3 | 400 | 1,200 |
| | TP4056 module | 3 | 35 | 105 |
| | USB cable + adapter | 3 | 320 | 960 |
| | RGB LED + resistors | 3 sets | 30 | 90 |
| **Beacon Tags** | nRF51822 wristband (pre-built) | 10 | 1,000 | 10,000 |
| **Passives** | Capacitors, wire, solder | – | – | 750 |
| **Subtotal** | | | | **14,905** |
| **Buffer (15%)** | | | | ~2,235 |
| **TOTAL (3-node, 10-tag)** | | | | **~17,140 BDT** |

### 5-Node Scanner + 10-Tag Setup (Full Demo)

| Category | Additional Items | Qty | Unit Price | Additional Cost |
|----------|-----------------|-----|------------|-----------------|
| Extra scanner nodes | ESP32 DevKit v1 + enclosure + power | 2 sets | 1,800/set | 3,600 |
| Spares | ESP32 + batteries | 2 | 900 | 1,800 |
| **TOTAL (5-node, 10-tag)** | | | | **~22,540 BDT** |

> [!TIP]
> **Total hardware cost for a demo-ready 5-node system with 10 tags: approximately BDT 22,500–25,000** (~USD 200–220). This is the figure to use when computing ROI in the pitch deck.

---

## 9. Patuatuly Market Sourcing Guide

**Patuatuly Electronics Market (পাটুয়াটুলি বাজার)** is Dhaka's primary wholesale electronics market.

**Location:** Patuatuly Road, Old Dhaka. Near Sadarghat river terminal.  
**Opening Hours:** Saturday–Thursday, 9:00 AM – 8:00 PM. Friday: 2:00 PM – 8:00 PM.  
**Best time to visit:** 10:00 AM – 1:00 PM (before it gets crowded and hot).

### Recommended Shops (by Category)

| Category | Where to Look | Notes |
|----------|---------------|-------|
| Microcontrollers (ESP32, Arduino) | Main road facing shops, upper floor of market buildings | Haggle — first price is 20–30% above fair |
| LiPo batteries / 18650 cells | Battery specialty shops (often mobile repair adjacent) | Always verify capacity with shop meter |
| TP4056 modules, resistors, capacitors | Component shops (bulk bins) | Buy in lots of 10–20 for best price |
| ABS enclosures, junction boxes | Electrical fittings section (south end of market) | Bring a sample ESP32 board to check fit |
| LEDs, switches, wire | Any general component shop | Common items — easy to find |
| Solder, flux | Hardware shops on the periphery | Buy local brand (Nihon or similar) |

### Haggling Tips
- **Quote in lots:** "আমি ১০টা নেব, কত দিবেন?" (I'll take 10, what's the price?) → expect 10–20% discount
- **Know the online price:** Techshopbd.com is your reference. Patuatuly should be equal or slightly cheaper for common items.
- **Cash only:** No card payments in most stalls.
- **Bring exact change:** Shopkeepers often "don't have change" for large bills.

### Elephant Road / Multiplan Centre

For higher-end or more reliable sourcing:
- **Multiplan Centre, New Elephant Road:** More organized, slightly higher prices, better quality guarantee
- Ground floor: General electronics
- 1st–2nd floor: Computer hardware, development boards
- Good for: ESP32, Raspberry Pi (when available), LCD screens

---

*BOM maintained by BlankFrame Technologies Hardware Team. Prices valid as of late 2025 — verify before purchasing.*
