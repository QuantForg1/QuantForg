"""Owner entry guard for the multi-account worker execution path.

The Weltrade robot path checks every new entry with
``evaluate_owner_entry`` in ``InstitutionalExecutionEngine``. Multi-account
workers send orders from their own MT5 terminals, so the backend cannot
read their quotes or deals itself. The worker attaches a fresh account
snapshot to its authorization request. The same final owner guard then
runs on that snapshot: 9% per trade, 25% daily budget (pre-trade, deposits
never forgive a loss), RR 1.5 after costs, spread 0.45, session
Mon-Fri 07:00-17:00 UTC, one position, 0.01 lot, and the user's own saved
caps (strictest wins).

The account environment comes from MT5 ``trade_mode`` in the snapshot,
never from the job payload. Anything missing, stale or inconsistent
rejects the entry. Nothing here sends an order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

SNAPSHOT_MAX_AGE_SECONDS = 30
MAX_OPEN_POSITIONS = 1
_MODE_TO_ENV = {"demo": "demo", "contest": "demo", "real": "live"}
VERIFIED_COMMISSION_SOURCES = frozenset({"verified_account_tariff"})


@dataclass(frozen=True, slots=True)
class WorkerGuardResult:
    environment: str | None
    reasons: tuple[str, ...]
    planned_inputs: dict[str, str]


def _dec(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        out = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return out if out.is_finite() else None


def _parse_time(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        return None
    return moment.astimezone(UTC)


def environment_from_snapshot(snapshot: dict[str, Any] | None) -> str | None:
    """``demo`` / ``live`` from MT5 trade_mode; ``None`` when unknown."""
    if not isinstance(snapshot, dict):
        return None
    mode = str(snapshot.get("trade_mode") or "").strip().lower()
    return _MODE_TO_ENV.get(mode)


def evaluate_worker_entry(
    *,
    snapshot: dict[str, Any] | None,
    claimed_environment: str | None,
    user_id: UUID,
    symbol: str,
    side: str,
    volume: object,
    entry: object,
    stop_loss: object,
    take_profit: object,
    now: datetime | None = None,
    user_caps: Any | None = None,
) -> WorkerGuardResult:
    """Run the final owner guard on a worker's account snapshot."""
    from app.application.services.live_account_risk_tracker import (
        LiveAccountRiskTracker,
    )
    from app.domain.institutional_trading import owner_live_limits as ol

    moment = now or datetime.now(UTC)
    if not isinstance(snapshot, dict):
        return WorkerGuardResult(None, ("account_snapshot_unavailable",), {})

    reasons: list[str] = []
    env = environment_from_snapshot(snapshot)
    if env is None:
        reasons.append("account_environment_unverified")
    claimed = str(claimed_environment or "").strip().lower() or None
    if env is not None and claimed is not None and claimed != env:
        reasons.append("account_environment_mismatch")

    captured = _parse_time(snapshot.get("captured_at"))
    if captured is None:
        reasons.append("account_snapshot_time_invalid")
    else:
        age = (moment - captured).total_seconds()
        if age > SNAPSHOT_MAX_AGE_SECONDS or age < -5:
            reasons.append("account_snapshot_stale")

    balance = _dec(snapshot.get("balance"))
    equity = _dec(snapshot.get("equity"))
    bid = _dec(snapshot.get("bid"))
    ask = _dec(snapshot.get("ask"))
    contract = _dec(snapshot.get("contract_size"))
    if None in (balance, equity, bid, ask, contract) or not equity or not contract:
        reasons.append("account_snapshot_incomplete")
        return WorkerGuardResult(env, tuple(reasons), {})
    assert balance is not None and equity is not None
    assert bid is not None and ask is not None and contract is not None

    open_positions = snapshot.get("open_positions")
    if not isinstance(open_positions, int) or open_positions < 0:
        reasons.append("open_positions_unknown")
    elif open_positions >= MAX_OPEN_POSITIONS:
        reasons.append(f"OWNER_MAX_POSITIONS: open {open_positions}")

    commission: Decimal | None = None
    if snapshot.get("commission_source") in VERIFIED_COMMISSION_SOURCES:
        commission = _dec(snapshot.get("commission_usd"))

    deals = snapshot.get("deals_today")
    if isinstance(deals, list):
        try:
            daily = LiveAccountRiskTracker.daily_loss_context(
                deals, balance=balance, equity=equity, now=moment
            )
        except Exception:
            daily = ol.DailyLossContext(
                trusted=False,
                realized_pnl=Decimal("0"),
                balance=balance,
                equity=equity,
                source="worker_deals_unreadable",
            )
    else:
        daily = None

    side_u = str(side or "").upper()
    entry_d = _dec(entry)
    if entry_d is None:
        entry_d = ask if side_u == "BUY" else bid

    if user_caps is None:
        from app.domain.institutional_trading.operations.live_prefs_tighten import (
            load_user_live_caps,
        )

        user_caps = load_user_live_caps(user_id)
    if not getattr(user_caps, "available", False):
        reasons.append("USER_RISK_UNAVAILABLE")

    vol = _dec(volume)
    if vol is None:
        reasons.append("volume_invalid")
        return WorkerGuardResult(env, tuple(reasons), {})

    violations = ol.evaluate_owner_entry(
        symbol=str(symbol or ""),
        side=side_u,
        volume=vol,
        entry=entry_d,
        stop_loss=_dec(stop_loss),
        take_profit=_dec(take_profit),
        spread=ask - bid,
        contract_size=contract,
        equity=equity,
        now=moment,
        commission=commission,
        daily=daily,
        user_planned_risk_pct=getattr(user_caps, "planned_risk_pct", None),
        user_daily_loss_pct=getattr(user_caps, "daily_loss_pct", None),
    )
    reasons.extend(violations)
    return WorkerGuardResult(
        env,
        tuple(reasons),
        {
            "equity": str(equity),
            "spread": str(ask - bid),
            "entry": str(entry_d),
            "commission": str(commission) if commission is not None else "unknown",
        },
    )
