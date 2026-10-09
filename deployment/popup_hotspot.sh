#!/bin/bash
# Configure Raspberry Pi as a WiFi Hotspot for FlowTrace Pop-Ups
# Uses hostapd and dnsmasq

set -e

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

echo "Installing hostapd and dnsmasq..."
apt-get update
apt-get install -y hostapd dnsmasq iptables netfilter-persistent iptables-persistent

echo "Stopping services during configuration..."
systemctl stop hostapd || true
systemctl stop dnsmasq || true

# Configure static IP for wlan0
echo "Configuring static IP for wlan0 (192.168.4.1)..."
cat <<EOF > /etc/dhcpcd.conf
# FlowTrace Hotspot Config
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF

# Restart dhcpcd
systemctl restart dhcpcd

# Configure dnsmasq
echo "Configuring dnsmasq..."
if [ -f /etc/dnsmasq.conf ]; then
    mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig
fi

cat <<EOF > /etc/dnsmasq.conf
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.100,255.255.255.0,24h
domain=flowtrace.local
address=/api.flowtrace.local/192.168.4.1
address=/mqtt.flowtrace.local/192.168.4.1
EOF

# Configure hostapd
echo "Configuring hostapd..."
cat <<EOF > /etc/hostapd/hostapd.conf
interface=wlan0
driver=nl80211
ssid=FlowTrace_PopUp
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=FlowTraceSecure2026!
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|g' /etc/default/hostapd

echo "Starting services..."
systemctl unmask hostapd
systemctl enable hostapd
systemctl enable dnsmasq
systemctl start hostapd
systemctl start dnsmasq

echo "Hotspot setup complete! SSID: FlowTrace_PopUp"
