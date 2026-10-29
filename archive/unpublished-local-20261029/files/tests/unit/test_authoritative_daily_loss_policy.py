"""Authoritative XAUUSD daily-loss policy is 19.0% of day-start equity.

Does not send orders, lower Opportunity/sniper, bypass Safety, or change
max positions / winner-only scale-in / TAKE semantics.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.institutional_decision_pipeline import (
    oms_risk_config_from_ite,
    oms_risk_engine_from_ite,
    risk_config_from_ite,
)
from app.application.services.institutional_execution_engine import (
    InstitutionalExecutionEngine,
    parse_order_intent,
)
from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.domain.entities.mt5_order import OrderConstraints, OrderIntent
from app.domain.value_objects.mt5_order import LotSize, StopLoss
from app.domain.enums.order import OrderSide, OrderType
from app.domain.exceptions.base import ValidationError
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
    may_add_scalping_trade,
)
from app.domain.institutional_trading.config import (
    DEFAULT_ITE_CONFIG,
    MAX_DAILY_LOSS_PCT,
    MAX_PLANNED_RISK_PCT,
    MAX_PLANNED_SL_RISK_USD,
    MAX_TOTAL_PLANNED_RISK_USD,
    MIN_PLANNED_RISK_USD,
)
from app.domain.institutional_trading.owner_risk_policy import planned_risk_cap_usd
from app.domain.institutional_trading.execution.models import (
    BridgeAbortReason,
    OmsSubmitResult,
)
from app.domain.institutional_trading.operations.daily_loss_lock import (
    sync_utc_daily_loss_lock,
    utc_daily_loss_exceeded,
    utc_daily_loss_pct,
    utc_daily_loss_resets_at,
)
from app.domain.institutional_trading.operations.execution_chain_log import (
    build_execution_handoff,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    GoldExecutionFacts,
    evaluate_gold_execution_contract,
)
from app.domain.institutional_trading.phase_a.execution_reject import (
    BROKER_REJECTED,
    MT5_REJECTED,
    classify_downstream_execution_reject,
    should_count_execution_reject,
)
from app.domain.trading.gold_only import (
    CANONICAL_GOLD_BROKER_DISPLAY,
    DISABLED_AUTONOMOUS_SYMBOL,
    is_gold_symbol,
    require_xauusd,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _account(*, equity: str = "100") -> AccountSnapshot:
    eq = Decimal(equity)
    return AccountSnapshot(
        login=1,
        balance=eq,
        equity=eq,
        margin=Decimal("0"),
        free_margin=eq,
        margin_level=Decimal("0"),
        profit=Decimal("0"),
        leverage=1000,
    )


def _gold_check(*, request_id: str = "dl-policy") -> RiskCheckInput:
    return RiskCheckInput(
        user_id=uuid4(),
        request_id=request_id,
        symbol="XAUUSD_i",
        side="sell",
        requested_lots=Decimal("0.01"),
        stop_loss_distance=Decimal("2.0"),
        sizing_method=PositionSizingMethod.FIXED_LOT,
        entry_price=Decimal("2400"),
        spread=Decimal("0.20"),
        session_allowed=True,
    )


def _daily_reasons(
    engine: RiskEngine, daily_pnl: Decimal, equity: str = "100"
) -> list[str]:
    _state, reasons, _warnings = engine.evaluate_drawdown(
        _account(equity=equity),
        daily_pnl=daily_pnl,
    )
    return list(reasons)


def _daily_loss_oms(*, message: str) -> OmsSubmitResult:
    return OmsSubmitResult(
        outcome="rejected",
        message=message,
        retcode=None,
        order_ticket=None,
        deal_ticket=None,
        oms_status="rejected",
        gateway_status="order_check_only",
        raw={
            "order_send_reached": False,
            "order_check_reached": True,
            "oms_reached": True,
            "gateway_reached": True,
        },
    )


def test_1_configured_daily_loss_cap_is_exactly_19() -> None:
    assert MAX_DAILY_LOSS_PCT == Decimal("19.0")
    assert DEFAULT_ITE_CONFIG.max_daily_loss_pct == Decimal("19.0")
    assert RiskEngineConfig().max_daily_loss_pct == Decimal("19.0")
    assert RiskEngineConfig().max_daily_loss_pct == MAX_DAILY_LOSS_PCT
    assert oms_risk_config_from_ite().max_daily_loss_pct == MAX_DAILY_LOSS_PCT
    assert risk_config_from_ite(DEFAULT_ITE_CONFIG).max_daily_loss_pct == MAX_DAILY_LOSS_PCT


def test_2_recorded_session_does_not_daily_loss_block() -> None:
    cap = MAX_DAILY_LOSS_PCT
    # equity already includes the realized loss. Day-start is 190.24.
    # Loss 25.11 is 13.20% of day-start, under 19%.
    assert utc_daily_loss_pct(
        daily_pnl=Decimal("-25.11"),
        equity=Decimal("165.13"),
        balance=Decimal("165.13"),
    ) == Decimal("13.20")
    assert not utc_daily_loss_exceeded(
        daily_pnl=Decimal("-25.11"),
        equity=Decimal("165.13"),
        balance=Decimal("165.13"),
        max_daily_loss_pct=cap,
    )
    ite = RiskEngine(config=risk_config_from_ite(DEFAULT_ITE_CONFIG))
    oms = oms_risk_engine_from_ite(DEFAULT_ITE_CONFIG)
    for engine in (ite, oms, RiskEngine()):
        reasons = _daily_reasons(
            engine, Decimal("-25.11"), equity="165.13"
        )
        assert not any("daily loss" in r.lower() for r in reasons)
        result = engine.evaluate(
            _gold_check(request_id="dl-15-21"),
            account=_account(equity="165.13"),
            positions=[],
            daily_pnl=Decimal("-25.11"),
        )
        daily_fail = [r for r in result.reasons if "daily loss" in r.lower()]
        assert daily_fail == []
        assert "exceeds 5%" not in " ".join(result.reasons)


def test_3_boundary_just_under_19_allowed() -> None:
    cap = MAX_DAILY_LOSS_PCT
    # Day-start 100, equity 81.01, realized loss 18.99 → 18.99%.
    assert not utc_daily_loss_exceeded(
        daily_pnl=Decimal("-18.99"),
        equity=Decimal("81.01"),
        balance=Decimal("81.01"),
        max_daily_loss_pct=cap,
    )
    reasons = _daily_reasons(RiskEngine(), Decimal("-18.99"), equity="81.01")
    assert not any("daily loss" in r.lower() for r in reasons)


def test_4_boundary_exact_19_allowed() -> None:
    cap = MAX_DAILY_LOSS_PCT
    # Day-start 100, equity 81, realized loss 19 → exactly 19%.
    assert not utc_daily_loss_exceeded(
        daily_pnl=Decimal("-19.00"),
        equity=Decimal("81.00"),
        balance=Decimal("81.00"),
        max_daily_loss_pct=cap,
    )
    reasons = _daily_reasons(RiskEngine(), Decimal("-19.00"), equity="81.00")
    assert not any("daily loss" in r.lower() for r in reasons)


def test_5_boundary_19_01_daily_loss_block() -> None:
    cap = MAX_DAILY_LOSS_PCT
    assert utc_daily_loss_exceeded(
        daily_pnl=Decimal("-19.01"),
        equity=Decimal("80.99"),
        balance=Decimal("80.99"),
        max_daily_loss_pct=cap,
    )
    engine = RiskEngine()
    reasons = _daily_reasons(engine, Decimal("-19.01"), equity="80.99")
    assert any("daily loss" in r.lower() for r in reasons)
    assert any("19.0" in r for r in reasons)
    result = engine.evaluate(
        _gold_check(request_id="dl-19-01"),
        account=_account(equity="80.99"),
        positions=[],
        daily_pnl=Decimal("-19.01"),
    )
    assert result.decision is RiskDecision.REJECT
    assert any("daily loss" in r.lower() for r in result.reasons)
    assert "exceeds 5%" not in " ".join(result.reasons)


def test_6_oms_uses_authoritative_19() -> None:
    cfg = oms_risk_config_from_ite(DEFAULT_ITE_CONFIG)
    assert cfg.max_daily_loss_pct == Decimal("19.0")
    engine = oms_risk_engine_from_ite()
    assert engine.config.max_daily_loss_pct == MAX_DAILY_LOSS_PCT
    factory = InstitutionalExecutionEngine.__dataclass_fields__["risk_engine"].default_factory
    assert factory is not None
    oms_engine = factory()
    assert oms_engine.config.max_daily_loss_pct == MAX_DAILY_LOSS_PCT


def test_7_no_independent_5_percent_daily_loss_default() -> None:
    import inspect

    src = inspect.getsource(RiskEngineConfig)
    assert "MAX_DAILY_LOSS_PCT" in src
    assert 'max_daily_loss_pct: Decimal = Decimal("5")' not in src
    assert RiskEngineConfig().max_daily_loss_pct != Decimal("5")
    assert oms_risk_config_from_ite().max_daily_loss_pct != Decimal("5")
    assert risk_config_from_ite(DEFAULT_ITE_CONFIG).max_daily_loss_pct != Decimal("5")


def test_8_risk_and_oms_agree_on_daily_loss_decision() -> None:
    ite = RiskEngine(config=risk_config_from_ite(DEFAULT_ITE_CONFIG))
    oms = oms_risk_engine_from_ite(DEFAULT_ITE_CONFIG)
    cases = (
        (Decimal("-25.11"), "165.13", False),
        (Decimal("-18.99"), "81.01", False),
        (Decimal("-19.00"), "81.00", False),
        (Decimal("-19.01"), "80.99", True),
    )
    for pnl, equity, blocked in cases:
        ite_hit = any(
            "daily loss" in r.lower() for r in _daily_reasons(ite, pnl, equity=equity)
        )
        oms_hit = any(
            "daily loss" in r.lower() for r in _daily_reasons(oms, pnl, equity=equity)
        )
        assert ite_hit is blocked
        assert oms_hit is blocked
        assert ite_hit is oms_hit
        assert ite.config.max_daily_loss_pct == oms.config.max_daily_loss_pct


def test_9_daily_loss_application_reject_does_not_increment_burst() -> None:
    oms = _daily_loss_oms(message="daily loss 15.21% exceeds 40.0%")
    assert should_count_execution_reject(
        oms,
        abort_reason=BridgeAbortReason.OMS_FAILURE,
        oms_submit_called=True,
    ) is False
    assert classify_downstream_execution_reject(oms) is None


def test_10_order_check_only_daily_loss_is_not_broker_mt5_reject() -> None:
    legacy = _daily_loss_oms(message="daily loss 15.21% exceeds 5%")
    assert should_count_execution_reject(
        legacy,
        abort_reason=BridgeAbortReason.OMS_FAILURE,
        oms_submit_called=True,
    ) is False
    assert classify_downstream_execution_reject(legacy) is None
    assert legacy.gateway_status == "order_check_only"
    assert legacy.retcode is None
    assert legacy.order_ticket is None


def test_11_genuine_mt5_order_send_reject_does_increment() -> None:
    genuine = OmsSubmitResult(
        outcome="rejected",
        message="TRADE_RETCODE_INVALID_STOPS",
        retcode=10016,
        order_ticket=None,
        deal_ticket=None,
        oms_status="rejected",
        gateway_status="order_send",
        raw={"order_send_reached": True, "oms_reached": True, "gateway_reached": True},
    )
    assert should_count_execution_reject(
        genuine,
        abort_reason=BridgeAbortReason.MT5_REJECTION,
        oms_submit_called=True,
    ) is True
    stage = classify_downstream_execution_reject(
        genuine, abort_reason="MT5_REJECTION"
    )
    assert stage in {MT5_REJECTED, BROKER_REJECTED}


def test_12_utc_day_reset_unchanged() -> None:
    resets = utc_daily_loss_resets_at(datetime(2026, 8, 27, 14, 0, tzinfo=UTC))
    assert resets.startswith("2026-08-28T00:00:00")


def test_13_untrusted_history_fail_closed_unchanged() -> None:
    plane = SimpleNamespace(
        daily_loss_exceeded=True,
        flag_daily_loss=lambda now=None: None,
        clear_daily_loss=lambda **k: False,
    )
    out = sync_utc_daily_loss_lock(
        plane,
        daily_pnl=Decimal("0"),
        equity=Decimal("165.13"),
        balance=Decimal("165.13"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        trusted=False,
    )
    assert out["daily_loss_exceeded"] is True
    assert out["source"] == "unavailable"
    assert out["daily_loss_lock"] == "UNKNOWN"
    assert plane.daily_loss_exceeded is True


def test_14_kill_switch_outranks_daily_loss() -> None:
    out = evaluate_gold_execution_contract(
        GoldExecutionFacts(
            symbol="XAUUSD_I",
            direction="SELL",
            action="SELL",
            market_open=True,
            tradable=True,
            candles_ok=True,
            bid=Decimal("2400.10"),
            ask=Decimal("2400.30"),
            quote_age_seconds=1.0,
            spread=Decimal("0.20"),
            structure_score=70,
            momentum_score=65,
            quality=80,
            confidence=75,
            pa_confluence=55,
            risk_reward=Decimal("1.20"),
            market_regime="TREND",
            volatility_ok=True,
            session_quality_ok=True,
            safety_allowed=True,
            kill_switch=True,
            execution_enabled=True,
            auto_running=True,
            account_leverage=Decimal("2000"),
            risk_eligible=False,
            risk_reasons=("daily loss 40.01% exceeds 40.0%",),
            approved_lots=Decimal("0"),
            gold_only=True,
            opportunity_score=80,
            opportunity_threshold=70,
            oms_orders_allowed=True,
            gateway_connected=True,
            broker_connected=True,
            optimizer_state="EXECUTE_NOW",
        )
    )
    assert out.may_submit_oms is False
    assert out.blocking_stage == "SAFETY"
    assert "kill" in (out.fault_reason or "").lower()


def test_15_max_positions_unchanged() -> None:
    assert DEFAULT_AI_SCALPING_CONFIG.max_positions_per_symbol == 2
    assert oms_risk_config_from_ite().max_open_positions == 5
    assert RiskEngineConfig().max_open_positions == 5


def test_16_winner_only_scale_in_unchanged() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.pyramid_winners_only is True
    assert cfg.allow_martingale is False
    winner = may_add_scalping_trade(
        open_positions=1,
        max_open=2,
        new_confidence=90,
        best_open_confidence=80,
        new_direction="SELL",
        open_directions=("SELL",),
        open_profits=(Decimal("12.5"),),
        require_unrealized_profit=True,
        require_improvement=True,
        min_confidence_delta=5,
    )
    assert winner.allow is True
    loser = may_add_scalping_trade(
        open_positions=1,
        max_open=2,
        new_confidence=90,
        best_open_confidence=80,
        new_direction="SELL",
        open_directions=("SELL",),
        open_profits=(Decimal("-4.0"),),
        require_unrealized_profit=True,
        require_improvement=True,
        min_confidence_delta=5,
    )
    assert loser.allow is False


def test_17_take_is_not_executed() -> None:
    handoff = build_execution_handoff(take=True, forwarded_to_oms=False)
    assert handoff["execution_confirmed"] is False
    assert handoff["oms_entered"] is False


def test_18_real_ticket_required_for_executed() -> None:
    no_ticket = build_execution_handoff(
        take=True, forwarded_to_oms=True, mt5_ticket=None
    )
    assert no_ticket["execution_confirmed"] is False
    with_ticket = build_execution_handoff(
        take=True, forwarded_to_oms=True, mt5_ticket=424242
    )
    assert with_ticket["execution_confirmed"] is True


def test_19_xauusd_i_is_only_executable_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )
    assert CANONICAL_GOLD_BROKER_DISPLAY == "XAUUSD_i"
    assert is_gold_symbol("XAUUSD_i")
    assert require_xauusd("XAUUSD_i")
    with pytest.raises(ValidationError) as exc:
        parse_order_intent(
            symbol="EURUSD", side="buy", order_type="market", volume="0.01"
        )
    assert exc.value.code == DISABLED_AUTONOMOUS_SYMBOL
    intent = parse_order_intent(
        symbol="XAUUSD_i", side="sell", order_type="market", volume="0.01"
    )
    assert is_gold_symbol(str(intent.symbol))


def test_21_nine_percent_of_equity_is_the_per_entry_cap() -> None:
    assert MAX_PLANNED_RISK_PCT == Decimal("9.0")
    assert MIN_PLANNED_RISK_USD == Decimal("0")
    assert MAX_PLANNED_SL_RISK_USD == Decimal("0")
    assert MAX_TOTAL_PLANNED_RISK_USD == Decimal("0")
    assert planned_risk_cap_usd(Decimal("1000")) == Decimal("90.00")
    engine = RiskEngine()
    # 0.45 lots * $2 stop * 100 oz = $90 = exactly 9% of $1000.
    exact = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="risk-exact-9",
            symbol="XAUUSD_i",
            side="sell",
            requested_lots=Decimal("0.45"),
            stop_loss_distance=Decimal("2.0"),
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=Decimal("2400"),
            spread=Decimal("0.20"),
            session_allowed=True,
        ),
        account=_account(equity="1000"),
        positions=[],
        daily_pnl=Decimal("0"),
    )
    assert exact.decision is not RiskDecision.REJECT
    assert exact.approved_lots == Decimal("0.45")
    # 0.46 lots * $2 * 100 = $92, above 9%.
    over = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="risk-over-9",
            symbol="XAUUSD_i",
            side="sell",
            requested_lots=Decimal("0.46"),
            stop_loss_distance=Decimal("2.0"),
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=Decimal("2400"),
            spread=Decimal("0.20"),
            session_allowed=True,
        ),
        account=_account(equity="1000"),
        positions=[],
        daily_pnl=Decimal("0"),
    )
    assert over.decision is RiskDecision.REJECT
    assert over.approved_lots == Decimal("0")


def test_22_weekly_monthly_and_peak_drawdown_do_not_halt() -> None:
    engine = RiskEngine()
    _state, reasons, warnings = engine.evaluate_drawdown(
        _account(equity="70"),
        peak_equity=Decimal("100"),
        daily_pnl=Decimal("0"),
        weekly_pnl=Decimal("-40"),
        monthly_pnl=Decimal("-40"),
    )
    assert reasons == []
    assert _state.equity_protected is True
    assert any("weekly loss" in w for w in warnings)
    assert any("monthly loss" in w for w in warnings)
    assert any("max drawdown" in w for w in warnings)


def test_23_missing_stop_is_rejected_before_a_replacement_is_invented() -> None:
    engine = RiskEngine()
    missing = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="missing-sl",
            symbol="XAUUSD_i",
            side="buy",
            requested_lots=Decimal("0.01"),
            stop_loss_distance=None,
            sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
            entry_price=Decimal("2400"),
            spread=Decimal("0.20"),
            session_allowed=True,
        ),
        account=_account(equity="1000"),
        positions=[],
    )
    assert missing.decision is RiskDecision.REJECT
    assert missing.approved_lots == Decimal("0")
    assert any("STOP_LOSS_REQUIRED" in r for r in missing.reasons)
    assert all("0.001" not in r for r in missing.reasons)
    validation = MT5OrderValidationService(adapter=object())
    constraints = OrderConstraints(symbol="XAUUSD_i", contract_size=Decimal("100"))
    intent = OrderIntent(
        symbol="XAUUSD_i",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=LotSize.of("0.01"),
        price=Decimal("2400"),
        stop_loss=StopLoss.of("2405"),
    )
    ok, message = validation.validate_stops(intent, constraints, entry_price=Decimal("2400"))
    assert ok is False
    assert "below" in message.lower()
    close = OrderIntent(
        symbol="XAUUSD_i",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        volume=LotSize.of("0.01"),
        oms_kind="close",
        position=10,
    )
    close_ok, _close_msg = validation.validate_stops(
        close, constraints, entry_price=Decimal("2400")
    )
    assert close_ok is True


def test_20_suite_does_not_send_orders() -> None:
    engine = RiskEngine()
    assert not hasattr(engine, "order_send")
    assert not hasattr(engine, "run_submit")
    result = engine.evaluate(
        _gold_check(request_id="dl-no-send"),
        account=_account(equity="165.13"),
        positions=[],
        daily_pnl=Decimal("-25.11"),
    )
    assert getattr(result, "order_ticket", None) is None
    assert "ticket" not in result.to_dict()
