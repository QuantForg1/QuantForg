"""Production Micro Account Analyzer — independent of Institutional Mode.

Reads broker lot specs (live or desk fallback), evaluates target micro balances
against mathematically correct percentage-risk sizing, and never fakes lots,
bypasses broker minima, or mutates Institutional thresholds / OMS / Safety.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Any

from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.micro_account_mode import (
    DEFAULT_ATR_STOP_MULTIPLIER,
    DEFAULT_MICRO_ACCOUNT_PROFILE,
    DEFAULT_REFERENCE_ATR,
    SUPPORTED_BALANCES,
    dollar_risk_at_lots,
    equity_floor_for_risk,
    min_usable_risk_pct,
    stop_distance_from_atr,
)
from app.domain.trading.gold_only import GOLD_SYMBOL
from app.domain.trading.xauusd_specs import (
    CONTRACT_SIZE,
    TICK_SIZE,
    TICK_VALUE,
    VOLUME_MAX,
    VOLUME_MIN,
    VOLUME_STEP,
)

# Operator risk ladder for min-safe-balance tables.
RISK_LADDER_PCT: tuple[Decimal, ...] = (
    Decimal("0.25"),
    Decimal("0.50"),
    Decimal("0.75"),
    Decimal("1.00"),
    Decimal("1.50"),
    Decimal("2.00"),
)

# Nano / micro lot threshold for advisory “Micro account compatible” badge.
_MICRO_LOT_THRESHOLD = Decimal("0.001")


@dataclass(frozen=True, slots=True)
class BrokerLotSpecs:
    """Broker trading constraints used for sizing (never overridden)."""

    volume_min: Decimal
    volume_step: Decimal
    volume_max: Decimal
    contract_size: Decimal
    tick_size: Decimal
    tick_value: Decimal
    source: str  # live_broker | desk_fallback
    symbol: str = GOLD_SYMBOL

    @property
    def micro_account_compatible(self) -> bool:
        """True when broker min lot supports nano/micro (≤0.001). Advisory only."""
        return self.volume_min <= _MICRO_LOT_THRESHOLD

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "volume_min": str(self.volume_min),
            "volume_step": str(self.volume_step),
            "volume_max": str(self.volume_max),
            "contract_size": str(self.contract_size),
            "tick_size": str(self.tick_size),
            "tick_value": str(self.tick_value),
            "source": self.source,
            "micro_account_compatible": self.micro_account_compatible,
            "micro_compatible_label": (
                "Micro account compatible"
                if self.micro_account_compatible
                else "Standard min lot (not nano)"
            ),
        }


def desk_fallback_specs() -> BrokerLotSpecs:
    """Canonical QuantForg XAUUSD desk specs when live broker is unavailable."""
    return BrokerLotSpecs(
        volume_min=VOLUME_MIN,
        volume_step=VOLUME_STEP,
        volume_max=VOLUME_MAX,
        contract_size=CONTRACT_SIZE,
        tick_size=TICK_SIZE,
        tick_value=TICK_VALUE,
        source="desk_fallback",
        symbol=GOLD_SYMBOL,
    )


def broker_specs_from_mapping(
    raw: dict[str, Any], *, source: str = "live_broker"
) -> BrokerLotSpecs:
    """Parse gateway / MT5 symbol payload into BrokerLotSpecs."""

    def _d(key: str, default: Decimal) -> Decimal:
        val = raw.get(key)
        if val is None or val == "":
            return default
        try:
            d = Decimal(str(val))
            return d if d > 0 else default
        except Exception:  # noqa: BLE001
            return default

    volume_min = _d("volume_min", VOLUME_MIN)
    volume_step = _d("volume_step", VOLUME_STEP)
    volume_max = _d("volume_max", VOLUME_MAX)
    contract_size = _d("contract_size", CONTRACT_SIZE)
    tick_size = _d("tick_size", _d("point", TICK_SIZE))
    tick_value = _d("tick_value", Decimal("0"))
    if tick_value <= 0 and tick_size > 0:
        # Gold CFD identity: tick_value ≈ contract_size × tick_size
        tick_value = (contract_size * tick_size).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    return BrokerLotSpecs(
        volume_min=volume_min,
        volume_step=volume_step,
        volume_max=volume_max,
        contract_size=contract_size,
        tick_size=tick_size,
        tick_value=tick_value,
        source=source,
        symbol=str(raw.get("code") or raw.get("symbol") or GOLD_SYMBOL).upper(),
    )


def institutional_profile_dict() -> dict[str, Any]:
    """Frozen Institutional profile — never mutated by Micro Account Mode."""
    return {
        "profile_id": "INSTITUTIONAL",
        "frozen": True,
        "quality": DEFAULT_ITE_CONFIG.min_trade_quality_score,
        "confluence": DEFAULT_ITE_CONFIG.min_confluence_score,
        "risk_pct": str(DEFAULT_ITE_CONFIG.risk_per_trade_pct),
        "reject_below_min_lot": True,
        "never_upsize_below_min_lot": True,
        "config_version": DEFAULT_ITE_CONFIG.config_version,
        "modified_by_micro_mode": False,
    }


def micro_profile_dict(
    *,
    specs: BrokerLotSpecs | None = None,
) -> dict[str, Any]:
    profile = DEFAULT_MICRO_ACCOUNT_PROFILE
    s = specs or desk_fallback_specs()
    return {
        "profile_id": "MICRO_ACCOUNT_MODE",
        "frozen": False,
        "independent_of_institutional": True,
        "target_balances": [str(b) for b in SUPPORTED_BALANCES],
        "recommended_max_risk_pct": str(profile.recommended_max_risk_pct),
        "hard_max_risk_pct": str(profile.hard_max_risk_pct),
        "broker_min_lot": str(s.volume_min),
        "never_fake_lots": True,
        "never_bypass_broker_rules": True,
        "never_force_min_lot": True,
        "activates_live_execution": False,
        "notes": [
            "Advisory / sizing analyzer only — does not weaken Institutional Mode.",
            "Does not change Strategy, OMS, Safety, or Institutional risk policy.",
        ],
    }


def dollar_risk_with_specs(
    *,
    lots: Decimal,
    stop_distance: Decimal,
    specs: BrokerLotSpecs,
) -> Decimal:
    """Loss at stop using tick geometry when available, else contract_size path."""
    if specs.tick_size > 0 and specs.tick_value > 0:
        ticks = stop_distance / specs.tick_size
        return (lots * ticks * specs.tick_value).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    return dollar_risk_at_lots(
        lots=lots,
        stop_distance=stop_distance,
        contract_size=specs.contract_size,
    )


def calculate_lots(
    *,
    equity: Decimal,
    risk_pct: Decimal,
    stop_distance: Decimal,
    specs: BrokerLotSpecs,
) -> Decimal:
    """Percentage-risk lots ROUND_DOWN to lot_step — never upsize to min_lot."""
    if equity <= 0 or risk_pct <= 0 or stop_distance <= 0:
        return Decimal("0")
    budget = equity * (risk_pct / Decimal("100"))
    # Prefer tick geometry for consistency with dollar_risk_with_specs
    if specs.tick_size > 0 and specs.tick_value > 0:
        risk_per_lot = (stop_distance / specs.tick_size) * specs.tick_value
    else:
        risk_per_lot = stop_distance * specs.contract_size
    if risk_per_lot <= 0:
        return Decimal("0")
    raw = budget / risk_per_lot
    lots = raw.quantize(specs.volume_step, rounding=ROUND_DOWN)
    if lots < 0:
        return Decimal("0")
    if lots > specs.volume_max:
        lots = specs.volume_max.quantize(specs.volume_step, rounding=ROUND_DOWN)
    return lots


@dataclass(frozen=True, slots=True)
class MicroEligibilityResult:
    balance: Decimal
    risk_pct: Decimal
    atr: Decimal
    stop_distance: Decimal
    calculated_lots: Decimal
    max_loss: Decimal
    eligible: bool
    status: str  # Eligible | NOT ELIGIBLE
    reason: str
    recommended_risk_pct: Decimal | None
    estimated_lot_size: Decimal | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "balance": str(self.balance),
            "risk_pct": str(self.risk_pct),
            "atr": str(self.atr),
            "atr_stop": str(self.stop_distance),
            "calculated_lots": str(self.calculated_lots),
            "max_loss": str(self.max_loss),
            "eligible": self.eligible,
            "status": self.status,
            "reason": self.reason,
            "recommended_risk_pct": (
                str(self.recommended_risk_pct)
                if self.recommended_risk_pct is not None
                else None
            ),
            "estimated_lot_size": (
                str(self.estimated_lot_size)
                if self.estimated_lot_size is not None
                else None
            ),
        }


def recommend_risk_pct(
    *,
    equity: Decimal,
    stop_distance: Decimal,
    specs: BrokerLotSpecs,
    ladder: tuple[Decimal, ...] = RISK_LADDER_PCT,
) -> Decimal | None:
    """Smallest ladder risk % where calculated lots ≥ broker min_lot."""
    for pct in ladder:
        lots = calculate_lots(
            equity=equity,
            risk_pct=pct,
            stop_distance=stop_distance,
            specs=specs,
        )
        if lots >= specs.volume_min:
            return pct
    return None


def evaluate_eligibility(
    *,
    balance: Decimal,
    risk_pct: Decimal,
    atr: Decimal,
    specs: BrokerLotSpecs,
    atr_multiplier: Decimal = DEFAULT_ATR_STOP_MULTIPLIER,
) -> MicroEligibilityResult:
    """YES/NO eligibility for one balance × risk × ATR — no forced lots."""
    stop = stop_distance_from_atr(atr, multiplier=atr_multiplier)
    lots = calculate_lots(
        equity=balance,
        risk_pct=risk_pct,
        stop_distance=stop,
        specs=specs,
    )
    min_lot_loss = dollar_risk_with_specs(
        lots=specs.volume_min,
        stop_distance=stop,
        specs=specs,
    )
    required_pct = min_usable_risk_pct(equity=balance, dollar_risk=min_lot_loss)
    recommended = recommend_risk_pct(
        equity=balance, stop_distance=stop, specs=specs
    )

    if lots >= specs.volume_min:
        max_loss = dollar_risk_with_specs(
            lots=lots, stop_distance=stop, specs=specs
        )
        return MicroEligibilityResult(
            balance=balance,
            risk_pct=risk_pct,
            atr=atr,
            stop_distance=stop,
            calculated_lots=lots,
            max_loss=max_loss,
            eligible=True,
            status="Eligible",
            reason=(
                f"Calculated lots {lots} ≥ broker min_lot {specs.volume_min} "
                f"at {risk_pct}% risk; max loss ${max_loss}."
            ),
            recommended_risk_pct=recommended,
            estimated_lot_size=lots,
        )

    return MicroEligibilityResult(
        balance=balance,
        risk_pct=risk_pct,
        atr=atr,
        stop_distance=stop,
        calculated_lots=lots,
        max_loss=min_lot_loss,
        eligible=False,
        status="NOT ELIGIBLE",
        reason=(
            f"NOT ELIGIBLE: calculated lots {lots} < broker min_lot "
            f"{specs.volume_min}. Min-lot stop-loss is ${min_lot_loss} "
            f"({required_pct}% of ${balance}); selected risk {risk_pct}% "
            f"budget cannot fund a real lot without faking size or "
            f"bypassing broker rules."
        ),
        recommended_risk_pct=recommended,
        estimated_lot_size=None,
    )


def min_safe_balances_table(
    *,
    stop_distance: Decimal,
    specs: BrokerLotSpecs,
    ladder: tuple[Decimal, ...] = RISK_LADDER_PCT,
) -> list[dict[str, Any]]:
    """Minimum equity for each risk % given fixed broker min_lot."""
    min_loss = dollar_risk_with_specs(
        lots=specs.volume_min,
        stop_distance=stop_distance,
        specs=specs,
    )
    rows: list[dict[str, Any]] = []
    for pct in ladder:
        floor = equity_floor_for_risk(
            dollar_risk_at_min_lot=min_loss, risk_pct=pct
        )
        rows.append(
            {
                "risk_pct": str(pct),
                "min_safe_balance": str(floor),
                "dollar_risk_at_min_lot": str(min_loss),
                "broker_min_lot": str(specs.volume_min),
            }
        )
    return rows


def analyze_micro_account(
    *,
    balance: Decimal,
    risk_pct: Decimal,
    atr: Decimal = DEFAULT_REFERENCE_ATR,
    specs: BrokerLotSpecs | None = None,
    atr_multiplier: Decimal = DEFAULT_ATR_STOP_MULTIPLIER,
) -> dict[str, Any]:
    """Full analyzer payload for UI: Balance → Specs → Risk → ATR → Lots → Eligible."""
    broker = specs or desk_fallback_specs()
    stop = stop_distance_from_atr(atr, multiplier=atr_multiplier)
    result = evaluate_eligibility(
        balance=balance,
        risk_pct=risk_pct,
        atr=atr,
        specs=broker,
        atr_multiplier=atr_multiplier,
    )
    ladder_balances = [
        evaluate_eligibility(
            balance=eq,
            risk_pct=risk_pct,
            atr=atr,
            specs=broker,
            atr_multiplier=atr_multiplier,
        ).to_dict()
        for eq in SUPPORTED_BALANCES
    ]
    fifty = next(
        (r for r in ladder_balances if Decimal(str(r["balance"])) == Decimal("50")),
        None,
    )
    fifty_clear = None
    if fifty is not None and not fifty["eligible"]:
        fifty_clear = (
            f"$50 is NOT tradable on this broker for XAUUSD at ATR={atr} "
            f"(stop={stop}): {fifty['reason']}"
        )

    return {
        "schema_version": "1.0.0",
        "analyzer": "Micro Account Analyzer",
        "symbol": GOLD_SYMBOL,
        "institutional_mode_modified": False,
        "strategy_oms_safety_unchanged": True,
        "profiles": {
            "INSTITUTIONAL": institutional_profile_dict(),
            "MICRO_ACCOUNT_MODE": micro_profile_dict(specs=broker),
        },
        "balance": str(balance),
        "broker_specs": broker.to_dict(),
        "risk_pct": str(risk_pct),
        "atr": str(atr),
        "atr_stop": str(stop),
        "atr_stop_multiplier": str(atr_multiplier),
        "calculated_lots": str(result.calculated_lots),
        "eligible": result.eligible,
        "eligible_label": "YES" if result.eligible else "NO",
        "status": result.status,
        "reason": result.reason,
        "recommended_risk_pct": (
            str(result.recommended_risk_pct)
            if result.recommended_risk_pct is not None
            else None
        ),
        "estimated_lot_size": (
            str(result.estimated_lot_size)
            if result.estimated_lot_size is not None
            else None
        ),
        "maximum_loss": str(result.max_loss),
        "min_safe_balances_by_risk": min_safe_balances_table(
            stop_distance=stop, specs=broker
        ),
        "supported_balance_matrix": ladder_balances,
        "fifty_dollar_clear_statement": fifty_clear,
        "flow": [
            {"step": "Balance", "value": str(balance)},
            {
                "step": "Broker Specs",
                "value": (
                    f"min={broker.volume_min} step={broker.volume_step} "
                    f"cs={broker.contract_size} tick={broker.tick_size}/"
                    f"{broker.tick_value} ({broker.source})"
                ),
            },
            {"step": "Risk %", "value": str(risk_pct)},
            {"step": "ATR Stop", "value": str(stop)},
            {"step": "Calculated Lots", "value": str(result.calculated_lots)},
            {
                "step": "Eligible",
                "value": "YES" if result.eligible else "NO",
            },
            {"step": "Reason", "value": result.reason},
        ],
    }
