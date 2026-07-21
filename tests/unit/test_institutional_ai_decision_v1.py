"""Unit tests — Institutional AI Decision Engine V1."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.domain.institutional_ai_decision import (
    DecisionEngineV1,
    DecisionEvaluateInput,
)
from app.domain.institutional_ai_decision.adaptive_risk import allocate_adaptive_risk
from app.domain.institutional_ai_decision.confidence import (
    score_institutional_confidence,
)
from app.domain.institutional_ai_decision.config import DecisionEngineV1Config
from app.domain.institutional_ai_decision.layers import (
    PIPELINE_LAYERS,
    LayerHints,
    evaluate_layers,
    required_layers_passed,
)
from app.domain.institutional_ai_decision.loss_protection import (
    evaluate_loss_protection,
)


def _passing_hints(**overrides: object) -> LayerHints:
    base: dict[str, object] = {
        "trend_aligned": True,
        "trend_label": "bullish",
        "structure_valid": True,
        "structure_bias": "bullish",
        "liquidity_ok": True,
        "order_block_valid": True,
        "fvg_valid": True,
        "spread": Decimal("0.40"),
        "atr": Decimal("8"),
        "price": Decimal("4000"),
        "risk_engine_passed": True,
        "safety_engine_passed": True,
        "as_of": datetime(2026, 7, 21, 14, 30, tzinfo=UTC),
    }
    base.update(overrides)
    return LayerHints(**base)  # type: ignore[arg-type]


def test_pipeline_has_nine_layers() -> None:
    assert PIPELINE_LAYERS == (
        "trend",
        "market_structure",
        "liquidity",
        "order_block",
        "fair_value_gap",
        "session",
        "spread",
        "risk",
        "safety",
    )


def test_layers_fail_closed_without_risk_safety() -> None:
    cfg = DecisionEngineV1Config()
    layers = evaluate_layers(
        cfg,
        LayerHints(
            trend_aligned=True,
            structure_valid=True,
            spread=Decimal("0.4"),
            atr=Decimal("8"),
            price=Decimal("4000"),
            as_of=datetime(2026, 7, 21, 14, 30, tzinfo=UTC),
            risk_engine_passed=None,
            safety_engine_passed=None,
        ),
    )
    assert not required_layers_passed(layers)
    assert any(layer.name == "risk" and not layer.passed for layer in layers)
    assert any(layer.name == "safety" and not layer.passed for layer in layers)


def test_abnormal_spread_and_volatility_blocked() -> None:
    cfg = DecisionEngineV1Config()
    loss = evaluate_loss_protection(
        cfg,
        consecutive_losses=0,
        daily_drawdown_pct=Decimal("0"),
        spread=Decimal("9.0"),
        atr=Decimal("200"),
        price=Decimal("4000"),
    )
    assert not loss.passed
    assert not loss.spread_ok
    assert not loss.volatility_ok


def test_consecutive_loss_and_daily_dd_protection() -> None:
    cfg = DecisionEngineV1Config(
        max_consecutive_losses=3, max_daily_drawdown_pct=Decimal("3")
    )
    loss = evaluate_loss_protection(
        cfg,
        consecutive_losses=3,
        daily_drawdown_pct=Decimal("3.5"),
        spread=Decimal("0.4"),
        atr=Decimal("8"),
        price=Decimal("4000"),
    )
    assert not loss.consecutive_losses_ok
    assert not loss.daily_drawdown_ok


def test_confidence_and_adaptive_risk_shrink_after_losses() -> None:
    cfg = DecisionEngineV1Config()
    layers = evaluate_layers(cfg, _passing_hints())
    conf = score_institutional_confidence(
        cfg, layers, consecutive_losses=0, daily_drawdown_pct=Decimal("0")
    )
    conf_loss = score_institutional_confidence(
        cfg,
        layers,
        consecutive_losses=3,
        daily_drawdown_pct=Decimal("2"),
    )
    assert conf_loss.score < conf.score

    risk_base = allocate_adaptive_risk(
        cfg,
        conf,
        equity=Decimal("10000"),
        stop_distance=Decimal("5"),
        daily_drawdown_pct=Decimal("0"),
        consecutive_losses=0,
    )
    risk_dd = allocate_adaptive_risk(
        cfg,
        conf,
        equity=Decimal("10000"),
        stop_distance=Decimal("5"),
        daily_drawdown_pct=Decimal("2"),
        consecutive_losses=3,
    )
    assert risk_dd.risk_pct <= risk_base.risk_pct
    assert risk_dd.approved_lots <= risk_base.approved_lots


def test_evaluate_wait_without_risk_safety() -> None:
    engine = DecisionEngineV1()
    result = engine.evaluate(
        DecisionEvaluateInput(
            dry_run=True,
            layers=_passing_hints(
                risk_engine_passed=None, safety_engine_passed=None
            ),
        )
    )
    assert result.decision == "WAIT"
    assert result.dry_run is True
    assert result.allow_trade_idea is False
    assert result.capabilities["martingale"] is False


def test_evaluate_trade_idea_dry_run_when_gates_pass() -> None:
    engine = DecisionEngineV1()
    result = engine.evaluate(
        DecisionEvaluateInput(
            dry_run=True,
            equity=Decimal("10000"),
            stop_distance=Decimal("5"),
            layers=_passing_hints(),
        )
    )
    assert result.decision == "TRADE_IDEA"
    assert result.dry_run is True
    assert result.card.accepted is True
    assert result.adaptive_risk.approved_lots > 0
    assert len(result.layers) == 9
    assert "never" in result.card.disclaimer.lower()


def test_auto_suspend_on_poor_health() -> None:
    engine = DecisionEngineV1(
        DecisionEngineV1Config(auto_suspend_health_below=Decimal("35"))
    )
    result = engine.evaluate(
        DecisionEvaluateInput(
            dry_run=True,
            closed_pnls=tuple(Decimal("-10") for _ in range(12)),
            layers=_passing_hints(),
        )
    )
    assert result.health.auto_pause is True
    assert result.decision == "SUSPENDED"


def test_forbidden_techniques_rejected() -> None:
    engine = DecisionEngineV1()
    result = engine.evaluate(
        DecisionEvaluateInput(
            technique="martingale",
            dry_run=True,
            layers=_passing_hints(),
        )
    )
    assert result.decision == "WAIT"
    assert any("martingale" in r.lower() for r in result.blocked_reasons)


def test_config_hard_locks() -> None:
    cfg = DecisionEngineV1Config(
        allow_martingale=True,  # type: ignore[arg-type]
        allow_grid=True,  # type: ignore[arg-type]
        allow_average_down=True,  # type: ignore[arg-type]
    )
    assert cfg.allow_martingale is False
    assert cfg.allow_grid is False
    assert cfg.allow_average_down is False


def test_service_status_and_evaluate() -> None:
    from app.application.services.institutional_ai_decision import (
        InstitutionalAiDecisionService,
    )

    svc = InstitutionalAiDecisionService()
    status = svc.status()
    assert "institutional-ai-decision" in str(status["version"])
    assert status["capabilities"]["dry_run_mode"] is True
    out = svc.evaluate(
        {
            "dry_run": True,
            "equity": "10000",
            "stop_distance": "5",
            "layers": {
                "trend_aligned": True,
                "structure_valid": True,
                "liquidity_ok": True,
                "order_block_valid": True,
                "fvg_valid": True,
                "spread": "0.4",
                "atr": "8",
                "price": "4000",
                "risk_engine_passed": True,
                "safety_engine_passed": True,
            },
        }
    )
    assert out["decision"] in {"TRADE_IDEA", "WAIT", "SUSPENDED"}
    assert out["dry_run"] is True
    assert len(out["layers"]) == 9
    assert "card" in out
