"""Force First Trade — temporary live-pipeline test override.

Isolated module: waive Quality / Confluence / MTF signal gates for at most
FORCE_FIRST_TRADE_MAX successful market orders, then auto-disarm.

Never bypasses: MT5 connectivity, margin, symbol, market open, spread,
broker validation, or Risk REJECT for non-signal reasons.
Never modifies scoring engines or trade management.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    ConfluenceResult,
    DecisionAction,
    TradeDecision,
    TradeDirection,
)
from app.domain.institutional_trading.eligibility import PositionEligibilityEngine
from app.domain.institutional_trading.models import MarketAnalysisSnapshot
from app.domain.institutional_trading.trade_decision import TradeDecisionEngine
from app.domain.market_structure.enums import TrendDirection
from core.logging import get_logger

logger = get_logger(__name__)

FORCED_REASON = "FORCED_TEST_TRADE"
_STATE_LOCK = Lock()
ForceDirection = Literal["BUY", "SELL", "AUTO"]


def force_first_trade_state_path() -> Path:
    raw = (os.environ.get("QUANTFORG_FORCE_FIRST_TRADE_STATE_PATH") or "").strip()
    if raw:
        return Path(raw)
    volume = (os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or "").strip()
    if volume:
        return Path(volume) / "force_first_trade_state.json"
    base = Path(os.environ.get("QUANTFORG_DATA_DIR") or "data")
    return base / "force_first_trade_state.json"


@dataclass(frozen=True, slots=True)
class ForceFirstTradeConfig:
    enabled: bool = False
    max_trades: int = 1
    lot: Decimal = Decimal("0.01")
    direction: ForceDirection = "AUTO"

    @classmethod
    def from_settings(cls, settings: Any) -> ForceFirstTradeConfig:
        raw_dir = str(
            getattr(settings, "force_first_trade_direction", "AUTO") or "AUTO"
        ).strip().upper()
        direction: ForceDirection = (
            raw_dir if raw_dir in {"BUY", "SELL", "AUTO"} else "AUTO"
        )
        max_trades = int(getattr(settings, "force_first_trade_max", 1) or 1)
        lot_raw = getattr(settings, "force_first_trade_lot", "0.01")
        try:
            lot = Decimal(str(lot_raw))
        except Exception:
            lot = Decimal("0.01")
        if lot <= 0:
            lot = Decimal("0.01")
        return cls(
            enabled=bool(getattr(settings, "force_first_trade", False)),
            max_trades=max(1, max_trades),
            lot=lot,
            direction=direction,
        )


@dataclass
class ForceFirstTradeState:
    executed_count: int = 0
    armed: bool = True
    last_ticket: int | None = None
    last_direction: str | None = None
    last_lot: str | None = None
    last_at: str | None = None
    last_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "executed_count": self.executed_count,
            "armed": self.armed,
            "last_ticket": self.last_ticket,
            "last_direction": self.last_direction,
            "last_lot": self.last_lot,
            "last_at": self.last_at,
            "last_detail": self.last_detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ForceFirstTradeState:
        if not data:
            return cls()
        return cls(
            executed_count=int(data.get("executed_count") or 0),
            armed=bool(data.get("armed", True)),
            last_ticket=(
                int(data["last_ticket"])
                if data.get("last_ticket") is not None
                else None
            ),
            last_direction=(
                str(data["last_direction"])
                if data.get("last_direction") is not None
                else None
            ),
            last_lot=(
                str(data["last_lot"]) if data.get("last_lot") is not None else None
            ),
            last_at=str(data["last_at"]) if data.get("last_at") is not None else None,
            last_detail=(
                str(data["last_detail"])
                if data.get("last_detail") is not None
                else None
            ),
        )


def _load_state() -> ForceFirstTradeState:
    path = force_first_trade_state_path()
    try:
        if not path.is_file():
            return ForceFirstTradeState()
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return ForceFirstTradeState.from_dict(raw)
    except Exception:
        logger.exception("force_first_trade_state_load_failed")
    return ForceFirstTradeState()


def _save_state(state: ForceFirstTradeState) -> None:
    path = force_first_trade_state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(state.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("force_first_trade_state_save_failed")


def get_force_first_trade_state() -> ForceFirstTradeState:
    with _STATE_LOCK:
        return _load_state()


def is_force_first_trade_armed(settings: Any) -> bool:
    """True when env enables force mode and local disarm counter still allows it."""
    cfg = ForceFirstTradeConfig.from_settings(settings)
    if not cfg.enabled:
        return False
    state = get_force_first_trade_state()
    return bool(state.armed and state.executed_count < cfg.max_trades)


def log_force_first_trade_startup(settings: Any) -> None:
    """Emit required startup banners when FORCE_FIRST_TRADE is loaded."""
    cfg = ForceFirstTradeConfig.from_settings(settings)
    enabled = bool(cfg.enabled)
    logger.warning("FORCE_FIRST_TRADE = %s", "TRUE" if enabled else "FALSE")
    if enabled and is_force_first_trade_armed(settings):
        logger.warning("FORCE_FIRST_TRADE armed")
        logger.warning(
            "force_first_trade_startup_config",
            max=cfg.max_trades,
            lot=str(cfg.lot),
            direction=cfg.direction,
        )
    elif enabled:
        state = get_force_first_trade_state()
        logger.warning(
            "FORCE_FIRST_TRADE enabled but DISARMED",
            executed_count=state.executed_count,
            max=cfg.max_trades,
            armed=state.armed,
        )


def is_forced_test_decision(decision: TradeDecision) -> bool:
    return FORCED_REASON in (decision.reasons or ())


def resolve_force_direction(
    *,
    configured: ForceDirection,
    snapshot: MarketAnalysisSnapshot,
    confluence: ConfluenceResult,
) -> TradeDirection | None:
    if configured == "BUY":
        return TradeDirection.BUY
    if configured == "SELL":
        return TradeDirection.SELL
    # AUTO — H4 macro bias, else strategy confluence direction
    bias = snapshot.trend.macro_bias
    if bias is TrendDirection.UP:
        return TradeDirection.BUY
    if bias is TrendDirection.DOWN:
        return TradeDirection.SELL
    if confluence.direction in {TradeDirection.BUY, TradeDirection.SELL}:
        return confluence.direction
    return None


def force_first_trade_status(
    settings: Any,
    *,
    gateway_connected: bool = False,
    broker_connected: bool = False,
    execution_enabled: bool = False,
    open_positions: int = 0,
) -> dict[str, Any]:
    cfg = ForceFirstTradeConfig.from_settings(settings)
    state = get_force_first_trade_state()
    remaining = max(0, cfg.max_trades - state.executed_count)
    armed = (
        cfg.enabled
        and state.armed
        and remaining > 0
        and bool(execution_enabled)
    )
    banner = bool(cfg.enabled and state.armed and remaining > 0)
    return {
        "enabled": cfg.enabled,
        "armed": armed,
        "banner": banner,
        "executed_count": state.executed_count,
        "max": cfg.max_trades,
        "remaining": remaining,
        "lot": str(cfg.lot),
        "direction": cfg.direction,
        "gateway_connected": bool(gateway_connected),
        "broker_connected": bool(broker_connected),
        "open_positions": int(open_positions),
        "last_ticket": state.last_ticket,
        "last_direction": state.last_direction,
        "last_at": state.last_at,
        "message": (
            "TEST MODE — Forced Trade Enabled"
            if banner
            else "Force First Trade inactive"
        ),
    }


def maybe_override_decision(
    decision: TradeDecision,
    *,
    snapshot: MarketAnalysisSnapshot,
    account: AccountRiskState,
    ite_config: ITEConfig,
    settings: Any,
    execution_enabled: bool,
    gateway_connected: bool,
    broker_connected: bool,
    force_shadow: bool,
) -> tuple[TradeDecision, bool]:
    """If armed, replace NO_TRADE/WATCH with one forced BUY/SELL decision."""
    if force_shadow:
        return decision, False
    if decision.action in {DecisionAction.BUY, DecisionAction.SELL}:
        return decision, False

    cfg = ForceFirstTradeConfig.from_settings(settings)
    with _STATE_LOCK:
        state = _load_state()
        if not cfg.enabled or not state.armed:
            return decision, False
        if state.executed_count >= cfg.max_trades:
            return decision, False
        if not execution_enabled:
            return decision, False
        if not gateway_connected or not broker_connected:
            return decision, False
        if account.open_positions > 0 or account.already_in_trade:
            return decision, False

        direction = resolve_force_direction(
            configured=cfg.direction,
            snapshot=snapshot,
            confluence=decision.confluence,
        )
        if direction is None:
            logger.warning(
                "force_first_trade_no_bias_defaulting_BUY",
                configured=cfg.direction,
            )
            direction = TradeDirection.BUY

        # Force First Trade continues past signal/risk soft blocks to OMS.
        # Margin / market-open / spread remain enforced in eligibility below.
        logger.warning("Force First Trade detected")
        logger.warning(
            "Bypassing:\n- Quality\n- Confluence\n- MTF"
        )

        forced_confluence = ConfluenceResult(
            confidence=decision.confluence.confidence,
            direction=direction,
            reasons=tuple(
                dict.fromkeys(
                    (
                        *decision.confluence.reasons,
                        FORCED_REASON,
                        "Manual Test — signal gates waived",
                    )
                )
            ),
            rejected_rules=decision.confluence.rejected_rules,
            input_hash=decision.confluence.input_hash,
            band="forced_test",
            passed=True,
            factors=dict(decision.confluence.factors),
        )

        eligibility = PositionEligibilityEngine(config=ite_config).evaluate(
            snapshot=snapshot,
            confluence=forced_confluence,
            account=account,
            risk_allowed=True,
            risk_reasons=decision.risk_reasons,
            waive_signal_gates=True,
            force_test_mode=True,
        )
        if not eligibility.eligible:
            exact = "; ".join(eligibility.rejection_reasons) or "eligibility_failed"
            logger.error(
                "FORCE_FIRST_TRADE REJECTED before OMS: %s",
                exact,
            )
            return decision, False

        engine = TradeDecisionEngine(config=ite_config)
        entry_zone, stop_zone, target_zone, rr, invalidations = engine._geometry(
            snapshot, direction, account
        )
        if entry_zone is None or stop_zone is None or target_zone is None:
            logger.error(
                "FORCE_FIRST_TRADE REJECTED before OMS: missing entry/stop/target zones"
            )
            return decision, False

        action = (
            DecisionAction.BUY
            if direction is TradeDirection.BUY
            else DecisionAction.SELL
        )
        digest = sha256(
            (
                f"force1|{snapshot.input_hash}|{direction.value}|"
                f"{cfg.lot}|{state.executed_count}"
            ).encode()
        ).hexdigest()[:32]

        forced = TradeDecision(
            action=action,
            direction=direction,
            confidence=decision.confidence,
            quality=decision.quality,
            risk_score=decision.risk_score,
            reasons=(
                FORCED_REASON,
                "Reason: Manual Test",
                f"Direction: {direction.value}",
                f"Lot: {cfg.lot}",
                "Signal gates waived (quality/confluence/MTF)",
                *tuple(
                    r
                    for r in decision.reasons
                    if r not in {FORCED_REASON, "Reason: Manual Test"}
                ),
            ),
            invalidations=tuple(invalidations),
            entry_zone=entry_zone,
            stop_zone=stop_zone,
            target_zone=target_zone,
            estimated_rr=rr,
            expected_duration="forced_test",
            confluence=forced_confluence,
            eligibility=eligibility,
            input_hash=digest,
            config_version=ite_config.config_version,
            symbol=snapshot.symbol,
            as_of=decision.as_of,
            approved_lots=cfg.lot,
            risk_reasons=decision.risk_reasons,
        )
        logger.warning("Submitting order...")
        logger.warning(
            "force_first_trade_submitting",
            direction=direction.value,
            lot=str(cfg.lot),
            quality=decision.quality,
            confluence=decision.confidence,
            mid=str(account.mid_price) if account.mid_price is not None else None,
        )
        return forced, True


def record_forced_trade_success(
    *,
    direction: str,
    lot: Decimal | str,
    ticket: int | None,
    price: Decimal | str | None = None,
) -> ForceFirstTradeState:
    """Increment counter, disarm, and emit the required audit log line."""
    now = datetime.now(UTC).isoformat()
    with _STATE_LOCK:
        state = _load_state()
        state.executed_count += 1
        state.armed = False
        state.last_ticket = int(ticket) if ticket is not None else None
        state.last_direction = str(direction)
        state.last_lot = str(lot)
        state.last_at = now
        state.last_detail = "FORCED TEST TRADE EXECUTED"
        _save_state(state)

    ticket_txt = str(ticket) if ticket is not None else "PENDING"
    price_txt = str(price) if price is not None else "N/A"
    msg = (
        "FORCED TEST TRADE EXECUTED\n"
        f"Ticket: {ticket_txt}\n"
        f"Direction: {direction}\n"
        f"Lot: {lot}\n"
        f"Price: {price_txt}"
    )
    logger.warning(msg)
    return state


def log_force_first_trade_rejection(
    *,
    stage: str,
    reason: str,
    retcode: int | None = None,
    oms_message: str | None = None,
    detail: str | None = None,
) -> None:
    """Print the exact broker/OMS rejection for operators."""
    parts = [
        f"FORCE_FIRST_TRADE REJECTED at {stage}",
        f"Reason: {reason}",
    ]
    if retcode is not None:
        parts.append(f"Retcode: {retcode}")
    if oms_message:
        parts.append(f"OMS/MT5: {oms_message}")
    if detail:
        parts.append(f"Detail: {detail}")
    logger.error("\n".join(parts))


def reset_force_first_trade_state_for_tests() -> None:
    """Test helper — clear persisted disarm state."""
    with _STATE_LOCK:
        path = force_first_trade_state_path()
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass
        _save_state(ForceFirstTradeState())
