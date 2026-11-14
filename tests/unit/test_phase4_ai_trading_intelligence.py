"""Phase 4 — AI Trading Intelligence unit coverage."""

from __future__ import annotations

from decimal import Decimal

from app.domain.ai_trading_intelligence.adaptive import (
    AdaptiveProposalStore,
    propose_adaptation,
)
from app.domain.ai_trading_intelligence.market_intelligence import (
    assemble_market_intelligence,
)
from app.domain.ai_trading_intelligence.optimizer import run_optimization_orchestrator
from app.domain.ai_trading_intelligence.regime import (
    CanonicalRegime,
    map_canonical_regime,
)
from app.domain.ai_trading_intelligence.risk_alerts import build_ai_risk_alerts
from app.domain.ai_trading_intelligence.signal_quality import score_signal_quality
from app.domain.ai_trading_intelligence.supervisor import (
    SupervisorMode,
    SupervisorState,
)


def test_regime_uncertain_on_low_confidence() -> None:
    out = map_canonical_regime("strong_trend", confidence=20)
    assert out.regime == CanonicalRegime.UNCERTAIN
    assert out.methodology.get("would_have_been") == "TRENDING"


def test_regime_maps_breakout() -> None:
    out = map_canonical_regime("breakout", confidence=80)
    assert out.regime == CanonicalRegime.BREAKOUT


def test_market_intelligence_does_not_invent_liquidity() -> None:
    bundle = assemble_market_intelligence(
        symbol="XAUUSD",
        facts={"regime_label": "ranging", "regime_confidence": 70},
    )
    assert bundle.liquidity is None
    assert "liquidity_omitted_unavailable" in bundle.notes
    assert bundle.methodology["invents_ohlc"] is False


def test_stale_signal_not_actionable() -> None:
    from datetime import UTC, datetime, timedelta

    past = datetime.now(UTC) - timedelta(seconds=30)
    score = score_signal_quality(
        symbol="XAUUSD",
        regime_label="trending",
        regime_confidence=80,
        confidence=80,
        quality=80,
        valid_until=past,
    )
    assert score.stale is True
    assert score.actionable is False
    assert "not" in score.disclaimer.lower()


def test_duplicate_signal_not_actionable() -> None:
    score = score_signal_quality(
        symbol="XAUUSD",
        regime_label="ranging",
        regime_confidence=70,
        confidence=70,
        quality=70,
        ttl_seconds=120,
        duplicate=True,
    )
    assert score.actionable is False


def test_adaptive_rejects_risk_increase() -> None:
    store = AdaptiveProposalStore()
    p = propose_adaptation(
        strategy_id="s1",
        current_params={"planned_risk_pct": "1.0", "max_lot": "0.01"},
        proposed_params={"planned_risk_pct": "2.0"},
        rationale="loosen",
        store=store,
    )
    assert p.accepted is False
    assert p.reject_reason and "risk_increase" in p.reject_reason


def test_adaptive_accepts_tighten_and_rollback() -> None:
    store = AdaptiveProposalStore()
    p = propose_adaptation(
        strategy_id="s2",
        current_params={"planned_risk_pct": "1.0", "max_lot": "0.02"},
        proposed_params={"planned_risk_pct": "0.5", "max_lot": "0.01"},
        rationale="tighten for range",
        store=store,
    )
    assert p.accepted is True
    assert p.status == "proposed"
    approved = store.approve(p.proposal_id)
    assert approved is not None and approved.status == "approved"
    restored = store.rollback("s2")
    assert restored is not None
    assert Decimal(str(restored["planned_risk_pct"])) == Decimal("1.0")


def test_optimizer_never_auto_live_deploy() -> None:
    result = run_optimization_orchestrator(
        strategy_id="gold",
        backtest_summary={"profit_factor": "1.4", "expectancy": "0.5"},
        walk_forward_summary={"profit_factor": "1.2"},
        out_of_sample_summary={"profit_factor": "1.1"},
        owner_promotion_approved=True,
    )
    assert result.live_deploy_allowed is False
    assert "auto" in result.live_deploy_reason or "never" in result.live_deploy_reason


def test_ai_risk_alerts_advisory_only() -> None:
    alerts = build_ai_risk_alerts(
        portfolio={"drawdown_pct": "12", "consecutive_losses": 3},
        strategy_health={"score": "30"},
    )
    codes = {a.code for a in alerts}
    assert "portfolio_drawdown" in codes
    assert "consecutive_losses" in codes
    assert "strategy_deterioration" in codes


def test_supervisor_monitor_only_never_mutates() -> None:
    state = SupervisorState()
    assert state.mode == SupervisorMode.MONITOR_ONLY
    ev = state.evaluate_action(action="pause_strategy", owner_approved=True)
    assert ev.applied is False
    assert ev.reject_reason == "monitor_only_no_mutate"


def test_supervisor_blocks_risk_increase_and_live() -> None:
    state = SupervisorState()
    state.set_mode(SupervisorMode.APPROVED_AUTOMATION)
    bad = state.evaluate_action(action="tighten_risk", increases_risk=True)
    assert bad.applied is False
    assert bad.reject_reason == "cannot_increase_risk"
    live = state.evaluate_action(action="pause_strategy", enables_live=True)
    assert live.applied is False
    assert live.reject_reason == "cannot_enable_live"
    ok = state.evaluate_action(action="pause_strategy")
    assert ok.applied is True


def test_optimizer_summary_has_no_order_send_in_methodology() -> None:
    result = run_optimization_orchestrator(strategy_id="x")
    assert result.methodology.get("order_send") is False
    assert result.methodology.get("auto_live_deploy") is False
