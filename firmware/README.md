# FlowTrace Firmware Guide

This directory contains the ESP32 firmware for Project FlowTrace.

## Architecture

1.  **Beacon (`beacon.ino`)**: Worn by the user (or placed on items). It advertises a unique BLE ID continuously. Designed for low power (deep sleep between broadcasts).
2.  **Scanner (`scanner.ino`)**: Placed around the venue (the "Invisible Frames"). Continuously scans for BLE advertisements, records RSSI and MAC/UUID, and sends data over WiFi (via MQTT or HTTP) to the backend.
3.  **Gateway (`gateway.ino`)**: (Optional) A local bridge to aggregate MQTT traffic before sending it to the main backend server if direct scanner-to-server connection is not desired.

## Setup & Flashing

### Requirements
*   Arduino IDE 2.x or VS Code with PlatformIO
*   ESP32 Board Package installed
*   Libraries: `NimBLE-Arduino`, `ArduinoJson`, `PubSubClient` (for MQTT)

### Flashing a Scanner Node
1.  Open `scanner/scanner.ino`.
2.  Edit `config.h` to set the `WIFI_SSID`, `WIFI_PASSWORD`, and `BACKEND_URL`.
3.  Ensure `NODE_ID` is unique for each flashed ESP32 (e.g., `NODE_A`, `NODE_B`).
4.  Connect ESP32, select port, and upload.

### Flashing a Beacon
1.  Open `beacon/beacon.ino`.
2.  Edit `config.h` to set a unique `DEVICE_ID` (e.g., `FLOWTRACE_TAG_001`).
3.  Upload.

## Hardware & Wiring

*   **ESP32 DevKit V1**: Standard dev board used for scanners. Powered via USB (5V) from standard wall adapters.
*   **Beacons**: Can use smaller boards (e.g., ESP32-C3 SuperMini) powered by 3.7V LiPo batteries.

*ASCII Wiring (Scanner)*:
[USB Power 5V] ---> [ESP32 MicroUSB Port]

*ASCII Wiring (Beacon with Battery)*:
[LiPo 3.7V +] ---> [ESP32 3.3V IN / VBAT]
[LiPo 3.7V -] ---> [ESP32 GND]
