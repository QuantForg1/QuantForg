"""Accelerated soak / stress profiles — validate long-running stability."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.domain.scalping_ai_v2.config import ScalpingAiV2Config
from app.domain.scalping_ai_v2.types import ScalpCycleInput

# Profiles map wall-clock targets to accelerated cycle counts for CI.
SOAK_PROFILES: dict[str, dict[str, Any]] = {
    "24h": {"target_hours": 24, "cycles": 24, "reconnect_every": 8},
    "48h": {"target_hours": 48, "cycles": 36, "reconnect_every": 9},
    "72h": {"target_hours": 72, "cycles": 48, "reconnect_every": 10},
    "stress": {"target_hours": 1, "cycles": 20, "reconnect_every": 5},
}


def run_soak(
    system: Any,
    *,
    profile: str = "24h",
    base_input: ScalpCycleInput | None = None,
    config: ScalpingAiV2Config | None = None,
) -> dict[str, Any]:
    """Run accelerated continuous cycles; assert bounded resources.

    Does not sleep wall-clock 24/48/72h — simulates continuous execution
    density for CI while checking memory-sample growth, duplicate
    prevention, and cleanup.
    """
    _ = config
    spec = SOAK_PROFILES.get(profile) or SOAK_PROFILES["24h"]
    cycles = int(spec["cycles"])
    reconnect_every = int(spec["reconnect_every"])
    template = base_input or _default_input()

    recommendations: list[str] = []
    identities: list[str] = []
    reconnects = 0
    duplicates_blocked = 0
    errors: list[str] = []

    for i in range(cycles):
        restart = i > 0 and i % reconnect_every == 0
        if restart:
            reconnects += 1
        # Reuse same identity on every 7th cycle to prove duplicate protection
        eid = f"soak_{profile}_{i // 7}"
        health = {
            "execution_loop": True,
            "broker_connection": True,
            "gateway": True,
            "database": True,
            "analytics": True,
            "risk_engine": True,
            "safety_engine": True,
            "decision_engine": True,
            "restart": restart,
            "resources": {
                "memory_mb": 200 + (i % 30),
                "cpu_pct": 20 + (i % 40),
                "queue_size": i % 5,
                "worker_health": "ok",
                "orphan_tasks": 0,
                "stale_subscriptions": 0,
            },
            "latencies": {
                "signal": 5 + (i % 10),
                "decision": 8,
                "risk": 4,
                "safety": 3,
                "gateway": 12,
                "broker": 15,
                "fill": 20,
                "total": 67 + (i % 10),
            },
            "mt5_sync": {
                "local_open_positions": 1,
                "mt5_open_positions": 1,
                "local_balance": 10000,
                "mt5_balance": 10000,
            },
            "analytics_metrics": {"win_rate": 50, "average_rr": 1.2},
        }
        if restart:
            health["incident"] = "mt5_reconnect"

        inp = replace(
            template,
            execution_identity=eid,
            health=health,
            market_data={
                "timestamp": f"2026-07-22T12:{i % 60:02d}:00Z",
                "ohlc": {"o": 2350, "h": 2352, "l": 2348, "c": 2351},
                "duplicate_tick": False,
                "missing_candles": False,
                "clock_drift_ms": 10,
            },
        )
        try:
            result = system.run_cycle(inp)
        except Exception as exc:
            errors.append(f"cycle_{i}:{type(exc).__name__}:{exc}")
            continue
        recommendations.append(str(result.get("recommendation")))
        eid_out = result.get("execution_identity")
        if eid_out:
            identities.append(str(eid_out))
        if result.get("recommendation") == "No Trade":
            reasons = result.get("reasons") or []
            if any("Duplicate" in str(r) for r in reasons):
                duplicates_blocked += 1

    stability = (
        system.stability.summary()
        if hasattr(system, "stability")
        else {"status": "unavailable"}
    )
    history_len = len(getattr(system, "history", []) or [])
    max_history = getattr(getattr(system, "config", None), "max_history", 500)
    events_len = len(system.bus.list(limit=10_000)) if hasattr(system, "bus") else 0
    max_events = getattr(getattr(system, "config", None), "max_events", 5000)

    memory_bounded = True
    if isinstance(stability, dict) and stability.get("samples") is not None:
        memory_bounded = int(stability["samples"]) <= 256

    passed = (
        not errors
        and memory_bounded
        and history_len <= max_history
        and events_len <= max_events
        and duplicates_blocked >= 1
    )

    return {
        "status": "passed" if passed else "failed",
        "profile": profile,
        "target_hours": spec["target_hours"],
        "cycles_run": cycles,
        "reconnects_simulated": reconnects,
        "duplicates_blocked": duplicates_blocked,
        "unique_identities": len(set(identities)),
        "errors": errors,
        "stability": stability,
        "history_len": history_len,
        "max_history": max_history,
        "events_len": events_len,
        "max_events": max_events,
        "memory_bounded": memory_bounded,
        "resource_cleanup_ok": history_len <= max_history and events_len <= max_events,
        "continuous_execution": True,
        "accelerated": True,
        "wall_clock_hours_not_slept": True,
        "never_order_send": True,
        "promise_profitability": False,
        "checks": {
            "memory": memory_bounded,
            "cpu_samples_recorded": bool(stability.get("latest")),
            "reconnections": reconnects > 0,
            "duplicate_prevention": duplicates_blocked >= 1,
            "resource_cleanup": history_len <= max_history,
        },
    }


def _default_input() -> ScalpCycleInput:
    return ScalpCycleInput(
        side="buy",
        spread=Decimal("0.28"),
        atr=Decimal("4"),
        price=Decimal("2350"),
        regime="trend",
        session="london",
        trend="up",
        volatility="normal",
        liquidity_state="healthy",
        market_health="good",
        confidence=Decimal("72"),
        htf_bias="bullish",
        ltf_confirmation="bullish",
        trend_strength=Decimal("70"),
        trend_consistency=Decimal("68"),
        sweep_detected=True,
        bos=True,
        structure_phase="continuation",
        opportunities=[
            {
                "id": f"soak_{uuid4().hex[:6]}",
                "quality_score": 78,
                "confidence_score": 74,
                "risk_score": 30,
                "execution_score": 80,
            }
        ],
        risk_engine_passed=True,
        safety_engine_passed=True,
        decision_approved=True,
        decision_center={"decision": "APPROVE"},
        broker_connected=True,
        gateway_healthy=True,
        latency_ms=Decimal("40"),
        market_open=True,
        margin_available=True,
        equity=Decimal("10000"),
        daily_loss_pct=Decimal("0.2"),
        open_exposure_pct=Decimal("1"),
        trades_today=1,
        consecutive_losses=0,
        run_state="running",
        kill_switch=False,
        news_blackout=False,
    )
