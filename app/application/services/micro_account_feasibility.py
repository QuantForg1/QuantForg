"""Micro Account Mode feasibility report builder (offline / advisory).

Does not modify Institutional Mode, RiskEngine defaults, or live execution.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.micro_account_mode import (
    DEFAULT_MICRO_ACCOUNT_PROFILE,
    DEFAULT_REFERENCE_ATR,
    MicroAccountProfile,
    MicroTradability,
    build_recommended_policy,
    equity_floor_for_risk,
    evaluate_balance,
    stop_distance_from_atr,
    dollar_risk_at_lots,
)
from app.domain.trading.gold_only import GOLD_SYMBOL


_ATR_SENSITIVITY: tuple[Decimal, ...] = (
    Decimal("8"),
    Decimal("10"),
    Decimal("12"),
    Decimal("15"),
    Decimal("20"),
)


def run_micro_account_feasibility(
    *,
    atr: Decimal = DEFAULT_REFERENCE_ATR,
    profile: MicroAccountProfile = DEFAULT_MICRO_ACCOUNT_PROFILE,
    atr_grid: tuple[Decimal, ...] = _ATR_SENSITIVITY,
) -> dict[str, Any]:
    """Build feasibility matrix for supported micro balances."""
    generated_at = datetime.now(UTC)
    balances = [
        evaluate_balance(eq, atr=atr, profile=profile)
        for eq in profile.supported_balances
    ]

    stop = stop_distance_from_atr(atr, multiplier=profile.atr_stop_multiplier)
    min_loss = dollar_risk_at_lots(
        lots=profile.broker_min_lot,
        stop_distance=stop,
        contract_size=profile.contract_size,
    )

    safe_balances = [
        str(b.equity) for b in balances if b.tradability is MicroTradability.SAFE
    ]
    conditional_balances = [
        str(b.equity)
        for b in balances
        if b.tradability is MicroTradability.CONDITIONAL
    ]
    not_tradable = [
        str(b.equity)
        for b in balances
        if b.tradability is MicroTradability.NOT_TRADABLE
    ]

    # Exact equity thresholds (not limited to supported ladder).
    safe_floor = equity_floor_for_risk(
        dollar_risk_at_min_lot=min_loss,
        risk_pct=profile.recommended_max_risk_pct,
    )
    hard_floor = equity_floor_for_risk(
        dollar_risk_at_min_lot=min_loss,
        risk_pct=profile.hard_max_risk_pct,
    )
    institutional_floor = equity_floor_for_risk(
        dollar_risk_at_min_lot=min_loss,
        risk_pct=Decimal("1.0"),
    )

    # First supported ladder balance that is SAFE / CONDITIONAL at this ATR.
    first_safe_supported = next(
        (str(b.equity) for b in balances if b.tradability is MicroTradability.SAFE),
        None,
    )
    first_conditional_supported = next(
        (
            str(b.equity)
            for b in balances
            if b.tradability is MicroTradability.CONDITIONAL
        ),
        None,
    )

    sensitivity: list[dict[str, Any]] = []
    for grid_atr in atr_grid:
        row_balances = [
            evaluate_balance(eq, atr=grid_atr, profile=profile)
            for eq in profile.supported_balances
        ]
        g_stop = stop_distance_from_atr(
            grid_atr, multiplier=profile.atr_stop_multiplier
        )
        g_loss = dollar_risk_at_lots(
            lots=profile.broker_min_lot,
            stop_distance=g_stop,
            contract_size=profile.contract_size,
        )
        sensitivity.append(
            {
                "atr": str(grid_atr),
                "stop_distance": str(g_stop),
                "dollar_risk_at_min_lot": str(g_loss),
                "equity_floor_safe": str(
                    equity_floor_for_risk(
                        dollar_risk_at_min_lot=g_loss,
                        risk_pct=profile.recommended_max_risk_pct,
                    )
                ),
                "equity_floor_hard": str(
                    equity_floor_for_risk(
                        dollar_risk_at_min_lot=g_loss,
                        risk_pct=profile.hard_max_risk_pct,
                    )
                ),
                "by_balance": {
                    str(b.equity): {
                        "min_usable_risk_pct": str(b.min_usable_risk_pct),
                        "tradability": b.tradability.value,
                        "consecutive_losses_to_20pct_dd": (
                            b.consecutive_losses_to_20pct_dd
                        ),
                    }
                    for b in row_balances
                },
            }
        )

    fifty = next((b for b in balances if b.equity == Decimal("50")), None)
    fifty_explicit = (
        "$50 cannot safely trade XAUUSD with broker min_lot 0.01 under "
        "mathematically correct sizing (would require "
        f"{fifty.min_usable_risk_pct}% risk at ATR={atr}, stop={stop}; "
        f"hard max is {profile.hard_max_risk_pct}%). Do not force execution."
        if fifty is not None and fifty.tradability is MicroTradability.NOT_TRADABLE
        else None
    )

    policy = build_recommended_policy(profile=profile, atr=atr)

    return {
        "schema_version": "1.0.0",
        "report_type": "micro_account_feasibility",
        "generated_at": generated_at.isoformat(),
        "symbol": GOLD_SYMBOL,
        "mode_id": profile.mode_id,
        "institutional_mode_modified": False,
        "institutional_unchanged": {
            "quality": DEFAULT_ITE_CONFIG.min_trade_quality_score,
            "confluence": DEFAULT_ITE_CONFIG.min_confluence_score,
            "risk_per_trade_pct": str(DEFAULT_ITE_CONFIG.risk_per_trade_pct),
            "config_version": DEFAULT_ITE_CONFIG.config_version,
            "never_upsize_below_min_lot": True,
        },
        "assumptions": {
            "atr": str(atr),
            "atr_stop_multiplier": str(profile.atr_stop_multiplier),
            "stop_distance": str(stop),
            "broker_min_lot": str(profile.broker_min_lot),
            "contract_size": str(profile.contract_size),
            "dollar_risk_at_min_lot": str(min_loss),
            "formula": "dollar_risk = lots × stop_distance × contract_size",
            "lot_formula": (
                "lots = floor((equity × risk_pct/100) / (stop × contract_size) "
                "/ lot_step) × lot_step; reject if lots < min_lot"
            ),
        },
        "profile": profile.to_dict(),
        "balances": [b.to_dict() for b in balances],
        "summary": {
            "safe_supported_balances": safe_balances,
            "conditional_supported_balances": conditional_balances,
            "not_tradable_supported_balances": not_tradable,
            "first_safe_supported_balance": first_safe_supported,
            "first_conditional_supported_balance": first_conditional_supported,
            "exact_equity_floor_safe": str(safe_floor),
            "exact_equity_floor_hard_max": str(hard_floor),
            "exact_equity_floor_institutional_1pct": str(institutional_floor),
            "xauusd_safely_tradable_at_supported_balances": safe_balances,
            "xauusd_conditionally_tradable_at_supported_balances": (
                conditional_balances
            ),
            "fifty_dollar_explicit": fifty_explicit,
        },
        "atr_sensitivity": sensitivity,
        "recommended_policy": policy,
    }


def report_to_markdown(report: dict[str, Any]) -> str:
    """Render feasibility + policy as markdown."""
    lines: list[str] = []
    assumptions = report.get("assumptions") or {}
    summary = report.get("summary") or {}
    profile = report.get("profile") or {}
    inst = report.get("institutional_unchanged") or {}

    lines.append("# Micro Account Mode — Feasibility Report")
    lines.append("")
    lines.append(f"- Generated at: `{report.get('generated_at', '—')}`")
    lines.append(f"- Mode: `{report.get('mode_id')}`")
    lines.append(f"- Symbol: `{report.get('symbol')}`")
    lines.append(
        f"- Institutional Mode modified: "
        f"**{report.get('institutional_mode_modified')}**"
    )
    lines.append(
        f"- Institutional unchanged: Q={inst.get('quality')} · "
        f"C={inst.get('confluence')} · risk={inst.get('risk_per_trade_pct')}% · "
        f"`{inst.get('config_version')}`"
    )
    lines.append("")
    lines.append("## Assumptions")
    lines.append("")
    lines.append(
        f"- ATR={assumptions.get('atr')} · multiplier="
        f"{assumptions.get('atr_stop_multiplier')} · "
        f"stop={assumptions.get('stop_distance')}"
    )
    lines.append(
        f"- Broker min_lot={assumptions.get('broker_min_lot')} · "
        f"contract_size={assumptions.get('contract_size')} · "
        f"dollar risk at min_lot=**${assumptions.get('dollar_risk_at_min_lot')}**"
    )
    lines.append(f"- Formula: `{assumptions.get('formula')}`")
    lines.append(
        f"- Recommended max risk: {profile.get('recommended_max_risk_pct')}% · "
        f"Hard max: {profile.get('hard_max_risk_pct')}%"
    )
    lines.append("")
    lines.append("## Feasibility by supported balance")
    lines.append("")
    lines.append(
        "| Equity | Min usable risk % | Smallest executable lot | "
        "Max loss / trade | Losses → 20% DD | Tradability |"
    )
    lines.append("|---:|---:|---:|---:|---:|---|")
    for b in report.get("balances") or []:
        lot = b.get("smallest_executable_lot")
        lot_txt = lot if lot is not None else "— (reject)"
        lines.append(
            f"| ${b.get('equity')} | {b.get('min_usable_risk_pct')}% | "
            f"{lot_txt} | ${b.get('max_loss_per_trade')} | "
            f"{b.get('consecutive_losses_to_20pct_dd')} | "
            f"**{b.get('tradability')}** |"
        )
    lines.append("")

    fifty = summary.get("fifty_dollar_explicit")
    if fifty:
        lines.append("### $50 explicit finding")
        lines.append("")
        lines.append(fifty)
        lines.append("")

    lines.append("## Exact balances where XAUUSD becomes safely tradable")
    lines.append("")
    lines.append(
        f"- Exact equity floor for ≤{profile.get('recommended_max_risk_pct')}% "
        f"(safe): **${summary.get('exact_equity_floor_safe')}**"
    )
    lines.append(
        f"- Exact equity floor for ≤{profile.get('hard_max_risk_pct')}% "
        f"(hard max / conditional): **${summary.get('exact_equity_floor_hard_max')}**"
    )
    lines.append(
        f"- Exact equity floor for Institutional 1%: "
        f"**${summary.get('exact_equity_floor_institutional_1pct')}**"
    )
    lines.append(
        f"- Safe among supported ladder ($50/$100/$250/$500): "
        f"**{summary.get('xauusd_safely_tradable_at_supported_balances') or 'none'}**"
    )
    lines.append(
        f"- Conditional among supported ladder: "
        f"**{summary.get('xauusd_conditionally_tradable_at_supported_balances') or 'none'}**"
    )
    lines.append("")
    lines.append("## Recommended micro-account policy")
    lines.append("")
    policy = report.get("recommended_policy") or {}
    micro = policy.get("micro_policy") or {}
    lines.append(
        f"- Activation: `{micro.get('activation')}` "
        f"(enabled_by_default={micro.get('enabled_by_default')})"
    )
    lines.append(
        f"- Recommended max risk: {micro.get('recommended_max_risk_pct')}% · "
        f"Hard max: {micro.get('hard_max_risk_pct')}%"
    )
    lines.append(
        f"- If calculated lots < min_lot: **{micro.get('if_calculated_lots_below_min_lot')}**"
    )
    lines.append(
        f"- Never fake lots / bypass broker min / exceed hard max: "
        f"**{micro.get('never_fake_lots')}** / "
        f"**{micro.get('never_bypass_broker_minimum')}** / "
        f"**{micro.get('never_exceed_hard_max_risk')}**"
    )
    lines.append("")
    for rec in policy.get("recommendations") or []:
        lines.append(f"- {rec}")
    lines.append("")
    lines.append("## ATR sensitivity")
    lines.append("")
    lines.append(
        "| ATR | Stop | $ risk @ 0.01 | Safe equity floor | Hard equity floor |"
    )
    lines.append("|---:|---:|---:|---:|---:|")
    for row in report.get("atr_sensitivity") or []:
        lines.append(
            f"| {row.get('atr')} | {row.get('stop_distance')} | "
            f"${row.get('dollar_risk_at_min_lot')} | "
            f"${row.get('equity_floor_safe')} | "
            f"${row.get('equity_floor_hard')} |"
        )
    lines.append("")
    lines.append("## Per-balance detail")
    lines.append("")
    for b in report.get("balances") or []:
        lines.append(f"### ${b.get('equity')}")
        lines.append("")
        for reason in b.get("reasons") or []:
            lines.append(f"- {reason}")
        for rec in b.get("recommendations") or []:
            lines.append(f"- Recommend: {rec}")
        lines.append("")
    return "\n".join(lines)
