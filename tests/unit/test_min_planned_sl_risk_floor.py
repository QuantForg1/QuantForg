"""Owner planned initial-SL band ($1.50 exclusive .. $2.00) on the final volume.

Does not create a second Risk/OMS/PME path. Never sends orders.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.application.services.telegram_events import (
    SIGNAL_CONFIRMED,
    TRADE_OPENED,
    public_channel_notices,
)
from app.domain.entities.mt5_portfolio import AccountSnapshot, MT5Position
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.dynamic_sizing_v2 import (
    calculate_dynamic_lots_v2,
)
from app.domain.institutional_trading.ai_scalping.profiles.scalping_v1 import (
    _SCALP_RR,
    build_scalping_v1_config,
)
from app.domain.institutional_trading.config import (
    MAX_PLANNED_SL_RISK_USD,
    MAX_TOTAL_PLANNED_RISK_USD,
    MIN_PLANNED_RISK_USD,
    TARGET_PLANNED_RISK_USD,
)
from app.domain.institutional_trading.management.class_policy import (
    SCALP_BREAK_EVEN_AT_R,
)
from app.domain.institutional_trading.operations.min_lot_feasibility import (
    CODE_MIN_LOT_EXCEEDS_RISK_BAND,
    CODE_MIN_PLANNED_RISK_NOT_REACHED,
    CODE_NEXT_VOLUME_STEP_EXCEEDS_MAX_RISK,
    CODE_REMAINING_PORTFOLIO_RISK_EXCEEDED,
    classify_private_no_fill_reason,
    lot_dollar_risk,
    normalize_lots_against_broker,
    planned_sl_risk_usd,
)
from app.domain.institutional_trading.owner_live_limits import OWNER_MAX_LOT

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_ROOT = Path(__file__).resolve().parents[2]
_FX_CS = Decimal("100000")
_FX_STOP = Decimal("0.0025")  # 0.01=$2.50, 0.02=$5.00, 0.03=$7.50
_GOLD_CS = Decimal("100")
_MIN = Decimal("0.01")
_STEP = Decimal("0.01")
_MAX = Decimal("10")
_EQUITY = Decimal("2000")


def _account(equity: Decimal = _EQUITY) -> AccountSnapshot:
    return AccountSnapshot(
        login=1,
        balance=equity,
        equity=equity,
        margin=Decimal("0"),
        free_margin=equity,
        margin_level=Decimal("0"),
        profit=Decimal("0"),
        leverage=500,
    )


def _fx_engine(**overrides: object) -> RiskEngine:
    kwargs: dict[str, object] = {
        "min_lot": _MIN,
        "lot_step": _STEP,
        "max_lot": _MAX,
        "contract_size": _FX_CS,
        "max_open_positions": 10,
        "max_symbol_exposure_pct": Decimal("200"),
        "max_asset_class_exposure_pct": Decimal("200"),
        "max_total_exposure_pct": Decimal("500"),
        "max_correlated_exposure_pct": Decimal("200"),
        "enforce_session": False,
        "enforce_spread": False,
        "enforce_atr": False,
        "min_planned_risk_usd": MIN_PLANNED_RISK_USD,
        "target_risk_per_trade_usd": TARGET_PLANNED_RISK_USD,
        "max_planned_sl_risk_usd": MAX_PLANNED_SL_RISK_USD,
        "max_total_planned_risk_usd": MAX_TOTAL_PLANNED_RISK_USD,
    }
    kwargs.update(overrides)
    return RiskEngine(config=RiskEngineConfig(**kwargs))  # type: ignore[arg-type]


def _fx_norm(**overrides: object):
    base: dict[str, object] = {
        "calculated_lot": Decimal("0.01"),
        "min_lot": _MIN,
        "lot_step": _STEP,
        "max_lot": _MAX,
        "equity": _EQUITY,
        "stop_distance": _FX_STOP,
        "contract_size": _FX_CS,
        "risk_budget": TARGET_PLANNED_RISK_USD,
        "remaining_portfolio_risk": MAX_TOTAL_PLANNED_RISK_USD,
    }
    base.update(overrides)
    return normalize_lots_against_broker(**base)  # type: ignore[arg-type]


def _gold_norm(*, stop: Decimal, **overrides: object):
    base: dict[str, object] = {
        "calculated_lot": Decimal("0.01"),
        "min_lot": _MIN,
        "lot_step": _STEP,
        "max_lot": _MAX,
        "equity": _EQUITY,
        "stop_distance": stop,
        "contract_size": _GOLD_CS,
        "risk_budget": TARGET_PLANNED_RISK_USD,
        "remaining_portfolio_risk": MAX_TOTAL_PLANNED_RISK_USD,
    }
    base.update(overrides)
    return normalize_lots_against_broker(**base)  # type: ignore[arg-type]


def _public_fields(*, opportunity: str, ticket: int | None) -> dict[str, object]:
    fields: dict[str, object] = {
        "symbol": "XAUUSD",
        "direction": "BUY",
        "opportunity": opportunity,
        "entry": "2650.50",
        "stop_loss": "2645.00",
        "take_profit": "2665.00",
    }
    if ticket is not None:
        fields["ticket"] = ticket
    return fields


def _qf_pos(
    *,
    ticket: int,
    symbol: str = "XAUUSD",
    volume: Decimal = Decimal("0.01"),
    entry: Decimal = Decimal("2300"),
    initial_stop: Decimal = Decimal("2293"),
    current_sl: Decimal | None = None,
) -> MT5Position:
    return MT5Position(
        ticket=ticket,
        symbol=symbol,
        side="buy",
        volume=volume,
        open_price=entry,
        current_price=entry,
        stop_loss=current_sl if current_sl is not None else initial_stop,
        take_profit=entry + Decimal("14"),
        profit=Decimal("0"),
        magic=260720,
        comment="ite:v1",
        initial_stop=initial_stop,
        initial_volume=volume,
    )


def test_tight_gold_stop_does_not_trade_when_cannot_step() -> None:
    # $0.50 at 0.01 is below the floor; owner max lot forbids stepping to 0.04.
    out = _gold_norm(stop=Decimal("0.50"), max_lot=OWNER_MAX_LOT)
    assert out.approved is False
    assert out.normalized_lot == Decimal("0")
    assert out.estimated_risk_amount == Decimal("0.50")
    assert out.block_reason == CODE_MIN_PLANNED_RISK_NOT_REACHED


def test_owner_band_accepts_1_51_at_min_lot() -> None:
    out = _gold_norm(stop=Decimal("1.51"), max_lot=OWNER_MAX_LOT)
    assert out.approved is True
    assert out.normalized_lot == Decimal("0.01")
    assert out.estimated_risk_amount == Decimal("1.51")
    assert out.estimated_risk_amount > MIN_PLANNED_RISK_USD
    assert out.estimated_risk_amount <= MAX_PLANNED_SL_RISK_USD


def test_exactly_1_50_is_rejected_at_owner_max_lot() -> None:
    # 0.01 * 100 * 1.50 = $1.50 is not above the exclusive floor; no step-up.
    out = _gold_norm(stop=Decimal("1.50"), max_lot=OWNER_MAX_LOT)
    assert out.estimated_risk_amount == Decimal("1.50")
    assert out.approved is False
    assert out.block_reason == CODE_MIN_PLANNED_RISK_NOT_REACHED


def test_six_01_is_now_rejected() -> None:
    out = _gold_norm(stop=Decimal("6.01"), max_lot=OWNER_MAX_LOT)
    assert out.approved is False
    assert out.normalized_lot == Decimal("0")


def test_seven_dollars_is_now_rejected() -> None:
    out = _gold_norm(stop=Decimal("7.00"), max_lot=OWNER_MAX_LOT)
    assert out.approved is False
    assert out.block_reason == CODE_MIN_LOT_EXCEEDS_RISK_BAND


def test_1_99_is_accepted() -> None:
    out = _gold_norm(stop=Decimal("1.99"))
    assert out.approved is True
    assert out.normalized_lot == Decimal("0.01")
    assert out.estimated_risk_amount == Decimal("1.99")


def test_2_00_is_accepted_inclusive() -> None:
    out = _gold_norm(stop=Decimal("2.00"))
    assert out.approved is True
    assert out.estimated_risk_amount == Decimal("2.00")


def test_20_01_is_rejected() -> None:
    out = _gold_norm(stop=Decimal("20.01"))
    assert out.approved is False
    assert out.normalized_lot == Decimal("0")
    assert out.block_reason == CODE_MIN_LOT_EXCEEDS_RISK_BAND
    assert out.estimated_risk_amount == Decimal("20.01")


def test_volume_min_itself_above_20_is_rejected() -> None:
    out = _gold_norm(stop=Decimal("21.00"))
    assert out.approved is False
    assert out.block_reason == CODE_MIN_LOT_EXCEEDS_RISK_BAND


def test_next_volume_step_exceeding_2_is_rejected_not_rounded_up() -> None:
    # 0.01=$1.90 is in band; 0.02 would be $3.80 — reject, never round up.
    in_band = _gold_norm(stop=Decimal("1.90"), calculated_lot=Decimal("0.01"))
    assert in_band.approved is True
    assert in_band.normalized_lot == Decimal("0.01")
    too_big = _gold_norm(stop=Decimal("1.90"), calculated_lot=Decimal("0.02"))
    assert too_big.approved is False
    assert too_big.normalized_lot == Decimal("0")
    assert too_big.block_reason == CODE_MIN_LOT_EXCEEDS_RISK_BAND


def test_remaining_portfolio_blocks_entry() -> None:
    # $1.90 at 0.01 but only $1.00 of portfolio risk remains.
    out = _gold_norm(stop=Decimal("1.90"), remaining_portfolio_risk=Decimal("1.00"))
    assert out.approved is False
    assert out.block_reason == CODE_REMAINING_PORTFOLIO_RISK_EXCEEDED


def test_open_initial_plus_proposed_above_2_is_rejected() -> None:
    engine = _fx_engine(contract_size=_GOLD_CS)
    open_leg = _qf_pos(
        ticket=880001,
        initial_stop=Decimal("2298.10"),  # 0.01 * 100 * 1.90 = $1.90
    )
    result = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="agg-2",
            symbol="XAUUSD",
            side="buy",
            requested_lots=Decimal("0.01"),
            stop_loss_distance=Decimal("1.90"),
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=Decimal("2300"),
            contract_size=_GOLD_CS,
        ),
        account=_account(),
        positions=[open_leg],
    )
    assert result.decision is RiskDecision.REJECT
    assert result.approved_lots == Decimal("0")
    assert CODE_REMAINING_PORTFOLIO_RISK_EXCEEDED in " ".join(result.reasons)


def test_be_trailing_does_not_reduce_initial_aggregate() -> None:
    engine = _fx_engine(contract_size=_GOLD_CS)
    trailed = _qf_pos(
        ticket=880002,
        initial_stop=Decimal("2293"),  # $7 initial
        current_sl=Decimal("2300"),  # BE — must not shrink book
    )
    assert engine.aggregate_planned_sl_risk([trailed]) == Decimal("7.00")
    result = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="be-book",
            symbol="XAUUSD",
            side="buy",
            requested_lots=Decimal("0.01"),
            stop_loss_distance=Decimal("24.00"),
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=Decimal("2300"),
            contract_size=_GOLD_CS,
        ),
        account=_account(),
        positions=[trailed],
    )
    assert result.decision is RiskDecision.REJECT
    assert result.approved_lots == Decimal("0")


def test_gold_uses_same_broker_aware_path() -> None:
    accept = _gold_norm(stop=Decimal("1.90"))
    assert accept.approved is True
    assert accept.normalized_lot == Decimal("0.01")
    assert accept.estimated_risk_amount == Decimal("1.90")
    reject = _gold_norm(stop=Decimal("2.01"))
    assert reject.approved is False
    assert reject.block_reason == CODE_MIN_LOT_EXCEEDS_RISK_BAND
    buy = planned_sl_risk_usd(
        volume=Decimal("0.01"),
        entry=Decimal("2300"),
        stop_loss=Decimal("2298.10"),
        contract_size=_GOLD_CS,
    )
    sell = planned_sl_risk_usd(
        volume=Decimal("0.01"),
        entry=Decimal("2300"),
        stop_loss=Decimal("2301.90"),
        contract_size=_GOLD_CS,
    )
    assert buy == sell == Decimal("1.90")


def test_no_universal_0_01_fallback_when_actual_below_floor() -> None:
    engine = _fx_engine(contract_size=_GOLD_CS, max_lot=OWNER_MAX_LOT)
    result = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="gold-below-floor",
            symbol="XAUUSD",
            side="buy",
            requested_lots=Decimal("0.01"),
            stop_loss_distance=Decimal("0.50"),
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=Decimal("2300"),
            contract_size=_GOLD_CS,
        ),
        account=_account(),
        positions=[],
    )
    assert result.decision is RiskDecision.REJECT
    assert result.approved_lots == Decimal("0")
    assert CODE_MIN_PLANNED_RISK_NOT_REACHED in " ".join(result.reasons)


def test_rejected_sizing_does_not_live_in_order_send_path() -> None:
    engine_src = (
        _ROOT / "app/application/services/institutional_execution_engine.py"
    ).read_text(encoding="utf-8")
    reject_idx = engine_src.find("if risk_reject:")
    send_idx = engine_src.find("gateway.mt5_order_send")
    assert reject_idx != -1
    assert send_idx != -1
    assert reject_idx < send_idx
    engine = _fx_engine(max_lot=Decimal("0.01"))
    result = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="no-send",
            symbol="EURUSD",
            side="sell",
            requested_lots=Decimal("0.01"),
            stop_loss_distance=_FX_STOP,
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=Decimal("1.08500"),
            contract_size=_FX_CS,
        ),
        account=_account(),
        positions=[],
    )
    assert result.decision is RiskDecision.REJECT
    assert result.approved_lots == Decimal("0")


def test_rejected_sizing_does_not_create_public_notice() -> None:
    notices = [
        {
            "event": TRADE_OPENED,
            "fields": _public_fields(opportunity="88", ticket=None),
        }
    ]
    assert public_channel_notices(notices) == []
    assert (
        classify_private_no_fill_reason(abort_reason=CODE_MIN_PLANNED_RISK_NOT_REACHED)
        == "MIN_LOT_EXCEEDS_RISK"
    )
    assert (
        classify_private_no_fill_reason(abort_reason=CODE_MIN_LOT_EXCEEDS_RISK_BAND)
        == "MIN_LOT_EXCEEDS_RISK"
    )
    assert (
        classify_private_no_fill_reason(
            abort_reason=CODE_NEXT_VOLUME_STEP_EXCEEDS_MAX_RISK
        )
        == "MIN_LOT_EXCEEDS_RISK"
    )
    assert (
        classify_private_no_fill_reason(
            abort_reason=CODE_REMAINING_PORTFOLIO_RISK_EXCEEDED
        )
        == "MIN_LOT_EXCEEDS_RISK"
    )


def test_p_above_70_with_real_ticket_still_public() -> None:
    public = public_channel_notices(
        [
            {
                "event": TRADE_OPENED,
                "fields": _public_fields(opportunity="91", ticket=881201),
            }
        ]
    )
    events = [item["event"] for item in public]
    assert SIGNAL_CONFIRMED in events
    assert TRADE_OPENED in events


def test_pyramid_winners_only_unchanged() -> None:
    assert DEFAULT_AI_SCALPING_CONFIG.pyramid_winners_only is True
    assert build_scalping_v1_config().pyramid_winners_only is True


def test_pme_be_and_trail_unchanged() -> None:
    cfg = build_scalping_v1_config()
    assert Decimal("0.80") == SCALP_BREAK_EVEN_AT_R
    assert Decimal("1.20") == cfg.partial_at_r
    assert Decimal("1.20") == cfg.trail_after_r
    assert Decimal("1.20") == _SCALP_RR


def test_v2_does_not_allow_below_min_planned() -> None:
    sized = calculate_dynamic_lots_v2(
        equity=_EQUITY,
        balance=_EQUITY,
        free_margin=_EQUITY,
        stop_distance=_FX_STOP,
        risk_pct=Decimal("1.0"),
        contract_size=_FX_CS,
        min_lot=_MIN,
        lot_step=_STEP,
        max_lot=Decimal("0.01"),
        tick_size=Decimal("0.00001"),
        tick_value=Decimal("1"),
        quality_score=85,
        confidence=85,
        opportunity_score=80,
        log=False,
    )
    assert sized.valid is False
    assert sized.final_lot == Decimal("0")


def test_tick_path_matches_contract_fallback_for_fx_step_up() -> None:
    tick = lot_dollar_risk(
        Decimal("0.03"),
        stop_distance=_FX_STOP,
        contract_size=_FX_CS,
        tick_size=Decimal("0.00001"),
        tick_value=Decimal("1"),
    )
    fallback = lot_dollar_risk(
        Decimal("0.03"),
        stop_distance=_FX_STOP,
        contract_size=_FX_CS,
    )
    assert tick == fallback == Decimal("7.50")


def test_constants_remain_single_source() -> None:
    assert Decimal("1.50") == MIN_PLANNED_RISK_USD
    assert Decimal("2.00") == TARGET_PLANNED_RISK_USD
    assert Decimal("2.00") == MAX_PLANNED_SL_RISK_USD
    assert Decimal("2.00") == MAX_TOTAL_PLANNED_RISK_USD
