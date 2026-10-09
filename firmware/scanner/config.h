// =============================================================================
// Project FlowTrace — BLE Scanner Node Configuration
// config.h
//
// All compile-time tunable parameters for the FlowTrace Scanner node.
// Edit this file before flashing to customise per-node behaviour.
// =============================================================================

#pragma once

// ---------------------------------------------------------------------------
// Node Identity
// ---------------------------------------------------------------------------

// Unique identifier for this scanner node (reported in every JSON upload).
// Use a short, descriptive string — it will appear in the backend database.
#ifndef NODE_ID
  #define NODE_ID                 "NODE_A"
#endif

// Human-readable location hint (optional; helps during debugging).
#define NODE_LOCATION             "Main Entrance"

// ---------------------------------------------------------------------------
// WiFi Credentials
// ---------------------------------------------------------------------------

#define WIFI_SSID                 "YourNetworkSSID"
#define WIFI_PASSWORD             "YourNetworkPassword"

// Maximum time (ms) to wait for WiFi association before giving up.
#define WIFI_CONNECT_TIMEOUT_MS   15000

// Milliseconds between WiFi reconnect attempts.
#define WIFI_RETRY_INTERVAL_MS    5000

// ---------------------------------------------------------------------------
// Backend HTTP Endpoint
// ---------------------------------------------------------------------------

// Full URL of the backend ingestion endpoint.
// The scanner will POST a JSON array of RSSI readings here.
#define BACKEND_URL               "http://192.168.1.100:8080/api/v1/readings"

// HTTP POST timeout (milliseconds).
#define HTTP_TIMEOUT_MS           8000

// How often the scanner flushes its buffer to the backend (milliseconds).
#define UPLOAD_INTERVAL_MS        10000

// ---------------------------------------------------------------------------
// BLE Scanning
// ---------------------------------------------------------------------------

// Device name / advertisement prefix used to identify FlowTrace beacons.
// Any BLE advertisement whose complete/shortened name starts with this
// string will be captured.  Leave empty ("") to capture everything.
#define AURA_DEVICE_PREFIX        "FLOWTRACE"

// iBeacon proximity UUID shared by all FlowTrace tags (used as a secondary filter
// when the device name is not present in the advertisement).
#define AURA_UUID_STR             "f7826da6-4fa2-4e98-8024-bc5b71e0893e"

// Duration of each BLE scan window (milliseconds).
// After this window the scanner uploads data, then starts again.
#define SCAN_DURATION_MS          9000   // Must be < UPLOAD_INTERVAL_MS

// BLE scan interval and window (in units of 0.625 ms).
// interval >= window.  Smaller window = lower power but less coverage.
#define SCAN_INTERVAL             80     // 80 * 0.625 ms = 50 ms
#define SCAN_WINDOW               40     // 40 * 0.625 ms = 25 ms

// Set to true to filter duplicate advertisements per scan window.
// Set to false to receive every advertisement (more granular RSSI data).
#define SCAN_FILTER_DUPLICATES    false

// ---------------------------------------------------------------------------
// Reading Buffer
// ---------------------------------------------------------------------------

// Maximum number of RSSI readings held in RAM before the oldest is dropped.
#define BUFFER_MAX_ENTRIES        100

// ---------------------------------------------------------------------------
// RGB LED Pins (WS2812 or discrete RGB — configure below)
// ---------------------------------------------------------------------------

// Set USE_RGB_LED to 1 for a discrete common-cathode RGB LED,
// or 0 to use the plain onboard LED on LED_MONO_PIN.
#define USE_RGB_LED               1

// Discrete RGB LED GPIO pins (active HIGH).
#define LED_RED_PIN               25
#define LED_GREEN_PIN             26
#define LED_BLUE_PIN              27

// Fallback mono LED (e.g. GPIO 2 onboard) when USE_RGB_LED == 0.
#define LED_MONO_PIN              2

// LED blink durations (ms).
#define LED_BLINK_MS              200

// ---------------------------------------------------------------------------
// Miscellaneous
// ---------------------------------------------------------------------------

#define SERIAL_BAUD               115200
#define FW_VERSION                "1.0.0"

// JSON batch maximum size (bytes) — guard against oversized HTTP bodies.
#define JSON_BUFFER_SIZE          8192
