"""Verified performance from broker deals. No order path, no invented fills."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

SCHEMA_VERSION = "trust-engine.v1"
SOURCE_BROKER_DEALS = "broker_history_deals"

_SCOPES = frozenset({"live", "demo", "backtest", "paper", "unknown"})
_NON_BROKER_SCOPES = frozenset({"backtest", "paper"})
_NON_TRADE_TYPES = frozenset({"balance", "credit", "deposit", "withdrawal"})

_LIMITATIONS = (
    "Spread, slippage, stop loss, and take profit are not on broker deals.",
    "Strategy identifiers stay omitted until a user-scoped source is supplied.",
    "Account environment is reported only when the caller already knows it.",
    "Blank profit and swap may already be stored as 0 by the history adapter. "
    "Blank commission stays unknown.",
)


@dataclass(frozen=True, slots=True)
class TrustBuildInput:
    """Inputs are records the caller already loaded. This module does not fetch."""

    deals: tuple[dict[str, Any], ...] | None
    history_available: bool
    account_scope: str = "unknown"
    source: str = SOURCE_BROKER_DEALS
    account_login: int | str | None = None
    broker_server: str | None = None
    floating_pnl: Decimal | str | None = None
    floating_source: str = "account_snapshot.profit"
    read_at: datetime | None = None
    strategy_by_position: dict[int, str] | None = None


def build_trust_report(spec: TrustBuildInput) -> dict[str, Any]:
    """Build a JSON-safe report. Never places or amends an order."""
    scope = spec.account_scope if spec.account_scope in _SCOPES else "unknown"
    source = spec.source.strip() or SOURCE_BROKER_DEALS
    read_at = _iso(spec.read_at) if spec.read_at is not None else None
    server = (spec.broker_server or "").strip() or None
    base = {
        "schema_version": SCHEMA_VERSION,
        "places_orders": False,
        "modifies_positions": False,
        "changes_risk_policy": False,
        "authoritative_for_execution": False,
        "history_available": bool(spec.history_available),
        "account_scope": scope,
        "account_id_masked": mask_account_id(spec.account_login),
        "broker_server": server,
        "read_at": read_at,
        "source": source,
        "known_limitations": list(_LIMITATIONS),
    }
    if not spec.history_available or spec.deals is None:
        blank = _pending_performance(
            source=source,
            observed_at=read_at,
            scope=scope,
            status="pending_synchronization" if spec.deals is None else "unavailable",
        )
        floating = _floating_figure(spec, scope=scope, observed_at=read_at)
        blank["floating_pnl"] = floating
        base["performance"] = blank
        base["trades"] = []
        base["strategy_performance"] = []
        base["live_performance"] = False
        return base

    closed, meta = _closed_trades(
        spec.deals,
        strategy_by_position=spec.strategy_by_position or {},
        account_id_masked=mask_account_id(spec.account_login),
        source=source,
        observed_at=read_at,
        scope=scope,
    )
    performance = _performance(
        closed,
        meta=meta,
        spec=spec,
        source=source,
        observed_at=read_at,
        scope=scope,
    )
    base["performance"] = performance
    base["trades"] = closed
    base["strategy_performance"] = _strategy_rows(
        closed, source=source, observed_at=read_at, scope=scope
    )
    net_status = performance["net_realized_pnl"]["status"]
    base["live_performance"] = scope == "live" and net_status == "verified"
    return base


def mask_account_id(login: int | str | None) -> str | None:
    """Mask a broker login. Short logins are fully masked."""
    if login is None:
        return None
    digits = "".join(ch for ch in str(login) if ch.isdigit())
    if not digits:
        return None
    if len(digits) <= 4:
        return "•" * len(digits)
    return f"{'•' * (len(digits) - 4)}{digits[-4:]}"


def _pending_performance(
    *,
    source: str,
    observed_at: str | None,
    scope: str,
    status: str,
) -> dict[str, Any]:
    names = (
        "total_trades",
        "winning_trades",
        "losing_trades",
        "breakeven_trades",
        "win_rate",
        "average_win",
        "average_loss",
        "profit_factor",
        "net_realized_pnl",
        "maximum_drawdown",
        "average_holding_time_seconds",
        "trading_costs",
        "excluded_non_trade_deals",
        "unpaired_deals",
    )
    return {
        name: _figure(
            None,
            status=status,
            source=source,
            method="withheld_until_broker_history_is_available",
            observed_at=observed_at,
            scope=scope,
        )
        for name in names
    }


def _floating_figure(
    spec: TrustBuildInput, *, scope: str, observed_at: str | None
) -> dict[str, Any]:
    parsed = _decimal(spec.floating_pnl)
    if parsed is None:
        return _figure(
            None,
            status="unavailable",
            source=spec.floating_source,
            method="broker_reported_account_profit",
            observed_at=observed_at,
            scope=scope,
        )
    return _figure(
        _money(parsed),
        status="verified",
        source=spec.floating_source,
        method="broker_reported_account_profit",
        observed_at=observed_at,
        scope=scope,
    )


def _closed_trades(
    deals: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    *,
    strategy_by_position: dict[int, str],
    account_id_masked: str | None,
    source: str,
    observed_at: str | None,
    scope: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    excluded = 0
    unpaired = 0
    for raw in deals:
        if not isinstance(raw, dict):
            unpaired += 1
            continue
        role = _role(str(raw.get("deal_type") or ""))
        if role == "non_trade":
            excluded += 1
            continue
        position_id = _int(raw.get("position_id"))
        symbol = str(raw.get("symbol") or "").strip()
        if (
            position_id is None
            or position_id <= 0
            or not symbol
            or symbol.upper() == "BALANCE"
        ):
            unpaired += 1
            continue
        grouped[position_id].append(raw)

    closed: list[dict[str, Any]] = []
    for position_id, group in grouped.items():
        entries = [
            row for row in group if _role(str(row.get("deal_type") or "")) == "entry"
        ]
        exits = [
            row for row in group if _role(str(row.get("deal_type") or "")) == "exit"
        ]
        if not entries or not exits:
            unpaired += len(group)
            continue
        entries.sort(key=_sort_key)
        exits.sort(key=_sort_key)
        trade = _one_trade(
            position_id=position_id,
            group=group,
            entries=entries,
            exits=exits,
            strategy_id=strategy_by_position.get(position_id),
            account_id_masked=account_id_masked,
            source=source,
            observed_at=observed_at,
            scope=scope,
        )
        closed.append(trade)
    closed.sort(
        key=lambda row: (
            (row.get("exit_time") or {}).get("value") or "",
            row.get("position_id") or 0,
        )
    )
    return closed, {"excluded_non_trade_deals": excluded, "unpaired_deals": unpaired}


def _one_trade(
    *,
    position_id: int,
    group: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    exits: list[dict[str, Any]],
    strategy_id: str | None,
    account_id_masked: str | None,
    source: str,
    observed_at: str | None,
    scope: str,
) -> dict[str, Any]:
    entry = entries[0]
    exit_row = exits[-1]
    entry_time = _parse_time(entry.get("time"))
    exit_time = _parse_time(exit_row.get("time"))
    prices_in = [_decimal(row.get("price")) for row in entries]
    prices_out = [_decimal(row.get("price")) for row in exits]
    profits = [_decimal(row.get("profit")) for row in group]
    commissions = [_decimal(row.get("commission")) for row in group]
    swaps = [_decimal(row.get("swap")) for row in group]
    volumes = [_decimal(row.get("volume")) for row in entries]
    sides = {str(row.get("side") or "").strip().lower() for row in entries}
    sides.discard("")

    gross = _sum_if_complete(profits)
    commission = _sum_if_complete(commissions)
    swap = _sum_if_complete(swaps)
    net = None
    if gross is not None and commission is not None and swap is not None:
        net = gross + commission + swap
    holding = None
    if entry_time is not None and exit_time is not None:
        holding = Decimal(str(max(0.0, (exit_time - entry_time).total_seconds())))

    multiple_legs = len(entries) > 1 or len(exits) > 1
    price_status = "partially_verified" if multiple_legs else "verified"
    entry_price = prices_in[0]
    exit_price = prices_out[-1]
    if entry_price is None:
        price_status = "unavailable"
    direction = next(iter(sides)) if len(sides) == 1 else None
    volume = _sum_if_complete(volumes)
    strategy = (
        strategy_id.strip()
        if isinstance(strategy_id, str) and strategy_id.strip()
        else None
    )

    def field(value: Any, *, status: str, method: str) -> dict[str, Any]:
        shown = value
        if isinstance(value, Decimal):
            shown = _money(value)
        if shown is None and status == "verified":
            status = "unavailable"
        return _figure(
            shown,
            status=status,
            source=source,
            method=method,
            observed_at=observed_at,
            scope=scope,
        )

    return {
        "position_id": position_id,
        "symbol": str(entry.get("symbol") or "").strip().upper(),
        "direction": field(
            direction,
            status="verified" if direction else "unavailable",
            method="entry_deal_side",
        ),
        "entry_price": field(
            entry_price,
            status=price_status if entry_price is not None else "unavailable",
            method="first_entry_deal_price",
        ),
        "exit_price": field(
            exit_price,
            status=price_status if exit_price is not None else "unavailable",
            method="last_exit_deal_price",
        ),
        "entry_time": field(
            _iso(entry_time),
            status="verified" if entry_time else "unavailable",
            method="first_entry_deal_time",
        ),
        "exit_time": field(
            _iso(exit_time),
            status="verified" if exit_time else "unavailable",
            method="last_exit_deal_time",
        ),
        "stop_loss": field(None, status="unavailable", method="not_on_broker_deal"),
        "take_profit": field(None, status="unavailable", method="not_on_broker_deal"),
        "volume": field(
            volume,
            status="verified" if volume is not None else "unavailable",
            method="sum_of_entry_deal_volume",
        ),
        "gross_pnl": field(
            gross,
            status="verified" if gross is not None else "unavailable",
            method="sum_of_deal_profit_on_position",
        ),
        "commission": field(
            commission,
            status="verified" if commission is not None else "unavailable",
            method="sum_of_deal_commission_on_position",
        ),
        "swap": field(
            swap,
            status="verified" if swap is not None else "unavailable",
            method="sum_of_deal_swap_on_position",
        ),
        "spread": field(None, status="unavailable", method="not_on_broker_deal"),
        "slippage": field(None, status="unavailable", method="not_on_broker_deal"),
        "net_pnl": field(
            net,
            status="verified" if net is not None else "unavailable",
            method="gross_plus_commission_plus_swap",
        ),
        "holding_time_seconds": field(
            _qty(holding, Decimal("0.001")) if holding is not None else None,
            status="verified" if holding is not None else "unavailable",
            method="exit_time_minus_entry_time",
        ),
        "strategy_id": field(
            strategy,
            status="verified" if strategy else "unavailable",
            method="caller_supplied_attribution",
        ),
        "account_id_masked": account_id_masked,
        "entry_deal_ticket": _int(entry.get("ticket")),
        "exit_deal_ticket": _int(exit_row.get("ticket")),
        "source": source,
        "account_scope": scope,
        "live_performance": scope == "live" and net is not None,
    }


def _performance(
    closed: list[dict[str, Any]],
    *,
    meta: dict[str, int],
    spec: TrustBuildInput,
    source: str,
    observed_at: str | None,
    scope: str,
) -> dict[str, Any]:
    nets = [_decimal(row["net_pnl"]["value"]) for row in closed]
    known = [net for net in nets if net is not None]
    missing_net = len(known) != len(nets)
    wins = [net for net in known if net > 0]
    losses = [net for net in known if net < 0]
    flat = [net for net in known if net == 0]
    count_status = "partially_verified" if missing_net else "verified"
    if not closed:
        outcome_status = "verified"
    elif not known:
        outcome_status = "unavailable"
    else:
        outcome_status = count_status

    def count_figure(value: int, *, status: str, method: str) -> dict[str, Any]:
        return _figure(
            value,
            status=status,
            source=source,
            method=method,
            observed_at=observed_at,
            scope=scope,
        )

    win_rate = None
    if known:
        win_rate = _qty(Decimal(len(wins)) / Decimal(len(known)), Decimal("0.000001"))
    average_win = (
        _qty(sum(wins, Decimal("0")) / Decimal(len(wins)), Decimal("0.000001"))
        if wins
        else None
    )
    average_loss = (
        _qty(sum(losses, Decimal("0")) / Decimal(len(losses)), Decimal("0.000001"))
        if losses
        else None
    )
    profit_factor = None
    pf_status = "unavailable"
    if losses:
        gross_loss = abs(sum(losses, Decimal("0")))
        gross_win = sum(wins, Decimal("0"))
        if gross_loss > 0:
            profit_factor = _qty(gross_win / gross_loss, Decimal("0.000001"))
            pf_status = count_status
    if not closed:
        net_total: Decimal | None = Decimal("0")
        net_status = "verified"
    elif missing_net:
        net_total = None
        net_status = "partially_verified" if known else "unavailable"
    else:
        net_total = sum(known, Decimal("0"))
        net_status = "verified"
    drawdown = _max_drawdown(closed) if not missing_net else None
    dd_status = "verified" if not missing_net else "unavailable"
    holding = _average_holding(closed)
    costs = _trading_costs(closed)

    report = {
        "total_trades": count_figure(
            len(closed), status="verified", method="paired_entry_and_exit_deals"
        ),
        "winning_trades": count_figure(
            len(wins), status=outcome_status, method="closed_trades_with_positive_net"
        ),
        "losing_trades": count_figure(
            len(losses), status=outcome_status, method="closed_trades_with_negative_net"
        ),
        "breakeven_trades": count_figure(
            len(flat), status=outcome_status, method="closed_trades_with_zero_net"
        ),
        "win_rate": _figure(
            win_rate,
            status=outcome_status if win_rate is not None else "unavailable",
            source=source,
            method="wins_over_closed_trades_with_known_net",
            observed_at=observed_at,
            scope=scope,
        ),
        "average_win": _figure(
            _money(Decimal(average_win)) if average_win is not None else None,
            status=count_status if average_win is not None else "unavailable",
            source=source,
            method="mean_positive_net",
            observed_at=observed_at,
            scope=scope,
        ),
        "average_loss": _figure(
            _money(Decimal(average_loss)) if average_loss is not None else None,
            status=count_status if average_loss is not None else "unavailable",
            source=source,
            method="mean_negative_net",
            observed_at=observed_at,
            scope=scope,
        ),
        "profit_factor": _figure(
            profit_factor,
            status=pf_status,
            source=source,
            method="gross_profit_over_abs_gross_loss_known_nets",
            observed_at=observed_at,
            scope=scope,
        ),
        "net_realized_pnl": _figure(
            _money(net_total) if net_total is not None else None,
            status=net_status,
            source=source,
            method="sum_of_complete_trade_nets_withheld_when_any_net_is_unknown",
            observed_at=observed_at,
            scope=scope,
        ),
        "floating_pnl": _floating_figure(spec, scope=scope, observed_at=observed_at),
        "maximum_drawdown": _figure(
            _money(drawdown) if drawdown is not None else None,
            status=dd_status if closed else "verified",
            source=source,
            method="peak_to_trough_of_closed_trade_net_sequence",
            observed_at=observed_at,
            scope=scope,
        ),
        "average_holding_time_seconds": _retarget(
            holding, source=source, observed_at=observed_at, scope=scope
        ),
        "trading_costs": _retarget_costs(
            costs, source=source, observed_at=observed_at, scope=scope
        ),
        "excluded_non_trade_deals": count_figure(
            meta["excluded_non_trade_deals"],
            status="verified",
            method="balance_credit_deposit_withdrawal_deals",
        ),
        "unpaired_deals": count_figure(
            meta["unpaired_deals"],
            status="verified",
            method="deals_without_both_entry_and_exit",
        ),
    }
    if not closed:
        report["maximum_drawdown"] = _figure(
            "0",
            status="verified",
            source=source,
            method="no_closed_trades",
            observed_at=observed_at,
            scope=scope,
        )
    return report


def _average_holding(closed: list[dict[str, Any]]) -> dict[str, Any]:
    samples = [
        _decimal(row["holding_time_seconds"]["value"])
        for row in closed
        if row["holding_time_seconds"]["value"] is not None
    ]
    total = Decimal("0")
    count = 0
    for item in samples:
        if item is None:
            continue
        total += item
        count += 1
    if count == 0:
        return {
            "value": None,
            "status": "unavailable",
            "method": "exit_time_minus_entry_time",
        }
    average = total / Decimal(count)
    status = "verified" if count == len(closed) else "partially_verified"
    return {
        "value": _qty(average, Decimal("0.001")),
        "status": status,
        "method": "mean_holding_seconds_over_trades_with_both_timestamps",
    }


def _trading_costs(closed: list[dict[str, Any]]) -> dict[str, Any]:
    complete: list[Decimal] = []
    for row in closed:
        commission = _decimal(row["commission"]["value"])
        swap = _decimal(row["swap"]["value"])
        if commission is None or swap is None:
            continue
        complete.append(commission + swap)
    if not closed:
        return {"value": "0", "status": "verified", "method": "no_closed_trades"}
    if len(complete) != len(closed):
        return {
            "value": None,
            "status": "partially_verified" if complete else "unavailable",
            "method": "commission_plus_swap_withheld_if_incomplete",
        }
    return {
        "value": _money(sum(complete, Decimal("0"))),
        "status": "verified",
        "method": "sum_of_commission_and_swap",
    }


def _retarget(
    payload: dict[str, Any], *, source: str, observed_at: str | None, scope: str
) -> dict[str, Any]:
    return _figure(
        payload["value"],
        status=payload["status"],
        source=source,
        method=payload["method"],
        observed_at=observed_at,
        scope=scope,
    )


def _retarget_costs(
    payload: dict[str, Any], *, source: str, observed_at: str | None, scope: str
) -> dict[str, Any]:
    return _retarget(payload, source=source, observed_at=observed_at, scope=scope)


def _strategy_rows(
    closed: list[dict[str, Any]],
    *,
    source: str,
    observed_at: str | None,
    scope: str,
) -> list[dict[str, Any]]:
    buckets: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    for row in closed:
        strategy = row["strategy_id"]["value"]
        buckets[strategy if isinstance(strategy, str) else None].append(row)
    rows: list[dict[str, Any]] = []
    for strategy_id, group in buckets.items():
        nets = [_decimal(row["net_pnl"]["value"]) for row in group]
        known = [net for net in nets if net is not None]
        complete = len(known) == len(group) and bool(group)
        net_value = _money(sum(known, Decimal("0"))) if complete else None
        rows.append(
            {
                "strategy_id": strategy_id,
                "trade_count": _figure(
                    len(group),
                    status="verified",
                    source=source,
                    method="closed_trades_for_strategy",
                    observed_at=observed_at,
                    scope=scope,
                ),
                "net_realized_pnl": _figure(
                    net_value,
                    status="verified" if complete else "unavailable",
                    source=source,
                    method="sum_of_complete_trade_nets_for_strategy",
                    observed_at=observed_at,
                    scope=scope,
                ),
            }
        )
    rows.sort(key=lambda row: (row["strategy_id"] is None, row["strategy_id"] or ""))
    return rows


def _max_drawdown(closed: list[dict[str, Any]]) -> Decimal:
    equity = Decimal("0")
    peak = Decimal("0")
    worst = Decimal("0")
    ordered = sorted(
        closed,
        key=lambda row: (row.get("exit_time") or {}).get("value") or "",
    )
    for row in ordered:
        net = _decimal(row["net_pnl"]["value"])
        if net is None:
            return Decimal("0")
        equity += net
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


def _figure(
    value: Any,
    *,
    status: str,
    source: str,
    method: str,
    observed_at: str | None,
    scope: str,
) -> dict[str, Any]:
    if value is None and status == "verified":
        status = "unavailable"
    if scope in _NON_BROKER_SCOPES and status == "verified":
        status = "partially_verified"
    return {
        "value": value,
        "status": status,
        "source": source,
        "method": method,
        "observed_at": observed_at,
        "account_scope": scope,
        "live_performance": scope == "live" and status == "verified",
    }


def _role(deal_type: str) -> str:
    text = deal_type.strip().lower()
    if not text:
        return "unknown"
    if text in _NON_TRADE_TYPES or any(token in text for token in _NON_TRADE_TYPES):
        return "non_trade"
    has_out = "out" in text
    has_in = "in" in text
    if has_in and has_out:
        return "unknown"
    if has_out:
        return "exit"
    if has_in:
        return "entry"
    return "unknown"


def _sum_if_complete(values: list[Decimal | None]) -> Decimal | None:
    if any(value is None for value in values):
        return None
    return sum((value for value in values if value is not None), Decimal("0"))


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _money(value: Decimal) -> str:
    return format(value, "f")


def _qty(value: Decimal, places: Decimal) -> str:
    return format(value.quantize(places, rounding=ROUND_HALF_UP), "f")


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat()


def _sort_key(row: dict[str, Any]) -> tuple[str, int]:
    stamp = _parse_time(row.get("time"))
    return (_iso(stamp) or "", _int(row.get("ticket")) or 0)
