"""Exposure rollups and concentration flags."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.portfolio_household.aggregation import PositionSlice


@dataclass(frozen=True, slots=True)
class ExposureBucket:
    key: str
    long_volume: Decimal
    short_volume: Decimal
    net_volume: Decimal
    floating_pnl: Decimal | None
    position_count: int
    share_of_equity_pct: Decimal | None
    concentration_flag: bool


@dataclass(frozen=True, slots=True)
class ExposureRollup:
    total_long_volume: Decimal
    total_short_volume: Decimal
    by_symbol: tuple[ExposureBucket, ...]
    by_broker: tuple[ExposureBucket, ...]
    by_strategy: tuple[ExposureBucket, ...]
    overlapping: tuple[dict[str, Any], ...]
    concentration_threshold_pct: Decimal
    methodology: dict[str, Any]


def _bucket_map(
    positions: list[PositionSlice],
    key_fn,
    equity: Decimal | None,
    threshold: Decimal,
) -> list[ExposureBucket]:
    acc: dict[str, dict[str, Any]] = {}
    for p in positions:
        key = key_fn(p) or "unspecified"
        slot = acc.setdefault(
            key,
            {
                "long": Decimal("0"),
                "short": Decimal("0"),
                "pnl": Decimal("0"),
                "pnl_known": False,
                "count": 0,
            },
        )
        side = (p.side or "").lower()
        if side in {"buy", "long"}:
            slot["long"] += p.volume
        else:
            slot["short"] += p.volume
        if p.profit is not None:
            slot["pnl"] += p.profit
            slot["pnl_known"] = True
        slot["count"] += 1

    out: list[ExposureBucket] = []
    for key, slot in sorted(acc.items()):
        net = slot["long"] - slot["short"]
        share = None
        flag = False
        if equity is not None and equity > 0 and slot["pnl_known"]:
            # Concentration by absolute floating PnL share is weak; use |net|
            # volume share of total abs net when equity known — mark by volume
            # weight vs equity only when we have a notional proxy (volume).
            share = None
        abs(net)
        if equity is not None and equity > 0:
            # Volume is lots, not currency — flag when one key owns >threshold
            # of total absolute volume across all keys in this dimension.
            pass
        out.append(
            ExposureBucket(
                key=key,
                long_volume=slot["long"],
                short_volume=slot["short"],
                net_volume=net,
                floating_pnl=slot["pnl"] if slot["pnl_known"] else None,
                position_count=slot["count"],
                share_of_equity_pct=share,
                concentration_flag=flag,
            )
        )

    total_abs = sum((abs(b.net_volume) for b in out), Decimal("0"))
    flagged: list[ExposureBucket] = []
    for b in out:
        share_pct = None
        conc = False
        if total_abs > 0:
            share_pct = (abs(b.net_volume) / total_abs) * Decimal("100")
            conc = share_pct >= threshold
        flagged.append(
            ExposureBucket(
                key=b.key,
                long_volume=b.long_volume,
                short_volume=b.short_volume,
                net_volume=b.net_volume,
                floating_pnl=b.floating_pnl,
                position_count=b.position_count,
                share_of_equity_pct=share_pct,
                concentration_flag=conc,
            )
        )
    return flagged


def find_overlapping(positions: list[PositionSlice]) -> list[dict[str, Any]]:
    """Same symbol open on multiple accounts / opposing sides."""
    by_symbol: dict[str, list[PositionSlice]] = {}
    for p in positions:
        by_symbol.setdefault(p.symbol, []).append(p)
    overlaps: list[dict[str, Any]] = []
    for symbol, group in by_symbol.items():
        accounts = {p.account_key for p in group}
        sides = {(p.side or "").lower() for p in group}
        if len(accounts) > 1 or (
            ("buy" in sides or "long" in sides)
            and ("sell" in sides or "short" in sides)
        ):
            overlaps.append(
                {
                    "symbol": symbol,
                    "accounts": sorted(accounts),
                    "sides": sorted(sides),
                    "position_count": len(group),
                    "kind": (
                        "cross_account" if len(accounts) > 1 else "opposing_sides"
                    ),
                }
            )
    return overlaps


def rollup_exposure(
    positions: list[PositionSlice],
    *,
    equity: Decimal | None = None,
    concentration_threshold_pct: Decimal = Decimal("40"),
) -> ExposureRollup:
    total_long = sum(
        (p.volume for p in positions if (p.side or "").lower() in {"buy", "long"}),
        Decimal("0"),
    )
    total_short = sum(
        (p.volume for p in positions if (p.side or "").lower() in {"sell", "short"}),
        Decimal("0"),
    )
    by_symbol = _bucket_map(
        positions, lambda p: p.symbol, equity, concentration_threshold_pct
    )
    by_broker = _bucket_map(
        positions,
        lambda p: p.broker_code or p.account_key,
        equity,
        concentration_threshold_pct,
    )
    by_strategy = _bucket_map(
        positions,
        lambda p: p.strategy or "unspecified",
        equity,
        concentration_threshold_pct,
    )
    return ExposureRollup(
        total_long_volume=total_long,
        total_short_volume=total_short,
        by_symbol=tuple(by_symbol),
        by_broker=tuple(by_broker),
        by_strategy=tuple(by_strategy),
        overlapping=tuple(find_overlapping(positions)),
        concentration_threshold_pct=concentration_threshold_pct,
        methodology={
            "volume_unit": "lots",
            "concentration": "share_of_abs_net_volume_in_dimension",
            "correlation": "omitted_unless_caller_supplies_pi_sample",
        },
    )
