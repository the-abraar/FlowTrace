"""
database/models.py
──────────────────
SQLAlchemy ORM models for Project FlowTrace.

Tables
------
- Node         — fixed BLE scanner nodes in the venue
- Device       — tracked BLE devices (visitors)
- Reading      — raw RSSI readings from nodes
- Position     — triangulated position estimates per device
- UserSession  — aggregated visit session per device
- AgentInsight — AI-generated insight records
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ──────────────────────────────────────────────────────────────────────────────
# Base
# ──────────────────────────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    pass


# ──────────────────────────────────────────────────────────────────────────────
# Node
# ──────────────────────────────────────────────────────────────────────────────


class Node(Base):
    """
    Represents a fixed BLE scanner node installed in the venue.

    Attributes
    ----------
    id       : Unique node identifier (e.g. "node-A")
    name     : Human-readable label
    x_pos    : X coordinate in metres from venue origin
    y_pos    : Y coordinate in metres from venue origin
    floor    : Floor number (0 = ground)
    venue_id : Parent venue identifier
    active   : Whether the node is currently active
    """

    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    x_pos: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    y_pos: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    floor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    venue_id: Mapped[str] = mapped_column(String(64), nullable=False, default="venue-001")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    readings: Mapped[list["Reading"]] = relationship(
        "Reading", back_populates="node", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to plain dict."""
        return {
            "id": self.id,
            "name": self.name,
            "x_pos": self.x_pos,
            "y_pos": self.y_pos,
            "floor": self.floor,
            "venue_id": self.venue_id,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Device
# ──────────────────────────────────────────────────────────────────────────────


class Device(Base):
    """
    Represents a tracked BLE device (visitor's phone/wearable).

    Attributes
    ----------
    id           : BLE MAC address or UUID
    label        : Optional human label (e.g. "VIP Guest 7")
    first_seen   : UTC timestamp of first detection
    last_seen    : UTC timestamp of most recent detection
    is_active    : True if seen within the last 5 minutes
    """

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    readings: Mapped[list["Reading"]] = relationship(
        "Reading", back_populates="device", cascade="all, delete-orphan"
    )
    positions: Mapped[list["Position"]] = relationship(
        "Position", back_populates="device", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession", back_populates="device", cascade="all, delete-orphan"
    )
    insights: Mapped[list["AgentInsight"]] = relationship(
        "AgentInsight", back_populates="device", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "is_active": self.is_active,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Reading
# ──────────────────────────────────────────────────────────────────────────────


class Reading(Base):
    """
    A single RSSI measurement from one node towards one device.

    Attributes
    ----------
    id          : Auto-increment PK
    node_id     : FK → nodes.id
    device_id   : FK → devices.id
    rssi        : Received signal strength in dBm (negative integer)
    timestamp   : When the measurement was taken (UTC)
    battery_pct : Optional node battery percentage [0–100]
    """

    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rssi: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )
    battery_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    node: Mapped["Node"] = relationship("Node", back_populates="readings")
    device: Mapped["Device"] = relationship("Device", back_populates="readings")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "node_id": self.node_id,
            "device_id": self.device_id,
            "rssi": self.rssi,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "battery_pct": self.battery_pct,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Position
# ──────────────────────────────────────────────────────────────────────────────


class Position(Base):
    """
    Triangulated position estimate for a device at a point in time.

    Attributes
    ----------
    id          : Auto-increment PK
    device_id   : FK → devices.id
    estimated_x : X coordinate estimate (metres)
    estimated_y : Y coordinate estimate (metres)
    floor       : Estimated floor
    confidence  : Confidence score [0.0 – 1.0]
    timestamp   : When the estimate was calculated (UTC)
    zone        : Detected zone name (nullable)
    """

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    estimated_x: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_y: Mapped[float] = mapped_column(Float, nullable=False)
    floor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )
    zone: Mapped[str | None] = mapped_column(String(128), nullable=True)

    device: Mapped["Device"] = relationship("Device", back_populates="positions")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "estimated_x": self.estimated_x,
            "estimated_y": self.estimated_y,
            "floor": self.floor,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "zone": self.zone,
        }


# ──────────────────────────────────────────────────────────────────────────────
# UserSession
# ──────────────────────────────────────────────────────────────────────────────


class UserSession(Base):
    """
    An aggregated visit session for a single device.

    Attributes
    ----------
    id            : Auto-increment PK
    device_id     : FK → devices.id
    entry_time    : Session start (first seen)
    exit_time     : Session end (last seen), NULL if ongoing
    zones_visited : JSON list of {zone, entry, exit, dwell_seconds}
    """

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    zones_visited: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=list)

    device: Mapped["Device"] = relationship("Device", back_populates="sessions")
    insights: Mapped[list["AgentInsight"]] = relationship(
        "AgentInsight", back_populates="session", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "zones_visited": self.zones_visited or [],
        }


# ──────────────────────────────────────────────────────────────────────────────
# AgentInsight
# ──────────────────────────────────────────────────────────────────────────────


class AgentInsight(Base):
    """
    An AI-generated insight record produced by the FlowTrace agent.

    Attributes
    ----------
    id            : Auto-increment PK
    device_id     : FK → devices.id (nullable for venue-wide insights)
    session_id    : FK → user_sessions.id (nullable)
    insight_type  : UPSELL | ALERT | RECOMMENDATION | ANOMALY
    message       : Human-readable insight text
    action_taken  : Optional action description (e.g. notification sent)
    confidence    : Agent's confidence score [0.0 – 1.0]
    raw_response  : Full raw agent response (JSON text)
    timestamp     : When the insight was generated (UTC)
    """

    __tablename__ = "agent_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_sessions.id", ondelete="SET NULL"), nullable=True
    )
    insight_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )

    device: Mapped["Device | None"] = relationship("Device", back_populates="insights")
    session: Mapped["UserSession | None"] = relationship(
        "UserSession", back_populates="insights"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "session_id": self.session_id,
            "insight_type": self.insight_type,
            "message": self.message,
            "action_taken": self.action_taken,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
