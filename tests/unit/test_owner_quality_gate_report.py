"""The live desk reports the owner quality floor and does not call it an OMS failure."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.application.services.institutional_decision_pipeline import (
    InstitutionalDecisionPipeline,
)
from app.application.services.strategy_diagnostics import owner_diagnostic_floor
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    ConfluenceResult,
    TradeDirection,
)
from app.domain.institutional_trading.executable_direction import quality_block_detail
from app.domain.institutional_trading.models import (
    MarketAnalysisSnapshot,
    NewsProtectionStatus,
    SessionFilterResult,
    TradeQualityScore,
    TrendSnapshot,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    evaluate_gold_execution_contract,
)
from app.domain.institutional_trading.phase_a.execution_reject import (
    first_blocking_gate_from_reasons,
)
from app.domain.institutional_trading.production_validation_mode.recorder import (
    ProductionValidationRecorder,
)
from app.domain.market_context.enums import MarketSession
from app.domain.market_structure.enums import TrendDirection
from tests.unit.test_autonomous_gold_execution import _ready

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

QUALITY = "OWNER_MIN_TRADE_QUALITY: trade quality 63 < 75"


def test_quality_block_detail_keeps_the_owner_gate_text() -> None:
    assert (
        quality_block_detail(
            executable_reason="AI quality gates rejected — NO_TRADE",
            reject_reason=QUALITY,
        )
        == QUALITY
    )
    assert (
        quality_block_detail(
            executable_reason="AI quality gates rejected — NO_TRADE",
            reject_reason=None,
        )
        == "AI quality gates rejected — NO_TRADE"
    )


def test_quality_reason_is_the_logged_first_gate() -> None:
    assert first_blocking_gate_from_reasons((QUALITY,)) == "OWNER_MIN_TRADE_QUALITY"
    assert (
        first_blocking_gate_from_reasons(("AI quality gates rejected — NO_TRADE",))
        == "RISK_REJECTED"
    )


def test_owner_diagnostic_floor_is_70_and_swing_default_stays_80() -> None:
    assert owner_diagnostic_floor() == 70
    assert DEFAULT_ITE_CONFIG.min_trade_quality_score == 80
    assert DEFAULT_ITE_CONFIG.min_confluence_score == 80


def test_new_validation_does_not_keep_a_prior_oms_fail() -> None:
    recorder = ProductionValidationRecorder()
    first = recorder.begin(symbol="XAUUSD")
    recorder.record_oms(
        response={"outcome": "rejected", "message": QUALITY},
        validation_id=first.validation_id,
    )
    assert recorder.dashboard()["oms_status"] == "FAIL"
    recorder.begin(symbol="XAUUSD")
    dash = recorder.dashboard()
    assert dash["oms_status"] == "NOT_REACHED"
    assert dash["mt5_status"] == "NOT_REACHED"
    assert dash["broker_status"] == "NOT_REACHED"


def test_quality_withheld_side_is_not_an_oms_failure() -> None:
    out = evaluate_gold_execution_contract(
        _ready(
            direction="NONE",
            action="NO_TRADE",
            quality=63,
            oms_orders_allowed=False,
            risk_eligible=False,
            approved_lots=Decimal("0"),
            risk_reasons=(QUALITY,),
        )
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "OWNER_MIN_TRADE_QUALITY"
    assert "63" in out.fault_reason and "75" in out.fault_reason
    # Stages start at NOT_REACHED. An earlier quality block must not
    # promote OMS to FAIL, BLOCK, or PASS.
    assert out.stages.get("OMS") == "NOT_REACHED"
    assert out.stages.get("BROKER") == "NOT_REACHED"
    assert out.direction == "NONE"


def _snapshot() -> MarketAnalysisSnapshot:
    return MarketAnalysisSnapshot(
        symbol="XAUUSD",
        as_of=datetime.now(UTC),
        config_version="ite-v1.0.0",
        input_hash="abc",
        structure_by_tf={},
        primary_structure=None,
        liquidity=None,
        order_blocks=None,
        fair_value_gaps=None,
        trend=TrendSnapshot(
            macro_bias=TrendDirection.DOWN,
            primary=TrendDirection.DOWN,
            entry=TrendDirection.DOWN,
            execution=TrendDirection.DOWN,
            alignment_score=77,
            aligned=False,
            why="test",
        ),
        session=SessionFilterResult(
            session=MarketSession.TOKYO,
            allowed=True,
            reason="Tokyo",
        ),
        news=NewsProtectionStatus(enabled=False, blocked=False, reason="clear"),
        trade_quality=TradeQualityScore(total=63, passed=False, band="reject"),
        spread=Decimal("0.30"),
    )


def test_scored_sell_below_75_is_withheld_with_the_quality_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _score(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            reject=True,
            direction="SELL",
            reject_reason=QUALITY,
            confidence=59,
            trade_quality=63,
            to_dict=lambda: {"direction": "SELL", "trade_quality": 63},
        )

    def _confluence(*_args: object, **_kwargs: object) -> ConfluenceResult:
        return ConfluenceResult(
            confidence=59,
            direction=TradeDirection.SELL,
            reasons=("scored sell",),
            rejected_rules=(),
            input_hash="c",
            passed=False,
        )

    monkeypatch.setattr(
        "app.domain.institutional_trading.ai_scalping.scoring.score_scalping_setup",
        _score,
    )
    monkeypatch.setattr(
        "app.domain.institutional_trading.confluence.ConfluenceEngine.evaluate",
        _confluence,
    )
    pipe = InstitutionalDecisionPipeline(config=ITEConfig(trading_mode="scalping"))
    decision = pipe.run(
        _snapshot(),
        AccountRiskState(
            equity=Decimal("100"),
            mid_price=Decimal("100"),
            atr=Decimal("1"),
            free_margin=Decimal("100"),
        ),
    )
    assert decision.action.value not in {"BUY", "SELL"}
    assert decision.direction.value == "NONE"
    assert decision.approved_lots == Decimal("0")
    assert decision.eligibility.eligible is False
    assert QUALITY in decision.eligibility.rejection_reasons
    assert QUALITY in decision.risk_reasons
