# RSSI Field Test Protocol

**Status: NO RSSI ACCURACY MEASUREMENTS EXIST YET.** Every accuracy figure in the pitch,
README or marketing material is unverified until this protocol has been run on real hardware.
The tools below were validated only on synthetic data (`tools/tests`).

## Equipment
- 3+ (ideally 4) production-firmware nodes mounted at final installation height, positions surveyed with a laser measure (+/- 5 cm).
- 2 tag/phone types (the ones customers will actually use).
- Tape measure or laser, floor markers, a laptop logging readings.

## Procedure
1. **Survey.** Draw the venue to scale. Record each node's (x, y) in metres, same origin as `VENUE_ZONES`: (0, 0) is the south-west corner, x grows east, y grows north.
2. **Grid.** Mark test points on a 2 m grid across the walkable floor (min 25 points; a 10x10 m room = ~25). Add 4 points within 0.5 m of each zone boundary (boundary points drive zone misclassification).
3. **Capture.** At each point, hold the tag at waist height (1.0 m), body *not* between tag and nodes, and log **N = 60 samples per node** (about 60 s at 1 Hz). Repeat at 3 orientations (facing 0, 120, 240 degrees) and, for phones, in-hand vs. trouser pocket.
4. **Conditions.** Run the full grid twice: (a) empty venue; (b) crowd of >= 20 people moving normally (or at least 50% of expected peak). Run a third pass at a different time of day if the venue has changing furniture/doors.
5. **Record** per sample: `node_id,node_x,node_y,tag_x,tag_y,rssi`; and in a side log: tag model, orientation, pocket/hand, crowd level, timestamp, firmware version, TX power, temperature. Never mix conditions in one file.
6. **Split.** Use ~half of the points (alternating) for calibration, the rest for evaluation. Never evaluate on calibration points.

## Analysis
```
python tools/calibrate_rssi.py calib_points.csv -o calibration.json
python tools/evaluate_accuracy.py eval_points.csv --calibration calibration.json
RSSI_CALIBRATION_JSON=calibration.json   # backend loads per-node params (every PositionEngine, incl. the fleet's and module-level position_engine)
```
Report median, p90, max error and per-zone misclassification, separately per condition and per orientation. Also report `rmse_db` and `n_used/n_total` from calibration (large rejection = unreliable environment).

## Thresholds for claims (p90 over eval points, crowd condition unless stated)
| Claim | Needed |
|---|---|
| "Zone-level occupancy / dwell time" | zone misclassification <= 10% overall, <= 20% for boundary points; median error <= 2.5 m |
| "Room-level / heatmap flow" | median <= 3 m, p90 <= 5 m |
| "~1-2 m positioning" | median <= 1.5 m AND p90 <= 3 m, empty AND crowded |
| "Sub-meter" | Not expected to be achievable with RSSI; do not claim |

State the venue, node count, conditions and N in any published figure. If crowded results are worse than empty, quote the crowded ones.

## TODO
- Kalman-smoothed (time-series) evaluation: current evaluator uses one median fix per point.
