"""Phase 73 — controlled live-trading authorization.

Additive gate on top of the existing OMS / risk / ITE path.
Does not create a second scanner, research engine, gateway, or OMS.

Research remains advisory. ``research_can_execute`` is True only when this
controller is ENABLED. Research itself never authorizes live trading.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum
from threading import RLock
from typing import Any, Literal
from uuid import UUID

from app.domain.institutional_trading.operations.models import OperatorIdentity

LiveTradingState = Literal[
    "DISABLED",
    "READY_FOR_REVIEW",
    "ARMED",
    "ENABLED",
    "PAUSED",
    "KILLED",
]

STATES: tuple[LiveTradingState, ...] = (
    "DISABLED",
    "READY_FOR_REVIEW",
    "ARMED",
    "ENABLED",
    "PAUSED",
    "KILLED",
)

# Operator-only transitions. Safety auto-PAUSE and emergency_disable are separate.
# ENABLED is the canonical live-authorization state (displayed as LIVE_ENABLED).
ALLOWED_TRANSITIONS: dict[LiveTradingState, frozenset[LiveTradingState]] = {
    "DISABLED": frozenset({"READY_FOR_REVIEW", "ARMED"}),
    "READY_FOR_REVIEW": frozenset({"ARMED", "DISABLED"}),
    "ARMED": frozenset({"ENABLED", "DISABLED"}),
    "ENABLED": frozenset({"PAUSED", "KILLED", "DISABLED"}),
    "PAUSED": frozenset({"ENABLED", "KILLED", "DISABLED"}),
    "KILLED": frozenset({"DISABLED"}),
}

_STATE_ALIASES: dict[str, LiveTradingState] = {
    "LIVE": "ENABLED",
    "LIVE_ENABLED": "ENABLED",
    "READY": "READY_FOR_REVIEW",
    "EMERGENCY_STOP": "DISABLED",
}

OPERATOR_ROLES = frozenset({"owner", "admin"})
MappingLike = dict[str, Any]

# Micro-account hard ceiling — configuration cannot exceed these.
# Existing ITE MAX_DAILY_LOSS_PCT (40%) remains the global engine cap;
# this overlay is strictly tighter for real-money live authorization.
HARD_CEILING_RISK_PER_TRADE_PCT = Decimal("1.00")
HARD_CEILING_DAILY_LOSS_PCT = Decimal("8.00")
HARD_CEILING_MAX_POSITIONS = 2
HARD_CEILING_CONSECUTIVE_LOSSES = 3
HARD_CEILING_MARGIN_UTIL_PCT = Decimal("40.00")
HARD_CEILING_TOTAL_EXPOSURE_PCT = Decimal("50.00")
HARD_CEILING_MAX_SPREAD = Decimal("2.00")
HARD_CEILING_MAX_SLIPPAGE = Decimal("1.00")
HARD_CEILING_QUOTE_AGE_S = Decimal("5.00")

# Conservative defaults for a ~$33 real-money account (capital preservation).
DEFAULT_RISK_PER_TRADE_PCT = Decimal("0.50")
DEFAULT_DAILY_LOSS_PCT = Decimal("3.00")
DEFAULT_MAX_POSITIONS = 1
DEFAULT_CONSECUTIVE_LOSSES = 2
DEFAULT_MARGIN_UTIL_PCT = Decimal("25.00")
DEFAULT_TOTAL_EXPOSURE_PCT = Decimal("30.00")
DEFAULT_MAX_SPREAD = Decimal("1.50")
DEFAULT_MAX_SLIPPAGE = Decimal("0.50")
DEFAULT_QUOTE_AGE_S = Decimal("3.00")
DEFAULT_MIN_RR = Decimal("1.20")
DEFAULT_MIN_SCORE = Decimal("70")
DEFAULT_DUPLICATE_TTL_S = 120
ACCOUNT_TOO_SMALL = "Account too small for configured risk limits on this instrument."

_NON_EXECUTABLE_SIGNAL_STATES = frozenset(
    {
        "NEUTRAL",
        "NONE",
        "STALE",
        "DATA_UNAVAILABLE",
        "MARKET_CLOSED",
        "FAILED",
        "UNSUPPORTED",
        "WAIT",
        "NO_TRADE",
        "QUEUED",
    }
)

_SECRET_KEYS = frozenset(
    {
        "password",
        "api_key",
        "apikey",
        "token",
        "access_token",
        "refresh_token",
        "service_role",
        "service_role_key",
        "secret",
        "mt5_password",
        "broker_password",
        "authorization",
        "caller_token",
        "gateway_token",
    }
)


class LiveTradingTransitionError(ValueError):
    """Illegal state transition or missing confirmation."""


class LiveTradingAuthError(PermissionError):
    """Caller is not OWNER/ADMIN."""


class LiveTradingStateName(StrEnum):
    DISABLED = "DISABLED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    ARMED = "ARMED"
    ENABLED = "ENABLED"
    LIVE_ENABLED = "ENABLED"
    PAUSED = "PAUSED"
    KILLED = "KILLED"


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_state(value: Any) -> LiveTradingState:
    raw = str(value or "").strip().upper()
    if raw in _STATE_ALIASES:
        return _STATE_ALIASES[raw]
    if raw in STATES:
        return raw  # type: ignore[return-value]
    return "DISABLED"


def orders_may_submit(state: Any) -> bool:
    """True only for canonical ENABLED (LIVE_ENABLED alias included)."""
    return normalize_state(state) == "ENABLED"


def public_state_name(
    state: Any, *, activation_ready: bool = False, emergency: bool = False
) -> str:
    """Operator-facing name. LIVE_ENABLED only when backend state is ENABLED."""
    canonical = normalize_state(state)
    if canonical == "ENABLED":
        return "LIVE_ENABLED"
    if canonical == "DISABLED" and emergency:
        return "DISABLED"
    if canonical == "DISABLED" and activation_ready:
        return "READY_FOR_REVIEW"
    if canonical == "KILLED":
        return "EMERGENCY_STOP"
    return canonical


def public_authorization_state(
    state: Any, *, orders_may_submit_flag: bool | None = None
) -> str:
    """Trader-facing live-authorization. Never inferred from broker connection."""
    canonical = normalize_state(state)
    if canonical == "ENABLED":
        if orders_may_submit_flag is False:
            return "EXECUTION_BLOCKED"
        return "LIVE_ENABLED"
    if canonical == "PAUSED":
        return "LIVE_PAUSED"
    return "LIVE_DISABLED"


def recover_after_restart(persisted: Any) -> LiveTradingState:
    """Fail closed after deploy / reconnect / uncertain hydrate.

    ENABLED / LIVE_ENABLED never survives a restart.
    Incomplete ARM / READY_FOR_REVIEW is dropped.
    Emergency KILLED recovers as DISABLED and requires re-arm.
    PAUSED is preserved so the operator must explicitly resume.
    """
    state = normalize_state(persisted)
    if state == "ENABLED":
        return "PAUSED"
    if state in {"ARMED", "READY_FOR_REVIEW", "KILLED"}:
        return "DISABLED"
    if state in {"PAUSED", "DISABLED"}:
        return state
    return "DISABLED"


def finite_positive(value: Any) -> bool:
    """Reject None, NaN, Inf, zero, and negatives. Never coerce into a price."""
    if value is None:
        return False
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception:
        return False
    return not (parsed.is_nan() or parsed.is_infinite() or parsed <= 0)


def _dec(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default))
    except Exception:
        return Decimal(default)


def _clamp(value: Decimal, *, lo: Decimal, hi: Decimal) -> Decimal:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def strip_secrets(payload: Any) -> Any:
    """Drop credentials from audit / API payloads. Never log secrets."""
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for key, val in payload.items():
            lk = str(key).strip().lower()
            if lk in _SECRET_KEYS or any(
                s in lk for s in ("password", "secret", "token")
            ):
                continue
            out[key] = strip_secrets(val)
        return out
    if isinstance(payload, list):
        return [strip_secrets(item) for item in payload]
    return payload


def require_operator(operator: OperatorIdentity) -> None:
    role = str(operator.role or "").strip().lower()
    if role not in OPERATOR_ROLES:
        raise LiveTradingAuthError(
            f"role={operator.role} is not authorized for live trading control"
        )


@dataclass(frozen=True, slots=True)
class LiveTradingRiskConfig:
    """Operator-configurable live risk — always clamped to the hard ceiling."""

    risk_per_trade_pct: Decimal = DEFAULT_RISK_PER_TRADE_PCT
    max_daily_loss_pct: Decimal = DEFAULT_DAILY_LOSS_PCT
    max_open_positions: int = DEFAULT_MAX_POSITIONS
    max_consecutive_losses: int = DEFAULT_CONSECUTIVE_LOSSES
    max_margin_utilization_pct: Decimal = DEFAULT_MARGIN_UTIL_PCT
    max_total_exposure_pct: Decimal = DEFAULT_TOTAL_EXPOSURE_PCT
    max_spread: Decimal = DEFAULT_MAX_SPREAD
    max_slippage: Decimal = DEFAULT_MAX_SLIPPAGE
    max_quote_age_seconds: Decimal = DEFAULT_QUOTE_AGE_S
    min_reward_risk: Decimal = DEFAULT_MIN_RR
    min_score: Decimal = DEFAULT_MIN_SCORE
    duplicate_ttl_seconds: int = DEFAULT_DUPLICATE_TTL_S
    close_positions_on_kill: bool = False
    allow_martingale: bool = False
    allow_grid_averaging: bool = False
    allow_revenge_sizing: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "risk_per_trade_pct",
            _clamp(
                _dec(self.risk_per_trade_pct, str(DEFAULT_RISK_PER_TRADE_PCT)),
                lo=Decimal("0.01"),
                hi=HARD_CEILING_RISK_PER_TRADE_PCT,
            ),
        )
        object.__setattr__(
            self,
            "max_daily_loss_pct",
            _clamp(
                _dec(self.max_daily_loss_pct, str(DEFAULT_DAILY_LOSS_PCT)),
                lo=Decimal("0.10"),
                hi=HARD_CEILING_DAILY_LOSS_PCT,
            ),
        )
        positions = int(self.max_open_positions or DEFAULT_MAX_POSITIONS)
        object.__setattr__(
            self,
            "max_open_positions",
            max(1, min(positions, HARD_CEILING_MAX_POSITIONS)),
        )
        losses = int(self.max_consecutive_losses or DEFAULT_CONSECUTIVE_LOSSES)
        object.__setattr__(
            self,
            "max_consecutive_losses",
            max(1, min(losses, HARD_CEILING_CONSECUTIVE_LOSSES)),
        )
        object.__setattr__(
            self,
            "max_margin_utilization_pct",
            _clamp(
                _dec(self.max_margin_utilization_pct, str(DEFAULT_MARGIN_UTIL_PCT)),
                lo=Decimal("1"),
                hi=HARD_CEILING_MARGIN_UTIL_PCT,
            ),
        )
        object.__setattr__(
            self,
            "max_total_exposure_pct",
            _clamp(
                _dec(self.max_total_exposure_pct, str(DEFAULT_TOTAL_EXPOSURE_PCT)),
                lo=Decimal("1"),
                hi=HARD_CEILING_TOTAL_EXPOSURE_PCT,
            ),
        )
        object.__setattr__(
            self,
            "max_spread",
            _clamp(
                _dec(self.max_spread, str(DEFAULT_MAX_SPREAD)),
                lo=Decimal("0.01"),
                hi=HARD_CEILING_MAX_SPREAD,
            ),
        )
        object.__setattr__(
            self,
            "max_slippage",
            _clamp(
                _dec(self.max_slippage, str(DEFAULT_MAX_SLIPPAGE)),
                lo=Decimal("0.01"),
                hi=HARD_CEILING_MAX_SLIPPAGE,
            ),
        )
        object.__setattr__(
            self,
            "max_quote_age_seconds",
            _clamp(
                _dec(self.max_quote_age_seconds, str(DEFAULT_QUOTE_AGE_S)),
                lo=Decimal("0.50"),
                hi=HARD_CEILING_QUOTE_AGE_S,
            ),
        )
        object.__setattr__(
            self,
            "min_reward_risk",
            max(_dec(self.min_reward_risk, str(DEFAULT_MIN_RR)), Decimal("1.00")),
        )
        object.__setattr__(
            self,
            "min_score",
            _clamp(
                _dec(self.min_score, str(DEFAULT_MIN_SCORE)),
                lo=Decimal("50"),
                hi=Decimal("100"),
            ),
        )
        ttl = int(self.duplicate_ttl_seconds or DEFAULT_DUPLICATE_TTL_S)
        object.__setattr__(self, "duplicate_ttl_seconds", max(15, min(ttl, 600)))
        # Hard bans — configuration cannot enable these.
        object.__setattr__(self, "allow_martingale", False)
        object.__setattr__(self, "allow_grid_averaging", False)
        object.__setattr__(self, "allow_revenge_sizing", False)
        object.__setattr__(
            self, "close_positions_on_kill", bool(self.close_positions_on_kill)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_per_trade_pct": str(self.risk_per_trade_pct),
            "max_daily_loss_pct": str(self.max_daily_loss_pct),
            "max_open_positions": self.max_open_positions,
            "max_consecutive_losses": self.max_consecutive_losses,
            "max_margin_utilization_pct": str(self.max_margin_utilization_pct),
            "max_total_exposure_pct": str(self.max_total_exposure_pct),
            "max_spread": str(self.max_spread),
            "max_slippage": str(self.max_slippage),
            "max_quote_age_seconds": str(self.max_quote_age_seconds),
            "min_reward_risk": str(self.min_reward_risk),
            "min_score": str(self.min_score),
            "duplicate_ttl_seconds": self.duplicate_ttl_seconds,
            "close_positions_on_kill": self.close_positions_on_kill,
            "allow_martingale": False,
            "allow_grid_averaging": False,
            "allow_revenge_sizing": False,
            "hard_ceiling": {
                "risk_per_trade_pct": str(HARD_CEILING_RISK_PER_TRADE_PCT),
                "max_daily_loss_pct": str(HARD_CEILING_DAILY_LOSS_PCT),
                "max_open_positions": HARD_CEILING_MAX_POSITIONS,
                "max_consecutive_losses": HARD_CEILING_CONSECUTIVE_LOSSES,
                "max_margin_utilization_pct": str(HARD_CEILING_MARGIN_UTIL_PCT),
                "max_total_exposure_pct": str(HARD_CEILING_TOTAL_EXPOSURE_PCT),
            },
        }

    def min_rr_or_default(self) -> Decimal:
        return self.min_reward_risk

    @classmethod
    def from_dict(cls, data: MappingLike | None) -> LiveTradingRiskConfig:
        raw = data if isinstance(data, dict) else {}
        return cls(
            risk_per_trade_pct=_dec(
                raw.get("risk_per_trade_pct"), str(DEFAULT_RISK_PER_TRADE_PCT)
            ),
            max_daily_loss_pct=_dec(
                raw.get("max_daily_loss_pct"), str(DEFAULT_DAILY_LOSS_PCT)
            ),
            max_open_positions=int(
                raw.get("max_open_positions") or DEFAULT_MAX_POSITIONS
            ),
            max_consecutive_losses=int(
                raw.get("max_consecutive_losses") or DEFAULT_CONSECUTIVE_LOSSES
            ),
            max_margin_utilization_pct=_dec(
                raw.get("max_margin_utilization_pct"), str(DEFAULT_MARGIN_UTIL_PCT)
            ),
            max_total_exposure_pct=_dec(
                raw.get("max_total_exposure_pct"), str(DEFAULT_TOTAL_EXPOSURE_PCT)
            ),
            max_spread=_dec(raw.get("max_spread"), str(DEFAULT_MAX_SPREAD)),
            max_slippage=_dec(raw.get("max_slippage"), str(DEFAULT_MAX_SLIPPAGE)),
            max_quote_age_seconds=_dec(
                raw.get("max_quote_age_seconds"), str(DEFAULT_QUOTE_AGE_S)
            ),
            min_reward_risk=_dec(raw.get("min_reward_risk"), str(DEFAULT_MIN_RR)),
            min_score=_dec(raw.get("min_score"), str(DEFAULT_MIN_SCORE)),
            duplicate_ttl_seconds=int(
                raw.get("duplicate_ttl_seconds") or DEFAULT_DUPLICATE_TTL_S
            ),
            close_positions_on_kill=bool(raw.get("close_positions_on_kill")),
        )


@dataclass(frozen=True, slots=True)
class BrokerSymbolSpec:
    """Broker-reported contract facts. Missing fields stay None — never assumed."""

    symbol: str
    contract_size: Decimal | None = None
    volume_min: Decimal | None = None
    volume_max: Decimal | None = None
    volume_step: Decimal | None = None
    tick_value: Decimal | None = None
    tick_size: Decimal | None = None
    margin_initial: Decimal | None = None
    leverage: Decimal | None = None
    stops_level: Decimal | None = None
    freeze_level: Decimal | None = None
    spread: Decimal | None = None
    trade_mode: str | None = None
    trade_allowed: bool | None = None
    market_open: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "contract_size": _fmt(self.contract_size),
            "volume_min": _fmt(self.volume_min),
            "volume_max": _fmt(self.volume_max),
            "volume_step": _fmt(self.volume_step),
            "tick_value": _fmt(self.tick_value),
            "tick_size": _fmt(self.tick_size),
            "margin_initial": _fmt(self.margin_initial),
            "leverage": _fmt(self.leverage),
            "stops_level": _fmt(self.stops_level),
            "freeze_level": _fmt(self.freeze_level),
            "spread": _fmt(self.spread),
            "trade_mode": self.trade_mode,
            "trade_allowed": self.trade_allowed,
            "market_open": self.market_open,
            "source": "broker" if self.contract_size is not None else "unavailable",
        }


def spec_from_broker(symbol: str, raw: Any) -> BrokerSymbolSpec:
    """Read contract fields from a live broker symbol info object/dict."""
    code = (symbol or "").strip().upper()

    def _get(*names: str) -> Any:
        for name in names:
            if isinstance(raw, dict) and name in raw and raw[name] not in (None, ""):
                return raw[name]
            if raw is not None and hasattr(raw, name):
                val = getattr(raw, name)
                if val not in (None, ""):
                    return val
        return None

    def _opt_dec(*names: str) -> Decimal | None:
        val = _get(*names)
        if val is None:
            return None
        parsed = _dec(val)
        return parsed if parsed > 0 else None

    trade_allowed = _get("trade_allowed", "tradeAllowed")
    market_open = _get("market_open", "marketOpen")
    return BrokerSymbolSpec(
        symbol=code,
        contract_size=_opt_dec("contract_size", "trade_contract_size", "contractSize"),
        volume_min=_opt_dec("volume_min", "volumeMin", "min_lot", "min_volume"),
        volume_max=_opt_dec("volume_max", "volumeMax", "max_lot", "max_volume"),
        volume_step=_opt_dec("volume_step", "volumeStep", "lot_step"),
        tick_value=_opt_dec("tick_value", "trade_tick_value", "tickValue"),
        tick_size=_opt_dec("tick_size", "trade_tick_size", "tickSize"),
        margin_initial=_opt_dec("margin_initial", "margin_hedged", "marginInitial"),
        leverage=_opt_dec("leverage"),
        stops_level=_opt_dec("stops_level", "trade_stops_level", "stopsLevel"),
        freeze_level=_opt_dec("freeze_level", "trade_freeze_level", "freezeLevel"),
        spread=_opt_dec("spread", "spread_current"),
        trade_mode=str(_get("trade_mode", "tradeMode") or "") or None,
        trade_allowed=None if trade_allowed is None else bool(trade_allowed),
        market_open=None if market_open is None else bool(market_open),
    )


def _fmt(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


@dataclass(frozen=True, slots=True)
class PositionSizeResult:
    accepted: bool
    volume: Decimal
    risk_amount: Decimal
    stop_distance: Decimal
    reason: str = ""
    monetary_loss_at_sl: Decimal = Decimal("0")
    percentage_account_risk: Decimal = Decimal("0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "volume": str(self.volume),
            "risk_amount": str(self.risk_amount),
            "stop_distance": str(self.stop_distance),
            "reason": self.reason,
            "monetary_loss_at_sl": str(self.monetary_loss_at_sl),
            "percentage_account_risk": str(self.percentage_account_risk),
        }


def size_from_broker_specs(
    *,
    equity: Decimal,
    risk_pct: Decimal,
    stop_distance: Decimal,
    spec: BrokerSymbolSpec,
    max_risk_amount: Decimal | None = None,
) -> PositionSizeResult:
    """Size from actual broker contract specs. Never uses a generic lot model.

    If the broker minimum lot would exceed the configured risk budget, reject.
    """
    if equity <= 0 or not finite_positive(equity):
        return PositionSizeResult(
            False, Decimal("0"), Decimal("0"), stop_distance, "equity_unavailable"
        )
    if stop_distance <= 0 or not finite_positive(stop_distance):
        return PositionSizeResult(
            False, Decimal("0"), Decimal("0"), stop_distance, "invalid_stop_distance"
        )
    if spec.contract_size is None or spec.contract_size <= 0:
        return PositionSizeResult(
            False,
            Decimal("0"),
            Decimal("0"),
            stop_distance,
            "broker_contract_size_unavailable",
        )
    if spec.volume_min is None or spec.volume_min <= 0:
        return PositionSizeResult(
            False,
            Decimal("0"),
            Decimal("0"),
            stop_distance,
            "broker_min_lot_unavailable",
        )
    if spec.volume_step is None or spec.volume_step <= 0:
        return PositionSizeResult(
            False,
            Decimal("0"),
            Decimal("0"),
            stop_distance,
            "broker_lot_step_unavailable",
        )

    risk_budget = (equity * (risk_pct / Decimal("100"))).quantize(Decimal("0.0001"))
    if max_risk_amount is not None and max_risk_amount > 0:
        risk_budget = min(risk_budget, max_risk_amount)
    if risk_budget <= 0:
        return PositionSizeResult(
            False, Decimal("0"), Decimal("0"), stop_distance, "risk_budget_zero"
        )

    loss_per_lot = stop_distance * spec.contract_size
    if spec.tick_size and spec.tick_value and spec.tick_size > 0:
        ticks = stop_distance / spec.tick_size
        tick_loss = ticks * spec.tick_value
        if tick_loss > 0:
            loss_per_lot = tick_loss
    if loss_per_lot <= 0:
        return PositionSizeResult(
            False, Decimal("0"), risk_budget, stop_distance, "loss_per_lot_invalid"
        )

    raw_lots = risk_budget / loss_per_lot
    step = spec.volume_step
    quantized = (raw_lots / step).to_integral_value(rounding=ROUND_DOWN) * step
    if quantized < spec.volume_min:
        min_loss = spec.volume_min * loss_per_lot
        pct_at_min = (
            (min_loss / equity) * Decimal("100") if equity > 0 else Decimal("0")
        )
        return PositionSizeResult(
            False,
            Decimal("0"),
            risk_budget,
            stop_distance,
            ACCOUNT_TOO_SMALL,
            monetary_loss_at_sl=min_loss,
            percentage_account_risk=pct_at_min.quantize(Decimal("0.0001")),
        )
    if spec.volume_max is not None and spec.volume_max > 0:
        quantized = min(quantized, spec.volume_max)
    actual_loss = quantized * loss_per_lot
    pct = (actual_loss / equity) * Decimal("100")
    if pct > risk_pct:
        return PositionSizeResult(
            False,
            Decimal("0"),
            risk_budget,
            stop_distance,
            ACCOUNT_TOO_SMALL,
            monetary_loss_at_sl=actual_loss,
            percentage_account_risk=pct.quantize(Decimal("0.0001")),
        )
    return PositionSizeResult(
        True,
        quantized,
        risk_budget,
        stop_distance,
        "",
        monetary_loss_at_sl=actual_loss,
        percentage_account_risk=pct.quantize(Decimal("0.0001")),
    )


@dataclass(frozen=True, slots=True)
class LiveOrderRequest:
    """Advisory input from research + live broker facts. Never fabricated."""

    symbol: str
    direction: str
    price: Decimal | None = None
    entry: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    score: Decimal | None = None
    edge: Decimal | None = None
    regime: str | None = None
    spread: Decimal | None = None
    quote_age_seconds: Decimal | None = None
    analysis_age_seconds: Decimal | None = None
    signal_id: str | None = None
    signal_status: str | None = None
    evidence: dict[str, Any] | None = None
    reward_risk: Decimal | None = None
    spec: BrokerSymbolSpec | None = None
    equity: Decimal | None = None
    balance: Decimal | None = None
    free_margin: Decimal | None = None
    used_margin: Decimal | None = None
    open_positions: int = 0
    open_exposure_pct: Decimal | None = None
    correlated_exposure_pct: Decimal | None = None
    daily_loss_pct: Decimal | None = None
    consecutive_losses: int = 0
    slippage: Decimal | None = None
    gateway_online: bool = False
    mt5_connected: bool = False
    ownership_ok: bool = False
    account_available: bool = False
    trading_permitted: bool = False
    symbol_available: bool = False
    symbol_tradeable: bool = False
    quote_fresh: bool = False
    price_valid: bool = False
    market_open: bool = False
    oms_healthy: bool = False
    risk_engine_healthy: bool = False
    audit_healthy: bool = False
    authenticated_authorized: bool = False
    request_id: str | None = None
    requested_volume: Decimal | None = None


@dataclass(frozen=True, slots=True)
class GateResult:
    key: str
    passed: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LiveOrderDecision:
    allowed: bool
    reasons: tuple[str, ...]
    gates: tuple[GateResult, ...]
    sizing: PositionSizeResult | None = None
    pause_execution: bool = False
    pause_symbol: str | None = None
    block_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "gates": [g.to_dict() for g in self.gates],
            "sizing": self.sizing.to_dict() if self.sizing else None,
            "pause_execution": self.pause_execution,
            "pause_symbol": self.pause_symbol,
            "block_code": self.block_code,
            "would_submit_order": self.allowed,
        }


def _gate(key: str, passed: bool, reason: str = "") -> GateResult:
    return GateResult(key=key, passed=passed, reason="" if passed else reason)


def evaluate_signal_quality(
    req: LiveOrderRequest, cfg: LiveTradingRiskConfig
) -> list[GateResult]:
    direction = str(req.direction or "").strip().upper()
    status = str(req.signal_status or "").strip().upper()
    symbol_ok = bool(str(req.symbol or "").strip())
    dir_ok = direction in {"BUY", "SELL"}
    status_ok = bool(status) and status not in _NON_EXECUTABLE_SIGNAL_STATES
    sl = req.stop_loss
    tp = req.take_profit
    entry = req.entry if req.entry is not None else req.price
    price_ok = finite_positive(req.price) and req.price_valid
    entry_ok = finite_positive(entry)
    sl_ok = finite_positive(sl) and entry_ok and sl != entry
    if sl_ok and entry is not None and sl is not None:
        if direction == "BUY":
            sl_ok = sl < entry
        elif direction == "SELL":
            sl_ok = sl > entry
    tp_ok = finite_positive(tp) and entry_ok and tp != entry
    if tp_ok and entry is not None and tp is not None:
        if direction == "BUY":
            tp_ok = tp > entry
        elif direction == "SELL":
            tp_ok = tp < entry
    evidence_ok = isinstance(req.evidence, dict) and bool(req.evidence)
    score_ok = req.score is not None and req.score >= cfg.min_score
    rr = req.reward_risk
    if (
        rr is None
        and sl_ok
        and tp_ok
        and entry is not None
        and sl is not None
        and tp is not None
    ):
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr = (reward / risk) if risk > 0 else None
    rr_ok = rr is not None and rr >= cfg.min_rr_or_default()
    regime_ok = bool(str(req.regime or "").strip())
    fresh = req.analysis_age_seconds is None or req.analysis_age_seconds <= Decimal(
        "180"
    )
    return [
        _gate("valid_symbol", symbol_ok, "invalid_symbol"),
        _gate("valid_direction", dir_ok, "invalid_direction"),
        _gate("valid_signal_status", status_ok, f"signal_status_{status or 'MISSING'}"),
        _gate("valid_price", price_ok, "invalid_price"),
        _gate("valid_entry", entry_ok, "invalid_entry"),
        _gate("valid_sl", bool(sl_ok), "invalid_or_missing_stop_loss"),
        _gate("valid_tp", bool(tp_ok), "invalid_or_missing_take_profit"),
        _gate("valid_evidence", evidence_ok, "missing_evidence"),
        _gate("valid_score", bool(score_ok), "score_below_minimum"),
        _gate("valid_regime", regime_ok, "missing_regime"),
        _gate("acceptable_rr", bool(rr_ok), "reward_risk_below_minimum"),
        _gate("fresh_analysis", bool(fresh), "stale_analysis_timestamp"),
    ]


def evaluate_broker_requirements(
    req: LiveOrderRequest, state: LiveTradingState
) -> list[GateResult]:
    return [
        _gate("authenticated_authorized", req.authenticated_authorized, "unauthorized"),
        _gate("ownership", req.ownership_ok, "broker_ownership_failure"),
        _gate("gateway_online", req.gateway_online, "gateway_offline"),
        _gate("mt5_connected", req.mt5_connected, "mt5_disconnected"),
        _gate("account_available", req.account_available, "account_unavailable"),
        _gate("trading_permitted", req.trading_permitted, "trading_not_permitted"),
        _gate("symbol_available", req.symbol_available, "symbol_unavailable"),
        _gate("symbol_tradeable", req.symbol_tradeable, "symbol_not_tradeable"),
        _gate("quote_fresh", req.quote_fresh, "stale_price"),
        _gate("price_valid", req.price_valid, "invalid_price"),
        _gate("market_open", req.market_open, "market_closed"),
        _gate("oms_healthy", req.oms_healthy, "oms_failure"),
        _gate("risk_engine_healthy", req.risk_engine_healthy, "risk_engine_failure"),
        _gate("audit_healthy", req.audit_healthy, "audit_failure"),
        _gate(
            "live_trading_state",
            orders_may_submit(state),
            f"live_trading_{normalize_state(state).lower()}",
        ),
    ]


def evaluate_live_order(
    req: LiveOrderRequest,
    *,
    state: LiveTradingState,
    cfg: LiveTradingRiskConfig,
    recent_signal_ids: set[str] | frozenset[str] = frozenset(),
    recent_order_keys: set[str] | frozenset[str] = frozenset(),
    last_loss_volume: Decimal | None = None,
) -> LiveOrderDecision:
    """Fail-closed pre-trade check. Never sends an order."""
    gates: list[GateResult] = []
    gates.extend(evaluate_broker_requirements(req, state))
    gates.extend(evaluate_signal_quality(req, cfg))

    spread_ok = req.spread is not None and req.spread <= cfg.max_spread
    gates.append(_gate("acceptable_spread", bool(spread_ok), "excessive_spread"))

    if req.quote_age_seconds is not None:
        q_ok = req.quote_age_seconds <= cfg.max_quote_age_seconds
        gates.append(_gate("quote_age", bool(q_ok), "stale_price"))

    slip_ok = req.slippage is None or req.slippage <= cfg.max_slippage
    gates.append(_gate("slippage", bool(slip_ok), "excessive_slippage"))

    if req.open_positions >= cfg.max_open_positions:
        gates.append(
            _gate(
                "max_positions",
                False,
                f"max_simultaneous_positions_{cfg.max_open_positions}",
            )
        )
    else:
        gates.append(_gate("max_positions", True))

    if req.consecutive_losses >= cfg.max_consecutive_losses:
        gates.append(
            _gate(
                "consecutive_losses",
                False,
                f"max_consecutive_losses_{cfg.max_consecutive_losses}",
            )
        )
    else:
        gates.append(_gate("consecutive_losses", True))

    if req.daily_loss_pct is not None and req.daily_loss_pct >= cfg.max_daily_loss_pct:
        gates.append(_gate("daily_loss", False, "daily_loss_limit"))
    else:
        gates.append(_gate("daily_loss", True))

    if (
        req.open_exposure_pct is not None
        and req.open_exposure_pct >= cfg.max_total_exposure_pct
    ):
        gates.append(_gate("exposure", False, "max_total_exposure"))
    else:
        gates.append(_gate("exposure", True))

    if (
        req.correlated_exposure_pct is not None
        and req.correlated_exposure_pct >= cfg.max_total_exposure_pct
    ):
        gates.append(_gate("correlated_exposure", False, "max_correlated_exposure"))
    else:
        gates.append(_gate("correlated_exposure", True))

    margin_util: Decimal | None = None
    if req.equity and req.equity > 0 and req.used_margin is not None:
        margin_util = (req.used_margin / req.equity) * Decimal("100")
    if margin_util is not None and margin_util >= cfg.max_margin_utilization_pct:
        gates.append(_gate("margin_utilization", False, "max_margin_utilization"))
    else:
        gates.append(_gate("margin_utilization", True))

    sid = str(req.signal_id or "").strip()
    if sid and sid in recent_signal_ids:
        gates.append(_gate("duplicate_signal", False, "duplicate_signal"))
    else:
        gates.append(_gate("duplicate_signal", True))

    order_key = _order_key(req)
    if order_key and order_key in recent_order_keys:
        gates.append(_gate("duplicate_order", False, "duplicate_order"))
    else:
        gates.append(_gate("duplicate_order", True))

    vol = req.requested_volume
    if vol is not None:
        vol_ok = finite_positive(vol)
        if vol_ok and req.spec is not None:
            if req.spec.volume_min is not None and vol < req.spec.volume_min:
                vol_ok = False
            if req.spec.volume_max is not None and vol > req.spec.volume_max:
                vol_ok = False
        gates.append(_gate("valid_volume", vol_ok, "invalid_volume"))
    else:
        gates.append(_gate("valid_volume", True))

    gates.append(_gate("martingale", not cfg.allow_martingale, "martingale_prohibited"))
    gates.append(
        _gate(
            "grid_averaging", not cfg.allow_grid_averaging, "grid_averaging_prohibited"
        )
    )
    gates.append(
        _gate("revenge", not cfg.allow_revenge_sizing, "revenge_trading_prohibited")
    )

    sizing: PositionSizeResult | None = None
    entry = req.entry if req.entry is not None else req.price
    sl = req.stop_loss
    if (
        req.spec is not None
        and req.equity is not None
        and finite_positive(entry)
        and finite_positive(sl)
    ):
        stop_dist = abs(entry - sl)
        sizing = size_from_broker_specs(
            equity=req.equity,
            risk_pct=cfg.risk_per_trade_pct,
            stop_distance=stop_dist,
            spec=req.spec,
        )
        gates.append(
            _gate("position_size", sizing.accepted, sizing.reason or "sizing_failed")
        )
        if (
            last_loss_volume is not None
            and sizing.accepted
            and sizing.volume > last_loss_volume
        ):
            # Size may change with equity/stop; increasing after a loss
            # is revenge/martingale.
            gates.append(
                _gate(
                    "no_loss_recovery_sizing",
                    False,
                    "position_size_increased_after_loss",
                )
            )
        else:
            gates.append(_gate("no_loss_recovery_sizing", True))
    elif req.spec is None:
        gates.append(_gate("position_size", False, "broker_spec_unavailable"))
        gates.append(_gate("no_loss_recovery_sizing", True))
    else:
        gates.append(_gate("position_size", False, "sizing_inputs_unavailable"))
        gates.append(_gate("no_loss_recovery_sizing", True))

    failed = tuple(g.reason or g.key for g in gates if not g.passed)
    pause_execution = any(
        g.key in {"daily_loss", "consecutive_losses", "exposure", "margin_utilization"}
        and not g.passed
        for g in gates
    )
    pause_symbol = (
        req.symbol
        if any(g.key == "quote_age" and not g.passed for g in gates)
        else None
    )
    if not req.gateway_online or not req.mt5_connected or not req.ownership_ok:
        pause_execution = True
    if not req.oms_healthy or not req.risk_engine_healthy or not req.audit_healthy:
        # Block, but do not flip ENABLED→PAUSED solely for a single-order health blip
        # unless already failing connectivity. Tests assert BLOCK vs PAUSE separately.
        pass
    allowed = not failed and orders_may_submit(state)
    block = failed[0] if failed else ""
    return LiveOrderDecision(
        allowed=allowed,
        reasons=failed,
        gates=tuple(gates),
        sizing=sizing,
        pause_execution=pause_execution and orders_may_submit(state),
        pause_symbol=pause_symbol,
        block_code=block,
    )


def _order_key(req: LiveOrderRequest) -> str:
    if req.request_id:
        return f"req:{req.request_id}"
    symbol = str(req.symbol or "").strip().upper()
    direction = str(req.direction or "").strip().upper()
    entry = req.entry if req.entry is not None else req.price
    if not symbol or not direction or entry is None:
        return ""
    return f"{symbol}:{direction}:{entry}"


@dataclass(frozen=True, slots=True)
class LiveTradingAuditEntry:
    timestamp: str
    operator_id: str
    operator: str
    role: str
    action: str
    state_before: LiveTradingState
    state_after: LiveTradingState
    reason: str
    account: str = ""
    broker: str = ""
    risk_configuration: dict[str, Any] = field(default_factory=dict)
    request_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return strip_secrets(
            {
                "timestamp": self.timestamp,
                "operator_id": self.operator_id,
                "operator": self.operator,
                "role": self.role,
                "action": self.action,
                "state_before": self.state_before,
                "state_after": self.state_after,
                "reason": self.reason,
                "account": self.account,
                "broker": self.broker,
                "risk_configuration": self.risk_configuration,
                "request_metadata": self.request_metadata,
            }
        )


@dataclass
class ExecutionRecord:
    timestamp: str
    symbol: str
    direction: str
    requested_entry: str | None
    actual_fill: str | None
    stop_loss: str | None
    take_profit: str | None
    volume: str | None
    ticket: str | None
    slippage: str | None
    risk_amount: str | None
    signal_id: str | None
    evidence: dict[str, Any]
    equity_before: str | None
    equity_after: str | None
    broker_confirmed: bool
    status: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return strip_secrets(asdict(self))


@dataclass
class LiveTradingController:
    """Process-local live-trading authorization. Default DISABLED."""

    state: LiveTradingState = "DISABLED"
    risk: LiveTradingRiskConfig = field(default_factory=LiveTradingRiskConfig)
    paused_symbols: set[str] = field(default_factory=set)
    audit: list[LiveTradingAuditEntry] = field(default_factory=list)
    fills: list[ExecutionRecord] = field(default_factory=list)
    rejections: list[dict[str, Any]] = field(default_factory=list)
    recent_signal_ids: dict[str, datetime] = field(default_factory=dict)
    recent_order_keys: dict[str, datetime] = field(default_factory=dict)
    consecutive_losses: int = 0
    last_loss_volume: Decimal | None = None
    last_rejection_reason: str = ""
    last_execution_at: str | None = None
    armed_at: str | None = None
    enabled_at: str | None = None
    kill_reason: str | None = None
    emergency_latched: bool = False
    recovered_from_enabled: bool = False
    paused_for_safety: bool = False
    _lock: RLock = field(default_factory=RLock, repr=False)

    def snapshot_state(self) -> LiveTradingState:
        with self._lock:
            return self.state

    def research_can_execute(self) -> bool:
        """True only after explicit ENABLE. Research never sets this."""
        return orders_may_submit(self.snapshot_state())

    def persist_payload(self) -> dict[str, Any]:
        with self._lock:
            return strip_secrets(
                {
                    "live_trading_state": self.state,
                    "live_trading_risk": self.risk.to_dict(),
                    "live_trading_armed_at": self.armed_at,
                    "live_trading_enabled_at": self.enabled_at,
                    "live_trading_kill_reason": self.kill_reason,
                    "live_trading_emergency_latched": self.emergency_latched,
                    "live_trading_consecutive_losses": self.consecutive_losses,
                    "live_trading_paused_symbols": sorted(self.paused_symbols),
                    "live_trading_audit": [e.to_dict() for e in self.audit[-50:]],
                }
            )

    def hydrate(
        self, payload: MappingLike | None, *, persist_recovery: bool = True
    ) -> LiveTradingState:
        data = payload if isinstance(payload, dict) else {}
        recovered = recover_after_restart(data.get("live_trading_state"))
        with self._lock:
            before = self.state
            self.state = recovered
            self.recovered_from_enabled = (
                normalize_state(data.get("live_trading_state")) == "ENABLED"
                and recovered == "PAUSED"
            )
            # Restart-PAUSE is safety recovery, not an operator pause.
            self.paused_for_safety = self.recovered_from_enabled
            persisted_killed = (
                normalize_state(data.get("live_trading_state")) == "KILLED"
            )
            if data.get("live_trading_risk"):
                self.risk = LiveTradingRiskConfig.from_dict(
                    data.get("live_trading_risk")
                )
            self.armed_at = (
                str(data.get("live_trading_armed_at") or "") or None
                if recovered == "ARMED"
                else None
            )
            self.enabled_at = None  # never assume still enabled after hydrate
            persisted_emergency = persisted_killed or bool(
                data.get("live_trading_emergency_latched")
            )
            self.emergency_latched = persisted_emergency and recovered in {
                "DISABLED",
                "KILLED",
            }
            self.kill_reason = (
                str(data.get("live_trading_kill_reason") or "") or None
                if self.emergency_latched
                else None
            )
            try:
                self.consecutive_losses = max(
                    0, int(data.get("live_trading_consecutive_losses") or 0)
                )
            except (TypeError, ValueError):
                self.consecutive_losses = 0
            paused = data.get("live_trading_paused_symbols") or []
            if isinstance(paused, list):
                self.paused_symbols = {str(s).upper() for s in paused if str(s).strip()}
            if recovered != before:
                self._record_locked(
                    operator=_system_operator("hydrate"),
                    action="restart_recovery",
                    before=before,
                    after=recovered,
                    reason="fail_closed_after_restart",
                )
        _ = persist_recovery
        return recovered

    def update_risk(
        self,
        operator: OperatorIdentity,
        patch: MappingLike,
        *,
        reason: str,
    ) -> LiveTradingRiskConfig:
        require_operator(operator)
        with self._lock:
            merged = {**self.risk.to_dict(), **(patch or {})}
            cfg = LiveTradingRiskConfig.from_dict(merged)
            old = self.risk.to_dict()
            self.risk = cfg
            self._record_locked(
                operator=operator,
                action="risk_config",
                before=self.state,
                after=self.state,
                reason=reason or "update_risk",
                extra={"old": old, "new": cfg.to_dict()},
            )
            return cfg

    def transition(
        self,
        operator: OperatorIdentity,
        target: LiveTradingState,
        *,
        confirmed: bool,
        reason: str,
        account: str = "",
        broker: str = "",
        metadata: MappingLike | None = None,
        now: datetime | None = None,
    ) -> LiveTradingState:
        require_operator(operator)
        wanted = normalize_state(target)
        if not confirmed:
            raise LiveTradingTransitionError("operator confirmation required")
        with self._lock:
            current = self.state
            allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
            if wanted not in allowed:
                raise LiveTradingTransitionError(
                    f"illegal_transition_{current}_to_{wanted}"
                )
            self.state = wanted
            moment = (now or utc_now()).isoformat()
            if wanted in {"ARMED", "ENABLED", "READY_FOR_REVIEW"}:
                self.emergency_latched = False
                self.kill_reason = None
            if wanted == "ARMED":
                self.armed_at = moment
            if wanted == "ENABLED":
                self.enabled_at = moment
                self.recovered_from_enabled = False
                self.paused_for_safety = False
            if wanted == "PAUSED":
                # Operator pause must not auto-resume after probes recover.
                self.recovered_from_enabled = False
                self.paused_for_safety = False
            if wanted == "DISABLED":
                self.armed_at = None
                self.enabled_at = None
                self.kill_reason = None
                self.emergency_latched = False
                self.paused_symbols.clear()
                self.recovered_from_enabled = False
                self.paused_for_safety = False
            if wanted == "KILLED":
                self.enabled_at = None
                self.kill_reason = reason or "kill_switch"
                self.emergency_latched = True
                self.recovered_from_enabled = False
                self.paused_for_safety = False
            self._record_locked(
                operator=operator,
                action=f"transition_{current}_{wanted}".lower(),
                before=current,
                after=wanted,
                reason=reason,
                account=account,
                broker=broker,
                extra=metadata or {},
                now=now,
            )
            return wanted

    def emergency_disable(
        self,
        operator: OperatorIdentity,
        *,
        reason: str,
        now: datetime | None = None,
    ) -> LiveTradingState:
        """ANY state → DISABLED. Blocks new orders. Does not close positions."""
        require_operator(operator)
        with self._lock:
            before = self.state
            self.state = "DISABLED"
            self.armed_at = None
            self.enabled_at = None
            self.kill_reason = reason or "emergency_stop"
            self.emergency_latched = True
            self.paused_symbols.clear()
            self.recovered_from_enabled = False
            self.paused_for_safety = False
            self._record_locked(
                operator=operator,
                action="emergency_stop",
                before=before,
                after="DISABLED",
                reason=self.kill_reason,
                now=now,
            )
            return self.state

    def safety_pause(
        self, *, reason: str, symbol: str | None = None
    ) -> LiveTradingState:
        with self._lock:
            if symbol:
                self.paused_symbols.add(str(symbol).strip().upper())
            if self.state != "ENABLED":
                return self.state
            before = self.state
            self.state = "PAUSED"
            self.paused_for_safety = True
            self._record_locked(
                operator=_system_operator("safety"),
                action="safety_pause",
                before=before,
                after="PAUSED",
                reason=reason,
            )
            return self.state

    def resume_after_safe_recovery(
        self, *, reason: str = "resume_after_safe_recovery"
    ) -> LiveTradingState:
        """PAUSED → ENABLED only after restart/safety pause. Not operator pause."""
        with self._lock:
            if self.state != "PAUSED":
                return self.state
            if not (self.recovered_from_enabled or self.paused_for_safety):
                return self.state
        return self.transition(
            _system_operator("safe_recovery"),
            "ENABLED",
            confirmed=True,
            reason=reason,
        )

    def remember_signal(self, signal_id: str, *, now: datetime | None = None) -> None:
        sid = str(signal_id or "").strip()
        if not sid:
            return
        moment = now or utc_now()
        with self._lock:
            self._purge_duplicates(moment)
            self.recent_signal_ids[sid] = moment

    def remember_order(self, key: str, *, now: datetime | None = None) -> None:
        token = str(key or "").strip()
        if not token:
            return
        moment = now or utc_now()
        with self._lock:
            self._purge_duplicates(moment)
            self.recent_order_keys[token] = moment

    def record_rejection(
        self, *, symbol: str, reason: str, payload: MappingLike | None = None
    ) -> None:
        with self._lock:
            self.last_rejection_reason = reason
            row = strip_secrets(
                {
                    "timestamp": utc_now().isoformat(),
                    "symbol": symbol,
                    "reason": reason,
                    "payload": payload or {},
                }
            )
            self.rejections.append(row)
            self.rejections = self.rejections[-200:]

    def record_fill(self, record: ExecutionRecord) -> None:
        with self._lock:
            if not record.broker_confirmed:
                record.status = "UNCONFIRMED"
            self.fills.append(record)
            self.fills = self.fills[-200:]
            if record.broker_confirmed and record.status.upper() in {
                "FILLED",
                "PARTIAL",
            }:
                self.last_execution_at = record.timestamp
                self.remember_order(
                    f"{record.symbol}:{record.direction}:{record.requested_entry}"
                )
                if record.signal_id:
                    self.remember_signal(record.signal_id)

    def note_closed_trade(self, *, loss: bool, volume: Decimal | None) -> None:
        with self._lock:
            if loss:
                self.consecutive_losses += 1
                self.last_loss_volume = volume
            else:
                self.consecutive_losses = 0
                self.last_loss_volume = None

    def evaluate(
        self, req: LiveOrderRequest, *, apply_side_effects: bool = True
    ) -> LiveOrderDecision:
        with self._lock:
            self._purge_duplicates(utc_now())
            if str(req.symbol or "").strip().upper() in self.paused_symbols:
                blocked = LiveOrderDecision(
                    allowed=False,
                    reasons=("symbol_paused_stale_data",),
                    gates=(_gate("symbol_paused", False, "symbol_paused_stale_data"),),
                    pause_symbol=req.symbol,
                    block_code="symbol_paused_stale_data",
                )
                return blocked
            decision = evaluate_live_order(
                req,
                state=self.state,
                cfg=self.risk,
                recent_signal_ids=set(self.recent_signal_ids),
                recent_order_keys=set(self.recent_order_keys),
                last_loss_volume=self.last_loss_volume,
            )
            if apply_side_effects:
                if decision.pause_execution:
                    self.safety_pause(reason=decision.block_code or "safety_limit")
                if decision.pause_symbol:
                    self.paused_symbols.add(str(decision.pause_symbol).upper())
            return decision

    def counts_today(self) -> dict[str, int]:
        day = utc_now().date().isoformat()
        with self._lock:
            orders = [f for f in self.fills if str(f.timestamp).startswith(day)]
            filled = [
                f
                for f in orders
                if f.broker_confirmed and f.status.upper() in {"FILLED", "PARTIAL"}
            ]
            rejected = [
                r
                for r in self.rejections
                if str(r.get("timestamp") or "").startswith(day)
            ]
            blocked = [
                r
                for r in rejected
                if str(r.get("reason") or "").startswith(
                    (
                        "live_trading_",
                        "unauthorized",
                        "gateway",
                        "mt5",
                        "stale",
                        "invalid",
                    )
                )
                or True
            ]
            return {
                "orders_today": len(orders),
                "filled_orders": len(filled),
                "rejected_orders": len(rejected),
                "blocked_orders": len(blocked),
            }

    def _purge_duplicates(self, now: datetime) -> None:
        ttl = timedelta(seconds=int(self.risk.duplicate_ttl_seconds))
        self.recent_signal_ids = {
            k: v for k, v in self.recent_signal_ids.items() if now - v <= ttl
        }
        self.recent_order_keys = {
            k: v for k, v in self.recent_order_keys.items() if now - v <= ttl
        }

    def _record_locked(
        self,
        *,
        operator: OperatorIdentity,
        action: str,
        before: LiveTradingState,
        after: LiveTradingState,
        reason: str,
        account: str = "",
        broker: str = "",
        extra: MappingLike | None = None,
        now: datetime | None = None,
    ) -> None:
        entry = LiveTradingAuditEntry(
            timestamp=(now or utc_now()).isoformat(),
            operator_id=str(operator.user_id),
            operator=operator.display_name or str(operator.user_id),
            role=str(operator.role or ""),
            action=action,
            state_before=before,
            state_after=after,
            reason=reason,
            account=account,
            broker=broker,
            risk_configuration=self.risk.to_dict(),
            request_metadata=strip_secrets(extra or {}),
        )
        self.audit.append(entry)
        self.audit = self.audit[-200:]


def _system_operator(name: str) -> OperatorIdentity:
    return OperatorIdentity(
        user_id=UUID("00000000-0000-0000-0000-000000000073"),
        role="owner",
        display_name=f"system:{name}",
    )


_CONTROLLER: LiveTradingController | None = None
_CONTROLLER_LOCK = RLock()


def get_live_trading_controller() -> LiveTradingController:
    global _CONTROLLER
    with _CONTROLLER_LOCK:
        if _CONTROLLER is None:
            _CONTROLLER = LiveTradingController()
        return _CONTROLLER


def reset_live_trading_controller_for_tests() -> LiveTradingController:
    global _CONTROLLER
    with _CONTROLLER_LOCK:
        _CONTROLLER = LiveTradingController()
        return _CONTROLLER
