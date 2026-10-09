// =============================================================================
// Project FlowTrace — BLE Beacon Firmware
// beacon.ino
//
// Hardware: ESP32 (any devkit with ADC1 pin available)
// Role    : Periodically broadcasts an iBeacon advertisement that contains:
//             • A unique device UUID + major/minor
//             • TX power calibration byte
//             • Battery voltage (encoded in the scan-response manufacturer data)
//           Between bursts the MCU enters deep sleep to conserve power.
//
// Duty cycle:
//   ADVERTISING_DURATION_MS  → advertise (BLE active)
//   SLEEP_DURATION_S         → deep sleep (ESP32 entirely off except RTC)
//
// Libraries required:
//   • ESP32 Arduino core ≥ 2.0.14   (bundled BLE stack)
//   • No external BLE library needed (uses built-in esp32-hal-bt.h / NimBLE)
//     NOTE: This sketch uses the Arduino-ESP32 BLE library (NimBLE backend
//     available as a drop-in via NimBLE-Arduino 1.4.1 — see config comments).
//
// Wiring:
//   GPIO 34  ←  Battery voltage divider (100k:100k → max 6.6 V on a 3.3 V ref)
//   GPIO 2   →  LED (onboard on most devkits, active HIGH)
//
// =============================================================================

#include "config.h"

#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEAdvertising.h>
#include <BLEUtils.h>
#include <esp_sleep.h>
#include <esp_bt.h>
#include <driver/adc.h>
#include <esp_adc_cal.h>

// ---------------------------------------------------------------------------
// iBeacon advertisement structure
// Apple iBeacon payload sits inside a Manufacturer-Specific Data AD type.
//
// Format (27 bytes total):
//  [0-1]   Apple company ID  = 0x4C 0x00
//  [2]     iBeacon type      = 0x02
//  [3]     iBeacon length    = 0x15 (21 bytes follow)
//  [4-19]  Proximity UUID    (16 bytes, big-endian)
//  [20-21] Major             (big-endian)
//  [22-23] Minor             (big-endian)
//  [24]    Measured power    (int8 dBm at 1 metre)
// ---------------------------------------------------------------------------

// Parsed AURA_UUID_STR → 16 raw bytes at compile time via a helper.
// We store them as a uint8_t array in big-endian order.
static const uint8_t AURA_UUID_BYTES[16] = {
  0xf7, 0x82, 0x6d, 0xa6,
  0x4f, 0xa2,
  0x4e, 0x98,
  0x80, 0x24,
  0xbc, 0x5b, 0x71, 0xe0, 0x89, 0x3e
};

// ---------------------------------------------------------------------------
// Scan-response manufacturer data — carries battery voltage so the scanner
// can log it without establishing a GATT connection.
//
// Format (6 bytes, company ID = 0xFFFF "test/internal"):
//   [0-1]  Company ID  = 0xFF 0xFF
//   [2-3]  Battery mV  (uint16, little-endian)
//   [4]    Flags       bit0 = low battery, bits 1-7 reserved
//   [5]    FW major version byte
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Forward declarations
// ---------------------------------------------------------------------------
static uint32_t readBatteryMillivolts();
static void     blinkLed(bool lowBattery);
static void     buildIBeaconPayload(uint8_t* buf, uint16_t battMv);
static void     buildScanResponsePayload(uint16_t battMv, uint8_t flags,
                                         std::string& nameOut,
                                         BLEAdvertisementData& scanResp);

// ---------------------------------------------------------------------------
// setup() — runs once after each wake from deep sleep
// ---------------------------------------------------------------------------
void setup() {
#if SERIAL_BAUD > 0
  Serial.begin(SERIAL_BAUD);
  delay(100); // let UART settle
  Serial.printf("\n[FlowTrace Beacon] %s  FW %s  woke up\n",
                DEVICE_ID, FW_VERSION);
#endif

  // ---- LED setup ----
#if LED_PIN >= 0
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
#endif

  // ---- Battery ADC setup ----
  // Use ADC1 only (ADC2 cannot be used while WiFi/BT is active).
  adc1_config_width(ADC_WIDTH_BIT_12);
  adc1_config_channel_atten(
    static_cast<adc1_channel_t>(
      digitalPinToAnalogChannel(BATTERY_ADC_PIN)),
    ADC_ATTEN_DB_11  // 0–3.9 V range
  );

  uint32_t battMv = readBatteryMillivolts();

#if SERIAL_BAUD > 0
  Serial.printf("[FlowTrace Beacon] Battery: %u mV\n", battMv);
#endif

  // If critically low, skip BLE entirely to protect the cell.
  if (battMv > 0 && battMv < BATTERY_CRITICAL_MV) {
#if SERIAL_BAUD > 0
    Serial.printf("[FlowTrace Beacon] CRITICAL battery (%u mV) — skipping BLE\n",
                  battMv);
#endif
    blinkLed(true); // signal distress
    goto deep_sleep; // jump directly to sleep
  }

  // ---- BLE initialisation ----
  {
    BLEDevice::init(std::string("AURA_") + DEVICE_ID);
    BLEDevice::setPower(static_cast<esp_power_level_t>(
      // Map dBm → ESP32 power enum.
      // esp_power_level_t: ESP_PWR_LVL_N12..ESP_PWR_LVL_P9
      // Values:  -12→0, -9→1, -6→2, -3→3, 0→4, +3→5, +6→6, +9→7
      (TX_POWER_DBM + 12) / 3
    ));

    BLEAdvertising* pAdv = BLEDevice::getAdvertising();

    // ---- Build iBeacon manufacturer data ----
    uint8_t iBeaconPayload[25]; // 2 company + 1 type + 1 len + 16 uuid +
                                // 2 major + 2 minor + 1 power
    buildIBeaconPayload(iBeaconPayload, battMv);

    BLEAdvertisementData advData;
    // Flags: LE General Discoverable, BR/EDR Not Supported
    advData.setFlags(0x04);
    // Raw manufacturer specific data
    std::string mfgData(reinterpret_cast<char*>(iBeaconPayload),
                        sizeof(iBeaconPayload));
    advData.setManufacturerData(mfgData);
    pAdv->setAdvertisementData(advData);

    // ---- Build scan-response (device name + battery data) ----
    BLEAdvertisementData scanResp;
    std::string devName;
    bool isLowBat = (battMv > 0 && battMv < BATTERY_LOW_MV);
    buildScanResponsePayload(static_cast<uint16_t>(battMv),
                             isLowBat ? 0x01 : 0x00,
                             devName, scanResp);
    pAdv->setScanResponseData(scanResp);

    // Advertising interval (NimBLE/ESP32 units: 0.625 ms/unit)
    uint16_t advIntervalUnits = static_cast<uint16_t>(
      ADV_INTERVAL_MS * 1000UL / 625UL);
    pAdv->setMinInterval(advIntervalUnits);
    pAdv->setMaxInterval(advIntervalUnits + 4); // slight jitter to avoid collisions

    // ---- Blink LED then start advertising ----
    blinkLed(isLowBat);

#if SERIAL_BAUD > 0
    Serial.printf("[FlowTrace Beacon] Advertising for %d ms  (TX %d dBm)\n",
                  ADVERTISING_DURATION_MS, TX_POWER_DBM);
#endif

    pAdv->start();
    delay(ADVERTISING_DURATION_MS);
    pAdv->stop();
    BLEDevice::deinit(true); // release memory before sleep
  }

  // ---- Enter deep sleep ----
  deep_sleep:
#if SERIAL_BAUD > 0
  Serial.printf("[FlowTrace Beacon] Sleeping for %d s\n", SLEEP_DURATION_S);
  Serial.flush();
#endif

  // Disable BT/WiFi radio to save power during sleep.
  esp_bt_controller_disable();

  esp_sleep_enable_timer_wakeup(
    static_cast<uint64_t>(SLEEP_DURATION_S) * 1000000ULL);
  esp_deep_sleep_start(); // does not return
}

// loop() is never reached because deep_sleep_start() resets the CPU.
void loop() {}

// ---------------------------------------------------------------------------
// readBatteryMillivolts()
// Averages BATTERY_SAMPLE_COUNT ADC readings and converts to mV, accounting
// for the external resistor divider.  Returns 0 if ADC pin is not configured.
// ---------------------------------------------------------------------------
static uint32_t readBatteryMillivolts() {
  if (BATTERY_ADC_PIN < 0) return 0;

  uint32_t sum = 0;
  for (int i = 0; i < BATTERY_SAMPLE_COUNT; i++) {
    sum += analogRead(BATTERY_ADC_PIN);
    delay(2);
  }
  float avgCount = static_cast<float>(sum) / BATTERY_SAMPLE_COUNT;

  // Convert ADC count → ADC input voltage (mV)
  float adcMv = (avgCount / ADC_MAX_COUNT) * ADC_VREF_MV;

  // Account for the resistor divider to get actual battery voltage.
  float battMv = adcMv / BATTERY_DIVIDER_RATIO;

  return static_cast<uint32_t>(battMv + 0.5f); // round
}

// ---------------------------------------------------------------------------
// blinkLed()
// Normal mode : one short blink.
// Low battery : two quick blinks.
// ---------------------------------------------------------------------------
static void blinkLed(bool lowBattery) {
#if LED_PIN < 0
  (void)lowBattery;
  return;
#else
  auto blink = [](uint32_t onMs, uint32_t offMs) {
    digitalWrite(LED_PIN, HIGH);
    delay(onMs);
    digitalWrite(LED_PIN, LOW);
    delay(offMs);
  };

  if (!lowBattery) {
    blink(LED_BLINK_NORMAL_ON_MS, LED_BLINK_NORMAL_OFF_MS);
  } else {
    // Double-blink for low battery.
    blink(LED_BLINK_LOWBAT_ON_MS, LED_BLINK_LOWBAT_OFF_MS);
    blink(LED_BLINK_LOWBAT_ON_MS, LED_BLINK_LOWBAT_OFF_MS);
  }
#endif
}

// ---------------------------------------------------------------------------
// buildIBeaconPayload()
// Fills a 25-byte buffer with the Apple iBeacon manufacturer-specific data.
// buf must point to at least 25 bytes of writable storage.
// ---------------------------------------------------------------------------
static void buildIBeaconPayload(uint8_t* buf, uint16_t battMv) {
  (void)battMv; // battery is carried in the scan-response instead

  // Apple company identifier (little-endian).
  buf[0] = 0x4C;
  buf[1] = 0x00;

  // iBeacon sub-type and length.
  buf[2] = 0x02; // iBeacon type
  buf[3] = 0x15; // remaining length = 21 bytes

  // Proximity UUID (big-endian).
  memcpy(&buf[4], AURA_UUID_BYTES, 16);

  // Major (big-endian).
  buf[20] = static_cast<uint8_t>(BEACON_MAJOR >> 8);
  buf[21] = static_cast<uint8_t>(BEACON_MAJOR & 0xFF);

  // Minor (big-endian).
  buf[22] = static_cast<uint8_t>(BEACON_MINOR >> 8);
  buf[23] = static_cast<uint8_t>(BEACON_MINOR & 0xFF);

  // Measured power (calibrated TX power at 1 m, signed byte).
  buf[24] = static_cast<uint8_t>(static_cast<int8_t>(TX_POWER_DBM));
}

// ---------------------------------------------------------------------------
// buildScanResponsePayload()
// Populates a BLEAdvertisementData object used as the scan-response.
// Embeds:
//   • Complete local name  ("AURA_<DEVICE_ID>")
//   • Manufacturer-specific data containing battery mV and flags
// ---------------------------------------------------------------------------
static void buildScanResponsePayload(uint16_t battMv,
                                     uint8_t  flags,
                                     std::string&       nameOut,
                                     BLEAdvertisementData& scanResp) {
  // Complete local name — scanners filter on the "FLOWTRACE" prefix.
  nameOut = std::string("AURA_") + DEVICE_ID;
  scanResp.setName(nameOut);

  // 6-byte manufacturer-specific data (company 0xFFFF = internal/test).
  uint8_t mfg[6];
  mfg[0] = 0xFF; // company ID low byte
  mfg[1] = 0xFF; // company ID high byte
  mfg[2] = static_cast<uint8_t>(battMv & 0xFF);        // batt mV low
  mfg[3] = static_cast<uint8_t>((battMv >> 8) & 0xFF); // batt mV high
  mfg[4] = flags;
  mfg[5] = static_cast<uint8_t>(FW_VERSION[0] - '0');  // major ver digit

  scanResp.setManufacturerData(std::string(reinterpret_cast<char*>(mfg),
                                           sizeof(mfg)));
}
