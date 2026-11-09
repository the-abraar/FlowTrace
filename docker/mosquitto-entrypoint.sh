#!/bin/sh
# Builds the broker password file from env, then runs mosquitto (see docker/mosquitto.conf).
set -eu
: "${MQTT_USERNAME:?set MQTT_USERNAME}" "${MQTT_PASSWORD:?set MQTT_PASSWORD}"
umask 077
rm -f /mosquitto/passwd
mosquitto_passwd -c -b /mosquitto/passwd "$MQTT_USERNAME" "$MQTT_PASSWORD"
chown mosquitto:mosquitto /mosquitto/passwd  # mosquitto drops root before it reads the file
exec mosquitto -c /mosquitto/config/mosquitto.conf
