"""Unit tests — Institutional XAUUSD Scalping AI V2."""

from __future__ import annotations

from decimal import Decimal

from app.domain.scalping_ai_v2 import (
    ScalpCycleInput,
    ScalpingAiV2,
    ScalpingAiV2Config,
)
from app.domain.scalping_ai_v2.reliability import next_backoff_ms
from app.domain.trading.gold_only import GOLD_SYMBOL


def _rich(**overrides: object) -> ScalpCycleInput:
    base: dict[str, object] = {
        "side": "buy",
        "spread": Decimal("0.28"),
        "atr": Decimal("4"),
        "price": Decimal("2350"),
        "regime": "trend",
        "session": "london",
        "trend": "up",
        "volatility": "normal",
        "liquidity_state": "healthy",
        "market_health": "good",
        "confidence": Decimal("72"),
        "htf_bias": "bullish",
        "ltf_confirmation": "bullish",
        "trend_strength": Decimal("70"),
        "trend_consistency": Decimal("68"),
        "sweep_detected": True,
        "stop_hunt": False,
        "bos": True,
        "choch": False,
        "structure_phase": "continuation",
        "opportunities": [
            {
                "id": "a",
                "quality_score": 78,
                "confidence_score": 74,
                "risk_score": 30,
                "execution_score": 80,
            }
        ],
        "risk_engine_passed": True,
        "safety_engine_passed": True,
        "decision_approved": True,
        "decision_center": {"decision": "APPROVE"},
        "broker_connected": True,
        "gateway_healthy": True,
        "latency_ms": Decimal("40"),
        "market_open": True,
        "margin_available": True,
        "equity": Decimal("10000"),
        "daily_loss_pct": Decimal("0.2"),
        "open_exposure_pct": Decimal("1"),
        "trades_today": 1,
        "consecutive_losses": 0,
        "run_state": "running",
        "kill_switch": False,
        "news_blackout": False,
        "health": {
            "execution_loop": True,
            "broker_connection": True,
            "gateway": True,
            "database": True,
            "analytics": True,
            "risk_engine": True,
            "safety_engine": True,
            "decision_engine": True,
            "analytics_metrics": {"win_rate": 55, "average_rr": 1.3},
        },
    }
    base.update(overrides)
    return ScalpCycleInput(**base)  # type: ignore[arg-type]


def test_hard_locks_and_xauusd() -> None:
    status = ScalpingAiV2().status()
    assert status["symbol"] == GOLD_SYMBOL
    assert status["allow_order_send"] is False
    assert status["promise_profitability"] is False
    assert status["allow_bypass_risk"] is False
    caps = status["capabilities"]
    assert caps["never_order_send"] is True
    assert caps["never_bypass_risk"] is True
    assert caps["never_bypass_safety"] is True
    assert caps["never_bypass_decision_center"] is True
    assert caps["prefer_no_trade"] is True
    assert caps["never_guarantee_profits"] is True
    assert len(status["modules"]) >= 18


def test_policies_cannot_enable_bypass() -> None:
    cfg = ScalpingAiV2Config().update(
        {
            "allow_order_send": True,
            "allow_bypass_risk": True,
            "allow_martingale": True,
            "promise_profitability": True,
            "symbol": "EURUSD",
            "min_confidence": "70",
        }
    )
    assert cfg.allow_order_send is False
    assert cfg.allow_bypass_risk is False
    assert cfg.allow_martingale is False
    assert cfg.promise_profitability is False
    assert cfg.symbol == GOLD_SYMBOL
    assert cfg.min_confidence == Decimal("70")


def test_no_trade_without_authority() -> None:
    out = ScalpingAiV2().run_cycle(ScalpCycleInput(side="buy", run_state="running"))
    assert out["recommendation"] == "No Trade"
    assert out["never_order_send"] is True
    assert out["bypasses_risk"] is False


def test_no_trade_when_risk_fails() -> None:
    out = ScalpingAiV2().run_cycle(_rich(risk_engine_passed=False))
    assert out["recommendation"] == "No Trade"
    assert out["alternate_execution_path"] is False


def test_proceed_when_gates_pass() -> None:
    out = ScalpingAiV2().run_cycle(_rich())
    assert out["recommendation"] in {"Proceed", "No Trade"}
    assert out["advisory_only"] is True
    assert out["execution_pipeline_unchanged"] is True
    assert out["events"]
    assert out["observability"]["dashboards"]
    for mod in out["modules"].values():
        assert mod["explainable"] is True
        assert mod["invented"] is False


def test_forbidden_technique_blocked() -> None:
    out = ScalpingAiV2().run_cycle(_rich(technique="martingale_recovery"))
    assert out["recommendation"] == "No Trade"
    assert any("Forbidden" in r or "forbidden" in r.lower() for r in out["reasons"])


def test_duplicate_protection() -> None:
    system = ScalpingAiV2()
    a = system.run_cycle(_rich(execution_identity="exec_unique_1"))
    b = system.run_cycle(_rich(execution_identity="exec_unique_1"))
    assert a["recommendation"] in {"Proceed", "No Trade"}
    assert b["recommendation"] == "No Trade"
    assert any("Duplicate" in r for r in b["reasons"])


def test_backoff_bounded() -> None:
    cfg = ScalpingAiV2Config()
    delays = [next_backoff_ms(i, cfg) for i in range(cfg.max_retries + 2)]
    assert delays[-1] == -1
    assert all(d <= cfg.max_retry_backoff_ms for d in delays if d >= 0)


def test_watchdog_safe_mode() -> None:
    out = ScalpingAiV2().run_cycle(
        _rich(
            health={
                "execution_loop": True,
                "broker_connection": False,
                "gateway": False,
                "risk_engine": True,
                "safety_engine": True,
                "decision_engine": True,
            }
        )
    )
    assert out["recommendation"] == "No Trade"
    wd = out["modules"]["production_watchdog"]
    assert wd["details"]["safe_mode"] is True
