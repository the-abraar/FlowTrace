"""
config.py
─────────
Centralised Pydantic-settings configuration loaded from .env.
All modules import `settings` from here — never read os.environ directly.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── OpenAI ──────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(default="", description="OpenAI secret key")
    OPENAI_MODEL: str = Field(default="gpt-4o", description="LLM model name")

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./flowtrace.db",
        description="Async SQLAlchemy database URL",
    )

    # ── MQTT ─────────────────────────────────────────────────────────────────
    MQTT_BROKER_HOST: str = Field(default="localhost")
    MQTT_BROKER_PORT: int = Field(default=1883)
    MQTT_USERNAME: str = Field(default="")
    MQTT_PASSWORD: str = Field(default="")
    MQTT_TOPIC_PREFIX: str = Field(default="flowtrace/nodes")
    MQTT_CLIENT_ID: str = Field(default="flowtrace-backend")

    # ── API ───────────────────────────────────────────────────────────────────
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    API_CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173"
    )

    @property
    def cors_origins(self) -> list[str]:
        """Split comma-separated CORS origins into a list."""
        return [o.strip() for o in self.API_CORS_ORIGINS.split(",") if o.strip()]

    # ── Background Tasks ─────────────────────────────────────────────────────
    POSITIONING_INTERVAL_SECONDS: float = Field(default=2.0)
    AGENT_ANALYSIS_INTERVAL_SECONDS: float = Field(default=30.0)

    # ── BLE Path-Loss ─────────────────────────────────────────────────────────
    BLE_TX_POWER: float = Field(default=-59.0, description="Reference RSSI at 1m (dBm)")
    BLE_PATH_LOSS_EXPONENT: float = Field(default=2.0, description="Path-loss exponent n")

    # ── Venue ─────────────────────────────────────────────────────────────────
    VENUE_ID: str = Field(default="venue-001")
    VENUE_NAME: str = Field(default="Project FlowTrace Demo Venue")

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO")


settings = Settings()
