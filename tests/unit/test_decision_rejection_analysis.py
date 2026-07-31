"""Unit tests — AI Decision Engine rejection analysis (advisory only)."""

from __future__ import annotations

from app.application.services.decision_rejection_analysis import (
    _normalize_from_diagnostics_cycle,
    analyze_decision_rejections,
)
from app.application.services.strategy_diagnostics import (
    reset_strategy_diagnostics_store,
)


def _sample_cycle(
    *,
    primary: str = "mtf_not_aligned",
    quality: int = 69,
    confluence: int = 57,
    mtf: int = 42,
) -> dict:
    return {
        "recorded_at": "2026-07-31T04:00:00+00:00",
        "trace_id": f"trace-{primary}-{quality}-{confluence}-{mtf}",
        "signal_id": f"sig-{primary}",
        "market_session": "tokyo",
        "session_allowed": True,
        "cycle_outcome": "no_trade",
        "decision_action": "NO_TRADE",
        "forwarded_to_oms": False,
        "executed": False,
        "rejected": True,
        "trend": {
            "h4": "range",
            "h1": "up",
            "m15": "down",
            "m5": "range",
            "aligned": False,
            "score": mtf,
        },
        "quality": {
            "score": quality,
            "required": 80,
            "difference": quality - 80,
            "passed": quality >= 80,
        },
        "confluence": {
            "total": confluence,
            "required": 80,
            "difference": confluence - 80,
            "passed": confluence >= 80,
            "components": {
                "smc": 82,
                "liquidity_sweep": 20,
                "bos": 90,
                "choch": 90,
                "trend_alignment": mtf,
                "news_filter": 100,
            },
            "engine_factors": {
                "mtf": 21,
                "liquidity": 20,
                "quality": quality,
                "session": 100,
                "news": 100,
                "spread": 93,
                "volatility": 80,
                "structure": 90,
            },
        },
        "rejection": {
            "primary": primary,
            "secondary": "quality_below_threshold",
            "tertiary": "confidence_below_threshold",
            "all_codes": [
                primary,
                "quality_below_threshold",
                "confidence_below_threshold",
                "no_liquidity_context",
            ],
            "decision_reasons": [
                f"MTF up: H4=range H1=up M15=down M5=range score={mtf} not aligned",
                f"Trade quality {quality} below gate",
                "Session tokyo open for 24/7 desk (*2, quality=55, riskx=0.70).",
                "News protection disabled (no reliable calendar feed required).",
                "Spread 0.474 elevated — soft score 93 (reject only above 1.50)",
                "ATR 0.13% of price acceptable",
                "AI quality gates rejected — NO_TRADE",
                "Weak structure score 55 < 70",
                "Insufficient liquidity score 20 < 60",
                "Momentum 40 < 65 — no confirmation",
                "Confidence 57 < adaptive 82 (normal)",
                "Trade quality 69 < adaptive 82 (normal)",
                "PA confluence 48 < 55",
                "Eligibility failed — NO_TRADE",
            ],
        },
        "sizing": {"atr": 5.06, "risk_pct": 8.0, "approved_lots": 0.0},
        "atr": 5.06,
        "explain": {
            "stages": [
                {"key": "session", "status": "PASS"},
                {"key": "mtf", "status": "FAIL"},
                {"key": "quality", "status": "FAIL"},
                {"key": "confluence", "status": "FAIL"},
                {"key": "risk", "status": "FAIL"},
                {"key": "safety", "status": "PASS"},
            ]
        },
    }


def test_normalize_parses_spread_atr_and_ai_checks() -> None:
    ev = _normalize_from_diagnostics_cycle(_sample_cycle())
    assert ev["quality_score"] == 69
    assert ev["confluence_score"] == 57
    assert ev["mtf_score"] == 42
    assert ev["spread"] == 0.474
    assert ev["atr_pct"] == 0.13
    assert "ai_check_fail:strong_structure" in ev["codes"]
    assert "ai_check_fail:high_liquidity" in ev["codes"]
    assert "ai_check_fail:adaptive_confidence" in ev["codes"]
    # Cascading risk FAIL with lots=0 must not invent a risk family hit alone
    assert "risk" not in ev["stage_fails"]
    assert "mtf" in ev["stage_fails"]


def test_analyze_decision_rejections_pareto_from_diagnostics(
    tmp_path, monkeypatch
) -> None:
    reset_strategy_diagnostics_store()
    from app.application.services.strategy_diagnostics import (
        get_strategy_diagnostics_store,
    )
    from app.domain.institutional_trading.ai_scalping import diagnostics as ai_diag

    # Isolate durable journals so leftover local JSONL cannot pollute averages.
    evidence = tmp_path / "ite_cycle_evidence.jsonl"
    ai_path = tmp_path / "ai_scalping_diagnostics_v6.jsonl"
    monkeypatch.setattr(
        "app.application.services.cycle_evidence._evidence_path",
        lambda: evidence,
    )
    monkeypatch.setattr(ai_diag, "_STORE", None)
    store_ai = ai_diag.ScalpingDiagnosticsStore()
    store_ai._path = ai_path
    monkeypatch.setattr(ai_diag, "_STORE", store_ai)

    store = get_strategy_diagnostics_store()
    for i in range(10):
        c = _sample_cycle(quality=69, confluence=57, mtf=42)
        c["trace_id"] = f"trace-{i}"
        c["signal_id"] = f"sig-{i}"
        c["recorded_at"] = f"2026-07-31T04:00:{i:02d}+00:00"
        # Bypass durable side-effects; analysis reads the in-memory store.
        with store._lock:
            store._cycles.append(dict(c))

    report = analyze_decision_rejections(limit=1000)
    assert report["advisory_only"] is True
    assert report["mutates_engines"] is False
    assert report["thresholds_changed"] is False
    assert report["cycles_analyzed"] == 10
    assert report["outcomes"]["rejection_rate_pct"] == 100.0
    assert report["averages"]["quality_score"] == 69.0
    assert report["averages"]["mtf_score"] == 42.0
    assert report["averages"]["confidence"] == 57.0
    primary = report["rejection_frequency_by_primary_code"][0]
    assert primary["code"] == "mtf_not_aligned"
    assert primary["share_pct"] == 100.0
    families = {
        row["family"]: row["share_of_cycles_pct"]
        for row in report["rejection_frequency_by_filter_family"]
    }
    assert families["mtf_alignment"] == 100.0
    assert families["ai_quality"] == 100.0
    assert families["liquidity"] == 100.0
    assert "rejection_combinations" in report
    assert report["ai_quality_check_fail_frequency"]
    soft = {
        row["family"]: row["share_of_cycles_pct"]
        for row in report.get("soft_observation_frequency_by_filter_family") or []
    }
    assert soft.get("spread") == 100.0
    assert soft.get("session") == 100.0