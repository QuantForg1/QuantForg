"""Gold Unified Brain — observe-only coordination + activation checklist.

Never ARM/ENABLE. Never order_send. Never claims profitability.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.micro_account_mode import evaluate_balance
from app.domain.trading.gold_unified_brain import (
    decide_gold,
    inventory_strategies,
)
from app.domain.trading.xauusd_specs import specs_dict
from core.logging import get_logger

logger = get_logger(__name__)

_CONFIRM_PHRASE = "I UNDERSTAND THIS USES REAL MONEY"


def activation_workflow_document() -> dict[str, Any]:
    """Official operator ARM → ENABLE prerequisites (read-only)."""
    return {
        "controller_states": [
            "DISABLED",
            "READY_FOR_REVIEW",
            "ARMED",
            "ENABLED",
            "PAUSED",
            "KILLED",
        ],
        "confirmation_phrase": _CONFIRM_PHRASE,
        "role_required": "OWNER or ADMIN",
        "endpoints": {
            "status": "GET /live-trading/status",
            "arm": "POST /live-trading/arm",
            "enable": "POST /live-trading/enable",
            "pause": "POST /live-trading/pause",
            "disable": "POST /live-trading/disable",
        },
        "arm_prerequisites": [
            "confirmed=true",
            f"confirmation_phrase exactly '{_CONFIRM_PHRASE}'",
            "gateway_online",
            "mt5_connected",
            "mt5_attached",
            "broker ownership OWNED",
            "account_available with equity>0 and balance>0",
        ],
        "enable_prerequisites": [
            "controller state ARMED or PAUSED",
            "same confirmation phrase",
            "activation probes still pass",
            "EXECUTION_ENABLED=true (env) — does not alone authorize",
        ],
        "never_auto": [
            "Deploy / restart never ENABLE",
            "OpenAI advice never ENABLE",
            "Strategy selection never ENABLE",
            "Unified brain decision never ENABLE",
        ],
        "restart_semantics": (
            "If previously ENABLED, restart recovers to PAUSED until "
            "gateway/MT5 ownership probes allow safe resume"
        ),
        "authorizes_trade_on_read": False,
    }


def micro_account_xauusd_feasibility(
    equity: Decimal | float | str = "50",
) -> dict[str, Any]:
    """Broker-min-lot feasibility for small balances — no fake lots."""
    eq = Decimal(str(equity))
    result = evaluate_balance(eq)
    return {
        "symbol_specs": specs_dict(),
        "equity": str(eq),
        "feasibility": result.to_dict(),
        "disclaimer": (
            "A $50 account is typically NOT_TRADABLE on XAUUSD at broker "
            "min_lot 0.01 under hard risk ceilings. Do not widen risk to "
            "manufacture trades. No profit guarantee."
        ),
    }


def evidence_status() -> dict[str, Any]:
    """Honest evaluation evidence status — no fabricated OOS results."""
    return {
        "walk_forward_executed_this_release": False,
        "out_of_sample_profitability_claimed": False,
        "live_eligible_profiles": [
            s["id"] for s in inventory_strategies()["live_eligible_profiles"]
        ],
        "promotion_gate": (
            "A strategy must pass predeclared OOS acceptance criteria before "
            "being treated as proven edge. Registry eligibility ≠ proven edge."
        ),
        "available_pipelines": [
            "GET /walkforward/*",
            "GET /backtest/*",
            "GET /research-validation-platform/*",
            "GET /micro-account-analyzer/*",
        ],
        "limitations": [
            "This endpoint does not fabricate tick-level backtest PnL",
            "MT5 real-tick coverage depends on gateway history availability",
            "Costs (spread/commission/slippage) must be applied in any OOS run",
        ],
    }


def build_gold_brain_status() -> dict[str, Any]:
    """Aggregate inventory + activation + evidence + worker blockers."""
    from app.application.services.execution_worker_status import (
        collect_execution_worker_status,
    )
    from app.application.services.signal_notification_policy import (
        notification_policy_diagnostics,
    )
    from app.domain.trading.gold_only import gold_only_diagnostics

    worker = collect_execution_worker_status()
    invent = inventory_strategies()
    return {
        "status": "ok",
        "symbol_focus": "XAUUSD",
        "unified_engine": "ai_scalping.strategies + gold_unified_brain facade",
        "duplicate_engines": False,
        "gold_only": gold_only_diagnostics(),
        "inventory": invent,
        "activation_workflow": activation_workflow_document(),
        "notification_policy": notification_policy_diagnostics(),
        "live_trading": worker.get("live_trading"),
        "continuous_trading_authorized": worker.get("continuous_trading_authorized"),
        "blockers": worker.get("blockers"),
        "advisory_blockers": worker.get("advisory_blockers"),
        "openai": worker.get("openai"),
        "worker": worker.get("worker"),
        "execution_enabled": worker.get("execution_enabled"),
        "evidence": evidence_status(),
        "micro_account_example_50usd": micro_account_xauusd_feasibility("50"),
        "authorizes_trade": False,
        "profitability_claimed": False,
    }


def decide_from_score(score: dict[str, Any]) -> dict[str, Any]:
    """Run unified coordination on a provided score snapshot (no orders)."""
    decision = decide_gold(score)
    out = decision.to_dict()
    out["openai_authorizes"] = False
    out["live_controller_bypass"] = False
    return out
