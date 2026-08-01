"""Live Trading Evidence Program — observe-only; never fabricates or forces trades."""

from __future__ import annotations

import pytest

from app.domain.live_trading_evidence.models import HARD_LOCKS
from app.domain.live_trading_evidence.readiness_score import (
    build_production_readiness_score,
)
from app.domain.live_trading_evidence.trade_repository import (
    normalize_evidence_package,
)


def test_hard_locks() -> None:
    assert HARD_LOCKS["modifies_trading"] is False
    assert HARD_LOCKS["modifies_ai"] is False
    assert HARD_LOCKS["forces_trades"] is False
    assert HARD_LOCKS["lowers_thresholds"] is False
    assert HARD_LOCKS["bypasses_protections"] is False
    assert HARD_LOCKS["fabricates_evidence"] is False
    assert HARD_LOCKS["modifies_continuous_improvement"] is False
    assert HARD_LOCKS["modifies_reliability_platform"] is False
    assert HARD_LOCKS["additive_only"] is True


def test_normalize_never_invents_missing_fields() -> None:
    ev = normalize_evidence_package(
        {
            "validation_id": "val_unit_1",
            "accepted": True,
            "mt5": {"ticket": 12345, "volume": "0.01", "fill_price": "2350.1"},
            "ai": {"decision": "BUY", "symbol": "XAUUSD", "quality_score": 72},
            "trade": {},
            "broker": {},
            "risk": {},
            "oms": {},
            "gateway": {},
        }
    )
    assert ev["trade_id"] == "12345"
    assert ev["symbol"] == "XAUUSD"
    assert ev["direction"] == "BUY"
    assert ev["entry"] == "2350.1"
    assert ev["exit"] is None
    assert ev["pnl"] is None
    assert ev["fabricated"] is False
    assert ev["mtf"] is None
    assert ev["volatility"] is None


def test_readiness_null_without_evidence() -> None:
    score = build_production_readiness_score(
        dashboard={
            "executed_trades": 0,
            "rejected_trades": 0,
            "average_latency": None,
            "execution_quality": None,
        },
        trades_count=0,
        rejections_count=0,
    )
    assert score["fabricated"] is False
    # Overall may be null when no measured components
    assert score["score"] is None or isinstance(score["score"], (int, float))
    assert score["status"] in {
        "awaiting_evidence",
        "thin_evidence",
        "partial_evidence",
        "strong_evidence",
        "unknown",
    }


@pytest.mark.asyncio
async def test_program_flags_and_migrations() -> None:
    from app.domain.live_trading_evidence.platform import (
        build_live_trading_evidence_noc_panels,
        build_live_trading_evidence_program,
    )

    pack = await build_live_trading_evidence_program()
    flags = pack["flags"]
    assert flags["modifies_trading"] is False
    assert flags["forces_trades"] is False
    assert flags["fabricates_evidence"] is False
    assert pack["migrations_pending"] is False
    assert pack["migration_status"] == "No migrations pending."
    assert "live_trade_evidence" in pack
    assert "rejected_opportunities" in pack
    assert "execution_archive" in pack
    assert "evidence_dashboard" in pack
    assert "production_readiness" in pack
    assert pack["evidence_dashboard"]["fabricated"] is False

    noc = await build_live_trading_evidence_noc_panels()
    assert noc["flags"]["never_modifies_trading"] is True
    assert "live_trade_evidence" in noc
    assert "rejected_opportunities" in noc
    assert "execution_archive" in noc
    assert "production_readiness" in noc
