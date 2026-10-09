// =============================================================================
// Project FlowTrace — WiFi Gateway Firmware
// gateway.ino
//
// Hardware: ESP32 (any devkit with WiFi)
// Role    : Central bridge between field scanner nodes (which speak MQTT) and
//           the backend HTTP API.  Also provides:
//             • ArduinoOTA  — flash new firmware over WiFi
//             • WiFiManager — captive-portal WiFi provisioning (first boot)
//             • Config web portal — view status, update backend URL
//
// Data flow:
//   Scanner → (MQTT publish)  →  Broker  →  Gateway (subscriber)
//   Gateway → (HTTP POST)     →  Backend REST API
//
// MQTT topic convention:
//   flowtrace/readings/<NODE_ID>   — scanner publishes JSON batch here
//   flowtrace/status/<GATEWAY_ID>  — gateway publishes its own heartbeat here
//
// Libraries required:
//   • WiFiManager          2.0.17   (tzapu/WiFiManager)
//   • PubSubClient         2.8      (knolleary/pubsubclient)
//   • ArduinoJson          6.21.3   (bblanchon/ArduinoJson)
//   • ArduinoOTA           (bundled with ESP32 Arduino core ≥ 2.0.14)
//   • ESPmDNS              (bundled with ESP32 Arduino core)
//   • WebServer            (bundled with ESP32 Arduino core)
//
// =============================================================================

#include "config.h"

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiManager.h>       // captive-portal WiFi config
#include <ArduinoOTA.h>        // OTA update
#include <ESPmDNS.h>           // mDNS for .local hostname
#include <WebServer.h>         // built-in HTTP server for config portal
#include <PubSubClient.h>      // MQTT client
#include <ArduinoJson.h>       // JSON parsing and serialisation
#include <HTTPClient.h>        // forward readings to backend

// ---------------------------------------------------------------------------
// Global objects
// ---------------------------------------------------------------------------

static WiFiClient    s_wifiClient;
static PubSubClient  s_mqtt(s_wifiClient);
static WebServer     s_webServer(WEB_PORTAL_PORT);

// Runtime-configurable backend URL (can be changed via web portal).
static char s_backendUrl[256] = BACKEND_URL;

// Statistics counters (reset on reboot).
static uint32_t s_rxCount      = 0;  // MQTT messages received
static uint32_t s_fwdCount     = 0;  // successfully forwarded to backend
static uint32_t s_errCount     = 0;  // forward failures
static uint32_t s_lastMqttMs   = 0;  // millis() of last received message
static bool     s_otaActive    = false;

// ---------------------------------------------------------------------------
// LED helpers
// ---------------------------------------------------------------------------

static void ledOn()  { if (LED_PIN >= 0) digitalWrite(LED_PIN, HIGH); }
static void ledOff() { if (LED_PIN >= 0) digitalWrite(LED_PIN, LOW);  }
static void ledBlink(uint32_t times = 1, uint32_t durMs = LED_BLINK_MS) {
  for (uint32_t i = 0; i < times; i++) {
    ledOn();  delay(durMs);
    ledOff(); delay(durMs);
  }
}

// ---------------------------------------------------------------------------
// HTTP forwarding
// Receives a raw JSON string (as published by a scanner) and POSTs it
// directly to the backend.  Returns true on HTTP 2xx.
// ---------------------------------------------------------------------------
static bool forwardToBackend(const char* payload, size_t len) {
  HTTPClient http;
  http.begin(s_backendUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Gateway-ID",  GATEWAY_ID);
  http.addHeader("X-FW-Version",  FW_VERSION);
  http.setTimeout(HTTP_TIMEOUT_MS);

  int code = http.POST(const_cast<uint8_t*>(
                         reinterpret_cast<const uint8_t*>(payload)),
                       len);
  http.end();

  if (code >= 200 && code < 300) {
    s_fwdCount++;
    Serial.printf("[Gateway] Forwarded %u bytes → backend (HTTP %d).  "
                  "Total: %u ok / %u err\n", len, code, s_fwdCount, s_errCount);
    return true;
  } else {
    s_errCount++;
    Serial.printf("[Gateway] Forward failed (HTTP %d).  "
                  "Total: %u ok / %u err\n", code, s_fwdCount, s_errCount);
    return false;
  }
}

// ---------------------------------------------------------------------------
// MQTT callback — called by PubSubClient when a subscribed message arrives.
// ---------------------------------------------------------------------------
static void mqttCallback(char* topic, byte* payload, unsigned int length) {
  s_rxCount++;
  s_lastMqttMs = millis();

  Serial.printf("[MQTT] Received on '%s' (%u bytes)\n", topic, length);

  // Null-terminate for JSON parsing safety check.
  // We work with the raw bytes for forwarding to avoid a double serialisation.
  if (length == 0 || length >= JSON_BUFFER_SIZE) {
    Serial.printf("[MQTT] Payload size %u out of range — discarding.\n",
                  length);
    s_errCount++;
    ledBlink(3, 100);
    return;
  }

  // Quick JSON validation (ensures the payload is well-formed before
  // forwarding, to avoid poisoning the backend with garbage).
  {
    StaticJsonDocument<256> probe;
    DeserializationError err = deserializeJson(probe, payload, length);
    if (err) {
      Serial.printf("[MQTT] Invalid JSON (%s) — discarding.\n",
                    err.c_str());
      s_errCount++;
      ledBlink(3, 100);
      return;
    }
    // We only probe; actual forwarding uses the raw bytes.
  }

  bool ok = forwardToBackend(reinterpret_cast<const char*>(payload), length);
  if (ok) {
    ledBlink(1, LED_BLINK_MS);
  } else {
    ledBlink(2, LED_BLINK_MS);
  }
}

// ---------------------------------------------------------------------------
// MQTT connection / reconnect
// ---------------------------------------------------------------------------
static bool mqttConnect() {
  if (s_mqtt.connected()) return true;

  Serial.printf("[MQTT] Connecting to %s:%d as '%s'...\n",
                MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_CLIENT_ID);

  bool ok;
  if (strlen(MQTT_USERNAME) > 0) {
    ok = s_mqtt.connect(MQTT_CLIENT_ID, MQTT_USERNAME, MQTT_PASSWORD);
  } else {
    ok = s_mqtt.connect(MQTT_CLIENT_ID);
  }

  if (ok) {
    Serial.println("[MQTT] Connected.");
    s_mqtt.subscribe(MQTT_SUBSCRIBE_TOPIC, MQTT_QOS);
    Serial.printf("[MQTT] Subscribed to '%s'\n", MQTT_SUBSCRIBE_TOPIC);

    // Publish gateway online status.
    char status[128];
    snprintf(status, sizeof(status),
             "{\"gateway\":\"%s\",\"fw\":\"%s\",\"status\":\"online\"}",
             GATEWAY_ID, FW_VERSION);
    s_mqtt.publish("flowtrace/status/" GATEWAY_ID, status, true /* retain */);
  } else {
    Serial.printf("[MQTT] Failed (state=%d)\n", s_mqtt.state());
  }
  return ok;
}

// ---------------------------------------------------------------------------
// Web portal — tiny HTML status page + backend URL update form
// ---------------------------------------------------------------------------

static const char PORTAL_HTML_HEADER[] PROGMEM =
  "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
  "<meta name='viewport' content='width=device-width,initial-scale=1'>"
  "<title>FlowTrace Gateway</title>"
  "<style>body{font-family:sans-serif;max-width:600px;margin:2rem auto;padding:0 1rem}"
  "h1{color:#1a73e8}label{display:block;margin:.5rem 0 .2rem}"
  "input[type=text]{width:100%;padding:.4rem;box-sizing:border-box}"
  ".card{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:1rem 0}"
  ".ok{color:green}.err{color:red}"
  "button{background:#1a73e8;color:#fff;border:none;padding:.5rem 1.2rem;"
  "border-radius:4px;cursor:pointer}</style></head><body>"
  "<h1>&#127760; FlowTrace Gateway</h1>";

static const char PORTAL_HTML_FOOTER[] PROGMEM =
  "</body></html>";

static void handleRoot() {
  // Basic-auth check.
  if (strlen(WEB_PORTAL_USER) > 0 &&
      !s_webServer.authenticate(WEB_PORTAL_USER, WEB_PORTAL_PASS)) {
    return s_webServer.requestAuthentication();
  }

  char uptime[32];
  uint32_t sec = millis() / 1000;
  snprintf(uptime, sizeof(uptime), "%02u:%02u:%02u",
           sec / 3600, (sec % 3600) / 60, sec % 60);

  String html;
  html.reserve(2048);
  html += FPSTR(PORTAL_HTML_HEADER);

  html += "<div class='card'><h2>Status</h2>";
  html += "<p>Gateway ID: <b>"; html += GATEWAY_ID; html += "</b></p>";
  html += "<p>FW Version: <b>"; html += FW_VERSION; html += "</b></p>";
  html += "<p>Uptime: <b>"; html += uptime; html += "</b></p>";
  html += "<p>IP: <b>"; html += WiFi.localIP().toString(); html += "</b></p>";
  html += "<p>MQTT: ";
  html += s_mqtt.connected()
        ? "<span class='ok'>Connected</span>"
        : "<span class='err'>Disconnected</span>";
  html += "</p>";

  html += "<p>Messages received: <b>"; html += s_rxCount; html += "</b></p>";
  html += "<p>Forwarded OK: <b><span class='ok'>"; html += s_fwdCount;
  html += "</span></b> &nbsp; Errors: <b><span class='err'>"; html += s_errCount;
  html += "</span></b></p></div>";

  html += "<div class='card'><h2>Backend URL</h2>";
  html += "<form method='POST' action='/update'>";
  html += "<label for='url'>Backend ingestion URL</label>";
  html += "<input type='text' id='url' name='url' value='";
  html += s_backendUrl;
  html += "'><br><br><button type='submit'>Save &amp; Apply</button></form></div>";

  html += "<div class='card'><h2>OTA Update</h2>";
  html += "<p>Use Arduino IDE or <code>espota.py</code>:</p>";
  html += "<pre>espota.py -i "; html += WiFi.localIP().toString();
  html += " -f firmware.bin -P "; html += OTA_PASSWORD; html += "</pre></div>";

  html += FPSTR(PORTAL_HTML_FOOTER);
  s_webServer.send(200, "text/html", html);
}

static void handleUpdate() {
  if (strlen(WEB_PORTAL_USER) > 0 &&
      !s_webServer.authenticate(WEB_PORTAL_USER, WEB_PORTAL_PASS)) {
    return s_webServer.requestAuthentication();
  }

  if (s_webServer.hasArg("url")) {
    String newUrl = s_webServer.arg("url");
    newUrl.trim();
    if (newUrl.length() > 0 && newUrl.length() < sizeof(s_backendUrl)) {
      strncpy(s_backendUrl, newUrl.c_str(), sizeof(s_backendUrl) - 1);
      Serial.printf("[Portal] Backend URL updated → %s\n", s_backendUrl);
    }
  }
  s_webServer.sendHeader("Location", "/", true);
  s_webServer.send(302, "text/plain", "");
}

static void handleNotFound() {
  s_webServer.send(404, "text/plain", "Not found");
}

// ---------------------------------------------------------------------------
// setup()
// ---------------------------------------------------------------------------
void setup() {
#if SERIAL_BAUD > 0
  Serial.begin(SERIAL_BAUD);
  delay(100);
  Serial.printf("\n[FlowTrace Gateway] %s  FW %s\n", GATEWAY_ID, FW_VERSION);
#endif

  // ---- LED ----
  if (LED_PIN >= 0) {
    pinMode(LED_PIN, OUTPUT);
    ledOff();
  }

  // ---- WiFiManager ----
  // On first boot (no saved credentials) it opens an AP and serves a
  // captive portal so the user can enter WiFi credentials from a phone/laptop.
  WiFiManager wm;
  wm.setConfigPortalTimeout(WIFIMANAGER_TIMEOUT_S);

  // Add a custom parameter for the backend URL.
  WiFiManagerParameter wmBackendUrl(
    "backend_url", "Backend URL", s_backendUrl, 255);
  wm.addParameter(&wmBackendUrl);

  Serial.printf("[WiFiManager] Starting AP '%s' if needed...\n",
                WIFIMANAGER_AP_NAME);

  bool connected;
  if (strlen(WIFIMANAGER_AP_PASSWORD) > 0) {
    connected = wm.autoConnect(WIFIMANAGER_AP_NAME, WIFIMANAGER_AP_PASSWORD);
  } else {
    connected = wm.autoConnect(WIFIMANAGER_AP_NAME);
  }

  if (!connected) {
    Serial.println("[WiFiManager] Failed to connect — rebooting.");
    delay(1000);
    ESP.restart();
  }

  // Save any custom parameter set via the portal.
  const char* newUrl = wmBackendUrl.getValue();
  if (newUrl && strlen(newUrl) > 0) {
    strncpy(s_backendUrl, newUrl, sizeof(s_backendUrl) - 1);
  }

  Serial.printf("[WiFi] Connected.  IP: %s\n",
                WiFi.localIP().toString().c_str());
  ledBlink(3, 100);

  // ---- mDNS ----
  if (MDNS.begin(MDNS_HOSTNAME)) {
    MDNS.addService("http", "tcp", WEB_PORTAL_PORT);
    Serial.printf("[mDNS] Hostname: http://%s.local\n", MDNS_HOSTNAME);
  }

  // ---- ArduinoOTA ----
  ArduinoOTA.setHostname(OTA_HOSTNAME);
  if (strlen(OTA_PASSWORD) > 0) {
    ArduinoOTA.setPassword(OTA_PASSWORD);
  }

  ArduinoOTA.onStart([]() {
    String type = (ArduinoOTA.getCommand() == U_FLASH) ? "sketch" : "SPIFFS";
    Serial.printf("[OTA] Starting update (%s)...\n", type.c_str());
    s_otaActive = true;
    ledOn();
  });
  ArduinoOTA.onEnd([]() {
    Serial.println("[OTA] Complete — rebooting.");
    ledOff();
  });
  ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
    static uint8_t lastPct = 255;
    uint8_t pct = (progress * 100) / total;
    if (pct != lastPct) {
      Serial.printf("[OTA] %u%%\n", pct);
      lastPct = pct;
    }
    // Blink LED during OTA.
    digitalWrite(LED_PIN, (millis() / 200) % 2);
  });
  ArduinoOTA.onError([](ota_error_t error) {
    const char* msg = "Unknown";
    switch (error) {
      case OTA_AUTH_ERROR:    msg = "Auth Failed";    break;
      case OTA_BEGIN_ERROR:   msg = "Begin Failed";   break;
      case OTA_CONNECT_ERROR: msg = "Connect Failed"; break;
      case OTA_RECEIVE_ERROR: msg = "Receive Failed"; break;
      case OTA_END_ERROR:     msg = "End Failed";     break;
    }
    Serial.printf("[OTA] Error: %s\n", msg);
    s_otaActive = false;
    ledOff();
  });
  ArduinoOTA.begin();
  Serial.printf("[OTA] Ready on port 3232.  Hostname: %s\n", OTA_HOSTNAME);

  // ---- Web portal ----
  s_webServer.on("/",       HTTP_GET,  handleRoot);
  s_webServer.on("/update", HTTP_POST, handleUpdate);
  s_webServer.onNotFound(handleNotFound);
  s_webServer.begin();
  Serial.printf("[Portal] Listening on http://%s:%d\n",
                WiFi.localIP().toString().c_str(), WEB_PORTAL_PORT);

  // ---- MQTT ----
  s_mqtt.setServer(MQTT_BROKER_HOST, MQTT_BROKER_PORT);
  s_mqtt.setKeepAlive(MQTT_KEEPALIVE_S);
  s_mqtt.setCallback(mqttCallback);
  s_mqtt.setBufferSize(JSON_BUFFER_SIZE);

  mqttConnect();

  s_lastMqttMs = millis();
  Serial.println("[Gateway] Initialisation complete.  Entering main loop.");
}

// ---------------------------------------------------------------------------
// loop()
// ---------------------------------------------------------------------------

static uint32_t s_lastMqttReconnect = 0;
static uint32_t s_lastIdleWarn      = 0;
static uint32_t s_lastHeartbeat     = 0;

void loop() {
  // ---- OTA handler ----
  ArduinoOTA.handle();
  if (s_otaActive) return; // don't interfere during update

  // ---- Web portal ----
  s_webServer.handleClient();

  // ---- MQTT loop ----
  if (!s_mqtt.connected()) {
    uint32_t now = millis();
    if (now - s_lastMqttReconnect >= static_cast<uint32_t>(MQTT_RECONNECT_DELAY_MS)) {
      s_lastMqttReconnect = now;
      Serial.println("[MQTT] Reconnecting...");
      mqttConnect();
    }
  } else {
    s_mqtt.loop(); // must be called frequently to receive messages
  }

  // ---- Idle warning ----
  {
    uint32_t now = millis();
    if (now - s_lastMqttMs >= static_cast<uint32_t>(IDLE_WARN_INTERVAL_MS) &&
        now - s_lastIdleWarn >= static_cast<uint32_t>(IDLE_WARN_INTERVAL_MS)) {
      s_lastIdleWarn = now;
      Serial.printf("[Gateway] Warning: no MQTT data for %lu s\n",
                    (now - s_lastMqttMs) / 1000);
    }
  }

  // ---- Heartbeat publish (every 60 s) ----
  {
    uint32_t now = millis();
    if (s_mqtt.connected() &&
        now - s_lastHeartbeat >= 60000UL) {
      s_lastHeartbeat = now;
      char hb[256];
      snprintf(hb, sizeof(hb),
               "{\"gateway\":\"%s\",\"uptime_s\":%lu,"
               "\"rx\":%u,\"fwd\":%u,\"err\":%u,\"ip\":\"%s\"}",
               GATEWAY_ID, now / 1000UL,
               s_rxCount, s_fwdCount, s_errCount,
               WiFi.localIP().toString().c_str());
      s_mqtt.publish("flowtrace/status/" GATEWAY_ID, hb, true /* retain */);
      Serial.printf("[Gateway] Heartbeat published.\n");
    }
  }

  // Small yield.
  delay(5);
}
