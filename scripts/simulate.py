"""
simulate.py — FlowTrace BLE Reading Simulator
Simulates 3 scanner nodes detecting 5 moving users in a 10m x 10m room.
Use this to test the backend without physical hardware.

Usage:
    python scripts/simulate.py --server http://localhost:8000 --users 5 --duration 300
"""

import asyncio
import httpx
import random
import math
import time
import argparse
from datetime import datetime, timezone

# ─── Node layout (x, y) in meters, for a 10m x 10m room ───────────────────────
NODES = {
    "NODE_A": {"x": 0.5, "y": 0.5},
    "NODE_B": {"x": 9.5, "y": 0.5},
    "NODE_C": {"x": 5.0, "y": 9.5},
    "NODE_D": {"x": 0.5, "y": 9.5},
    "NODE_E": {"x": 9.5, "y": 9.5},
}

# ─── Venue zones ───────────────────────────────────────────────────────────────
ZONES = {
    "VR_ZONE":    {"x": 1, "y": 1, "w": 3, "h": 3},
    "LASER_TAG":  {"x": 6, "y": 1, "w": 3, "h": 3},
    "FOOD_COURT": {"x": 3, "y": 5, "w": 4, "h": 4},
    "EXIT":       {"x": 4, "y": 0, "w": 2, "h": 1},
}

# ─── RSSI simulation parameters ────────────────────────────────────────────────
TX_POWER = -59        # RSSI at 1 meter (dBm)
PATH_LOSS_EXP = 2.2   # environment-specific (2.0 = free space, 3.0 = indoors)
NOISE_STD = 4         # random noise on RSSI readings (dBm)


def distance_to_rssi(distance_m: float) -> int:
    """Convert a true distance to a simulated RSSI value with noise."""
    if distance_m < 0.1:
        distance_m = 0.1
    rssi = TX_POWER - 10 * PATH_LOSS_EXP * math.log10(distance_m)
    rssi += random.gauss(0, NOISE_STD)
    return int(rssi)


class SimulatedUser:
    """A virtual visitor wandering around the venue."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.x = random.uniform(1, 9)
        self.y = random.uniform(1, 9)
        self.target_x = self.x
        self.target_y = self.y
        self.speed = random.uniform(0.3, 0.8)  # m/s
        self.dwell_timer = 0
        self.battery_pct = random.randint(70, 100)

    def update(self, dt: float):
        """Move the user towards their target, pick new target when reached."""
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        dist = math.sqrt(dx**2 + dy**2)

        if dist < 0.2 or self.dwell_timer <= 0:
            # Pick a new target (bias toward zones)
            zone = random.choice(list(ZONES.values()))
            self.target_x = zone["x"] + random.uniform(0, zone["w"])
            self.target_y = zone["y"] + random.uniform(0, zone["h"])
            self.target_x = max(0.1, min(9.9, self.target_x))
            self.target_y = max(0.1, min(9.9, self.target_y))
            self.dwell_timer = random.uniform(10, 60)  # dwell 10–60 seconds
        else:
            # Move toward target
            speed = min(self.speed * dt, dist)
            self.x += (dx / dist) * speed
            self.y += (dy / dist) * speed
            self.dwell_timer -= dt

        # Clamp to room bounds
        self.x = max(0.1, min(9.9, self.x))
        self.y = max(0.1, min(9.9, self.y))

    def get_readings(self) -> list[dict]:
        """Generate RSSI readings from each node for this user's current position."""
        readings = []
        for node_id, node_pos in NODES.items():
            dist = math.sqrt(
                (self.x - node_pos["x"]) ** 2 + (self.y - node_pos["y"]) ** 2
            )
            rssi = distance_to_rssi(dist)
            readings.append({
                "node_id": node_id,
                "device_id": self.user_id,
                "rssi": rssi,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "battery_pct": self.battery_pct,
                # Include true position for ground truth comparison
                "_true_x": round(self.x, 2),
                "_true_y": round(self.y, 2),
            })
        return readings


async def post_readings(client: httpx.AsyncClient, server: str, readings: list[dict]):
    """Send a batch of readings to the backend."""
    try:
        resp = await client.post(
            f"{server}/api/v1/readings",
            json={"readings": readings},
            timeout=5.0,
        )
        if resp.status_code != 200:
            print(f"  [WARN] Server returned {resp.status_code}: {resp.text[:100]}")
    except httpx.ConnectError:
        print(f"  [ERROR] Cannot connect to {server}. Is the backend running?")
    except Exception as e:
        print(f"  [ERROR] {e}")


async def run_simulation(server: str, num_users: int, duration: int):
    """Main simulation loop."""
    print(f"🟢 FlowTrace Simulator starting")
    print(f"   Server: {server}")
    print(f"   Users:  {num_users}")
    print(f"   Duration: {duration}s")
    print(f"   Nodes:  {list(NODES.keys())}")
    print()

    users = [SimulatedUser(f"FLOWTRACE_TAG_{i:03d}") for i in range(1, num_users + 1)]
    start_time = time.time()
    tick = 0

    async with httpx.AsyncClient() as client:
        while time.time() - start_time < duration:
            tick_start = time.time()
            dt = 2.0  # simulate 2-second ticks

            all_readings = []
            for user in users:
                user.update(dt)
                all_readings.extend(user.get_readings())

            await post_readings(client, server, all_readings)

            elapsed = time.time() - start_time
            tick += 1
            print(
                f"  Tick {tick:04d} | t={elapsed:.0f}s | "
                f"{len(users)} users | {len(all_readings)} readings sent"
            )

            # Print user positions every 10 ticks
            if tick % 10 == 0:
                for u in users:
                    print(f"    {u.user_id}: ({u.x:.1f}, {u.y:.1f})")

            # Sleep until next tick
            sleep_time = max(0, dt - (time.time() - tick_start))
            await asyncio.sleep(sleep_time)

    print("\n✅ Simulation complete.")


def main():
    parser = argparse.ArgumentParser(description="FlowTrace BLE Reading Simulator")
    parser.add_argument("--server", default="http://localhost:8000", help="Backend server URL")
    parser.add_argument("--users", type=int, default=5, help="Number of simulated users")
    parser.add_argument("--duration", type=int, default=300, help="Simulation duration in seconds")
    args = parser.parse_args()

    asyncio.run(run_simulation(args.server, args.users, args.duration))


if __name__ == "__main__":
    main()
