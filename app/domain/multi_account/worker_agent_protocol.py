"""Windows MT5 worker agent protocol (Phase 1B).

The agent runs on managed Windows hosts beside an isolated MetaTrader 5
terminal. Railway hosts the control plane only — it cannot run terminal64.

Implementations must:
- Never log passwords or credential payloads.
- Reject investor/read-only credentials for trade-enabled workers.
- Authenticate to the control plane with a service identity token.
- Own exactly one broker account session.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AgentAuthRequest:
    worker_id: UUID
    user_id: UUID
    broker_account_id: UUID
    login: str
    server: str
    # Password is transient in-memory only; never persist or log.
    password: str
    service_token: str


@dataclass(frozen=True, slots=True)
class AgentAuthResult:
    ok: bool
    trade_allowed: bool
    runtime_session_id: str = ""
    verified_login: str = ""
    verified_server: str = ""
    error: str = ""


@dataclass(frozen=True, slots=True)
class AgentHealth:
    worker_id: UUID
    alive: bool
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    terminal_running: bool = False
    detail: str = ""


class Mt5WorkerAgentPort(Protocol):
    """Port implemented by the Windows worker agent (or CI mock)."""

    async def start_terminal(self, *, worker_id: UUID) -> bool:
        """Start the dedicated terminal runtime for this worker slot."""
        ...

    async def authenticate(self, request: AgentAuthRequest) -> AgentAuthResult:
        """Login + verify account. Must fail closed for investor passwords."""
        ...

    async def disconnect(self, *, worker_id: UUID) -> None:
        """Disconnect the MT5 session without touching other workers."""
        ...

    async def health(self, *, worker_id: UUID) -> AgentHealth:
        """Local health snapshot for supervisor heartbeats."""
        ...


@dataclass
class MockMt5WorkerAgent:
    """CI / unit-test agent. Does NOT prove a real MT5 terminal session."""

    fail_auth: bool = False
    investor_password: bool = False
    started: set[UUID] | None = None
    disconnected: set[UUID] | None = None

    def __post_init__(self) -> None:
        if self.started is None:
            self.started = set()
        if self.disconnected is None:
            self.disconnected = set()

    async def start_terminal(self, *, worker_id: UUID) -> bool:
        assert self.started is not None
        self.started.add(worker_id)
        return True

    async def authenticate(self, request: AgentAuthRequest) -> AgentAuthResult:
        # Never echo password.
        _ = request.password
        if not request.service_token.strip():
            return AgentAuthResult(
                ok=False,
                trade_allowed=False,
                error="missing_service_token",
            )
        if self.fail_auth:
            return AgentAuthResult(
                ok=False, trade_allowed=False, error="mock_auth_failed"
            )
        if self.investor_password:
            return AgentAuthResult(
                ok=False,
                trade_allowed=False,
                error="investor_or_readonly_credentials_rejected",
                verified_login=request.login,
                verified_server=request.server,
            )
        return AgentAuthResult(
            ok=True,
            trade_allowed=True,
            runtime_session_id=f"mock-session-{request.worker_id.hex[:8]}",
            verified_login=request.login,
            verified_server=request.server,
        )

    async def disconnect(self, *, worker_id: UUID) -> None:
        assert self.disconnected is not None
        self.disconnected.add(worker_id)

    async def health(self, *, worker_id: UUID) -> AgentHealth:
        assert self.started is not None
        return AgentHealth(
            worker_id=worker_id,
            alive=worker_id in self.started
            and worker_id not in (self.disconnected or set()),
            terminal_running=worker_id in self.started,
            detail="mock_agent_not_real_mt5",
        )
