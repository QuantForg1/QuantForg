"""Unit tests — QuantForg Multi-Agent AI Architecture."""

from __future__ import annotations

from decimal import Decimal

from app.domain.multi_agent_ai import (
    CollaborationInput,
    MultiAgentConfig,
    MultiAgentSystem,
)
from app.domain.trading.gold_only import GOLD_SYMBOL


def _rich(**overrides: object) -> CollaborationInput:
    base = {
        "side": "buy",
        "spread": Decimal("0.4"),
        "confidence": Decimal("75"),
        "regime": "trend",
        "strategy_id": "gold-a",
        "strategy_signal": "buy",
        "portfolio_exposure": Decimal("15"),
        "open_positions": 1,
        "execution_mode": "LIVE",
        "news_blackout": False,
        "kill_switch": False,
        "risk_engine_passed": True,
        "safety_engine_passed": True,
    }
    base.update(overrides)
    return CollaborationInput(**base)  # type: ignore[arg-type]


def test_xauusd_and_hard_locks() -> None:
    status = MultiAgentSystem().status()
    assert status["symbol"] == GOLD_SYMBOL
    assert status["allow_order_send"] is False
    assert status["allow_bypass_risk"] is False
    assert status["allow_bypass_safety"] is False
    assert status["allow_memory_rewrite_rules"] is False
    caps = status["capabilities"]
    assert caps["never_order_send"] is True
    assert caps["never_bypass_risk"] is True
    assert caps["never_bypass_safety"] is True
    assert caps["risk_safety_authoritative"] is True
    assert caps["execution_pipeline_unchanged"] is True
    assert caps["memory_never_rewrites_rules"] is True
    assert len(status["agents"]) == 6


def test_policies_cannot_enable_bypass() -> None:
    cfg = MultiAgentConfig().update(
        {
            "allow_order_send": True,
            "allow_bypass_risk": True,
            "allow_bypass_safety": True,
            "allow_memory_rewrite_rules": True,
            "symbol": "EURUSD",
            "min_vote_confidence": "60",
            "feature_flags": {"bypass_risk": True, "rewrite_rules": True},
        }
    )
    assert cfg.allow_order_send is False
    assert cfg.allow_bypass_risk is False
    assert cfg.allow_bypass_safety is False
    assert cfg.allow_memory_rewrite_rules is False
    assert cfg.symbol == GOLD_SYMBOL
    assert cfg.min_vote_confidence == Decimal("60")
    assert "bypass_risk" not in cfg.feature_flags


def test_hold_without_risk_safety() -> None:
    out = MultiAgentSystem().collaborate(CollaborationInput(side="buy"))
    assert out["decision"] in {"HOLD", "REJECT"}
    assert out["allow_execution_path"] is False
    assert out["never_order_send"] is True
    assert out["bypasses_risk"] is False


def test_risk_reject_authoritative() -> None:
    out = MultiAgentSystem().collaborate(
        _rich(risk_engine_passed=False, safety_engine_passed=True)
    )
    assert out["decision"] == "REJECT"
    assert out["allow_execution_path"] is False
    risk = next(a for a in out["agents"] if a["agent"] == "risk")
    assert risk["vote"] == "REJECT"
    assert risk["authoritative"] is True


def test_safety_reject_authoritative() -> None:
    out = MultiAgentSystem().collaborate(
        _rich(risk_engine_passed=True, safety_engine_passed=False)
    )
    assert out["decision"] == "REJECT"
    assert out["allow_execution_path"] is False


def test_approve_advisory_when_engines_pass() -> None:
    out = MultiAgentSystem().collaborate(_rich())
    assert out["decision"] in {"APPROVE", "HOLD"}
    assert out["advisory_only"] is True
    assert out["never_order_send"] is True
    assert out["execution_pipeline_unchanged"] is True
    assert out["risk_engine_authoritative"] is True
    assert out["safety_engine_authoritative"] is True
    for agent in out["agents"]:
        assert agent["explainable"] is True
        assert agent["reasons"]
        assert agent["never_order_send"] is True
    assert out["events"]
    assert out["voting"]
    assert out["governance"]["allow_order_send"] is False


def test_events_auditable() -> None:
    system = MultiAgentSystem()
    out = system.collaborate(_rich())
    listed = system.list_events(session_id=out["session_id"])
    assert listed["status"] == "available"
    assert listed["events"]
    assert all(e.get("auditable") is True for e in listed["events"])


def test_memory_rejects_rule_rewrite() -> None:
    system = MultiAgentSystem()
    rejected = system.store_memory(
        kind="trading_rule",
        agent="rogue",
        content={"max_spread": "99"},
    )
    assert rejected["status"] == "rejected"
    assert rejected["rewrites_rules"] is False
    ok = system.store_memory(
        kind="observation",
        agent="market",
        content={"note": "spread tight"},
    )
    assert ok["rewrites_rules"] is False
    assert "memory_id" in ok
    mem = system.list_memory()
    assert mem["allow_memory_rewrite_rules"] is False


def test_kill_switch_safety_hold_or_reject() -> None:
    out = MultiAgentSystem().collaborate(_rich(kill_switch=True))
    assert out["decision"] in {"HOLD", "REJECT"}
    assert out["allow_execution_path"] is False
    safety = next(a for a in out["agents"] if a["agent"] == "safety")
    assert safety["vote"] == "REJECT"
