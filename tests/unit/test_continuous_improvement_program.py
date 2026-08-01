"""Continuous Improvement Program — additive; never fabricates or trades."""

from __future__ import annotations

import pytest

from app.domain.continuous_improvement.continuous_validation import (
    build_continuous_validation,
)
from app.domain.continuous_improvement.models import HARD_LOCKS
from app.domain.continuous_improvement.release_confidence import (
    record_deployment,
    record_rollback,
)
from app.domain.continuous_improvement.trading_effectiveness import (
    build_trading_effectiveness,
)


def test_hard_locks() -> None:
    assert HARD_LOCKS["modifies_trading"] is False
    assert HARD_LOCKS["modifies_ai"] is False
    assert HARD_LOCKS["modifies_oms"] is False
    assert HARD_LOCKS["modifies_mt5"] is False
    assert HARD_LOCKS["modifies_execution_intelligence"] is False
    assert HARD_LOCKS["modifies_adaptive_intelligence"] is False
    assert HARD_LOCKS["modifies_auth"] is False
    assert HARD_LOCKS["modifies_pricing"] is False
    assert HARD_LOCKS["fabricates_metrics"] is False
    assert HARD_LOCKS["additive_only"] is True


def test_validation_records_history() -> None:
    pack = build_continuous_validation(record_history=True)
    assert pack["fabricated"] is False
    assert pack["never_modifies_trading"] is True
    assert "components" in pack
    assert pack["history_count"] >= 1


def test_trading_effectiveness_never_fabricates() -> None:
    pack = build_trading_effectiveness()
    assert pack["fabricated"] is False
    assert pack["observe_only"] is True
    # Unmeasured fields may be null — never invent numbers
    for key in (
        "win_rate",
        "profit_factor",
        "expectancy",
        "signals_generated",
    ):
        val = pack.get(key)
        assert val is None or isinstance(val, (int, float))


def test_release_records() -> None:
    dep = record_deployment(
        platform="railway",
        deployment_id="dep_unit",
        commit_sha="abc123",
        status="SUCCESS",
    )
    assert dep["fabricated"] is False
    rb = record_rollback(
        platform="railway",
        from_deployment="a",
        to_deployment="b",
        reason="unit",
    )
    assert rb["fabricated"] is False


@pytest.mark.asyncio
async def test_program_flags_and_migrations() -> None:
    from app.domain.continuous_improvement.platform import (
        build_continuous_improvement_noc_panels,
        build_continuous_improvement_program,
    )

    pack = await build_continuous_improvement_program()
    flags = pack["flags"]
    assert flags["modifies_trading"] is False
    assert flags["fabricates_metrics"] is False
    assert pack["migrations_pending"] is False
    assert pack["migration_status"] == "No migrations pending."
    assert "continuous_validation" in pack
    assert "trading_effectiveness" in pack
    assert "learning_review" in pack
    assert "release_confidence" in pack
    assert "operational_scorecard" in pack
    assert "historical_trends" in pack
    assert "auto_reports" in pack
    assert pack["learning_review"]["operator_review_only"] is True
    assert pack["learning_review"]["auto_applies"] is False

    noc = await build_continuous_improvement_noc_panels()
    assert noc["flags"]["never_modifies_trading"] is True
    assert "production_validation" in noc
    assert "trading_effectiveness" in noc
    assert "learning_review" in noc
    assert "operational_scorecard" in noc
    assert "historical_trends" in noc
