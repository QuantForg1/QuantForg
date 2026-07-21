"""Session / spread / volatility / news filter architecture for Robot V1."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from app.domain.ai_trading_robot.config import RobotV1Config
from app.domain.institutional_trading.session_filter import classify_session_utc


@dataclass(frozen=True, slots=True)
class FilterResult:
    name: str
    passed: bool
    reason: str
    current: str = ""
    threshold: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "passed": self.passed,
            "reason": self.reason,
            "current": self.current,
            "threshold": self.threshold,
        }


@dataclass(frozen=True, slots=True)
class NewsEventView:
    code: str
    title: str
    scheduled_at: datetime
    impact: str = "high"


class NewsCalendarPort(Protocol):
    """Architecture port — wire a calendar feed to enforce blackouts."""

    def events_near(
        self,
        *,
        as_of: datetime,
        minutes_before: int,
        minutes_after: int,
    ) -> Sequence[NewsEventView]: ...


def evaluate_session_filter(
    config: RobotV1Config, *, as_of: datetime | None = None
) -> FilterResult:
    now = as_of or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    session = classify_session_utc(now)
    name = session.value if hasattr(session, "value") else str(session)
    name_l = str(name).lower().replace(" ", "_")
    allowed = {s.lower().replace(" ", "_") for s in config.allowed_sessions}
    ok = name_l in allowed or any(
        a in name_l or name_l in a for a in allowed
    )
    if "overlap" in name_l and any("overlap" in a for a in allowed):
        ok = True
    return FilterResult(
        name="session",
        passed=ok,
        reason=(
            f"Session {name} allowed"
            if ok
            else f"Session {name} outside allowed {sorted(allowed)}"
        ),
        current=str(name),
        threshold=",".join(sorted(allowed)),
    )


def evaluate_spread_filter(
    config: RobotV1Config, *, spread: Decimal | None
) -> FilterResult:
    if spread is None:
        return FilterResult(
            name="spread",
            passed=False,
            reason="Spread unavailable — fail closed.",
            current="—",
            threshold=str(config.max_spread),
        )
    ok = spread <= config.max_spread
    return FilterResult(
        name="spread",
        passed=ok,
        reason=(
            f"Spread {spread} within {config.max_spread}"
            if ok
            else f"Spread {spread} exceeds max {config.max_spread}"
        ),
        current=str(spread),
        threshold=str(config.max_spread),
    )


def evaluate_volatility_filter(
    config: RobotV1Config,
    *,
    atr: Decimal | None,
    price: Decimal | None,
) -> FilterResult:
    if atr is None or price is None or price <= 0:
        return FilterResult(
            name="volatility",
            passed=False,
            reason="ATR/price unavailable — fail closed for new entries.",
            current="—",
            threshold=(
                f"{config.min_atr_pct_of_price}-{config.max_atr_pct_of_price}%"
            ),
        )
    atr_pct = (atr / price * Decimal("100")).quantize(Decimal("0.01"))
    if atr_pct > config.max_atr_pct_of_price:
        return FilterResult(
            name="volatility",
            passed=False,
            reason=f"ATR {atr_pct}% exceeds max {config.max_atr_pct_of_price}%",
            current=str(atr_pct),
            threshold=str(config.max_atr_pct_of_price),
        )
    if atr_pct < config.min_atr_pct_of_price:
        return FilterResult(
            name="volatility",
            passed=False,
            reason=(
                f"ATR {atr_pct}% below min "
                f"{config.min_atr_pct_of_price}% (dead market)"
            ),
            current=str(atr_pct),
            threshold=str(config.min_atr_pct_of_price),
        )
    return FilterResult(
        name="volatility",
        passed=True,
        reason=f"ATR {atr_pct}% within band",
        current=str(atr_pct),
        threshold=(
            f"{config.min_atr_pct_of_price}-{config.max_atr_pct_of_price}"
        ),
    )


def evaluate_news_filter(
    config: RobotV1Config,
    *,
    as_of: datetime | None = None,
    calendar: NewsCalendarPort | None = None,
    minutes_before: int = 30,
    minutes_after: int = 30,
) -> FilterResult:
    """News filter architecture — blocks only when enabled + feed present."""
    if not config.news_filter_enabled:
        return FilterResult(
            name="news",
            passed=True,
            reason="News filter disabled by policy.",
            current="disabled",
            threshold="n/a",
        )
    if calendar is None:
        return FilterResult(
            name="news",
            passed=True,
            reason=(
                "News filter architecture ready — no calendar feed wired. "
                "Fail-open for availability; connect a feed to enforce blackouts."
            ),
            current="no_feed",
            threshold=f"±{minutes_before}/{minutes_after}m",
        )
    now = as_of or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    hits = [
        e
        for e in calendar.events_near(
            as_of=now,
            minutes_before=minutes_before,
            minutes_after=minutes_after,
        )
        if e.impact.lower() == "high"
    ]
    if hits:
        titles = ", ".join(f"{e.code}:{e.title}" for e in hits[:3])
        return FilterResult(
            name="news",
            passed=False,
            reason=f"High-impact news blackout: {titles}",
            current=str(len(hits)),
            threshold=f"±{minutes_before}/{minutes_after}m",
        )
    return FilterResult(
        name="news",
        passed=True,
        reason="No high-impact events in blackout window.",
        current="0",
        threshold=f"±{minutes_before}/{minutes_after}m",
    )


def evaluate_daily_drawdown(
    config: RobotV1Config, *, daily_drawdown_pct: Decimal
) -> FilterResult:
    ok = daily_drawdown_pct < config.max_daily_drawdown_pct
    return FilterResult(
        name="daily_drawdown",
        passed=ok,
        reason=(
            f"Daily DD {daily_drawdown_pct}% within {config.max_daily_drawdown_pct}%"
            if ok
            else f"Daily DD {daily_drawdown_pct}% reached limit "
            f"{config.max_daily_drawdown_pct}% — pause new entries"
        ),
        current=str(daily_drawdown_pct),
        threshold=str(config.max_daily_drawdown_pct),
    )


def evaluate_consecutive_losses(
    config: RobotV1Config,
    *,
    consecutive_losses: int,
    cooldown_active: bool,
) -> FilterResult:
    if consecutive_losses >= config.max_consecutive_losses:
        return FilterResult(
            name="consecutive_losses",
            passed=False,
            reason=(
                f"Loss streak {consecutive_losses} ≥ "
                f"{config.max_consecutive_losses} — entries blocked"
            ),
            current=str(consecutive_losses),
            threshold=str(config.max_consecutive_losses),
        )
    if cooldown_active:
        return FilterResult(
            name="consecutive_losses",
            passed=False,
            reason=(
                f"Cooldown active after loss streak "
                f"({config.cooldown_minutes_after_streak}m policy)"
            ),
            current="cooldown",
            threshold=str(config.cooldown_minutes_after_streak),
        )
    return FilterResult(
        name="consecutive_losses",
        passed=True,
        reason=f"Loss streak {consecutive_losses} below cap",
        current=str(consecutive_losses),
        threshold=str(config.max_consecutive_losses),
    )
