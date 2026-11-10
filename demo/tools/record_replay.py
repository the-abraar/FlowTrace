#!/usr/bin/env python3
"""Record a replay for demo/index.html: 4 scripted tags walk the venue, the backend's /ws positions are saved.

Readings are SIMULATED (no hardware): RSSI comes from scripts/simulate.py's model (n=2.2, 4 dB noise) at the
seeded node positions; positions, zones, bounce rate and A/B split are the real backend's output for them.

Usage (backend running with INGEST_API_KEY set, VENUE_WIDTH_M=10 VENUE_HEIGHT_M=10):
    INGEST_API_KEY=<key> python demo/tools/record_replay.py --server http://127.0.0.1:18000 --duration 300
Writes demo/data/replay.json and demo/data/summary.json.
"""
import argparse
import asyncio
import json
import math
import os
import random
import statistics
import sys
import time
from datetime import datetime, timezone

import httpx
import websockets

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from positioning.zone_detector import VENUE_ZONES, ZoneDetector  # noqa: E402
from simulate import NODES, NOISE_STD, PATH_LOSS_EXP, TX_POWER, auth_headers, distance_to_rssi  # noqa: E402

TICK_S = 2.0  # same cadence as scripts/simulate.py
SPEED = 0.7  # walking speed, m/s
CENTRE = {z.name: (sum(p[0] for p in z.polygon) / len(z.polygon), sum(p[1] for p in z.polygon) / len(z.polygon))
          for z in VENUE_ZONES}
# (start offset s, [(zone, dwell s), ...]); each tag walks zone centre to zone centre, then loops.
SCRIPTS = {
    "TAG_1": (0, [("ENTRANCE", 10), ("LASER_TAG", 120), ("FOOD_COURT", 90), ("EXIT", 20)]),
    "TAG_2": (20, [("ENTRANCE", 10), ("RETAIL", 20), ("EXIT", 10)]),  # quick look: should count as a bounce
    "TAG_3": (40, [("ENTRANCE", 10), ("VR_ZONE", 150), ("RETAIL", 70), ("EXIT", 10)]),
    "TAG_4": (60, [("ENTRANCE", 10), ("FOOD_COURT", 80), ("VR_ZONE", 70), ("LASER_TAG", 90), ("EXIT", 10)]),
}


def legs(script):
    """[(x0, y0, x1, y1, walk_s, dwell_s)] for one loop of a script."""
    out, stops = [], script + script[:1]
    for (a, _), (b, dwell) in zip(stops, stops[1:]):
        (x0, y0), (x1, y1) = CENTRE[a], CENTRE[b]
        out.append((x0, y0, x1, y1, math.dist((x0, y0), (x1, y1)) / SPEED, dwell))
    return out


def true_pos(tag, t):
    """Ground-truth (x, y) of *tag* at *t* seconds into the run, or None before it enters."""
    start, script = SCRIPTS[tag]
    if t < start:
        return None
    path = legs(script)
    t = (t - start) % sum(w + d for *_, w, d in path)
    for x0, y0, x1, y1, walk, dwell in path:
        if t < walk:
            f = t / walk
            return (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)
        t -= walk
        if t < dwell:
            return (x1, y1)
        t -= dwell
    return (x1, y1)


async def send(client, server, t0, duration):
    while (t := time.monotonic() - t0) < duration:
        readings = []
        for tag in SCRIPTS:
            p = true_pos(tag, t)
            if p is None:
                continue
            for node_id, n in NODES.items():
                readings.append({"node_id": node_id, "device_id": tag, "rssi": distance_to_rssi(math.dist(p, (n["x"], n["y"]))),
                                 "ts_ms": int(t * 1000), "timestamp": datetime.now(timezone.utc).isoformat()})
        if readings:
            r = await client.post(f"{server}/api/v1/readings", json={"readings": readings}, timeout=5.0)
            if r.status_code != 200 or r.json().get("status") != "ok":
                raise SystemExit(f"backend refused readings: {r.status_code} {r.text[:200]}")
        await asyncio.sleep(max(0.0, TICK_S - (time.monotonic() - t0 - t)))


async def listen(ws_url, t0, duration, frames, zd):
    async with websockets.connect(ws_url) as ws:
        while (t := time.monotonic() - t0) < duration:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=duration - t))
            except asyncio.TimeoutError:
                break
            if msg.get("type") != "positions":
                continue
            t = time.monotonic() - t0
            tags = []
            for d in msg["data"]:
                tp = true_pos(d["device_id"], t) if d["device_id"] in SCRIPTS else None
                if tp is None:
                    continue
                tags.append({"id": d["device_id"], "x": round(d["x"], 2), "y": round(d["y"], 2), "zone": d["zone"],
                             "conf": round(d["confidence"], 2), "tx": round(tp[0], 2), "ty": round(tp[1], 2),
                             "tzone": zd.point_in_zone(*tp)})
            frames.append({"t": round(t, 1), "tags": tags})


async def run(server, duration):
    random.seed(7)  # same noise each run
    zd = ZoneDetector()
    frames = []
    ws_url = server.replace("http", "ws", 1) + "/ws"
    t0 = time.monotonic()
    async with httpx.AsyncClient(headers=auth_headers()) as client:
        await asyncio.gather(send(client, server, t0, duration), listen(ws_url, t0, duration, frames, zd))
        summary = (await client.get(f"{server}/api/v1/analytics/summary")).json()
    return frames, summary


def visits(frames, key):
    """Finished zone visits per frame sequence: [(zone, seconds)], zone read from tag field *key*."""
    out, cur = [], {}
    for f in frames:
        for g in f["tags"]:
            z, (cz, t0) = g[key], cur.get(g["id"], (None, f["t"]))
            if z != cz:
                if cz is not None:
                    out.append((cz, f["t"] - t0))
                cur[g["id"]] = (z, f["t"])
    return out


def score(frames):
    rows = [g for f in frames for g in f["tags"]]
    err = sorted(math.dist((g["x"], g["y"]), (g["tx"], g["ty"])) for g in rows)
    seen, truth = visits(frames, "zone"), visits(frames, "tzone")
    return {"samples": len(rows),
            "finished_visits": {"backend": len(seen), "script": len(truth)},
            "bounce_rate_script": round(sum(d < 60 for _, d in truth) / len(truth), 3) if truth else None,
            "zone_match": round(sum(g["zone"] == g["tzone"] for g in rows) / len(rows), 3),
            "error_m_median": round(statistics.median(err), 2),
            "error_m_p90": round(err[int(0.9 * (len(err) - 1))], 2)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--server", default="http://127.0.0.1:18000")
    ap.add_argument("--duration", type=float, default=300)
    ap.add_argument("--out", default=os.path.join(ROOT, "demo", "data"))
    a = ap.parse_args()
    frames, summary = asyncio.run(run(a.server, a.duration))
    assert frames, "no /ws positions received"
    meta = {"recorded": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "duration_s": a.duration, "tick_s": TICK_S,
            "simulated": "RSSI readings are simulated (scripts/simulate.py model); no hardware was used",
            "rssi_model": {"tx_power_dbm": TX_POWER, "path_loss_exp": PATH_LOSS_EXP, "noise_std_db": NOISE_STD},
            "nodes": [{"id": k, **v} for k, v in NODES.items()],
            "zones": [{"name": z.name, "label": z.label, "color": z.color, "polygon": z.polygon} for z in VENUE_ZONES],
            "scripts": {k: {"start_s": s, "stops": [{"zone": z, "dwell_s": d} for z, d in st]} for k, (s, st) in SCRIPTS.items()}}
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "replay.json"), "w") as f:
        json.dump({"meta": meta, "frames": frames}, f, separators=(",", ":"))
    with open(os.path.join(a.out, "summary.json"), "w") as f:
        json.dump({"source": "GET /api/v1/analytics/summary at the end of the run", "backend": summary,
                   "vs_script_truth": score(frames)}, f, indent=1)
    print(json.dumps(score(frames)), len(frames), "frames")


if __name__ == "__main__":
    # self-check: the script walks where it says (entry stop at t=start, dwell in the first target zone)
    assert true_pos("TAG_2", 0) is None and true_pos("TAG_2", 20) == CENTRE["ENTRANCE"]
    assert ZoneDetector().point_in_zone(*true_pos("TAG_3", 40 + 60)) == "VR_ZONE"
    _f = [{"t": t, "tags": [{"id": "A", "zone": z}]} for t, z in [(0, "X"), (2, "X"), (70, "Y"), (72, "X")]]
    assert visits(_f, "zone") == [("X", 70), ("Y", 2)]
    main()
