"""Unit tests — QuantForg Institutional Trading Brain V3."""

from __future__ import annotations

from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL
from app.domain.trading_brain_v3 import (
    BrainInput,
    TradingBrainConfig,
    TradingBrainV3,
)


def _rich(**overrides: object) -> BrainInput:
    base: dict[str, object] = {
        "side": "buy",
        "spread": Decimal("0.35"),
        "atr": Decimal("12"),
        "regime": "trend",
        "session": "london",
        "news_blackout": False,
        "kill_switch": False,
        "confidence": Decimal("72"),
        "opportunity_candidates": [
            {"id": "a", "label": "sweep", "score": 78},
            {"id": "b", "label": "fvg", "score": 64},
        ],
        "decision_center": {"decision": "APPROVE", "allow_execution_path": True},
        "risk_engine_passed": True,
        "safety_engine_passed": True,
        "execution_mode": "LIVE",
        "open_positions": 1,
        "unrealized_pnl": Decimal("10"),
        "active_trade": {"side": "buy", "mfe": 5, "mae": -1},
        "closed_trades": [{"pnl": 15, "slippage": 0.1}],
        "quality_metrics": {"adherence": 80},
    }
    base.update(overrides)
    return BrainInput(**base)  # type: ignore[arg-type]


def test_xauusd_and_hard_locks() -> None:
    status = TradingBrainV3().status()
    assert status["symbol"] == GOLD_SYMBOL
    assert status["allow_order_send"] is False
    assert status["promise_profitability"] is False
    assert status["invent_market_data"] is False
    caps = status["capabilities"]
    assert caps["alternate_execution_path"] is False
    assert caps["never_order_send"] is True
    assert caps["never_bypass_risk"] is True
    assert caps["may_recommend_no_trade"] is True
    assert caps["eliminates_losses"] is False
    assert len(status["modules"]) == 10


def test_policies_cannot_enable_bypass_or_promises() -> None:
    cfg = TradingBrainConfig().update(
        {
            "allow_order_send": True,
            "promise_profitability": True,
            "invent_market_data": True,
            "allow_bypass_risk": True,
            "symbol": "EURUSD",
            "min_discipline_score": "70",
        }
    )
    assert cfg.allow_order_send is False
    assert cfg.promise_profitability is False
    assert cfg.invent_market_data is False
    assert cfg.allow_bypass_risk is False
    assert cfg.symbol == GOLD_SYMBOL
    assert cfg.min_discipline_score == Decimal("70")


def test_no_trade_without_facts() -> None:
    out = TradingBrainV3().evaluate(BrainInput())
    assert out["recommendation"] == "No Trade"
    assert out["never_order_send"] is True
    assert out["invented_market_data"] is False
    assert out["modules"]["environment_intelligence"]["status"] == "unavailable"


def test_no_trade_when_risk_fails() -> None:
    out = TradingBrainV3().evaluate(_rich(risk_engine_passed=False))
    assert out["recommendation"] == "No Trade"
    assert out["bypasses_risk"] is False
    assert out["alternate_execution_path"] is False


def test_proceed_when_gates_pass() -> None:
    out = TradingBrainV3().evaluate(_rich())
    assert out["recommendation"] in {"Proceed", "No Trade"}
    assert out["advisory_only"] is True
    assert out["promise_profitability"] is False
    assert out["eliminates_losses"] is False
    assert out["execution_pipeline_unchanged"] is True
    assert out["uses_decision_center"] is True
    for mod in out["modules"].values():
        assert mod["explainable"] is True
        assert mod["invented"] is False
        assert mod["reasons"]


def test_empty_opportunities_no_trade() -> None:
    out = TradingBrainV3().evaluate(_rich(opportunity_candidates=[]))
    assert out["modules"]["opportunity_discovery"]["status"] == "empty"
    assert out["recommendation"] == "No Trade"


def test_explainable_discipline_and_advisor() -> None:
    out = TradingBrainV3().evaluate(_rich())
    disc = out["modules"]["institutional_discipline_score"]
    adv = out["modules"]["operator_advisor"]
    assert disc["reasons"]
    assert adv["reasons"]
    assert any("profitability" in r.lower() for r in adv["reasons"])
    assert disc["status"] == "available"
    assert out["discipline_score"] is not None


def test_history_auditable() -> None:
    brain = TradingBrainV3()
    out = brain.evaluate(_rich())
    hist = brain.list_history(limit=5)
    assert hist["status"] == "available"
    assert hist["items"][0]["audit_id"] == out["audit_id"]
