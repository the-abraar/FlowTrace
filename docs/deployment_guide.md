# FlowTrace Deployment Guide

## Production Server Setup
We recommend running the backend on a dedicated Linux machine (Ubuntu 22.04 LTS) or a VPS if the venue has reliable internet. For offline-first venues, a Raspberry Pi 4 (4GB+) works perfectly.

### Prerequisites
*   Docker & Docker Compose installed.
*   Static IP for the server (so nodes can always find it).

### Steps
1.  Clone the repository.
2.  Set `OPENAI_API_KEY` in `backend/.env`.
3.  Set `VITE_API_URL` to the server's static IP in `dashboard/.env.production`.
4.  Run `docker-compose up -d --build`.

## Node Deployment Strategy
*   **Height:** Place nodes 2.5 - 3 meters high to ensure line-of-sight over crowds (human bodies block 2.4GHz signals).
*   **Geometry:** Aim for equilateral triangles between nodes. Avoid placing all nodes in a straight line.
*   **Power:** Use reliable 5V 2A USB power adapters. Avoid cheap adapters that introduce electrical noise.

## Network Configuration
*   **VLAN:** Put all ESP32 nodes on a dedicated IoT VLAN. They should only have access to the backend server IP on port 8000 (HTTP) or 1883 (MQTT). No general internet access required.
