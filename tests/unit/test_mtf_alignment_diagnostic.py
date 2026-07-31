"""Unit tests — MTF alignment diagnostic (evidence taxonomy only)."""

from __future__ import annotations

from app.application.services.mtf_alignment_diagnostic import (
    analyze_cycle,
    diagnose_mtf_alignment,
    propose_improvements,
)


def _cycle(
    *,
    h1: str,
    m15: str,
    m5: str,
    score: int = 50,
    bos: int = 10,
    choch: int = 8,
    bos_trend: str = "up",
    ob: int = 1,
    fvg: int = 2,
) -> dict:
    return {
        "trace_id": f"t-{h1}-{m15}-{m5}",
        "trend": {
            "h4": "range",
            "h1": h1,
            "m15": m15,
            "m5": m5,
            "aligned": False,
            "score": score,
        },
        "quality": {"score": 72},
        "confluence": {
            "total": 58,
            "components": {
                "bos": 90,
                "choch": 90,
                "order_block": 85,
                "fair_value_gap": 80,
                "liquidity_sweep": 20,
            },
            "engine_factors": {"liquidity": 20, "structure": 90},
        },
        "rejection": {
            "primary": "mtf_not_aligned",
            "all_codes": ["mtf_not_aligned"],
            "decision_reasons": [
                f"MTF up: H4=range H1={h1} M15={m15} M5={m5} score={score} not aligned",
                f"M15 structure events bos={bos} choch={choch}",
                f"Latest BOS trend={bos_trend}",
                f"Active order blocks={ob}",
                f"Open FVGs={fvg}",
            ],
        },
    }


def test_m5_only_blocker_example() -> None:
    rec = analyze_cycle(_cycle(h1="up", m15="up", m5="down"))
    assert rec is not None
    assert rec.fully_aligned is False
    assert rec.blockers == ("M5",)
    assert rec.execution_trigger == "m5_entry_conflict"
    assert rec.conflict_signature == "H1=up|M15=up|M5=down"


def test_m15_opposite_m5_agree() -> None:
    rec = analyze_cycle(_cycle(h1="up", m15="down", m5="up"))
    assert rec is not None
    assert rec.blockers == ("M15",)
    assert rec.execution_trigger == "m15_confirmation_conflict"


def test_both_blockers() -> None:
    rec = analyze_cycle(_cycle(h1="up", m15="down", m5="range"))
    assert rec is not None
    assert set(rec.blockers) == {"M15", "M5"}


def test_diagnose_aggregate() -> None:
    cycles = [
        _cycle(h1="up", m15="up", m5="down"),
        _cycle(h1="up", m15="down", m5="up"),
        _cycle(h1="up", m15="down", m5="down"),
        _cycle(h1="up", m15="range", m5="range"),
        _cycle(h1="up", m15="up", m5="up", score=100),
    ]
    # last one fully aligned
    report = diagnose_mtf_alignment(cycles)
    assert report["cycles_analyzed"] == 5
    assert report["full_h1_m15_m5_alignment"]["count"] == 1
    assert report["thresholds_changed"] is False
    assert report["which_timeframe_prevented_alignment"]["M5_only"] == 1
    assert report["which_timeframe_prevented_alignment"]["M15_only"] == 1
    proposals = propose_improvements(report)
    assert any(p["id"] == "P_SAFE" for p in proposals)
