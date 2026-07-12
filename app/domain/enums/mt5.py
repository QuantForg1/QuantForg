"""MT5-specific enumerations (connection layer)."""

from __future__ import annotations

from enum import StrEnum


class MT5ConnectionStatus(StrEnum):
    """Lifecycle status of an MT5 terminal connection."""

    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
