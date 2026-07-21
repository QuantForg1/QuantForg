"""Trading session manager — entries vs management windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.ai_trading_robot.config import RobotV1Config
from app.domain.ai_trading_robot.filters import evaluate_session_filter
from app.domain.institutional_trading.session_filter import classify_session_utc


@dataclass(frozen=True, slots=True)
class SessionManagerState:
    session: str
    entries_allowed: bool
    manage_positions: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "session": self.session,
            "entries_allowed": self.entries_allowed,
            "manage_positions": self.manage_positions,
            "reason": self.reason,
        }


def evaluate_session_manager(
    config: RobotV1Config, *, as_of: datetime | None = None
) -> SessionManagerState:
    now = as_of or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    session = classify_session_utc(now)
    name = session.value if hasattr(session, "value") else str(session)
    filt = evaluate_session_filter(config, as_of=now)
    manage = True
    if not filt.passed and not config.manage_positions_off_session:
        manage = False
    reason = filt.reason
    if filt.passed:
        reason = f"Entries allowed in {name}."
    elif config.manage_positions_off_session:
        reason = (
            f"New entries blocked in {name}; open positions may still be managed."
        )
    else:
        reason = f"Session {name} — entries and management blocked by policy."
    return SessionManagerState(
        session=str(name),
        entries_allowed=filt.passed,
        manage_positions=manage,
        reason=reason,
    )
