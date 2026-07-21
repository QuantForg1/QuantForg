"""Unit tests — QuantForg Research & Validation Platform."""

from __future__ import annotations

from decimal import Decimal

from app.domain.research_validation_platform import (
    ResearchValidationConfig,
    ResearchValidationPlatform,
)
from app.domain.research_validation_platform.util import reproducible_hash
from app.domain.trading.gold_only import GOLD_SYMBOL


def test_xauusd_and_hard_locks() -> None:
    status = ResearchValidationPlatform().status()
    assert status["symbol"] == GOLD_SYMBOL
    assert status["allow_live_execution"] is False
    assert status["allow_order_send"] is False
    assert status["require_certification_for_production"] is True
    caps = status["capabilities"]
    assert caps["live_execution_pipeline_unchanged"] is True
    assert caps["never_order_send"] is True
    assert caps["validation_reproducible"] is True
    assert caps["versions_traceable"] is True
    assert caps["certification_mandatory_before_production"] is True
    assert caps["rollback_preserves_audit"] is True
    assert len(status["modules"]) == 10


def test_policies_cannot_enable_live() -> None:
    cfg = ResearchValidationConfig().update(
        {
            "allow_live_execution": True,
            "allow_order_send": True,
            "require_certification_for_production": False,
            "symbol": "EURUSD",
            "min_certification_score": "80",
        }
    )
    assert cfg.allow_live_execution is False
    assert cfg.allow_order_send is False
    assert cfg.require_certification_for_production is True
    assert cfg.symbol == GOLD_SYMBOL
    assert cfg.min_certification_score == Decimal("80")


def test_registry_and_replay_reproducible() -> None:
    platform = ResearchValidationPlatform()
    reg = platform.list_registry()
    assert reg["count"] >= 4
    bars = [
        {"time": "t1", "open": "1", "high": "2", "low": "0.5", "close": "1.5"}
    ]
    a = platform.replay_load(
        {"strategy_key": "trend_following", "version": "v1", "bars": bars}
    )
    b = platform.replay_load(
        {"strategy_key": "trend_following", "version": "v1", "bars": bars}
    )
    assert a["input_hash"] == b["input_hash"]
    assert a["reproducible"] is True
    assert a["invented_bars"] is False
    step = platform.replay_step()
    assert step["current"]["close"] == "1.5"


def test_walk_forward_and_paper_from_supplied() -> None:
    platform = ResearchValidationPlatform()
    empty = platform.walk_forward({"strategy_key": "x"})
    assert empty["status"] == "unavailable"
    wf = platform.walk_forward(
        {
            "strategy_key": "trend_following",
            "version": "v1",
            "folds": [
                {"fold": 1, "score": 70},
                {"fold": 2, "score": 60},
            ],
        }
    )
    assert wf["passed"] is True
    assert wf["reproducible"] is True
    paper = platform.paper(
        {
            "strategy_key": "trend_following",
            "version": "v1",
            "trade_count": 40,
            "profit_factor": "1.5",
            "max_drawdown_pct": "10",
            "win_rate": "55",
        }
    )
    assert paper["passed"] is True
    assert paper["paper_only"] is True
    assert paper["affects_live_execution"] is False


def test_comparison_dashboard() -> None:
    out = ResearchValidationPlatform().compare(
        {
            "runs": [
                {
                    "strategy_key": "a",
                    "version": "1",
                    "profit_factor": "1.5",
                    "sharpe": "1.0",
                    "max_drawdown_pct": "10",
                    "trade_count": 40,
                },
                {
                    "strategy_key": "b",
                    "version": "1",
                    "profit_factor": "0.9",
                    "sharpe": "0.2",
                    "max_drawdown_pct": "30",
                    "trade_count": 10,
                },
            ]
        }
    )
    assert out["status"] == "available"
    assert out["leader"]["strategy_key"] == "a"
    assert out["reproducible"] is True


def test_certification_mandatory_and_release() -> None:
    platform = ResearchValidationPlatform()
    missing = platform.certify({"strategy_key": "trend_following"})
    assert missing["certified"] is False
    assert missing["require_certification_for_production"] is True

    cert = platform.certify(
        {
            "strategy_key": "trend_following",
            "version": "v1",
            "stage_results": {
                "registry": {"passed": True},
                "replay": {"passed": True},
                "walk_forward": {"passed": True, "score": 70},
                "paper": {"passed": True, "score": 70},
                "comparison": {"passed": True},
                "operator_review": {"passed": True},
            },
        }
    )
    assert cert["certified"] is True
    assert cert["affects_live_execution"] is False

    blocked = platform.release(
        {
            "strategy_key": "trend_following",
            "version": "v1",
            "certified": False,
            "operator_approved": True,
        }
    )
    assert blocked["release_allowed"] is False

    allowed = platform.release(
        {
            "strategy_key": "trend_following",
            "version": "v1",
            "certified": True,
            "operator_approved": True,
        }
    )
    assert allowed["release_allowed"] is True
    assert allowed["production_go_live"] is False
    assert allowed["never_order_send"] is True


def test_version_traceable_and_rollback_preserves_audit() -> None:
    platform = ResearchValidationPlatform()
    v1 = platform.record_version(
        {
            "strategy_key": "trend_following",
            "version": "v1.0.0",
            "parameters": {"n": 1},
        }
    )
    v2 = platform.record_version(
        {
            "strategy_key": "trend_following",
            "version": "v1.1.0",
            "parameters": {"n": 2},
            "parent_version": "v1.0.0",
        }
    )
    assert v1["traceable"] is True
    assert v2["content_hash"] != v1["content_hash"]
    assert platform.versions.active_version("trend_following") == "v1.0.0"

    # Activate v1.1 then rollback
    platform.versions.set_active("trend_following", "v1.1.0")
    rb = platform.rollback(
        {
            "strategy_key": "trend_following",
            "target_version": "v1.0.0",
            "reason": "test",
        }
    )
    assert rb["rolled_back"] is True
    assert rb["audit_preserved"] is True
    audit = platform.rollback_audit()
    assert audit["status"] == "available"
    assert audit["items"][0]["to_version"] == "v1.0.0"
    # Prior versions still listed
    listed = platform.list_versions(strategy_key="trend_following")
    assert len(listed["versions"]) >= 2


def test_observatory_never_fabricates() -> None:
    platform = ResearchValidationPlatform()
    empty = platform.observatory({"strategy_key": "x"})
    assert empty["status"] == "unavailable"
    obs = platform.observatory(
        {
            "strategy_key": "trend_following",
            "metrics": {"sharpe": "0.8", "trades": 30},
        }
    )
    assert obs["status"] == "available"
    assert obs["promise_profitability"] is False
    assert all(p["invented"] is False for p in obs["panels"])


def test_reproducible_hash_stable() -> None:
    a = reproducible_hash({"b": 1, "a": 2})
    b = reproducible_hash({"a": 2, "b": 1})
    assert a == b
