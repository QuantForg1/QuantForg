"""MT5 domain entities — connection layer only (no orders/trading)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity
from app.domain.enums.mt5 import MT5ConnectionStatus


@dataclass(frozen=True, slots=True)
class MT5Server:
    """Broker server metadata reported by the terminal."""

    name: str
    company: str = ""
    trade_mode: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "company", self.company.strip())
        object.__setattr__(self, "trade_mode", self.trade_mode.strip())

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "company": self.company,
            "trade_mode": self.trade_mode,
        }


@dataclass(frozen=True, slots=True)
class MT5Terminal:
    """Local MetaTrader 5 terminal metadata."""

    build: int
    name: str = "MetaTrader 5"
    path: str = ""
    company: str = ""
    language: str = ""
    connected: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "path", self.path.strip())
        object.__setattr__(self, "company", self.company.strip())
        object.__setattr__(self, "language", self.language.strip())
        if self.build < 0:
            msg = "terminal build must be >= 0"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "build": self.build,
            "name": self.name,
            "path": self.path,
            "company": self.company,
            "language": self.language,
            "connected": self.connected,
        }


@dataclass(frozen=True, slots=True)
class MT5AccountInfo:
    """Read-only MT5 account snapshot (no trading execution fields)."""

    login: int
    name: str
    server: str
    currency: str = "USD"
    leverage: int = 1
    balance: Decimal = Decimal("0")
    equity: Decimal = Decimal("0")
    margin: Decimal = Decimal("0")
    free_margin: Decimal = Decimal("0")
    margin_level: Decimal = Decimal("0")
    profit: Decimal = Decimal("0")
    company: str = ""
    trade_mode: str = ""

    def __post_init__(self) -> None:
        if self.login <= 0:
            msg = "login must be > 0"
            raise ValueError(msg)
        if self.leverage < 1:
            msg = "leverage must be >= 1"
            raise ValueError(msg)
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "server", self.server.strip())
        object.__setattr__(self, "currency", self.currency.strip().upper() or "USD")
        object.__setattr__(self, "company", self.company.strip())
        object.__setattr__(self, "trade_mode", self.trade_mode.strip())

    def to_dict(self) -> dict[str, object]:
        return {
            "login": self.login,
            "name": self.name,
            "server": self.server,
            "currency": self.currency,
            "leverage": self.leverage,
            "balance": str(self.balance),
            "equity": str(self.equity),
            "margin": str(self.margin),
            "free_margin": str(self.free_margin),
            "margin_level": str(self.margin_level),
            "profit": str(self.profit),
            "company": self.company,
            "trade_mode": self.trade_mode,
        }


@dataclass(eq=False, kw_only=True)
class MT5Connection(Entity):
    """Persisted / in-process MT5 connection state (connection layer only)."""

    user_id: UUID
    login: int
    server: str
    status: MT5ConnectionStatus = MT5ConnectionStatus.DISCONNECTED
    session_ref: str = ""
    terminal_path: str = ""
    terminal_build: int | None = None
    terminal_version: str = ""
    latency_ms: float | None = None
    last_heartbeat_at: datetime | None = None
    connected: bool = False
    login_status: str = "logged_out"
    last_error: str = ""
    history: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        require(self.login > 0, "login must be > 0")
        self.server = self.server.strip()
        require(len(self.server) > 0, "server is required")
        self.terminal_path = self.terminal_path.strip()
        self.terminal_version = self.terminal_version.strip()[:64]
        self.login_status = self.login_status.strip()[:64] or "logged_out"
        self.last_error = self.last_error.strip()[:1000]
        self.session_ref = self.session_ref.strip()

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        login: int,
        server: str,
        terminal_path: str = "",
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "login": login,
            "server": server,
            "terminal_path": terminal_path,
            "status": MT5ConnectionStatus.DISCONNECTED,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def mark_initializing(self) -> None:
        self.status = MT5ConnectionStatus.INITIALIZING
        self.login_status = "initializing"
        self.connected = False
        self._append_history("initialize")
        self.touch()

    def mark_logging_in(self) -> None:
        self.status = MT5ConnectionStatus.CONNECTING
        self.login_status = "logging_in"
        self._append_history("login")
        self.touch()

    def mark_connected(
        self,
        *,
        session_ref: str,
        terminal_build: int | None = None,
        terminal_version: str = "",
        latency_ms: float | None = None,
    ) -> None:
        require(len(session_ref.strip()) > 0, "session_ref is required")
        self.session_ref = session_ref.strip()
        self.status = MT5ConnectionStatus.CONNECTED
        self.login_status = "logged_in"
        self.connected = True
        self.terminal_build = terminal_build
        if terminal_version:
            self.terminal_version = terminal_version.strip()[:64]
        if latency_ms is not None:
            self.latency_ms = max(0.0, latency_ms)
        self.last_heartbeat_at = datetime.now(UTC)
        self.last_error = ""
        self._append_history("connected")
        self.touch()

    def mark_heartbeat(self, *, latency_ms: float) -> None:
        self.latency_ms = max(0.0, latency_ms)
        self.last_heartbeat_at = datetime.now(UTC)
        if self.status is MT5ConnectionStatus.CONNECTED:
            self.connected = True
            self.login_status = "logged_in"
        self._append_history("heartbeat")
        self.touch()

    def mark_reconnecting(self) -> None:
        self.status = MT5ConnectionStatus.RECONNECTING
        self.login_status = "reconnecting"
        self.connected = False
        self._append_history("reconnect")
        self.touch()

    def mark_disconnected(self, *, error: str = "") -> None:
        self.status = MT5ConnectionStatus.DISCONNECTED
        self.login_status = "logged_out"
        self.connected = False
        self.session_ref = ""
        self.last_error = error.strip()[:1000]
        self._append_history("shutdown" if not error else "error")
        self.touch()

    def mark_error(self, error: str) -> None:
        self.status = MT5ConnectionStatus.ERROR
        self.login_status = "error"
        self.connected = False
        self.last_error = error.strip()[:1000]
        self._append_history("error")
        self.touch()

    def _append_history(self, event: str) -> None:
        self.history.append(
            {
                "event": event,
                "at": datetime.now(UTC).isoformat(),
                "status": self.status.value,
            }
        )
        # Cap in-memory history depth
        if len(self.history) > 100:
            self.history = self.history[-100:]

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "login": self.login,
                "server": self.server,
                "status": self.status.value,
                "session_ref": self.session_ref,
                "terminal_path": self.terminal_path,
                "terminal_build": self.terminal_build,
                "terminal_version": self.terminal_version,
                "latency_ms": self.latency_ms,
                "last_heartbeat_at": (
                    self.last_heartbeat_at.isoformat()
                    if self.last_heartbeat_at
                    else None
                ),
                "connected": self.connected,
                "login_status": self.login_status,
                "last_error": self.last_error,
            }
        )
        return base
