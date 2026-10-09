// =============================================================================
// Project FlowTrace — BLE Beacon Configuration
// config.h
//
// All compile-time tunable parameters for the FlowTrace BLE Beacon node.
// Edit this file before flashing to customise per-device behaviour.
// =============================================================================

#pragma once

// ---------------------------------------------------------------------------
// Device Identity
// ---------------------------------------------------------------------------

// Unique human-readable tag identifier (max 20 chars, ASCII).
// This is embedded in the Eddystone-UID namespace + instance bytes.
#ifndef DEVICE_ID
  #define DEVICE_ID               "FLOWTRACE_TAG_001"
#endif

// Beacon "major" and "minor" values used in the iBeacon payload.
// These let the backend distinguish tags without parsing the full UUID.
#define BEACON_MAJOR              0x0001
#define BEACON_MINOR              0x0001

// iBeacon / Eddystone proximity UUID (16 bytes, big-endian).
// All FlowTrace tags share the same UUID; major/minor differentiate them.
#define AURA_UUID_STR             "f7826da6-4fa2-4e98-8024-bc5b71e0893e"

// ---------------------------------------------------------------------------
// BLE Advertisement
// ---------------------------------------------------------------------------

// Advertising TX power level sent in the advertisement payload (dBm).
// Measured at 0 m; used by the scanner for path-loss calculations.
// Valid range on ESP32: -12, -9, -6, -3, 0, 3, 6, 9  (dBm)
#define TX_POWER_DBM              (-6)

// Duration of each active advertising burst (milliseconds).
// Shorter = less air time = more battery; longer = higher scanner hit-rate.
#define ADVERTISING_DURATION_MS   100

// BLE advertising interval during the active burst (ms, 20–10240 ms).
// 100 ms is a good balance of discoverability vs. power.
#define ADV_INTERVAL_MS           100

// ---------------------------------------------------------------------------
// Deep-Sleep / Duty Cycle
// ---------------------------------------------------------------------------

// How long the beacon sleeps between advertising bursts (seconds).
#define SLEEP_DURATION_S          5

// ---------------------------------------------------------------------------
// Battery Monitoring
// ---------------------------------------------------------------------------

// GPIO pin connected to a resistor-divider on the battery.
// Default: GPIO 34 (ADC1_CH6, input-only pin — safe for ADC).
#define BATTERY_ADC_PIN           34

// Resistor divider ratio: R1/(R1+R2).
// Example: 100 kΩ + 100 kΩ → ratio = 0.5  (maps 8.4 V → 3.3 V full scale)
// For a single-cell LiPo (max ~4.2 V) with 100k/100k: ratio = 0.5
#define BATTERY_DIVIDER_RATIO     0.5f

// ADC reference voltage (ESP32 internal = ~3.3 V; calibrate if needed).
#define ADC_VREF_MV               3300.0f

// ADC resolution (ESP32 = 12-bit → 4095 counts).
#define ADC_MAX_COUNT             4095.0f

// Battery voltage thresholds (millivolts).
#define BATTERY_LOW_MV            3400   // Below this → "low battery" blink
#define BATTERY_CRITICAL_MV       3000   // Below this → skip BLE, just sleep

// Number of ADC samples to average (reduces noise).
#define BATTERY_SAMPLE_COUNT      8

// ---------------------------------------------------------------------------
// LED Indicators
// ---------------------------------------------------------------------------

// Single-colour status LED pin (active HIGH).  Set to -1 to disable.
#define LED_PIN                   2      // GPIO 2 = onboard LED on most devkits

// Blink timings (milliseconds)
#define LED_BLINK_NORMAL_ON_MS    20     // Short blink → advertising OK
#define LED_BLINK_NORMAL_OFF_MS   0      // Off immediately after blink
#define LED_BLINK_LOWBAT_ON_MS    50     // Double-blink → low battery
#define LED_BLINK_LOWBAT_OFF_MS   100    // Gap between low-bat blinks

// ---------------------------------------------------------------------------
// Miscellaneous
// ---------------------------------------------------------------------------

// Serial baud rate (set to 0 to disable serial output and save ~50 µA).
#define SERIAL_BAUD               115200

// Firmware version string embedded in the scan-response name field.
#define FW_VERSION                "1.0.0"
