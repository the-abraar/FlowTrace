"""
positioning/triangulator.py
────────────────────────────
BLE RSSI-to-distance conversion + weighted least-squares triangulation
with a per-device Kalman filter for smooth position tracking.

Algorithm overview
──────────────────
1. RSSI → distance via log-distance path-loss model:
       d = 10 ^ ((TxPower - RSSI) / (10 × n))
2. Weighted least-squares from 3+ node readings to (x, y).
3. Kalman filter applied per device to smooth jitter.
4. Confidence derived from residual error and number of anchors.

Classes
───────
- KalmanFilter2D   — Simple constant-velocity 2-D Kalman filter
- PositionEngine   — Manages per-device state, exposes estimate()
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import NamedTuple

import numpy as np

from config import settings

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────────────


class NodeAnchor(NamedTuple):
    """A node's known position and its distance estimate to the target."""

    node_id: str
    x: float
    y: float
    distance: float
    rssi: int


@dataclass
class PositionEstimate:
    """Output of the triangulation + Kalman pipeline."""

    x: float
    y: float
    confidence: float          # [0.0 – 1.0]
    anchor_count: int
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "confidence": round(self.confidence, 3),
            "anchor_count": self.anchor_count,
            "timestamp": self.timestamp.isoformat(),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Kalman filter (2-D, constant-velocity model)
# ──────────────────────────────────────────────────────────────────────────────


class KalmanFilter2D:
    """
    Minimal 2-D Kalman filter assuming constant velocity.

    State vector: [x, y, vx, vy]
    Measurement:  [x, y]
    """

    def __init__(
        self,
        process_noise: float = 0.1,
        measurement_noise: float = 1.5,
    ) -> None:
        # State vector [x, y, vx, vy]
        self._x = np.zeros((4, 1), dtype=float)
        # State covariance
        self._P = np.eye(4, dtype=float) * 500.0
        # Transition matrix (dt inserted at predict time)
        self._F = np.eye(4, dtype=float)
        # Measurement matrix
        self._H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=float)
        # Process noise covariance
        self._Q = np.eye(4, dtype=float) * process_noise
        # Measurement noise covariance
        self._R = np.eye(2, dtype=float) * measurement_noise
        self._last_update: datetime | None = None
        self._initialised = False

    def initialise(self, x: float, y: float) -> None:
        """Seed the filter with a first observation."""
        self._x = np.array([[x], [y], [0.0], [0.0]], dtype=float)
        self._initialised = True
        self._last_update = datetime.utcnow()

    def update(self, x: float, y: float) -> tuple[float, float]:
        """
        Run one predict + update cycle.

        Parameters
        ----------
        x, y : Measured position in metres.

        Returns
        -------
        Filtered (x, y) tuple.
        """
        if not self._initialised:
            self.initialise(x, y)
            return x, y

        now = datetime.utcnow()
        dt = (now - self._last_update).total_seconds() if self._last_update else 1.0
        self._last_update = now

        # Build transition matrix with current dt
        F = np.eye(4, dtype=float)
        F[0, 2] = dt
        F[1, 3] = dt

        # Predict
        self._x = F @ self._x
        self._P = F @ self._P @ F.T + self._Q

        # Update
        z = np.array([[x], [y]], dtype=float)
        y_res = z - self._H @ self._x
        S = self._H @ self._P @ self._H.T + self._R
        K = self._P @ self._H.T @ np.linalg.inv(S)
        self._x = self._x + K @ y_res
        self._P = (np.eye(4) - K @ self._H) @ self._P

        return float(self._x[0, 0]), float(self._x[1, 0])


# ──────────────────────────────────────────────────────────────────────────────
# RSSI → distance
# ──────────────────────────────────────────────────────────────────────────────


def rssi_to_distance(
    rssi: int,
    tx_power: float | None = None,
    n: float | None = None,
) -> float:
    """
    Convert RSSI (dBm) to estimated distance (metres) using the
    log-distance path-loss model.

        d = 10 ^ ((TxPower - RSSI) / (10 × n))

    Parameters
    ----------
    rssi     : Measured RSSI in dBm (typically negative).
    tx_power : Reference RSSI at 1 metre (dBm).  Defaults to settings value.
    n        : Path-loss exponent.  Defaults to settings value.

    Returns
    -------
    Estimated distance in metres (minimum 0.1 m to avoid log singularity).
    """
    tx_power = tx_power if tx_power is not None else settings.BLE_TX_POWER
    n = n if n is not None else settings.BLE_PATH_LOSS_EXPONENT

    exponent = (tx_power - rssi) / (10.0 * n)
    distance = math.pow(10.0, exponent)
    return max(distance, 0.1)


# ──────────────────────────────────────────────────────────────────────────────
# Weighted least-squares triangulation
# ──────────────────────────────────────────────────────────────────────────────


def triangulate(anchors: list[NodeAnchor]) -> tuple[float, float, float]:
    """
    Weighted least-squares position estimate from 3+ anchors.

    Uses the linearised distance equations:
        (x - xi)^2 + (y - yi)^2 = di^2

    Subtracting the last anchor's equation linearises the system.
    Weights are inversely proportional to distance (closer ≈ more reliable).

    Parameters
    ----------
    anchors : List of NodeAnchor with known (x, y) and estimated distance d.

    Returns
    -------
    (x_est, y_est, confidence) — confidence in [0, 1].

    Raises
    ------
    ValueError : If fewer than 3 anchors are provided.
    """
    if len(anchors) < 2:
        raise ValueError("At least 2 anchors required for triangulation.")

    if len(anchors) == 2:
        # Linear interpolation along the line between two anchors
        a, b = anchors
        total = a.distance + b.distance
        ratio = a.distance / total if total > 0 else 0.5
        x_est = a.x + ratio * (b.x - a.x)
        y_est = a.y + ratio * (b.y - a.y)
        return x_est, y_est, 0.4   # low confidence for 2-anchor case

    # Build A and b matrices for WLS (using anchor[0] as reference)
    ref = anchors[-1]
    rows_A = []
    rows_b = []
    weights = []

    for anc in anchors[:-1]:
        # Linearised: 2(xi - xn)x + 2(yi - yn)y = di^2 - dn^2 - xi^2 + xn^2 - yi^2 + yn^2
        row_a = [
            2.0 * (anc.x - ref.x),
            2.0 * (anc.y - ref.y),
        ]
        row_b = (
            anc.x**2
            - ref.x**2
            + anc.y**2
            - ref.y**2
            - anc.distance**2
            + ref.distance**2
        )
        rows_A.append(row_a)
        rows_b.append(row_b)
        # Weight: inverse of distance squared (closer nodes are more reliable)
        w = 1.0 / max(anc.distance**2, 0.01)
        weights.append(w)

    A = np.array(rows_A, dtype=float)
    b_vec = np.array(rows_b, dtype=float)
    W = np.diag(weights)

    # WLS: x = (A^T W A)^-1 A^T W b
    try:
        AtWA = A.T @ W @ A
        AtWb = A.T @ W @ b_vec
        result = np.linalg.solve(AtWA, AtWb)
        x_est, y_est = float(result[0]), float(result[1])
    except np.linalg.LinAlgError:
        logger.warning("Singular matrix in triangulation — falling back to centroid.")
        x_est = float(np.mean([a.x for a in anchors]))
        y_est = float(np.mean([a.y for a in anchors]))

    # Confidence: derived from residual error vs number of anchors
    residuals = [
        abs(math.hypot(x_est - a.x, y_est - a.y) - a.distance) for a in anchors
    ]
    mean_residual = float(np.mean(residuals))
    # Map residual to [0, 1] with sigmoid-like decay (0 error = 1.0, 5m error ≈ 0.04)
    confidence = 1.0 / (1.0 + mean_residual)
    # Bonus for more anchors
    anchor_bonus = min((len(anchors) - 2) * 0.05, 0.2)
    confidence = min(confidence + anchor_bonus, 1.0)

    return x_est, y_est, confidence


def load_calibration() -> dict[str, dict]:
    """Per-node {tx_power, n} from tools/calibrate_rssi.py output at $RSSI_CALIBRATION_JSON; {} if unset."""
    path = os.environ.get("RSSI_CALIBRATION_JSON")
    if not path:
        return {}
    with open(path) as f:
        return json.load(f)


# ──────────────────────────────────────────────────────────────────────────────
# Position Engine
# ──────────────────────────────────────────────────────────────────────────────


class PositionEngine:
    """
    Maintains per-device positioning state including Kalman filters.

    Usage
    -----
    engine = PositionEngine()
    estimate = engine.estimate(device_id, anchors)
    """

    def __init__(
        self,
        process_noise: float = 0.1,
        measurement_noise: float = 1.5,
        bounds: tuple[float, float] | None = None,  # (width, height), origin (0,0)
        calibration: dict[str, dict] | None = None,  # None: load from $RSSI_CALIBRATION_JSON
    ) -> None:
        self._bounds = bounds
        self.calibration = load_calibration() if calibration is None else calibration
        self._process_noise = process_noise
        self._measurement_noise = measurement_noise
        # device_id → KalmanFilter2D
        self._filters: dict[str, KalmanFilter2D] = {}
        # device_id → last PositionEstimate
        self._last_estimates: dict[str, PositionEstimate] = {}

    def distance(self, node_id: str, rssi: int) -> float:
        """RSSI -> metres with this node's calibrated tx_power/n, falling back to settings."""
        c = self.calibration.get(node_id, {})
        return rssi_to_distance(rssi, c.get("tx_power"), c.get("n"))

    def _get_filter(self, device_id: str) -> KalmanFilter2D:
        if device_id not in self._filters:
            self._filters[device_id] = KalmanFilter2D(
                process_noise=self._process_noise,
                measurement_noise=self._measurement_noise,
            )
        return self._filters[device_id]

    def estimate(
        self,
        device_id: str,
        anchors: list[NodeAnchor],
    ) -> PositionEstimate | None:
        """
        Compute a smoothed position estimate for *device_id*.

        Parameters
        ----------
        device_id : BLE device identifier.
        anchors   : List of NodeAnchor instances (≥ 2 required).

        Returns
        -------
        PositionEstimate or None if insufficient anchors.
        """
        if len(anchors) < 2:
            logger.debug(
                "Device %s: only %d anchor(s) — skipping.", device_id, len(anchors)
            )
            return None

        try:
            raw_x, raw_y, confidence = triangulate(anchors)
        except ValueError as exc:
            logger.warning("Triangulation failed for %s: %s", device_id, exc)
            return None

        kf = self._get_filter(device_id)
        smooth_x, smooth_y = kf.update(raw_x, raw_y)

        if self._bounds:
            smooth_x = min(max(smooth_x, 0.0), self._bounds[0])
            smooth_y = min(max(smooth_y, 0.0), self._bounds[1])

        estimate = PositionEstimate(
            x=smooth_x,
            y=smooth_y,
            confidence=confidence,
            anchor_count=len(anchors),
        )
        self._last_estimates[device_id] = estimate
        return estimate

    def last_estimate(self, device_id: str) -> PositionEstimate | None:
        """Return the most recent estimate for a device without recalculating."""
        return self._last_estimates.get(device_id)

    def remove_device(self, device_id: str) -> None:
        """Clean up state for a device that has left the venue."""
        self._filters.pop(device_id, None)
        self._last_estimates.pop(device_id, None)

    def active_devices(self) -> list[str]:
        """Return all device IDs currently tracked."""
        return list(self._last_estimates.keys())


# Singleton instance shared across the application
position_engine = PositionEngine()


class PositioningFleet:
    """Per-device, per-node latest-RSSI window feeding a PositionEngine."""

    def __init__(self, window_s: float = 10.0, bounds: tuple[float, float] | None = None,
                 ttl_s: float | None = None, max_devices: int | None = None, clock=None) -> None:
        import time
        self.ttl_s = settings.DEVICE_TTL_SECONDS if ttl_s is None else ttl_s
        self.max_devices = settings.MAX_TRACKED_DEVICES if max_devices is None else max_devices
        self._clock = clock or time.time
        self.rejected = 0
        self.engine = PositionEngine(bounds=bounds)
        self.window_s = window_s
        self._nodes: dict[str, tuple[float, float]] = {}
        self._rssi: dict[str, dict[str, tuple[int, float]]] = {}

    def configure_nodes(self, nodes: list[dict]) -> None:
        self._nodes = {n["node_id"]: (n["x"], n["y"]) for n in nodes}

    def has_capacity(self, device_id: str) -> bool:
        if device_id in self._rssi or len(self._rssi) < self.max_devices:
            return True
        self.rejected += 1
        if self.rejected == 1 or self.rejected % 1000 == 0:
            logger.warning("Device cap %d reached: rejected %d new device(s)", self.max_devices, self.rejected)
        return False

    def evict_idle(self) -> None:
        """Drop devices whose newest reading is older than ttl_s (called from the position loop)."""
        now = self._clock()
        for dev in [d for d, pn in self._rssi.items() if now - max(ts for _, ts in pn.values()) > self.ttl_s]:
            del self._rssi[dev]
            self.engine.remove_device(dev)

    def ingest_reading(self, node_id: str, device_id: str, rssi: int, ts: float) -> None:
        if node_id in self._nodes and self.has_capacity(device_id):
            self._rssi.setdefault(device_id, {})[node_id] = (rssi, ts)

    def get_all_positions(self) -> dict[str, PositionEstimate | None]:
        now = self._clock()
        out = {}
        for dev, per_node in self._rssi.items():
            anchors = [
                NodeAnchor(nid, *self._nodes[nid], self.engine.distance(nid, r), r)
                for nid, (r, ts) in per_node.items()
                if now - ts <= self.window_s
            ]
            out[dev] = self.engine.estimate(dev, anchors)
        return out
