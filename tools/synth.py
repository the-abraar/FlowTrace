"""Synthetic RSSI generator (log-distance + Gaussian shadowing) for testing the tools."""
import csv
import math
import random

FIELDS = ["node_id", "node_x", "node_y", "tag_x", "tag_y", "rssi"]


def generate(nodes, points, params, samples=30, sigma=4.0, outlier_frac=0.0, seed=0):
    """nodes: {id:(x,y)}; params: {id:(tx_power,n)}. Returns list of row dicts."""
    rng = random.Random(seed)
    rows = []
    for px, py in points:
        for nid, (nx, ny) in nodes.items():
            a, n = params[nid]
            d = max(math.hypot(px - nx, py - ny), 0.1)
            for _ in range(samples):
                r = a - 10 * n * math.log10(d) + rng.gauss(0, sigma)
                if rng.random() < outlier_frac:
                    r -= rng.uniform(15, 30)  # body-block / multipath dropout
                rows.append(dict(node_id=nid, node_x=nx, node_y=ny, tag_x=px, tag_y=py, rssi=round(r)))
    return rows


def write_csv(rows, path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)
