"""Phase B unit tests — confluence, risk gates, eligibility, trade decision."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.institutional_decision_pipeline import (
    InstitutionalDecisionPipeline,
)
from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.confluence import ConfluenceEngine
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    ConfluenceResult,
    DecisionAction,
    TradeDirection,
)
from app.domain.institutional_trading.eligibility import PositionEligibilityEngine
from app.domain.institutional_trading.models import (
    MarketAnalysisSnapshot,
    NewsProtectionStatus,
    SessionFilterResult,
    TradeQualityFactor,
    TradeQualityScore,
    TrendSnapshot,
)
from app.domain.institutional_trading.trade_decision import TradeDecisionEngine
from app.domain.market_context.enums import MarketSession
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import StructureRole, TrendDirection
from app.domain.market_structure.models import StructureSnapshot, TrendState
from app.domain.value_objects.identity import SymbolCode


def _trend(
    *,
    macro: TrendDirection = TrendDirection.UP,
    primary: TrendDirection = TrendDirection.UP,
    entry: TrendDirection = TrendDirection.UP,
    execution: TrendDirection = TrendDirection.UP,
    score: int = 95,
    aligned: bool = True,
) -> TrendSnapshot:
    return TrendSnapshot(
        macro_bias=macro,
        primary=primary,
        entry=entry,
        execution=execution,
        alignment_score=score,
        aligned=aligned,
        frames={
            "H4": macro.value,
            "H1": primary.value,
            "M15": entry.value,
            "M5": execution.value,
        },
        why="test trend",
    )


def _quality(total: int = 90) -> TradeQualityScore:
    return TradeQualityScore(
        total=total,
        passed=total >= 80,
        band=(
            "high_confidence"
            if total >= 90
            else ("tradable" if total >= 80 else "reject")
        ),
        factors=(
            TradeQualityFactor(code="trend", weight=20, score=total),
            TradeQualityFactor(code="session", weight=10, score=100),
        ),
    )


def _structure(direction: TrendDirection = TrendDirection.UP) -> StructureSnapshot:
    code = SymbolCode(value="XAUUSD")
    as_of = datetime(2026, 3, 10, 14, 0, tzinfo=UTC)
    return StructureSnapshot(
        symbol_code=code,
        timeframe=Timeframe.H1,
        as_of=as_of,
        swings=(),
        nodes=(),
        trend=TrendState(
            symbol_code=code,
            timeframe=Timeframe.H1,
            direction=direction,
            as_of=as_of,
            last_structure_role=StructureRole.HIGHER_HIGH,
            swing_count=4,
        ),
        breaks_of_structure=(),
        changes_of_character=(),
    )


def _snapshot(
    *,
    trend: TrendSnapshot | None = None,
    quality: int = 90,
    session: MarketSession = MarketSession.LONDON_NY_OVERLAP,
    session_allowed: bool = True,
    news_blocked: bool = False,
    spread: Decimal = Decimal("0.30"),
    direction_bias: TrendDirection = TrendDirection.UP,
) -> MarketAnalysisSnapshot:
    t = trend or _trend(
        macro=direction_bias,
        primary=direction_bias,
        entry=direction_bias,
        execution=direction_bias,
    )
    return MarketAnalysisSnapshot(
        symbol="XAUUSD",
        as_of=datetime(2026, 3, 10, 14, 30, tzinfo=UTC),
        config_version="ite-v1.0.0",
        input_hash="abc123deadbeef001122334455667788",
        structure_by_tf={"H1": _structure(direction_bias)},
        primary_structure=_structure(direction_bias),
        liquidity=None,
        order_blocks=None,
        fair_value_gaps=None,
        trend=t,
        session=SessionFilterResult(
            session=session,
            allowed=session_allowed,
            reason="ok" if session_allowed else "blocked session",
        ),
        news=NewsProtectionStatus(
            enabled=news_blocked,
            blocked=news_blocked,
            reason="news blackout" if news_blocked else "news clear",
        ),
        trade_quality=_quality(quality),
        spread=spread,
    )


def _account(**kwargs: object) -> AccountRiskState:
    base = dict(  # noqa: C408
        equity=Decimal("10000"),
        peak_equity=Decimal("10000"),
        daily_pnl=Decimal("0"),
        weekly_pnl=Decimal("0"),
        open_positions=0,
        already_in_trade=False,
        consecutive_losses=0,
        cooldown_active=False,
        market_open=True,
        atr=Decimal("5"),
        mid_price=Decimal("2300"),
        free_margin=Decimal("10000"),
    )
    base.update(kwargs)
    return AccountRiskState(**base)  # type: ignore[arg-type]


@pytest.mark.unit
class TestConfluenceEngine:
    def test_strong_buy_path_factors(self) -> None:
        snap = _snapshot(direction_bias=TrendDirection.UP, quality=92)
        # Without OB/FVG confidence is capped — still deterministic
        result = ConfluenceEngine(config=ITEConfig()).evaluate(snap, atr=Decimal("5"))
        assert result.direction in {TradeDirection.BUY, TradeDirection.NONE}
        assert 0 <= result.confidence <= 100
        assert result.input_hash
        # Same input → same hash
        again = ConfluenceEngine(config=ITEConfig()).evaluate(snap, atr=Decimal("5"))
        assert again.input_hash == result.input_hash
        assert again.confidence == result.confidence

    def test_mtf_misalignment_rejects_direction(self) -> None:
        snap = _snapshot(
            trend=_trend(
                macro=TrendDirection.UP,
                primary=TrendDirection.DOWN,
                aligned=False,
                score=40,
            )
        )
        result = ConfluenceEngine(config=ITEConfig()).evaluate(snap)
        assert result.direction is TradeDirection.NONE
        assert "mtf_not_aligned" in result.rejected_rules

    def test_low_quality_rejected(self) -> None:
        snap = _snapshot(quality=50)
        result = ConfluenceEngine(config=ITEConfig()).evaluate(snap)
        assert "quality_below_threshold" in result.rejected_rules
        assert result.passed is False


@pytest.mark.unit
class TestExtendedRiskEngine:
    def _acct(self) -> AccountSnapshot:
        return AccountSnapshot(
            login=1,
            balance=Decimal("10000"),
            equity=Decimal("10000"),
            margin=Decimal("0"),
            free_margin=Decimal("10000"),
            margin_level=Decimal("0"),
            profit=Decimal("0"),
            leverage=100,
        )

    def test_consecutive_losses_reject(self) -> None:
        engine = RiskEngine(
            config=RiskEngineConfig(max_consecutive_losses=3, max_open_positions=5)
        )
        check = RiskCheckInput(
            user_id=uuid4(),
            request_id="r1",
            symbol="XAUUSD",
            side="buy",
            entry_price=Decimal("2300"),
            stop_loss_distance=Decimal("5"),
            consecutive_losses=3,
            sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
        )
        result = engine.evaluate(check, account=self._acct(), positions=[])
        assert result.decision is RiskDecision.REJECT
        assert any("consecutive losses" in r for r in result.reasons)

    def test_cooldown_reject(self) -> None:
        engine = RiskEngine(config=RiskEngineConfig(max_open_positions=5))
        check = RiskCheckInput(
            user_id=uuid4(),
            request_id="r2",
            symbol="XAUUSD",
            side="buy",
            entry_price=Decimal("2300"),
            stop_loss_distance=Decimal("5"),
            cooldown_active=True,
            cooldown_remaining_minutes=30,
        )
        result = engine.evaluate(check, account=self._acct(), positions=[])
        assert result.decision is RiskDecision.REJECT
        assert any("cooldown" in r for r in result.reasons)

    def test_high_spread_reject(self) -> None:
        engine = RiskEngine(
            config=RiskEngineConfig(max_spread=Decimal("2"), max_open_positions=5)
        )
        check = RiskCheckInput(
            user_id=uuid4(),
            request_id="r3",
            symbol="XAUUSD",
            side="buy",
            entry_price=Decimal("2300"),
            stop_loss_distance=Decimal("5"),
            spread=Decimal("3.5"),
        )
        result = engine.evaluate(check, account=self._acct(), positions=[])
        assert result.decision is RiskDecision.REJECT
        assert any("spread" in r for r in result.reasons)

    def test_session_restriction(self) -> None:
        engine = RiskEngine(config=RiskEngineConfig(max_open_positions=5))
        check = RiskCheckInput(
            user_id=uuid4(),
            request_id="r4",
            symbol="XAUUSD",
            side="buy",
            entry_price=Decimal("2300"),
            stop_loss_distance=Decimal("5"),
            session_allowed=False,
            session_name="tokyo",
        )
        result = engine.evaluate(check, account=self._acct(), positions=[])
        assert result.decision is RiskDecision.REJECT
        assert any("session" in r for r in result.reasons)

    def test_daily_loss_exceeded(self) -> None:
        engine = RiskEngine(
            config=RiskEngineConfig(
                max_daily_loss_pct=Decimal("3"),
                max_open_positions=5,
            )
        )
        check = RiskCheckInput(
            user_id=uuid4(),
            request_id="r5",
            symbol="XAUUSD",
            side="buy",
            entry_price=Decimal("2300"),
            stop_loss_distance=Decimal("5"),
        )
        # -4% daily on 10k equity
        result = engine.evaluate(
            check,
            account=self._acct(),
            positions=[],
            daily_pnl=Decimal("-400"),
        )
        assert result.decision is RiskDecision.REJECT
        assert result.reasons


@pytest.mark.unit
class TestEligibilityAndDecision:
    def test_already_in_trade_blocks(self) -> None:
        snap = _snapshot()
        conf = ConfluenceResult(
            confidence=90,
            direction=TradeDirection.BUY,
            reasons=("aligned",),
            rejected_rules=(),
            input_hash="h1",
            band="high_confidence",
            passed=True,
            factors={},
        )
        elig = PositionEligibilityEngine(config=ITEConfig()).evaluate(
            snapshot=snap,
            confluence=conf,
            account=_account(already_in_trade=True, open_positions=1),
            risk_allowed=True,
        )
        assert elig.eligible is False
        assert any("Already in trade" in r for r in elig.rejection_reasons)

    def test_news_blocked(self) -> None:
        snap = _snapshot(news_blocked=True)
        conf = ConfluenceResult(
            confidence=90,
            direction=TradeDirection.BUY,
            reasons=(),
            rejected_rules=(),
            input_hash="h2",
            band="high_confidence",
            passed=True,
            factors={},
        )
        elig = PositionEligibilityEngine(config=ITEConfig()).evaluate(
            snapshot=snap,
            confluence=conf,
            account=_account(),
            risk_allowed=True,
        )
        assert elig.eligible is False
        assert any("news" in r.lower() for r in elig.rejection_reasons)

    def test_wrong_session(self) -> None:
        snap = _snapshot(session=MarketSession.TOKYO, session_allowed=False)
        conf = ConfluenceResult(
            confidence=90,
            direction=TradeDirection.SELL,
            reasons=(),
            rejected_rules=(),
            input_hash="h3",
            band="high_confidence",
            passed=True,
            factors={},
        )
        elig = PositionEligibilityEngine(config=ITEConfig()).evaluate(
            snapshot=snap,
            confluence=conf,
            account=_account(),
            risk_allowed=True,
        )
        assert elig.eligible is False

    def test_quality_below_threshold(self) -> None:
        snap = _snapshot(quality=60)
        conf = ConfluenceResult(
            confidence=90,
            direction=TradeDirection.BUY,
            reasons=(),
            rejected_rules=(),
            input_hash="h4",
            band="high_confidence",
            passed=True,
            factors={},
        )
        elig = PositionEligibilityEngine(config=ITEConfig()).evaluate(
            snapshot=snap,
            confluence=conf,
            account=_account(),
            risk_allowed=True,
        )
        assert elig.eligible is False
        assert any("quality" in r.lower() for r in elig.rejection_reasons)

    def test_decision_no_trade_when_ineligible(self) -> None:
        snap = _snapshot()
        conf = ConfluenceResult(
            confidence=95,
            direction=TradeDirection.BUY,
            reasons=("strong",),
            rejected_rules=(),
            input_hash="h5",
            band="high_confidence",
            passed=True,
            factors={},
        )
        elig = PositionEligibilityEngine(config=ITEConfig()).evaluate(
            snapshot=snap,
            confluence=conf,
            account=_account(already_in_trade=True, open_positions=1),
            risk_allowed=True,
        )
        decision = TradeDecisionEngine(config=ITEConfig()).decide(
            snapshot=snap,
            confluence=conf,
            eligibility=elig,
            account=_account(already_in_trade=True),
            risk_score=10,
        )
        assert decision.action is DecisionAction.NO_TRADE
        assert decision.confidence == 95
        assert decision.quality == 90

    def test_strong_buy_decision_when_eligible(self) -> None:
        snap = _snapshot(direction_bias=TrendDirection.UP, quality=92)
        conf = ConfluenceResult(
            confidence=92,
            direction=TradeDirection.BUY,
            reasons=("H4/H1 aligned", "quality ok"),
            rejected_rules=(),
            input_hash="h6",
            band="high_confidence",
            passed=True,
            factors={"mtf": 95},
        )
        elig = PositionEligibilityEngine(config=ITEConfig()).evaluate(
            snapshot=snap,
            confluence=conf,
            account=_account(),
            risk_allowed=True,
        )
        assert elig.eligible is True
        decision = TradeDecisionEngine(config=ITEConfig()).decide(
            snapshot=snap,
            confluence=conf,
            eligibility=elig,
            account=_account(),
            risk_score=20,
            approved_lots=Decimal("0.10"),
        )
        assert decision.action is DecisionAction.BUY
        assert decision.direction is TradeDirection.BUY
        assert decision.entry_zone is not None
        assert decision.estimated_rr is not None
        # Determinism
        again = TradeDecisionEngine(config=ITEConfig()).decide(
            snapshot=snap,
            confluence=conf,
            eligibility=elig,
            account=_account(),
            risk_score=20,
            approved_lots=Decimal("0.10"),
        )
        assert again.input_hash == decision.input_hash
        assert again.to_dict()["action"] == "BUY"

    def test_strong_sell_decision(self) -> None:
        snap = _snapshot(direction_bias=TrendDirection.DOWN, quality=91)
        conf = ConfluenceResult(
            confidence=91,
            direction=TradeDirection.SELL,
            reasons=("bearish",),
            rejected_rules=(),
            input_hash="h7",
            band="high_confidence",
            passed=True,
            factors={},
        )
        elig = PositionEligibilityEngine(config=ITEConfig()).evaluate(
            snapshot=snap,
            confluence=conf,
            account=_account(),
            risk_allowed=True,
        )
        decision = TradeDecisionEngine(config=ITEConfig()).decide(
            snapshot=snap,
            confluence=conf,
            eligibility=elig,
            account=_account(),
            risk_score=15,
        )
        assert decision.action is DecisionAction.SELL

    def test_low_confidence_watch_or_no_trade(self) -> None:
        snap = _snapshot(quality=85)
        conf = ConfluenceResult(
            confidence=75,
            direction=TradeDirection.BUY,
            reasons=("forming",),
            rejected_rules=("confidence_below_threshold",),
            input_hash="h8",
            band="reject",
            passed=False,
            factors={},
        )
        elig = PositionEligibilityEngine(config=ITEConfig()).evaluate(
            snapshot=snap,
            confluence=conf,
            account=_account(),
            risk_allowed=True,
        )
        decision = TradeDecisionEngine(config=ITEConfig()).decide(
            snapshot=snap,
            confluence=conf,
            eligibility=elig,
            account=_account(),
            risk_score=20,
        )
        assert decision.action in {DecisionAction.WATCH, DecisionAction.NO_TRADE}

    def test_pipeline_high_spread_no_trade(self) -> None:
        snap = _snapshot(spread=Decimal("5.0"), quality=90)
        pipe = InstitutionalDecisionPipeline(config=ITEConfig())
        decision = pipe.run(snap, _account())
        assert decision.action is DecisionAction.NO_TRADE
        assert decision.eligibility.eligible is False or decision.risk_reasons

    def test_pipeline_deterministic(self) -> None:
        snap = _snapshot()
        acct = _account()
        pipe = InstitutionalDecisionPipeline(config=ITEConfig())
        a = pipe.run(snap, acct, request_id="det_1")
        b = pipe.run(snap, acct, request_id="det_1")
        assert a.action == b.action
        assert a.confidence == b.confidence
        assert a.confluence.input_hash == b.confluence.input_hash
