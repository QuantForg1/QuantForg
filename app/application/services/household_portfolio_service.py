"""Phase 3 household portfolio orchestration (read-only)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from app.application.dto.broker import BrokerAccountDTO
from app.application.dto.portfolio import PortfolioDTO
from app.domain.portfolio_household.aggregation import (
    AccountMetricSlice,
    HouseholdPortfolio,
    PositionSlice,
    account_from_live_snapshot,
    aggregate_household,
    classify_status,
)
from app.domain.portfolio_household.exposure import ExposureRollup, rollup_exposure
from app.domain.portfolio_household.performance import (
    ClosedTrade,
    PerformanceReport,
    build_performance_report,
    performance_to_csv,
)
from app.domain.portfolio_household.risk_allocation import (
    HouseholdRiskCheck,
    evaluate_household_risk,
)


def _broker_code_from_label(acct: BrokerAccountDTO) -> str:
    meta = acct.metadata or {}
    for key in ("broker_code", "broker", "provider"):
        val = meta.get(key)
        if val:
            return str(val).strip().lower()
    # Fall back to label token
    label = (acct.label or "").strip().lower()
    if label:
        return label.split()[0]
    return str(acct.broker_id)[:8]


def build_household_from_sources(
    *,
    user_id: UUID,
    registry_accounts: list[BrokerAccountDTO],
    live: PortfolioDTO | None,
    display_currency: str | None = None,
    verified_fx: dict[str, Decimal] | None = None,
    fx_as_of: datetime | None = None,
    ownership_by_id: dict[str, bool] | None = None,
) -> HouseholdPortfolio:
    """Merge registry + optional live snapshot into an honest household view."""
    ownership_by_id = ownership_by_id or {}
    live_login = str(live.account.login) if live is not None else None
    accounts: list[AccountMetricSlice] = []
    positions: list[PositionSlice] = []

    live_matched = False
    for acct in registry_accounts:
        code = _broker_code_from_label(acct)
        connected = (acct.connection_status or "").lower() in {
            "connected",
            "online",
            "active",
        }
        ownership = ownership_by_id.get(str(acct.id))
        matches_live = (
            live is not None
            and live_login is not None
            and live_login == str(acct.external_account_id).strip()
        )
        if matches_live and live is not None:
            live_matched = True
            snap = {
                "login": live.account.login,
                "balance": live.account.balance,
                "equity": live.account.equity,
                "margin": live.account.margin,
                "free_margin": live.account.free_margin,
                "profit": live.account.profit,
                "currency": live.account.currency,
                "server": live.account.server,
            }
            accounts.append(
                account_from_live_snapshot(
                    broker_account_id=str(acct.id),
                    broker_code=code,
                    broker_name=acct.label or code,
                    snapshot=snap,
                    ownership_verified=ownership if ownership is not None else True,
                    active_positions=live.position_count,
                    pending_orders=live.pending_order_count,
                    as_of=live.synced_at,
                )
            )
            for p in live.positions:
                side = p.side
                positions.append(
                    PositionSlice(
                        account_key=str(acct.id),
                        broker_account_id=str(acct.id),
                        broker_code=code,
                        ticket=p.ticket,
                        symbol=p.symbol,
                        side=side,
                        volume=Decimal(str(p.volume)),
                        profit=(
                            Decimal(str(p.profit))
                            if p.profit not in (None, "")
                            else None
                        ),
                        strategy=_strategy_from_comment(p.comment),
                    )
                )
            continue

        status = classify_status(
            has_live=False,
            as_of=None,
            connected=connected if acct.connection_status else None,
            ownership_verified=ownership,
        )
        if acct.status.lower() in {"revoked", "disabled"}:
            status = "unavailable"
        accounts.append(
            AccountMetricSlice(
                broker_account_id=str(acct.id),
                broker_code=code,
                broker_name=acct.label or code,
                server=acct.server or None,
                login=acct.external_account_id,
                currency=None,
                data_status=status,
                as_of=None,
                ownership_verified=ownership,
                trade_allowed=None,
                note="no_readable_snapshot",
            )
        )

    # Live snapshot with no registry match still surfaces as one live card.
    if live is not None and not live_matched:
        snap = {
            "login": live.account.login,
            "balance": live.account.balance,
            "equity": live.account.equity,
            "margin": live.account.margin,
            "free_margin": live.account.free_margin,
            "profit": live.account.profit,
            "currency": live.account.currency,
            "server": live.account.server,
        }
        accounts.append(
            account_from_live_snapshot(
                broker_account_id=None,
                broker_code="active_session",
                broker_name="Active MT5 session",
                snapshot=snap,
                active_positions=live.position_count,
                pending_orders=live.pending_order_count,
                as_of=live.synced_at,
            )
        )
        for p in live.positions:
            positions.append(
                PositionSlice(
                    account_key=f"live:{live.account.login}",
                    broker_account_id=None,
                    broker_code="active_session",
                    ticket=p.ticket,
                    symbol=p.symbol,
                    side=p.side,
                    volume=Decimal(str(p.volume)),
                    profit=(
                        Decimal(str(p.profit)) if p.profit not in (None, "") else None
                    ),
                    strategy=_strategy_from_comment(p.comment),
                )
            )

    return aggregate_household(
        user_id=user_id,
        accounts=accounts,
        positions=positions,
        display_currency=display_currency,
        verified_fx=verified_fx,
        fx_as_of=fx_as_of,
    )


def _strategy_from_comment(comment: str | None) -> str | None:
    if not comment:
        return None
    text = comment.strip()
    if not text:
        return None
    # Common patterns: strategy=NAME or [NAME]
    lower = text.lower()
    if "strategy=" in lower:
        return text.split("=", 1)[-1].strip()[:64] or None
    return text[:64]


def household_exposure(portfolio: HouseholdPortfolio) -> ExposureRollup:
    return rollup_exposure(
        list(portfolio.positions),
        equity=portfolio.totals.equity,
    )


def household_risk_check(
    portfolio: HouseholdPortfolio,
    *,
    effective: dict[str, Any] | None,
    user_id: UUID | None = None,
    proposed_symbol: str | None = None,
    proposed_risk_pct: Decimal | None = None,
) -> HouseholdRiskCheck:
    return evaluate_household_risk(
        accounts=list(portfolio.accounts),
        positions=list(portfolio.positions),
        effective=effective,
        proposed_symbol=proposed_symbol,
        proposed_risk_pct=proposed_risk_pct,
        user_id=user_id,
    )


def closed_trades_from_deals(
    deals: list[dict[str, Any]],
    *,
    broker_code: str | None = None,
    account_key: str | None = None,
) -> list[ClosedTrade]:
    """Best-effort pairing: only deals with explicit profit + ticket are confirmed."""
    out: list[ClosedTrade] = []
    for d in deals:
        profit = d.get("profit")
        ticket = d.get("ticket") or d.get("position_id") or d.get("order")
        if profit is None or ticket is None:
            continue
        try:
            pnl = Decimal(str(profit))
        except (InvalidOperation, ValueError, TypeError):
            continue
        entry = d.get("time") or d.get("opened_at")
        exit_at = d.get("time") or d.get("closed_at")
        confirmed = bool(d.get("confirmed", True)) and ticket is not None
        out.append(
            ClosedTrade(
                trade_id=str(ticket),
                symbol=str(d.get("symbol") or ""),
                side=str(d.get("type") or d.get("side") or ""),
                pnl=pnl,
                commission=(
                    Decimal(str(d["commission"]))
                    if d.get("commission") is not None
                    else None
                ),
                swap=Decimal(str(d["swap"])) if d.get("swap") is not None else None,
                opened_at=entry if isinstance(entry, datetime) else None,
                closed_at=exit_at if isinstance(exit_at, datetime) else None,
                hold_seconds=None,
                strategy=str(d["strategy"]) if d.get("strategy") else None,
                broker_code=broker_code,
                account_key=account_key,
                signal_id=str(d["signal_id"]) if d.get("signal_id") else None,
                order_ticket=int(ticket) if str(ticket).isdigit() else None,
                position_ticket=int(ticket) if str(ticket).isdigit() else None,
                session=str(d["session"]) if d.get("session") else None,
                confirmed=confirmed,
            )
        )
    return out


def build_household_performance(
    trades: list[ClosedTrade],
) -> PerformanceReport:
    return build_performance_report(trades)


def export_performance_csv(report: PerformanceReport) -> str:
    return performance_to_csv(report)


def serialize_household(portfolio: HouseholdPortfolio) -> dict[str, Any]:
    def _num(v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    totals = portfolio.totals
    return {
        "user_id": portfolio.user_id,
        "as_of": portfolio.as_of.isoformat(),
        "methodology": portfolio.methodology,
        "totals": {
            "display_currency": totals.display_currency,
            "conversion_status": totals.conversion_status,
            "conversion_as_of": (
                totals.conversion_as_of.isoformat() if totals.conversion_as_of else None
            ),
            "balance": _num(totals.balance),
            "equity": _num(totals.equity),
            "margin": _num(totals.margin),
            "free_margin": _num(totals.free_margin),
            "used_margin": _num(totals.used_margin),
            "floating_pnl": _num(totals.floating_pnl),
            "realized_pnl": _num(totals.realized_pnl),
            "daily_pnl": _num(totals.daily_pnl),
            "weekly_pnl": _num(totals.weekly_pnl),
            "monthly_pnl": _num(totals.monthly_pnl),
            "overall_return_pct": _num(totals.overall_return_pct),
            "overall_return_reason": totals.overall_return_reason,
            "active_positions": totals.active_positions,
            "pending_orders": totals.pending_orders,
            "connected_accounts": totals.connected_accounts,
            "accounts_with_metrics": totals.accounts_with_metrics,
            "accounts_excluded": totals.accounts_excluded,
        },
        "accounts": [
            {
                "broker_account_id": a.broker_account_id,
                "broker_code": a.broker_code,
                "broker_name": a.broker_name,
                "server": a.server,
                "login": a.login,
                "currency": a.currency,
                "data_status": a.data_status,
                "as_of": a.as_of.isoformat() if a.as_of else None,
                "balance": _num(a.balance),
                "equity": _num(a.equity),
                "margin": _num(a.margin),
                "free_margin": _num(a.free_margin),
                "used_margin": _num(a.used_margin),
                "floating_pnl": _num(a.floating_pnl),
                "realized_pnl": _num(a.realized_pnl),
                "daily_pnl": _num(a.daily_pnl),
                "weekly_pnl": _num(a.weekly_pnl),
                "monthly_pnl": _num(a.monthly_pnl),
                "active_positions": a.active_positions,
                "pending_orders": a.pending_orders,
                "ownership_verified": a.ownership_verified,
                "trade_allowed": a.trade_allowed,
                "conversion_status": a.conversion_status,
                "conversion_as_of": (
                    a.conversion_as_of.isoformat() if a.conversion_as_of else None
                ),
                "note": a.note,
            }
            for a in portfolio.accounts
        ],
        "positions": [
            {
                "account_key": p.account_key,
                "broker_account_id": p.broker_account_id,
                "broker_code": p.broker_code,
                "ticket": p.ticket,
                "symbol": p.symbol,
                "side": p.side,
                "volume": str(p.volume),
                "profit": _num(p.profit),
                "strategy": p.strategy,
            }
            for p in portfolio.positions
        ],
    }


def serialize_exposure(exp: ExposureRollup) -> dict[str, Any]:
    def _bucket(b: Any) -> dict[str, Any]:
        return {
            "key": b.key,
            "long_volume": str(b.long_volume),
            "short_volume": str(b.short_volume),
            "net_volume": str(b.net_volume),
            "floating_pnl": str(b.floating_pnl) if b.floating_pnl is not None else None,
            "position_count": b.position_count,
            "share_of_equity_pct": (
                str(b.share_of_equity_pct)
                if b.share_of_equity_pct is not None
                else None
            ),
            "concentration_flag": b.concentration_flag,
        }

    return {
        "total_long_volume": str(exp.total_long_volume),
        "total_short_volume": str(exp.total_short_volume),
        "by_symbol": [_bucket(b) for b in exp.by_symbol],
        "by_broker": [_bucket(b) for b in exp.by_broker],
        "by_strategy": [_bucket(b) for b in exp.by_strategy],
        "overlapping": list(exp.overlapping),
        "concentration_threshold_pct": str(exp.concentration_threshold_pct),
        "methodology": exp.methodology,
    }


def serialize_risk(check: HouseholdRiskCheck) -> dict[str, Any]:
    return {
        "allowed": check.allowed,
        "block_reason": check.block_reason,
        "aggregate_open_risk_pct": (
            str(check.aggregate_open_risk_pct)
            if check.aggregate_open_risk_pct is not None
            else None
        ),
        "aggregate_open_risk_used_pct": (
            str(check.aggregate_open_risk_used_pct)
            if check.aggregate_open_risk_used_pct is not None
            else None
        ),
        "max_portfolio_exposure_pct": (
            str(check.max_portfolio_exposure_pct)
            if check.max_portfolio_exposure_pct is not None
            else None
        ),
        "concentration_flags": list(check.concentration_flags),
        "budgets": check.budgets,
        "methodology": check.methodology,
    }


def serialize_performance(report: PerformanceReport) -> dict[str, Any]:
    def _m(m: Any) -> dict[str, Any]:
        return {
            "strategy": m.strategy,
            "total_trades": m.total_trades,
            "winning_trades": m.winning_trades,
            "losing_trades": m.losing_trades,
            "win_rate": str(m.win_rate) if m.win_rate is not None else None,
            "net_profit": str(m.net_profit),
            "gross_profit": str(m.gross_profit),
            "gross_loss": str(m.gross_loss),
            "profit_factor": (
                str(m.profit_factor) if m.profit_factor is not None else None
            ),
            "average_win": str(m.average_win) if m.average_win is not None else None,
            "average_loss": str(m.average_loss) if m.average_loss is not None else None,
            "average_rr": str(m.average_rr) if m.average_rr is not None else None,
            "max_drawdown": str(m.max_drawdown) if m.max_drawdown is not None else None,
            "expectancy": str(m.expectancy) if m.expectancy is not None else None,
            "average_holding_seconds": m.average_holding_seconds,
        }

    return {
        "trades_considered": report.trades_considered,
        "trades_excluded_unconfirmed": report.trades_excluded_unconfirmed,
        "overall": _m(report.overall),
        "by_strategy": [_m(x) for x in report.by_strategy],
        "by_symbol": [_m(x) for x in report.by_symbol],
        "by_broker": [_m(x) for x in report.by_broker],
        "by_session": [_m(x) for x in report.by_session],
        "attribution": [
            {
                "trade_id": r.trade_id,
                "signal_id": r.signal_id,
                "strategy": r.strategy,
                "broker_code": r.broker_code,
                "account_key": r.account_key,
                "symbol": r.symbol,
                "order_ticket": r.order_ticket,
                "position_ticket": r.position_ticket,
                "entry_at": r.entry_at.isoformat() if r.entry_at else None,
                "exit_at": r.exit_at.isoformat() if r.exit_at else None,
                "realized_pnl": str(r.realized_pnl),
                "fees": str(r.fees) if r.fees is not None else None,
                "slippage": str(r.slippage) if r.slippage is not None else None,
                "chain_complete": r.chain_complete,
                "missing_links": list(r.missing_links),
            }
            for r in report.attribution
        ],
        "methodology": report.methodology,
    }
