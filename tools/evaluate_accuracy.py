#!/usr/bin/env python3
"""Run backend positioning on raw readings and report error vs ground truth.

CSV columns: node_id,node_x,node_y,tag_x,tag_y,rssi  (tag_x/tag_y = ground truth).
Per test point, per node, the median RSSI is fed to PositionEngine (fresh engine per point,
so Kalman smoothing is not exercised: this measures raw triangulation accuracy).
Usage: evaluate_accuracy.py readings.csv [--calibration calibration.json] [--bounds W H]
"""
import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from positioning.triangulator import NodeAnchor, PositionEngine, rssi_to_distance  # noqa: E402
from positioning.zone_detector import VENUE_ZONES, ZoneDetector  # noqa: E402


def evaluate(rows, calib=None, bounds=None, zones=None):
    pts = defaultdict(lambda: defaultdict(list))
    pos = {}
    for r in rows:
        t = (float(r["tag_x"]), float(r["tag_y"]))
        pts[t][r["node_id"]].append(float(r["rssi"]))
        pos[r["node_id"]] = (float(r["node_x"]), float(r["node_y"]))
    zd = ZoneDetector(zones or VENUE_ZONES)
    errs, per_zone, skipped = [], defaultdict(lambda: [0, 0]), 0
    for (tx, ty), per_node in pts.items():
        anchors = []
        for nid, v in per_node.items():
            c = (calib or {}).get(nid, {})
            m = float(np.median(v))
            anchors.append(NodeAnchor(nid, *pos[nid], rssi_to_distance(m, c.get("tx_power"), c.get("n")), int(round(m))))
        est = PositionEngine(bounds=bounds).estimate("t", anchors)
        if est is None:
            skipped += 1
            continue
        errs.append(math.hypot(est.x - tx, est.y - ty))
        tz, ez = zd.point_in_zone(tx, ty), zd.point_in_zone(est.x, est.y)
        per_zone[tz][0] += 1
        per_zone[tz][1] += tz != ez
    e = np.array(errs)
    return dict(
        n_points=len(e), n_skipped=skipped,
        median_m=round(float(np.median(e)), 2), p90_m=round(float(np.percentile(e, 90)), 2),
        max_m=round(float(e.max()), 2),
        zone_misclass_rate={str(z): round(w / n, 3) for z, (n, w) in per_zone.items()},
        zone_misclass_overall=round(sum(w for _, w in per_zone.values()) / max(1, sum(n for n, _ in per_zone.values())), 3),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("csv")
    p.add_argument("--calibration")
    p.add_argument("--bounds", type=float, nargs=2)
    a = p.parse_args()
    cal = json.load(open(a.calibration)) if a.calibration else None
    print(json.dumps(evaluate(list(csv.DictReader(open(a.csv))), cal, tuple(a.bounds) if a.bounds else None), indent=2))
