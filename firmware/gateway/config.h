// =============================================================================
// Project FlowTrace — WiFi Gateway Configuration
// config.h
//
// All compile-time tunable parameters for the FlowTrace Gateway node.
// The gateway bridges MQTT scanner messages to the HTTP backend and
// provides OTA update + web-portal management capabilities.
// =============================================================================

#pragma once

// ---------------------------------------------------------------------------
// Gateway Identity
// ---------------------------------------------------------------------------

#ifndef GATEWAY_ID
  #define GATEWAY_ID              "GATEWAY_01"
#endif

// mDNS hostname (accessible as http://<MDNS_HOSTNAME>.local on LAN).
#define MDNS_HOSTNAME             "flowtrace-gateway"

// ---------------------------------------------------------------------------
// WiFi — managed by WiFiManager (captive portal on first boot)
// ---------------------------------------------------------------------------

// AP name shown in WiFiManager captive portal.
#define WIFIMANAGER_AP_NAME       "FlowTrace-Gateway-Setup"

// Optional AP password (leave "" for open portal).
#define WIFIMANAGER_AP_PASSWORD   ""

// How long (seconds) to wait for portal configuration before continuing
// with saved credentials (0 = wait forever).
#define WIFIMANAGER_TIMEOUT_S     180

// ---------------------------------------------------------------------------
// MQTT Broker
// ---------------------------------------------------------------------------

// Address of the MQTT broker.  Scanners publish here; the gateway subscribes.
#define MQTT_BROKER_HOST          "192.168.1.100"
#define MQTT_BROKER_PORT          1883

// Credentials (leave blank for anonymous access).
#define MQTT_USERNAME             ""
#define MQTT_PASSWORD             ""

// Client ID used by the gateway when connecting to the broker.
#define MQTT_CLIENT_ID            "flowtrace-gateway-01"

// Topic pattern the gateway subscribes to.
// Scanners publish to flowtrace/readings/<NODE_ID>.
#define MQTT_SUBSCRIBE_TOPIC      "flowtrace/readings/#"

// QoS level for subscriptions (0 = at-most-once, 1 = at-least-once).
#define MQTT_QOS                  1

// Keepalive interval (seconds).
#define MQTT_KEEPALIVE_S          60

// Reconnect delay when the broker is unreachable (ms).
#define MQTT_RECONNECT_DELAY_MS   5000

// ---------------------------------------------------------------------------
// Backend HTTP Forwarding
// ---------------------------------------------------------------------------

#define BACKEND_URL               "http://192.168.1.100:8080/api/v1/readings"
#define HTTP_TIMEOUT_MS           8000

// ---------------------------------------------------------------------------
// OTA Updates (ArduinoOTA)
// ---------------------------------------------------------------------------

// OTA hostname (shows up in Arduino IDE network ports list).
#define OTA_HOSTNAME              "flowtrace-gateway"

// OTA password (strongly recommended in production).
#define OTA_PASSWORD              "aura_ota_secret"

// ---------------------------------------------------------------------------
// Web Configuration Portal
// ---------------------------------------------------------------------------

// Port for the tiny built-in HTTP config portal.
#define WEB_PORTAL_PORT           80

// Basic-auth credentials for the portal (set to "" to disable auth).
#define WEB_PORTAL_USER           "admin"
#define WEB_PORTAL_PASS           "aura2024"

// ---------------------------------------------------------------------------
// LED Indicator
// ---------------------------------------------------------------------------

// Onboard LED (active HIGH).  Set to -1 to disable.
#define LED_PIN                   2
#define LED_BLINK_MS              300

// ---------------------------------------------------------------------------
// Miscellaneous
// ---------------------------------------------------------------------------

#define SERIAL_BAUD               115200
#define FW_VERSION                "1.0.0"

// Size of the internal JSON forwarding buffer (bytes).
#define JSON_BUFFER_SIZE          16384

// How long the gateway waits for a scanner MQTT message before logging
// a "no data" warning (milliseconds).
#define IDLE_WARN_INTERVAL_MS     30000
