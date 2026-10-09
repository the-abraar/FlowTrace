"""
positioning/zone_detector.py
─────────────────────────────
Venue zone definitions and detection utilities for Project FlowTrace.

Each zone is a named polygon in the same coordinate space used by the
triangulator (0–10 m × 0–10 m for the demo room).

Classes
───────
- Zone          — immutable zone definition (name + polygon vertices)
- ZoneDetector  — point-in-polygon, per-device dwell-time tracking
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import NamedTuple

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Geometry helpers
# ──────────────────────────────────────────────────────────────────────────────

Point = tuple[float, float]
Polygon = list[Point]


def ray_cast(x: float, y: float, polygon: Polygon) -> bool:
    """
    Determine whether point (x, y) lies inside *polygon* using
    the ray-casting algorithm.

    Parameters
    ----------
    x, y    : Test point coordinates.
    polygon : Ordered list of (px, py) vertex tuples.

    Returns
    -------
    True if inside (or on the boundary), False otherwise.
    """
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        # Check if ray from (x, y) rightward crosses edge (i → j)
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


# ──────────────────────────────────────────────────────────────────────────────
# Zone definition
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Zone:
    """Immutable definition of a named venue zone."""

    name: str                      # e.g. "VR_ZONE"
    label: str                     # Human-readable label
    polygon: tuple[Point, ...]     # Clockwise or CCW vertex list
    color: str = "#888888"         # CSS hex colour for dashboard rendering

    def contains(self, x: float, y: float) -> bool:
        """Return True if (x, y) falls within this zone's polygon."""
        return ray_cast(x, y, list(self.polygon))


# ──────────────────────────────────────────────────────────────────────────────
# Demo venue zone map (10 m × 10 m room)
# ──────────────────────────────────────────────────────────────────────────────
#
#   y
#   10 ┌──────────────────────────────────────┐
#      │  ENTRANCE   │       VR_ZONE          │
#    7 ├─────────────┼───────────────────────-┤
#      │  FOOD_COURT │   LASER_TAG            │
#    4 ├─────────────┼────────────────────────┤
#      │  EXIT       │   RETAIL               │
#    0 └─────────────┴────────────────────────┘
#      0             4                       10  x

VENUE_ZONES: list[Zone] = [
    Zone(
        name="ENTRANCE",
        label="Entrance",
        polygon=((0, 7), (4, 7), (4, 10), (0, 10)),
        color="#4CAF50",
    ),
    Zone(
        name="VR_ZONE",
        label="VR Experience",
        polygon=((4, 7), (10, 7), (10, 10), (4, 10)),
        color="#9C27B0",
    ),
    Zone(
        name="FOOD_COURT",
        label="Food Court",
        polygon=((0, 4), (4, 4), (4, 7), (0, 7)),
        color="#FF9800",
    ),
    Zone(
        name="LASER_TAG",
        label="Laser Tag Arena",
        polygon=((4, 4), (10, 4), (10, 7), (4, 7)),
        color="#F44336",
    ),
    Zone(
        name="EXIT",
        label="Exit Area",
        polygon=((0, 0), (4, 0), (4, 4), (0, 4)),
        color="#607D8B",
    ),
    Zone(
        name="RETAIL",
        label="Retail / Merch",
        polygon=((4, 0), (10, 0), (10, 4), (4, 4)),
        color="#2196F3",
    ),
]

# Quick lookup: zone_name → Zone
ZONE_MAP: dict[str, Zone] = {z.name: z for z in VENUE_ZONES}


# ──────────────────────────────────────────────────────────────────────────────
# Dwell time record
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class ZoneVisit:
    """Tracks a single zone visit for one device."""

    zone_name: str
    entry_time: datetime
    exit_time: datetime | None = None

    @property
    def dwell_seconds(self) -> float:
        end = self.exit_time or datetime.utcnow()
        return (end - self.entry_time).total_seconds()

    def to_dict(self) -> dict:
        return {
            "zone": self.zone_name,
            "entry": self.entry_time.isoformat(),
            "exit": self.exit_time.isoformat() if self.exit_time else None,
            "dwell_seconds": round(self.dwell_seconds, 1),
        }


@dataclass
class DeviceZoneState:
    """Mutable zone-tracking state for a single device."""

    device_id: str
    current_zone: str | None = None
    zone_entry_time: datetime | None = None
    # zone_name → total accumulated seconds
    dwell_totals: dict[str, float] = field(default_factory=dict)
    # ordered list of zone visits (for journey reconstruction)
    visit_log: list[ZoneVisit] = field(default_factory=list)
    # active (open) visit
    active_visit: ZoneVisit | None = None


# ──────────────────────────────────────────────────────────────────────────────
# ZoneDetector
# ──────────────────────────────────────────────────────────────────────────────


class ZoneDetector:
    """
    Manages zone detection and dwell-time tracking for all active devices.

    Thread safety
    -------------
    This class is *not* thread-safe. It is intended to be used from a single
    async event loop via the positioning background task.
    """

    def __init__(self, zones: list[Zone] | None = None) -> None:
        self._zones: list[Zone] = zones or VENUE_ZONES
        self._device_states: dict[str, DeviceZoneState] = {}

    # ── Point-in-zone ─────────────────────────────────────────────────────────

    def point_in_zone(self, x: float, y: float) -> str | None:
        """
        Return the name of the first zone that contains (x, y), or None.

        Zones are evaluated in list order; the first match wins.
        """
        for zone in self._zones:
            if zone.contains(x, y):
                return zone.name
        return None

    # ── Current zone ──────────────────────────────────────────────────────────

    def get_current_zone(self, device_id: str) -> str | None:
        """Return the currently tracked zone for *device_id*."""
        state = self._device_states.get(device_id)
        return state.current_zone if state else None

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, device_id: str, x: float, y: float) -> str | None:
        """
        Update zone tracking for a device at position (x, y).

        Records zone entry / exit events and accumulates dwell time.

        Returns
        -------
        Current zone name (or None if outside all zones).
        """
        detected_zone = self.point_in_zone(x, y)
        now = datetime.utcnow()

        if device_id not in self._device_states:
            self._device_states[device_id] = DeviceZoneState(device_id=device_id)

        state = self._device_states[device_id]

        if detected_zone != state.current_zone:
            # Zone transition
            if state.active_visit is not None:
                # Close out the previous visit
                state.active_visit.exit_time = now
                prev_zone = state.active_visit.zone_name
                dwell = state.active_visit.dwell_seconds
                state.dwell_totals[prev_zone] = (
                    state.dwell_totals.get(prev_zone, 0.0) + dwell
                )
                logger.info(
                    "Device %s left %s after %.1fs",
                    device_id,
                    prev_zone,
                    dwell,
                )

            state.current_zone = detected_zone
            if detected_zone is not None:
                new_visit = ZoneVisit(zone_name=detected_zone, entry_time=now)
                state.active_visit = new_visit
                state.visit_log.append(new_visit)
                logger.info("Device %s entered %s", device_id, detected_zone)
            else:
                state.active_visit = None

        state.zone_entry_time = now if detected_zone else None
        return detected_zone

    # ── Dwell time ────────────────────────────────────────────────────────────

    def track_zone_dwell_time(self, device_id: str) -> dict[str, float]:
        """
        Return accumulated dwell time (seconds) per zone for *device_id*.

        Includes time in the currently active zone up to "now".
        """
        state = self._device_states.get(device_id)
        if state is None:
            return {}

        totals = dict(state.dwell_totals)
        # Add in-progress dwell for active zone
        if state.active_visit is not None:
            z = state.active_visit.zone_name
            extra = state.active_visit.dwell_seconds
            totals[z] = totals.get(z, 0.0) + extra

        return totals

    # ── Journey ───────────────────────────────────────────────────────────────

    def get_device_journey(self, device_id: str) -> list[dict]:
        """Return the ordered list of zone visits for a device."""
        state = self._device_states.get(device_id)
        if state is None:
            return []
        return [v.to_dict() for v in state.visit_log]

    # ── Venue-wide stats ──────────────────────────────────────────────────────

    def get_zone_stats(self) -> dict[str, dict]:
        """
        Return aggregate occupancy stats per zone across all active devices.

        Returns
        -------
        dict[zone_name, {device_count, avg_dwell_seconds}]
        """
        zone_devices: dict[str, list[str]] = {z.name: [] for z in self._zones}
        zone_dwells: dict[str, list[float]] = {z.name: [] for z in self._zones}

        for device_id, state in self._device_states.items():
            if state.current_zone:
                zone_devices[state.current_zone].append(device_id)
            for zone_name, dwell in self.track_zone_dwell_time(device_id).items():
                zone_dwells.setdefault(zone_name, []).append(dwell)

        stats: dict[str, dict] = {}
        for zone in self._zones:
            devices_in = zone_devices.get(zone.name, [])
            all_dwells = zone_dwells.get(zone.name, [])
            stats[zone.name] = {
                "label": zone.label,
                "current_occupancy": len(devices_in),
                "active_device_ids": devices_in,
                "avg_dwell_seconds": (
                    round(sum(all_dwells) / len(all_dwells), 1) if all_dwells else 0.0
                ),
                "total_visits": len(all_dwells),
            }
        return stats

    def remove_device(self, device_id: str) -> None:
        """Remove tracking state for a device (e.g. on session end)."""
        self._device_states.pop(device_id, None)

    def all_zones(self) -> list[dict]:
        """Serialise zone definitions for the API."""
        return [
            {
                "name": z.name,
                "label": z.label,
                "polygon": list(z.polygon),
                "color": z.color,
            }
            for z in self._zones
        ]


# Singleton instance shared across the application
zone_detector = ZoneDetector()
