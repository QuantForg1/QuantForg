"""Unit tests — QuantForg Trading Kernel V1."""

from __future__ import annotations

from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL
from app.domain.trading_kernel import KernelCycleInput, TradingKernel
from app.domain.trading_kernel.config import KernelConfig
from app.domain.trading_kernel.plugins import KernelPlugin


class _ProbePlugin:
    name = "probe"

    def evaluate(self, snapshot: dict) -> dict:
        return {
            "status": "ok",
            "order_send": True,  # must be stripped
            "risk_engine_passed": True,  # must be stripped
            "safety_engine_passed": True,  # must be stripped
            "note": snapshot.get("side"),
        }


def test_xauusd_and_hard_locks() -> None:
    status = TradingKernel().status()
    assert status["symbol"] == GOLD_SYMBOL
    assert status["allow_order_send"] is False
    assert status["allow_bypass_risk"] is False
    assert status["allow_bypass_safety"] is False
    caps = status["capabilities"]
    assert caps["never_order_send"] is True
    assert caps["never_bypass_risk"] is True
    assert caps["never_bypass_safety"] is True
    assert caps["execution_pipeline_unchanged"] is True
    assert caps["orchestrates_only"] is True


def test_policies_cannot_enable_bypass_or_order_send() -> None:
    cfg = KernelConfig().update(
        {
            "allow_order_send": True,
            "allow_bypass_risk": True,
            "allow_bypass_safety": True,
            "symbol": "EURUSD",
            "max_spread": "1.25",
            "feature_flags": {"bypass_risk": True, "order_send": True},
        }
    )
    assert cfg.allow_order_send is False
    assert cfg.allow_bypass_risk is False
    assert cfg.allow_bypass_safety is False
    assert cfg.symbol == GOLD_SYMBOL
    assert cfg.max_spread == Decimal("1.25")
    assert "bypass_risk" not in cfg.feature_flags
    assert "order_send" not in cfg.feature_flags


def test_hold_without_risk_or_safety() -> None:
    kernel = TradingKernel()
    out = kernel.run_cycle(KernelCycleInput(side="buy", decision="APPROVE"))
    assert out["decision"] == "HOLD"
    assert out["allow_execution_path"] is False
    assert out["never_order_send"] is True
    assert out["bypasses_risk"] is False


def test_hold_when_risk_fails() -> None:
    out = TradingKernel().run_cycle(
        KernelCycleInput(
            side="buy",
            risk_engine_passed=False,
            safety_engine_passed=True,
            decision="APPROVE",
            spread=Decimal("0.3"),
            confidence=Decimal("80"),
        )
    )
    assert out["decision"] == "HOLD"
    assert out["allow_execution_path"] is False


def test_approve_advisory_never_order_send() -> None:
    out = TradingKernel().run_cycle(
        KernelCycleInput(
            side="buy",
            risk_engine_passed=True,
            safety_engine_passed=True,
            decision="APPROVE",
            spread=Decimal("0.3"),
            confidence=Decimal("80"),
            news_blackout=False,
            kill_switch=False,
        )
    )
    assert out["decision"] == "APPROVE"
    assert out["allow_execution_path"] is True
    assert out["advisory_only"] is True
    assert out["never_order_send"] is True
    assert out["execution_pipeline_unchanged"] is True
    assert out["events"]
    assert out["graph"]["nodes"]


def test_events_auditable() -> None:
    kernel = TradingKernel()
    out = kernel.run_cycle(
        KernelCycleInput(
            risk_engine_passed=True,
            safety_engine_passed=True,
            decision="HOLD",
            spread=Decimal("0.4"),
            confidence=Decimal("70"),
        )
    )
    listed = kernel.list_events(trace_id=out["trace_id"])
    assert listed["status"] == "available"
    assert listed["events"]
    assert all("event_id" in e or "id" in e for e in listed["events"])


def test_stage_and_deterministic_replay() -> None:
    kernel = TradingKernel()
    out = kernel.run_cycle(
        KernelCycleInput(
            risk_engine_passed=True,
            safety_engine_passed=True,
            decision="APPROVE",
            spread=Decimal("0.4"),
            confidence=Decimal("70"),
            news_blackout=False,
            kill_switch=False,
        )
    )
    stage = kernel.stage_replay(trace_id=out["trace_id"])
    assert stage["status"] == "available"
    assert stage["mode"] == "stage"
    det = kernel.deterministic_replay_cycle(out["trace_id"])
    assert det["mode"] == "deterministic"
    assert det["deterministic"] is True
    assert det["status"] == "available"


def test_plugins_isolated() -> None:
    kernel = TradingKernel()
    plugin: KernelPlugin = _ProbePlugin()
    kernel.plugins.register(plugin)
    out = kernel.run_cycle(
        KernelCycleInput(
            risk_engine_passed=True,
            safety_engine_passed=True,
            decision="HOLD",
            spread=Decimal("0.4"),
            confidence=Decimal("70"),
            plugin_snapshot={"side": "buy"},
        )
    )
    plugin_stage = next(
        (n for n in out["graph"]["nodes"] if n["stage"] == "plugins"), None
    )
    assert plugin_stage is not None
    results = plugin_stage["outputs"]["results"]
    assert results[0]["isolated"] is True
    assert "order_send" not in results[0]
    assert "risk_engine_passed" not in results[0]
    assert "safety_engine_passed" not in results[0]


def test_certification_never_auto_live() -> None:
    cert = TradingKernel().certification(go_nogo="GO")
    assert cert.get("auto_promote") is False
    assert cert.get("never_order_send") is True
    assert cert.get("human_gate_required") is True
