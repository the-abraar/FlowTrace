import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import synth
from calibrate_rssi import calibrate
from evaluate_accuracy import evaluate

NODES = {"A": (0, 0), "B": (10, 0), "C": (0, 10), "D": (10, 10)}
PARAMS = {"A": (-59, 2.0), "B": (-62, 2.5), "C": (-57, 2.2), "D": (-60, 1.8)}
GRID = [(x, y) for x in (1.5, 3, 5, 7, 8.5) for y in (1.5, 3, 5, 7, 8.5)]


def test_calibration_recovers_params_with_outliers():
    rows = synth.generate(NODES, GRID, PARAMS, samples=40, sigma=3, outlier_frac=0.1, seed=1)
    out = calibrate(rows)
    for nid, (a, n) in PARAMS.items():
        assert abs(out[nid]["tx_power"] - a) < 2.5 and abs(out[nid]["n"] - n) < 0.25
        assert out[nid]["n_used"] < out[nid]["n_total"]  # outliers were rejected


def test_evaluation_accuracy_and_calibration_helps():
    rows = synth.generate(NODES, GRID, PARAMS, samples=40, sigma=2, seed=2)
    cal = calibrate(rows)
    raw, fit = evaluate(rows), evaluate(rows, cal)
    assert fit["n_points"] == len(GRID)
    assert fit["median_m"] < 2.0
    assert fit["median_m"] <= raw["median_m"]
    assert fit["median_m"] <= fit["p90_m"] <= fit["max_m"]
    assert 0 <= fit["zone_misclass_overall"] <= 1
