#!/bin/bash
set -euo pipefail

# FlowTrace Edge Deployment Setup Script for Raspberry Pi 4
# Sets up Docker, Docker Compose, Static IP, and starts the FlowTrace stack.

TARGET_DIR="/opt/flowtrace"
STATIC_IP="192.168.1.100/24"
ROUTER_IP="192.168.1.1"
DNS_IPS="8.8.8.8 1.1.1.1"

echo "=== FlowTrace Offline Edge Setup ==="

# 1. Update packages
echo "[1/4] Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# 2. Install Docker and Docker Compose
echo "[2/4] Installing Docker and Docker Compose..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
fi

if ! command -v docker-compose &> /dev/null; then
    sudo apt-get install -y docker-compose
fi

# 3. Configure Static IP
echo "[3/4] Configuring Static IP on eth0 ($STATIC_IP)..."
# Check if using NetworkManager (Bookworm+) or dhcpcd (Bullseye and older)
if command -v nmcli &> /dev/null; then
    # NetworkManager configuration
    sudo nmcli con mod "Wired connection 1" ipv4.addresses $STATIC_IP ipv4.gateway $ROUTER_IP ipv4.dns "$DNS_IPS" ipv4.method manual || \
    sudo nmcli con add type ethernet ifname eth0 con-name "eth0" ipv4.addresses $STATIC_IP ipv4.gateway $ROUTER_IP ipv4.dns "$DNS_IPS" ipv4.method manual
    sudo nmcli con up "Wired connection 1" || sudo nmcli con up "eth0"
elif [ -f /etc/dhcpcd.conf ]; then
    # dhcpcd configuration
    if ! grep -q "interface eth0" /etc/dhcpcd.conf; then
        cat <<EOF | sudo tee -a /etc/dhcpcd.conf

interface eth0
static ip_address=$STATIC_IP
static routers=$ROUTER_IP
static domain_name_servers=$DNS_IPS
EOF
        sudo systemctl restart dhcpcd
    fi
else
    echo "Warning: Neither nmcli nor dhcpcd found. Static IP not configured."
fi

# 4. Start the FlowTrace Stack
echo "[4/4] Starting the FlowTrace stack..."
if [ -d "$TARGET_DIR" ] && [ -f "$TARGET_DIR/docker-compose.yml" ]; then
    cd "$TARGET_DIR"
    sudo docker-compose pull || echo "Offline mode: Skipping pull"
    sudo docker-compose up -d
    echo "FlowTrace stack started successfully."
else
    echo "Error: Directory $TARGET_DIR or docker-compose.yml not found."
    echo "Please ensure the application files are copied to $TARGET_DIR before running this script."
fi

echo "=== Setup Complete ==="
