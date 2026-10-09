// =============================================================================
// Project FlowTrace — BLE Scanner Node Firmware
// scanner.ino
//
// Hardware: ESP32 (any devkit with WiFi + BLE)
// Role    : Continuously scans for FlowTrace BLE beacons, buffers RSSI readings,
//           and periodically POSTs a JSON batch to the backend server.
//
// Behaviour overview:
//   1. Initialise RGB LED, Serial, WiFi.
//   2. Start BLE scan for SCAN_DURATION_MS (default 9 s).
//      Every advertisement matching the FLOWTRACE prefix is logged to a ring buffer.
//   3. After UPLOAD_INTERVAL_MS (default 10 s) flush the buffer:
//      POST JSON array → BACKEND_URL via HTTP.
//   4. LED reflects state:
//        Blue  → scanning
//        Green → upload succeeded
//        Red   → WiFi/HTTP error
//
// Libraries required (install via Arduino Library Manager or platformio.ini):
//   • NimBLE-Arduino    1.4.1   (preferred — lower memory than stock BLE)
//   • ArduinoJson       6.21.3
//   • ESP32 Arduino core ≥ 2.0.14  (provides WiFi.h, HTTPClient.h)
//
// =============================================================================

#include "config.h"

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

// Use NimBLE for a significantly smaller RAM footprint.
#include <NimBLEDevice.h>
#include <NimBLEScan.h>
#include <NimBLEAdvertisedDevice.h>

#include <ArduinoJson.h>

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

struct AuraReading {
  char    deviceId[32];   // e.g. "FLOWTRACE_TAG_001"
  char    macAddr[18];    // e.g. "AA:BB:CC:DD:EE:FF"
  int8_t  rssi;           // RSSI in dBm
  uint16_t battMv;        // battery voltage from scan-response (0 if absent)
  uint32_t timestampMs;   // millis() at capture time
};

// ---------------------------------------------------------------------------
// Globals
// ---------------------------------------------------------------------------

// Circular ring buffer — protected by a mutex (BLE callback runs on a
// separate FreeRTOS task).
static AuraReading  s_buffer[BUFFER_MAX_ENTRIES];
static int          s_head    = 0;   // next write position
static int          s_count   = 0;   // number of valid entries
static portMUX_TYPE s_bufMux  = portMUX_INITIALIZER_UNLOCKED;

static NimBLEScan*  s_pScan   = nullptr;
static bool         s_scanning = false;

// Timestamps for duty-cycle management (all in ms).
static uint32_t     s_lastUploadMs  = 0;
static uint32_t     s_scanStartMs   = 0;

// WiFi status cache.
static bool         s_wifiOk        = false;

// ---------------------------------------------------------------------------
// LED helpers
// ---------------------------------------------------------------------------

static inline void ledOff() {
#if USE_RGB_LED
  digitalWrite(LED_RED_PIN,   LOW);
  digitalWrite(LED_GREEN_PIN, LOW);
  digitalWrite(LED_BLUE_PIN,  LOW);
#else
  digitalWrite(LED_MONO_PIN, LOW);
#endif
}

static inline void ledBlue() {
  ledOff();
#if USE_RGB_LED
  digitalWrite(LED_BLUE_PIN, HIGH);
#else
  digitalWrite(LED_MONO_PIN, HIGH);
#endif
}

static inline void ledGreen() {
  ledOff();
#if USE_RGB_LED
  digitalWrite(LED_GREEN_PIN, HIGH);
#else
  // Mono LED: blink twice to indicate success.
  for (int i = 0; i < 2; i++) {
    digitalWrite(LED_MONO_PIN, HIGH); delay(LED_BLINK_MS);
    digitalWrite(LED_MONO_PIN, LOW);  delay(LED_BLINK_MS);
  }
#endif
}

static inline void ledRed() {
  ledOff();
#if USE_RGB_LED
  digitalWrite(LED_RED_PIN, HIGH);
#else
  // Mono LED: long blink to indicate error.
  digitalWrite(LED_MONO_PIN, HIGH); delay(LED_BLINK_MS * 3);
  digitalWrite(LED_MONO_PIN, LOW);
#endif
}

static inline void ledBlink(void(*colorFn)(), uint32_t durationMs = 200) {
  colorFn();
  delay(durationMs);
  ledOff();
}

// ---------------------------------------------------------------------------
// Buffer helpers (must be called with s_bufMux held)
// ---------------------------------------------------------------------------

static void bufferPush_ISR(const AuraReading& r) {
  // Overwrite oldest entry if full.
  s_buffer[s_head] = r;
  s_head = (s_head + 1) % BUFFER_MAX_ENTRIES;
  if (s_count < BUFFER_MAX_ENTRIES) s_count++;
}

// ---------------------------------------------------------------------------
// BLE Scan Callback
// ---------------------------------------------------------------------------

class AuraScanCallbacks : public NimBLEAdvertisedDeviceCallbacks {
public:
  void onResult(NimBLEAdvertisedDevice* device) override {
    // ---- Name-based filter ------------------------------------------------
    // Accept devices whose name starts with AURA_DEVICE_PREFIX.
    // If the prefix is empty we accept everything (useful for debugging).
    const char* prefix = AURA_DEVICE_PREFIX;
    bool nameMatch = false;

    if (strlen(prefix) == 0) {
      nameMatch = true;
    } else if (device->haveName()) {
      std::string name = device->getName();
      nameMatch = (name.rfind(prefix, 0) == 0); // starts-with
    }

    // ---- UUID-based filter ------------------------------------------------
    // Secondary filter: check iBeacon manufacturer data for our UUID.
    bool uuidMatch = false;
    if (!nameMatch && device->haveManufacturerData()) {
      std::string mfgData = device->getManufacturerData();
      // iBeacon: bytes 0-1 = 0x4C 0x00, bytes 4-19 = UUID
      if (mfgData.size() >= 25 &&
          (uint8_t)mfgData[0] == 0x4C &&
          (uint8_t)mfgData[1] == 0x00 &&
          (uint8_t)mfgData[2] == 0x02) {
        // Quick check: compare first 4 UUID bytes (f7 82 6d a6).
        uuidMatch = ((uint8_t)mfgData[4] == 0xf7 &&
                     (uint8_t)mfgData[5] == 0x82 &&
                     (uint8_t)mfgData[6] == 0x6d &&
                     (uint8_t)mfgData[7] == 0xa6);
      }
    }

    if (!nameMatch && !uuidMatch) return;

    // ---- Build reading record ---------------------------------------------
    AuraReading r;
    memset(&r, 0, sizeof(r));

    // Device ID from name (or MAC if name absent).
    if (device->haveName()) {
      strncpy(r.deviceId, device->getName().c_str(), sizeof(r.deviceId) - 1);
    } else {
      strncpy(r.deviceId, device->getAddress().toString().c_str(),
              sizeof(r.deviceId) - 1);
    }

    strncpy(r.macAddr, device->getAddress().toString().c_str(),
            sizeof(r.macAddr) - 1);

    r.rssi        = static_cast<int8_t>(device->getRSSI());
    r.timestampMs = millis();

    // ---- Extract battery mV from scan-response manufacturer data ----------
    // Our scan-response uses company ID 0xFFFF, bytes 2-3 = battMv LE.
    // NimBLE provides the raw manufacturer data including the company bytes.
    if (device->haveManufacturerData()) {
      std::string mfgData = device->getManufacturerData();
      if (mfgData.size() >= 6 &&
          (uint8_t)mfgData[0] == 0xFF &&
          (uint8_t)mfgData[1] == 0xFF) {
        r.battMv = static_cast<uint16_t>(
          (uint8_t)mfgData[2] | ((uint8_t)mfgData[3] << 8));
      }
    }

    // ---- Push to ring buffer (ISR-safe) -----------------------------------
    portENTER_CRITICAL(&s_bufMux);
    bufferPush_ISR(r);
    portEXIT_CRITICAL(&s_bufMux);

#if SERIAL_BAUD > 0
    Serial.printf("[Scan] %-20s  MAC: %s  RSSI: %d dBm  Batt: %u mV\n",
                  r.deviceId, r.macAddr, (int)r.rssi, r.battMv);
#endif
  }
};

static AuraScanCallbacks s_scanCallbacks;

// ---------------------------------------------------------------------------
// WiFi helpers
// ---------------------------------------------------------------------------

static bool connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;

  Serial.printf("[WiFi] Connecting to %s ...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > WIFI_CONNECT_TIMEOUT_MS) {
      Serial.println("[WiFi] Connection timed out.");
      return false;
    }
    delay(200);
  }
  Serial.printf("[WiFi] Connected.  IP: %s\n",
                WiFi.localIP().toString().c_str());
  return true;
}

// ---------------------------------------------------------------------------
// HTTP upload — serialises buffered readings to JSON and POSTs to backend.
// Returns true on HTTP 2xx response.
// ---------------------------------------------------------------------------
static bool uploadReadings() {
  // Snapshot the buffer under lock, then release so BLE can keep writing.
  AuraReading snapshot[BUFFER_MAX_ENTRIES];
  int count = 0;

  portENTER_CRITICAL(&s_bufMux);
  count = s_count;
  if (count > 0) {
    // Copy entries in chronological order (oldest first).
    int tail = (s_head - s_count + BUFFER_MAX_ENTRIES) % BUFFER_MAX_ENTRIES;
    for (int i = 0; i < count; i++) {
      snapshot[i] = s_buffer[(tail + i) % BUFFER_MAX_ENTRIES];
    }
    s_head  = 0;
    s_count = 0;
  }
  portEXIT_CRITICAL(&s_bufMux);

  if (count == 0) {
    Serial.println("[Upload] Buffer empty — nothing to send.");
    return true; // not a failure
  }

  // Build JSON payload.
  // Schema:
  // {
  //   "node_id":   "NODE_A",
  //   "fw_version": "1.0.0",
  //   "readings": [
  //     { "device_id": "FLOWTRACE_TAG_001", "mac": "AA:BB:CC:DD:EE:FF",
  //       "rssi": -65, "batt_mv": 3800, "ts_ms": 12345 },
  //     ...
  //   ]
  // }

  // Use a DynamicJsonDocument sized for the maximum possible payload.
  DynamicJsonDocument doc(JSON_BUFFER_SIZE);
  doc["node_id"]    = NODE_ID;
  doc["fw_version"] = FW_VERSION;
  JsonArray readings = doc.createNestedArray("readings");

  for (int i = 0; i < count; i++) {
    JsonObject obj = readings.createNestedObject();
    obj["device_id"] = snapshot[i].deviceId;
    obj["mac"]       = snapshot[i].macAddr;
    obj["rssi"]      = snapshot[i].rssi;
    obj["batt_mv"]   = snapshot[i].battMv;
    obj["ts_ms"]     = snapshot[i].timestampMs;
  }

  String body;
  body.reserve(JSON_BUFFER_SIZE);
  serializeJson(doc, body);

  Serial.printf("[Upload] Sending %d readings (%d bytes) → %s\n",
                count, body.length(), BACKEND_URL);

  HTTPClient http;
  http.begin(BACKEND_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(HTTP_TIMEOUT_MS);

  int httpCode = http.POST(body);
  http.end();

  if (httpCode >= 200 && httpCode < 300) {
    Serial.printf("[Upload] OK (HTTP %d)\n", httpCode);
    return true;
  } else {
    Serial.printf("[Upload] Failed (HTTP %d)\n", httpCode);
    // Re-buffer the readings so we don't lose them.
    portENTER_CRITICAL(&s_bufMux);
    for (int i = 0; i < count && s_count < BUFFER_MAX_ENTRIES; i++) {
      bufferPush_ISR(snapshot[i]);
    }
    portEXIT_CRITICAL(&s_bufMux);
    return false;
  }
}

// ---------------------------------------------------------------------------
// BLE scan management
// ---------------------------------------------------------------------------

static void startScan() {
  if (s_scanning) return;

  s_pScan->clearResults();
  // Active scan = scanner sends a scan-request to get scan-response from beacon.
  s_pScan->setActiveScan(true);
  s_pScan->setInterval(SCAN_INTERVAL);
  s_pScan->setWindow(SCAN_WINDOW);
  s_pScan->setFilterPolicy(BLE_HCI_SCAN_FILT_NO_WL);

  // Non-blocking scan (duration 0 = indefinite; we stop it manually).
  s_pScan->start(0, false);
  s_scanning    = true;
  s_scanStartMs = millis();

  ledBlue();
  Serial.println("[BLE] Scan started.");
}

static void stopScan() {
  if (!s_scanning) return;
  s_pScan->stop();
  s_scanning = false;
  Serial.printf("[BLE] Scan stopped after %lu ms.  Buffer: %d entries.\n",
                millis() - s_scanStartMs, s_count);
}

// ---------------------------------------------------------------------------
// setup()
// ---------------------------------------------------------------------------
void setup() {
#if SERIAL_BAUD > 0
  Serial.begin(SERIAL_BAUD);
  delay(100);
  Serial.printf("\n[FlowTrace Scanner] NODE_ID=%s  FW=%s\n", NODE_ID, FW_VERSION);
#endif

  // ---- LED init ----
#if USE_RGB_LED
  pinMode(LED_RED_PIN,   OUTPUT);
  pinMode(LED_GREEN_PIN, OUTPUT);
  pinMode(LED_BLUE_PIN,  OUTPUT);
#else
  pinMode(LED_MONO_PIN, OUTPUT);
#endif
  ledOff();

  // ---- WiFi ----
  s_wifiOk = connectWiFi();
  if (!s_wifiOk) ledRed(); else ledGreen();
  delay(LED_BLINK_MS);
  ledOff();

  // ---- NimBLE init ----
  NimBLEDevice::init("");
  NimBLEDevice::setPower(ESP_PWR_LVL_N6); // scanner TX power (for scan req)
  s_pScan = NimBLEDevice::getScan();
  s_pScan->setAdvertisedDeviceCallbacks(&s_scanCallbacks,
    SCAN_FILTER_DUPLICATES); // second arg = filter duplicates flag
  s_pScan->setDuplicateFilter(SCAN_FILTER_DUPLICATES);

  s_lastUploadMs = millis();
  startScan();
}

// ---------------------------------------------------------------------------
// loop()
// ---------------------------------------------------------------------------
void loop() {
  uint32_t now = millis();

  // ---- Upload window ----
  // Every UPLOAD_INTERVAL_MS: stop scan, upload, restart scan.
  if (now - s_lastUploadMs >= static_cast<uint32_t>(UPLOAD_INTERVAL_MS)) {
    s_lastUploadMs = now;

    stopScan();

    // Ensure WiFi is up.
    if (!s_wifiOk || WiFi.status() != WL_CONNECTED) {
      Serial.println("[WiFi] Reconnecting...");
      s_wifiOk = connectWiFi();
    }

    if (s_wifiOk) {
      bool ok = uploadReadings();
      if (ok) {
        ledBlink(ledGreen, LED_BLINK_MS);
      } else {
        ledBlink(ledRed, LED_BLINK_MS * 2);
      }
    } else {
      ledBlink(ledRed, LED_BLINK_MS * 2);
    }

    startScan();
    return;
  }

  // ---- Scan window guard ----
  // Stop scan a little before the upload window so the MCU has time to
  // serialise JSON while the buffer is already populated.
  uint32_t elapsed = now - s_lastUploadMs;
  if (s_scanning && elapsed >= static_cast<uint32_t>(SCAN_DURATION_MS)) {
    stopScan();
    ledOff();
  }

  // Small yield to avoid WDT reset.
  delay(10);
}
