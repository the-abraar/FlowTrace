"""API-key auth. Keys are read from env at call time.

INGEST_API_KEY guards writes (POST /readings; MQTT uses broker creds). READ_API_KEY optionally guards GETs and /ws.
Unset INGEST_API_KEY: writes stay open only if DEBUG/DEV is truthy, otherwise they are refused (503).
Unset READ_API_KEY: reads are open (documented).
"""
import hmac
import logging
import os
from fastapi import HTTPException, Request, WebSocket

logger = logging.getLogger(__name__)


def dev_mode() -> bool:
    return any(os.getenv(k, "").lower() in ("1", "true", "yes") for k in ("DEBUG", "DEV"))


def _ok(given: str | None, expected: str) -> bool:
    return hmac.compare_digest((given or "").encode(), expected.encode())


def _key(request: Request) -> str | None:
    return request.headers.get("x-api-key") or request.query_params.get("key")


def require_ingest(request: Request) -> None:
    expected = os.getenv("INGEST_API_KEY", "")
    if not expected:
        if dev_mode():
            return
        raise HTTPException(503, "INGEST_API_KEY not set: unauthenticated writes refused (set DEBUG=1 for local dev)")
    if not _ok(request.headers.get("x-api-key"), expected):
        raise HTTPException(401, "invalid or missing API key")


def require_read(request: Request) -> None:
    expected = os.getenv("READ_API_KEY", "")
    if expected and not _ok(_key(request), expected):
        raise HTTPException(401, "invalid or missing API key")


def ws_allowed(ws: WebSocket) -> bool:
    expected = os.getenv("READ_API_KEY", "")
    return not expected or _ok(ws.headers.get("x-api-key") or ws.query_params.get("key"), expected)


def warn_if_open() -> None:
    if not os.getenv("INGEST_API_KEY"):
        logger.warning("!!! INGEST_API_KEY is UNSET: %s", "DEBUG/DEV on, writes are OPEN" if dev_mode()
                       else "unauthenticated writes are REFUSED")
    if not os.getenv("READ_API_KEY"):
        logger.warning("!!! READ_API_KEY is UNSET: read endpoints and /ws are OPEN")
