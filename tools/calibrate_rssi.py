#!/usr/bin/env python3
"""Fit per-node log-distance path loss: rssi = tx_power - 10*n*log10(d).

CSV columns: node_id,node_x,node_y,tag_x,tag_y,rssi
Usage: calibrate_rssi.py samples.csv -o calibration.json
Output JSON: {node_id: {"tx_power", "n", "n_used", "n_total", "rmse_db"}}
"""
import argparse
import csv
import json
import math
from collections import defaultdict

import numpy as np


def fit(d, rssi, k=3.0, iters=5):
    """Least squares with iterative MAD-based outlier rejection."""
    x = -10 * np.log10(np.maximum(d, 0.1))
    keep = np.ones(len(x), bool)
    for _ in range(iters):
        if np.ptp(x[keep]) < 1e-9:
            raise ValueError("need samples at >= 2 distinct distances")
        n, a = np.polyfit(x[keep], rssi[keep], 1)  # rssi = a + n*x
        res = rssi - (a + n * x)
        mad = np.median(np.abs(res[keep] - np.median(res[keep]))) * 1.4826
        new = np.abs(res) <= k * max(mad, 0.5)
        if (new == keep).all():
            break
        keep = new
    rmse = float(np.sqrt(np.mean(res[keep] ** 2)))
    return dict(tx_power=round(float(a), 2), n=round(float(n), 3), n_used=int(keep.sum()),
                n_total=len(x), rmse_db=round(rmse, 2))


def calibrate(rows):
    by = defaultdict(lambda: ([], []))
    for r in rows:
        dist = math.hypot(float(r["tag_x"]) - float(r["node_x"]), float(r["tag_y"]) - float(r["node_y"]))
        by[r["node_id"]][0].append(dist)
        by[r["node_id"]][1].append(float(r["rssi"]))
    return {nid: fit(np.array(d), np.array(s)) for nid, (d, s) in by.items()}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("csv")
    p.add_argument("-o", "--out", default="calibration.json")
    a = p.parse_args()
    out = calibrate(list(csv.DictReader(open(a.csv))))
    json.dump(out, open(a.out, "w"), indent=2)
    for nid, v in out.items():
        print(nid, v)
