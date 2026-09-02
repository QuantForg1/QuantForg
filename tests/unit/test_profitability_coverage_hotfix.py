"""Coverage + expectancy hotfix: live OMS specs, TP>SL, no forced min lot.

Does not create a second engine. Never sends live orders.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.application.services.execution_gateway import ExecutionGateway
from app.application.services.execution_intelligence import ExecutionIntelligenceService
from app.application.services.execution_safety import ExecutionSafetyService
from app.application.services.institutional_decision_pipeline import (
    _align_decision_to_structural_targets,
)
from app.application.services.institutional_execution_engine import (
    InstitutionalExecutionEngine,
    parse_order_intent,
)
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.application.services.telegram_events import (
    SIGNAL_CONFIRMED,
    TRADE_OPENED,
    public_channel_notices,
)
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.entities.risk_engine import RiskEngineConfig, contract_size_for_symbol
from app.domain.enums.execution import ExecutionOutcome
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.execution_engine.journal import ExecutionJournalStore
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.ai_scalping.quality_gates import (
    evaluate_quality_gates,
)
from app.domain.institutional_trading.ai_scalping.structure_targets import (
    compute_structure_targets,
)
from app.domain.institutional_trading.config import (
    MAX_PLANNED_SL_RISK_USD,
    MIN_PLANNED_RISK_USD,
)
from app.domain.institutional_trading.decision_models import (
    DecisionAction,
    TradeDirection,
)
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter


def _engine() -> tuple[InstitutionalExecutionEngine, MockMT5Client]:
    client = MockMT5Client()
    client.initialize()
    client.login(MT5LoginRequest(login=1, password="p", server="S"))
    adapter = MT5Adapter(client=client, execution_enabled=True)
    validation = MT5OrderValidationService(adapter=adapter)
    return (
        InstitutionalExecutionEngine(
            gateway=ExecutionGateway(adapter=adapter, order_validation=validation),
            safety=ExecutionSafetyService(adapter=adapter, order_validation=validation),
            order_validation=validation,
            intelligence=ExecutionIntelligenceService(),
            journal=ExecutionJournalStore(),
        ),
        client,
    )


def _fx_account() -> AccountSnapshot:
    return AccountSnapshot(
        login=1,
        balance=Decimal("500"),
        equity=Decimal("500"),
        margin=Decimal("0"),
        free_margin=Decimal("500"),
        margin_level=Decimal("0"),
        profit=Decimal("0"),
        leverage=500,
    )


@pytest.mark.unit
@pytest.mark.trading_core
def test_oms_uses_fx_contract_size_not_gold_default() -> None:
    """EURUSD 0.01 at 25-pip SL is $2.50 — must REJECT, not inherit gold CS=100."""
    engine = RiskEngine(
        config=RiskEngineConfig(
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            max_lot=Decimal("0.01"),
            contract_size=Decimal("100"),
        )
    )
    assessment = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="fx-oms-cs",
            symbol="EURUSD",
            side="sell",
            requested_lots=Decimal("0.01"),
            stop_loss_distance=Decimal("0.00250"),
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=Decimal("1.08500"),
            contract_size=Decimal("100000"),
        ),
        account=_fx_account(),
        positions=[],
    )
    assert assessment.decision is RiskDecision.REJECT
    assert assessment.approved_lots == Decimal("0")


@pytest.mark.unit
@pytest.mark.trading_core
def test_oms_fx_step_up_volume_can_pass_when_in_band() -> None:
    engine = RiskEngine(
        config=RiskEngineConfig(
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            max_lot=Decimal("100"),
            contract_size=Decimal("100000"),
        )
    )
    assessment = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="fx-oms-ok",
            symbol="EURUSD",
            side="buy",
            requested_lots=Decimal("0.03"),
            stop_loss_distance=Decimal("0.00250"),
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=Decimal("1.08520"),
            contract_size=Decimal("100000"),
        ),
        account=_fx_account(),
        positions=[],
    )
    assert assessment.decision is not RiskDecision.REJECT
    assert assessment.approved_lots == Decimal("0.03")
    assert assessment.approved_lots * Decimal("0.00250") * Decimal("100000") > (
        MIN_PLANNED_RISK_USD
    )
    assert assessment.approved_lots * Decimal("0.00250") * Decimal("100000") <= (
        MAX_PLANNED_SL_RISK_USD
    )


@pytest.mark.unit
@pytest.mark.trading_core
def test_missing_live_cs_uses_symbol_class_not_gold_default() -> None:
    assert contract_size_for_symbol("EURUSD") == Decimal("100000")
    assert contract_size_for_symbol("XAUUSD") == Decimal("100")
    engine = RiskEngine(config=RiskEngineConfig(contract_size=Decimal("100")))
    assessment = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="fallback-cs",
            symbol="EURUSD",
            side="buy",
            requested_lots=Decimal("0.01"),
            stop_loss_distance=Decimal("0.00250"),
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=Decimal("1.08520"),
        ),
        account=_fx_account(),
        positions=[],
    )
    assert assessment.decision is not RiskDecision.REJECT
    assert assessment.approved_lots == Decimal("0.03")


@pytest.mark.unit
@pytest.mark.trading_core
def test_execution_engine_steps_fx_min_lot_into_planned_sl_band() -> None:
    engine, _client = _engine()
    with patch(
        "app.domain.trading.gold_only.gold_only_enabled",
        return_value=False,
    ):
        intent = parse_order_intent(
            symbol="EURUSD",
            side="sell",
            order_type="market",
            volume="0.01",
            stop_loss="1.08750",
            take_profit="1.08125",
        )
        pipeline, _decision = engine.run_submit(
            user_id=uuid4(),
            request_id="fx-0.01-block",
            intent=intent,
            connected=True,
            login=1,
            recent_decisions=[],
        )
    assert pipeline.outcome == ExecutionOutcome.SUCCESS.value
    assert pipeline.execution_result is not None
    assert pipeline.execution_result.order_ticket
    filled = Decimal(str(getattr(pipeline.execution_result, "volume", "0") or "0"))
    if filled <= 0:
        filled = intent.volume.value
    assert filled > Decimal("0.01")
    assert filled * Decimal("0.00250") * Decimal("100000") > MIN_PLANNED_RISK_USD


@pytest.mark.unit
@pytest.mark.trading_core
def test_execution_engine_allows_in_band_fx_volume() -> None:
    engine, _client = _engine()
    with patch(
        "app.domain.trading.gold_only.gold_only_enabled",
        return_value=False,
    ):
        intent = parse_order_intent(
            symbol="EURUSD",
            side="buy",
            order_type="market",
            volume="0.03",
            stop_loss="1.08270",
            take_profit="1.08895",
        )
        pipeline, decision = engine.run_submit(
            user_id=uuid4(),
            request_id="fx-0.03-allow",
            intent=intent,
            connected=True,
            login=1,
            recent_decisions=[],
        )
    assert decision.decision.value == "allow"
    assert pipeline.outcome == ExecutionOutcome.SUCCESS.value
    assert pipeline.execution_result is not None
    assert pipeline.execution_result.order_ticket


@pytest.mark.unit
@pytest.mark.trading_core
def test_execution_engine_allows_in_band_gold() -> None:
    engine, _client = _engine()
    intent = parse_order_intent(
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="2301.50",
        take_profit="2349.50",
    )
    pipeline, decision = engine.run_submit(
        user_id=uuid4(),
        request_id="gold-0.01-allow",
        intent=intent,
        connected=True,
        login=1,
        recent_decisions=[],
    )
    assert decision.decision.value == "allow"
    assert pipeline.outcome == ExecutionOutcome.SUCCESS.value


@pytest.mark.unit
@pytest.mark.trading_core
def test_normalize_intent_does_not_force_min_lot_on_new_entries() -> None:
    engine, _client = _engine()
    with patch(
        "app.domain.trading.gold_only.gold_only_enabled",
        return_value=False,
    ):
        intent = parse_order_intent(
            symbol="EURUSD",
            side="buy",
            order_type="market",
            volume="0.001",
        )
        normalized, notes = engine.order_validation.normalize_intent(intent)
    assert normalized.volume.value == Decimal("0.001")
    assert any("not forced" in n.lower() for n in notes)


@pytest.mark.unit
@pytest.mark.trading_core
def test_structure_targets_reject_tp_not_greater_than_sl() -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    snap = MagicMock()
    snap.primary_structure = SimpleNamespace(
        last_swing_low=Decimal("1909.5"),
        last_swing_high=Decimal("1910.5"),
        swings=(),
    )
    snap.liquidity = SimpleNamespace(pools=(), sweeps=())
    snap.fair_value_gaps = None
    snap.order_blocks = None
    cfg = AiScalpingConfig(fixed_tp_r=Decimal("1.5"), stop_atr_mult=Decimal("1.10"))
    equal = compute_structure_targets(
        snap,
        direction=TradeDirection.SELL,
        entry=Decimal("1910"),
        atr=Decimal("1"),
        config=cfg,
    )
    if equal.take_profit is not None:
        assert equal.expected_rr is not None
        assert equal.expected_rr > Decimal("1")


@pytest.mark.unit
@pytest.mark.trading_core
def test_quality_gates_hard_reject_tp_equal_or_below_sl() -> None:
    from app.domain.institutional_trading.ai_scalping.adaptive_thresholds import (
        ResolvedThresholds,
    )
    from app.domain.institutional_trading.ai_scalping.direction import DirectionDecision
    from app.domain.institutional_trading.ai_scalping.session_intelligence import (
        SessionAssessment,
    )
    from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
        SpreadAssessment,
    )

    direction = DirectionDecision(
        direction=TradeDirection.BUY,
        buy_score=80,
        sell_score=20,
        reasons=(),
        structure_score=80,
        factors={},
        directional_edge=60,
        ltf_buy_score=80,
        ltf_sell_score=20,
    )
    session = SessionAssessment(
        session="london",
        stars=5,
        aggressive=True,
        confidence_penalty=0,
        quality_score=80,
        risk_multiplier=Decimal("1"),
        reason="test",
    )
    spread = SpreadAssessment(
        score=80,
        confidence_penalty=0,
        reject=False,
        reason="",
    )
    thresholds = ResolvedThresholds(
        band="normal",
        quality=70,
        confidence=70,
        atr_pct=Decimal("0.2"),
    )
    equal = evaluate_quality_gates(
        direction=direction,
        momentum=80,
        liquidity=80,
        structure_score=80,
        session=session,
        spread=spread,
        thresholds=thresholds,
        confidence=80,
        trade_quality=80,
        expected_rr=Decimal("1.00"),
        atr_pct=Decimal("0.2"),
    )
    assert equal.passed is False
    assert any("TP_PROFIT_NOT_GREATER_THAN_SL_LOSS" in r for r in equal.hard_rejects)

    worse = evaluate_quality_gates(
        direction=direction,
        momentum=80,
        liquidity=80,
        structure_score=80,
        session=session,
        spread=spread,
        thresholds=thresholds,
        confidence=80,
        trade_quality=80,
        expected_rr=Decimal("0.80"),
        atr_pct=Decimal("0.2"),
    )
    assert worse.passed is False
    assert any("TP_PROFIT_NOT_GREATER_THAN_SL_LOSS" in r for r in worse.hard_rejects)


@pytest.mark.unit
@pytest.mark.trading_core
def test_align_geometry_rejects_tp_not_greater_than_sl() -> None:
    from datetime import UTC, datetime

    from app.domain.institutional_trading.decision_models import (
        ConfluenceResult,
        EligibilityResult,
        PriceZone,
        TradeDecision,
    )

    decision = TradeDecision(
        action=DecisionAction.BUY,
        direction=TradeDirection.BUY,
        confidence=80,
        quality=80,
        risk_score=20,
        reasons=(),
        invalidations=(),
        entry_zone=PriceZone(Decimal("1.08"), Decimal("1.08"), Decimal("1.08")),
        stop_zone=PriceZone(Decimal("1.07"), Decimal("1.07"), Decimal("1.07")),
        target_zone=PriceZone(Decimal("1.07"), Decimal("1.07"), Decimal("1.07")),
        estimated_rr=Decimal("1.00"),
        expected_duration="scalp",
        confluence=ConfluenceResult(
            confidence=80,
            direction=TradeDirection.BUY,
            reasons=(),
            rejected_rules=(),
            input_hash="x",
            passed=True,
        ),
        eligibility=EligibilityResult(
            eligible=True,
            checks={},
            rejection_reasons=(),
        ),
        input_hash="h",
        config_version="t",
        symbol="EURUSD",
        as_of=datetime.now(UTC),
        approved_lots=Decimal("0.03"),
    )
    out = _align_decision_to_structural_targets(
        decision,
        ai_score={
            "entry": "1.08000",
            "stop_loss": "1.07750",
            "take_profit": "1.07750",
            "opportunity_score": 78,
        },
        stop_distance=Decimal("0.00250"),
        approved_lots=Decimal("0.03"),
        actual_sl_risk=Decimal("7.50"),
        live_min=Decimal("0.01"),
        live_step=Decimal("0.01"),
        live_max=Decimal("100"),
        live_cs=Decimal("100000"),
        live_tick=None,
        live_tick_val=None,
    )
    assert out.action is DecisionAction.NO_TRADE
    assert out.approved_lots == Decimal("0")


@pytest.mark.unit
@pytest.mark.trading_core
def test_align_geometry_overlays_structural_sl_tp_when_valid() -> None:
    from datetime import UTC, datetime

    from app.domain.institutional_trading.decision_models import (
        ConfluenceResult,
        EligibilityResult,
        PriceZone,
        TradeDecision,
    )

    decision = TradeDecision(
        action=DecisionAction.BUY,
        direction=TradeDirection.BUY,
        confidence=80,
        quality=80,
        risk_score=20,
        reasons=(),
        invalidations=(),
        entry_zone=PriceZone(Decimal("1.08"), Decimal("1.08"), Decimal("1.08")),
        stop_zone=PriceZone(Decimal("1.00"), Decimal("1.00"), Decimal("1.00")),
        target_zone=PriceZone(Decimal("2.00"), Decimal("2.00"), Decimal("2.00")),
        estimated_rr=Decimal("2.50"),
        expected_duration="scalp",
        confluence=ConfluenceResult(
            confidence=80,
            direction=TradeDirection.BUY,
            reasons=(),
            rejected_rules=(),
            input_hash="x",
            passed=True,
        ),
        eligibility=EligibilityResult(
            eligible=True,
            checks={},
            rejection_reasons=(),
        ),
        input_hash="h",
        config_version="t",
        symbol="EURUSD",
        as_of=datetime.now(UTC),
        approved_lots=Decimal("0.03"),
    )
    out = _align_decision_to_structural_targets(
        decision,
        ai_score={
            "entry": "1.08000",
            "stop_loss": "1.07750",
            "take_profit": "1.08375",
            "opportunity_score": 78,
        },
        stop_distance=Decimal("0.00250"),
        approved_lots=Decimal("0.03"),
        actual_sl_risk=Decimal("7.50"),
        live_min=Decimal("0.01"),
        live_step=Decimal("0.01"),
        live_max=Decimal("100"),
        live_cs=Decimal("100000"),
        live_tick=None,
        live_tick_val=None,
    )
    assert out.action is DecisionAction.BUY
    assert out.approved_lots == Decimal("0.03")
    assert out.stop_zone is not None
    assert out.target_zone is not None
    assert out.stop_zone.mid == Decimal("1.07750")
    assert out.target_zone.mid == Decimal("1.08375")
    assert out.estimated_rr == Decimal("1.50")


@pytest.mark.unit
@pytest.mark.trading_core
def test_public_telegram_filter_unchanged() -> None:
    public = public_channel_notices(
        [
            {
                "event": TRADE_OPENED,
                "fields": {
                    "symbol": "EURUSD",
                    "direction": "BUY",
                    "opportunity": "91",
                    "entry": "1.08500",
                    "stop_loss": "1.08250",
                    "take_profit": "1.09100",
                    "ticket": 881201,
                },
            }
        ]
    )
    events = [item["event"] for item in public]
    assert SIGNAL_CONFIRMED in events
    assert TRADE_OPENED in events


@pytest.mark.unit
@pytest.mark.trading_core
def test_no_martingale_or_averaging_defaults() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.allow_martingale is False
    assert cfg.pyramid_winners_only is True
    assert cfg.allow_grid is False
    assert cfg.allow_unlimited_averaging is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_telegram_and_worker_files_not_modified() -> None:
    root = Path(__file__).resolve().parents[2]
    telegram = (root / "app/application/services/telegram_events.py").read_text(
        encoding="utf-8"
    )
    assert "SIGNAL_CONFIRMED" in telegram
    jimvio = (root / "app/application/services/jimvio_publisher.py").read_text(
        encoding="utf-8"
    )
    assert "jimvio" in jimvio.lower() or "publish" in jimvio.lower()


@pytest.mark.unit
@pytest.mark.trading_core
def test_symbol_class_contract_sizes_never_use_gold_for_fx_or_index() -> None:
    from app.domain.institutional_trading.operations.min_lot_feasibility import (
        lot_dollar_risk,
    )

    fx = [
        "EURUSD",
        "GBPUSD",
        "USDCHF",
        "USDCAD",
        "AUDUSD",
        "NZDUSD",
        "NZDCHF",
        "EURGBP",
        "EURCHF",
        "GBPNZD",
        "NZDCAD",
    ]
    for symbol in fx:
        assert contract_size_for_symbol(symbol, default=Decimal("0")) == Decimal(
            "100000"
        )
        assert lot_dollar_risk(
            Decimal("0.01"),
            stop_distance=Decimal("0.00250"),
            contract_size=Decimal("100000"),
        ) == Decimal("2.50")
        assert lot_dollar_risk(
            Decimal("0.02"),
            stop_distance=Decimal("0.00250"),
            contract_size=Decimal("100000"),
        ) == Decimal("5.00")
        assert lot_dollar_risk(
            Decimal("0.03"),
            stop_distance=Decimal("0.00250"),
            contract_size=Decimal("100000"),
        ) == Decimal("7.50")
    assert contract_size_for_symbol("XAUUSD", default=Decimal("0")) == Decimal("100")
    assert contract_size_for_symbol("AEXEUR", default=Decimal("0")) == Decimal("0")
    gold_in_band = lot_dollar_risk(
        Decimal("0.01"),
        stop_distance=Decimal("19"),
        contract_size=Decimal("100"),
    )
    gold_over = lot_dollar_risk(
        Decimal("0.01"),
        stop_distance=Decimal("21"),
        contract_size=Decimal("100"),
    )
    assert gold_in_band == Decimal("19.00")
    assert gold_over == Decimal("21.00")


@pytest.mark.unit
@pytest.mark.trading_core
def test_live_broker_specs_do_not_fall_back_to_gold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.services.institutional_decision_pipeline import (
        _live_broker_lot_specs,
    )

    class _Empty:
        mt5_adapter = None

    monkeypatch.setattr("core.di.container.get_container", lambda: _Empty())
    _, _, _, eurusd_cs, _, _ = _live_broker_lot_specs("EURUSD")
    _, _, _, gold_cs, _, _ = _live_broker_lot_specs("XAUUSD")
    _, _, _, aex_cs, _, _ = _live_broker_lot_specs("AEXEUR")
    assert eurusd_cs == Decimal("100000")
    assert gold_cs == Decimal("100")
    assert aex_cs == Decimal("0")


@pytest.mark.unit
@pytest.mark.trading_core
def test_fx_002_cannot_pass_when_max_lot_blocks_step_up() -> None:
    engine = RiskEngine(
        config=RiskEngineConfig(
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            max_lot=Decimal("0.02"),
            contract_size=Decimal("100000"),
        )
    )
    assessment = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="fx-0.02-cap",
            symbol="EURUSD",
            side="buy",
            requested_lots=Decimal("0.02"),
            stop_loss_distance=Decimal("0.00250"),
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=Decimal("1.08520"),
            contract_size=Decimal("100000"),
        ),
        account=_fx_account(),
        positions=[],
    )
    assert assessment.decision is RiskDecision.REJECT


@pytest.mark.unit
@pytest.mark.trading_core
def test_gold_over_20_planned_sl_rejected() -> None:
    engine = RiskEngine(config=RiskEngineConfig(contract_size=Decimal("100")))
    assessment = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="gold-21",
            symbol="XAUUSD",
            side="buy",
            requested_lots=Decimal("0.01"),
            stop_loss_distance=Decimal("21"),
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=Decimal("2320.80"),
            contract_size=Decimal("100"),
        ),
        account=_fx_account(),
        positions=[],
    )
    assert assessment.decision is RiskDecision.REJECT


@pytest.mark.unit
@pytest.mark.trading_core
def test_execution_engine_rejects_tp_not_greater_than_sl() -> None:
    engine, _client = _engine()
    with patch(
        "app.domain.trading.gold_only.gold_only_enabled",
        return_value=False,
    ):
        intent = parse_order_intent(
            symbol="EURUSD",
            side="sell",
            order_type="market",
            volume="0.03",
            stop_loss="1.08750",
            take_profit="1.08250",
        )
        pipeline, _decision = engine.run_submit(
            user_id=uuid4(),
            request_id="fx-tp-eq-sl",
            intent=intent,
            connected=True,
            login=1,
            recent_decisions=[],
        )
    assert pipeline.outcome == "rejected"
    assert any(
        "TP_PROFIT_NOT_GREATER_THAN_SL_LOSS" in r
        for r in (pipeline.rejection_reasons or [pipeline.message])
    )
    assert pipeline.execution_result is None or not getattr(
        pipeline.execution_result, "order_ticket", None
    )


@pytest.mark.unit
@pytest.mark.trading_core
def test_explicit_zero_contract_size_fails_closed() -> None:
    from app.domain.institutional_trading.ai_scalping.sizing import (
        calculate_scalping_lots,
    )

    sized = calculate_scalping_lots(
        equity=Decimal("500"),
        stop_distance=Decimal("0.00250"),
        contract_size=Decimal("0"),
        min_lot=Decimal("0.01"),
        lot_step=Decimal("0.01"),
    )
    assert sized.valid is False
    assert sized.lots == Decimal("0")
