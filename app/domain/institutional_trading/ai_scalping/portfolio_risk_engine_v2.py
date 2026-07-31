"""Institutional Portfolio Risk Engine v2.

Portfolio-aware allocation: live book exposure, correlation/sector/currency
caps, quality-weighted dynamic sizing, winner-only pyramiding.

Hard safety contracts:
- Never fixed lots
- Never force broker minimum lot
- Never exceed configured max risk %
- Never average into losing trades
- Portfolio limits always override trade requests
- Do not weaken AI / spread / vol / liquidity / news / session / risk gates
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.entities.mt5_portfolio import MT5Position
from app.domain.entities.risk_engine import contract_size_for_symbol
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.ai_scalping.correlation_book import (
    correlation_group_members,
    correlation_group_name,
    currency_for,
    normalize_book_symbol,
    sector_for,
)
from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
    AddTradeDecision,
    may_add_scalping_trade,
)
from app.domain.institutional_trading.ai_scalping.dynamic_sizing_v2 import (
    DynamicSizingDecision,
    calculate_dynamic_lots_v2,
    check_portfolio_sizing_limits,
)
from app.domain.institutional_trading.ai_scalping.portfolio_risk import (
    portfolio_daily_loss_pct,
    portfolio_exposure_pct,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.decision_models import AccountRiskState
from app.domain.trading.xauusd_specs import margin_required
from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = threading.RLock()


@dataclass(frozen=True, slots=True)
class BrokerComplianceSpec:
    """Live broker constraints for the candidate symbol."""

    min_lot: Decimal
    lot_step: Decimal
    max_lot: Decimal
    contract_size: Decimal
    stops_level: int | None = None
    freeze_level: int | None = None
    trade_mode: str | None = None
    trade_allowed: bool | None = None
    tick_value: Decimal | None = None
    point: Decimal | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "min_lot": str(self.min_lot),
            "lot_step": str(self.lot_step),
            "max_lot": str(self.max_lot),
            "contract_size": str(self.contract_size),
            "stops_level": self.stops_level,
            "freeze_level": self.freeze_level,
            "trade_mode": self.trade_mode,
            "trade_allowed": self.trade_allowed,
            "tick_value": str(self.tick_value) if self.tick_value is not None else None,
            "point": str(self.point) if self.point is not None else None,
        }


@dataclass(frozen=True, slots=True)
class PortfolioBookSnapshot:
    """Live portfolio book used by PRE v2 gates."""

    timestamp: str
    balance: Decimal
    equity: Decimal
    free_margin: Decimal | None
    used_margin: Decimal | None
    floating_pnl: Decimal
    open_positions: int
    exposure_pct: Decimal
    floating_exposure_pct: Decimal
    margin_usage_pct: Decimal | None
    daily_loss_pct: Decimal
    symbol_exposure: dict[str, Decimal]
    sector_exposure: dict[str, Decimal]
    currency_exposure: dict[str, Decimal]
    correlated_exposure: dict[str, Decimal]
    positions_per_symbol: dict[str, int]
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "balance": str(self.balance),
            "equity": str(self.equity),
            "free_margin": (
                str(self.free_margin) if self.free_margin is not None else None
            ),
            "used_margin": (
                str(self.used_margin) if self.used_margin is not None else None
            ),
            "floating_pnl": str(self.floating_pnl),
            "open_positions": self.open_positions,
            "exposure_pct": str(self.exposure_pct),
            "floating_exposure_pct": str(self.floating_exposure_pct),
            "margin_usage_pct": (
                str(self.margin_usage_pct)
                if self.margin_usage_pct is not None
                else None
            ),
            "daily_loss_pct": str(self.daily_loss_pct),
            "symbol_exposure": {k: str(v) for k, v in self.symbol_exposure.items()},
            "sector_exposure": {k: str(v) for k, v in self.sector_exposure.items()},
            "currency_exposure": {k: str(v) for k, v in self.currency_exposure.items()},
            "correlated_exposure": {
                k: str(v) for k, v in self.correlated_exposure.items()
            },
            "positions_per_symbol": dict(self.positions_per_symbol),
            "reasons": list(self.reasons),
            "engine": "portfolio_risk_engine_v2",
        }


@dataclass(frozen=True, slots=True)
class PortfolioAllocationDecision:
    """Full allocation verdict — sizing + portfolio gates + evidence."""

    allow: bool
    approved_lots: Decimal
    book: PortfolioBookSnapshot
    sizing: DynamicSizingDecision | None
    pyramid: AddTradeDecision | None
    correlation_score: Decimal
    correlation_group: str | None
    symbol_exposure_pct: Decimal
    correlated_exposure_pct: Decimal
    sector_exposure_pct: Decimal
    currency_exposure_pct: Decimal
    rejection_reason: str | None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "engine": "portfolio_risk_engine_v2",
            "allow": self.allow,
            "approved_lots": str(self.approved_lots),
            "correlation_score": str(self.correlation_score),
            "correlation_group": self.correlation_group,
            "symbol_exposure_pct": str(self.symbol_exposure_pct),
            "correlated_exposure_pct": str(self.correlated_exposure_pct),
            "sector_exposure_pct": str(self.sector_exposure_pct),
            "currency_exposure_pct": str(self.currency_exposure_pct),
            "rejection_reason": self.rejection_reason,
            "book": self.book.to_dict(),
            "sizing": self.sizing.to_dict() if self.sizing is not None else None,
            "pyramid": self.pyramid.to_dict() if self.pyramid is not None else None,
        }
        if self.evidence:
            payload["evidence"] = dict(self.evidence)
        return payload


def _d(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    try:
        if value is None:
            return default
        return Decimal(str(value))
    except Exception:
        return default


def _opt_d(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _position_unrealized(position: MT5Position) -> Decimal:
    """Prefer broker profit; fall back to mark-to-market on price."""
    profit = _d(getattr(position, "profit", 0))
    if profit != 0:
        return profit
    side = str(getattr(position, "side", "") or "").lower()
    open_px = _d(getattr(position, "open_price", 0))
    cur_px = _d(getattr(position, "current_price", 0))
    vol = _d(getattr(position, "volume", 0))
    if open_px <= 0 or cur_px <= 0 or vol <= 0:
        return Decimal("0")
    sym = str(getattr(position, "symbol", "") or "")
    cs = contract_size_for_symbol(sym)
    delta = cur_px - open_px
    if side == "sell":
        delta = -delta
    return (delta * vol * cs).quantize(Decimal("0.01"))


def build_portfolio_book(
    *,
    account: AccountRiskState,
    positions: Sequence[MT5Position] | None = None,
    balance: Decimal | None = None,
    used_margin: Decimal | None = None,
    floating_pnl: Decimal | None = None,
    leverage: Decimal | None = None,
    risk_per_trade_pct: Decimal | None = None,
    config: AiScalpingConfig | None = None,
    ite_config: ITEConfig | None = None,
) -> PortfolioBookSnapshot:
    """Aggregate live book: exposure, margin, sector/currency/correlation."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    ite = ite_config or DEFAULT_ITE_CONFIG
    risk_pct = (
        risk_per_trade_pct
        if risk_per_trade_pct is not None and risk_per_trade_pct > 0
        else cfg.risk_per_trade_pct
    )
    equity = _d(account.equity)
    bal = balance if balance is not None and balance > 0 else _opt_d(account.balance)
    if bal is None or bal <= 0:
        bal = equity
    free = account.free_margin if account.free_margin is not None else None
    used = used_margin if used_margin is not None else account.used_margin
    if used is None and free is not None and equity > 0:
        # Derive used margin when broker reports free but not used
        used = max(Decimal("0"), equity - free)

    pos_list = list(positions or [])
    open_n = max(int(account.open_positions or 0), len(pos_list))

    float_pnl = floating_pnl if floating_pnl is not None else account.floating_pnl
    if float_pnl is None:
        float_pnl = sum((_position_unrealized(p) for p in pos_list), Decimal("0"))

    # Per-position risk contribution (configured risk model; never fixed lots)
    position_risks: list[Decimal] = []
    symbol_exp: dict[str, Decimal] = {}
    sector_exp: dict[str, Decimal] = {}
    currency_exp: dict[str, Decimal] = {}
    corr_exp: dict[str, Decimal] = {}
    per_sym_count: dict[str, int] = {}
    lev = leverage if leverage is not None and leverage > 0 else Decimal("1000")

    for p in pos_list:
        sym = normalize_book_symbol(str(getattr(p, "symbol", "") or ""))
        if not sym:
            continue
        per_sym_count[sym] = per_sym_count.get(sym, 0) + 1
        # Prefer explicit risk% contribution; else one configured unit per position
        contrib = risk_pct
        position_risks.append(contrib)
        symbol_exp[sym] = symbol_exp.get(sym, Decimal("0")) + contrib
        sec = sector_for(sym)
        sector_exp[sec] = sector_exp.get(sec, Decimal("0")) + contrib
        cur = currency_for(sym)
        currency_exp[cur] = currency_exp.get(cur, Decimal("0")) + contrib
        gname = correlation_group_name(sym)
        if gname:
            corr_exp[gname] = corr_exp.get(gname, Decimal("0")) + contrib

    # If book empty but account reports opens, fall back to count x risk
    if not position_risks and open_n > 0:
        exposure = portfolio_exposure_pct(
            open_positions=open_n, risk_per_trade_pct=risk_pct
        )
    else:
        exposure = portfolio_exposure_pct(
            open_positions=open_n,
            risk_per_trade_pct=risk_pct,
            position_risk_pcts=position_risks,
        )

    floating_exp = Decimal("0")
    if equity > 0 and float_pnl is not None:
        floating_exp = (abs(float_pnl) / equity * Decimal("100")).quantize(
            Decimal("0.01")
        )

    margin_usage: Decimal | None = None
    if used is not None and equity > 0:
        margin_usage = (used / equity * Decimal("100")).quantize(Decimal("0.01"))
    elif free is not None and equity > 0 and free >= 0:
        # used ≈ equity - free when floating is embedded in equity
        approx_used = max(Decimal("0"), equity - free)
        if approx_used > 0:
            margin_usage = (approx_used / equity * Decimal("100")).quantize(
                Decimal("0.01")
            )

    daily_loss = portfolio_daily_loss_pct(
        equity=equity, daily_pnl=_d(account.daily_pnl)
    )

    reasons = (
        (
            f"PRE_v2 open={open_n} exposure={exposure}% "
            f"float_pnl={float_pnl} margin_usage={margin_usage}% "
            f"daily_loss={daily_loss}% max_dd={ite.max_daily_loss_pct}% lev={lev}"
        ),
    )
    return PortfolioBookSnapshot(
        timestamp=datetime.now(UTC).isoformat(),
        balance=bal,
        equity=equity,
        free_margin=free,
        used_margin=used,
        floating_pnl=_d(float_pnl),
        open_positions=open_n,
        exposure_pct=exposure,
        floating_exposure_pct=floating_exp,
        margin_usage_pct=margin_usage,
        daily_loss_pct=daily_loss,
        symbol_exposure=symbol_exp,
        sector_exposure=sector_exp,
        currency_exposure=currency_exp,
        correlated_exposure=corr_exp,
        positions_per_symbol=per_sym_count,
        reasons=reasons,
    )


def correlation_score_for(
    *,
    candidate_symbol: str,
    book: PortfolioBookSnapshot,
    max_correlated_exposure_pct: Decimal,
) -> Decimal:
    """0 = no correlated heat; 1 = at/over correlated cap."""
    gname = correlation_group_name(candidate_symbol)
    if gname is None:
        return Decimal("0")
    current = book.correlated_exposure.get(gname, Decimal("0"))
    if max_correlated_exposure_pct <= 0:
        return Decimal("0")
    score = (current / max_correlated_exposure_pct).quantize(Decimal("0.0001"))
    if score < 0:
        return Decimal("0")
    if score > 1:
        return Decimal("1")
    return score


def _broker_blocks_new_entry(spec: BrokerComplianceSpec | None) -> str | None:
    if spec is None:
        return None
    mode = (spec.trade_mode or "").strip().lower()
    if mode in {"disabled", "closeonly", "close_only"}:
        return f"Broker trade_mode={mode} — new entries blocked"
    if spec.trade_allowed is False:
        return "Broker trade_allowed=false — new entries blocked"
    return None


def _stop_distance_ok(
    *,
    stop_distance: Decimal | None,
    spec: BrokerComplianceSpec | None,
) -> str | None:
    if stop_distance is None or stop_distance <= 0:
        return None
    if spec is None:
        return None
    point = spec.point if spec.point is not None and spec.point > 0 else None
    if point is None:
        return None
    stops = spec.stops_level if spec.stops_level is not None else 0
    freeze = spec.freeze_level if spec.freeze_level is not None else 0
    min_dist = point * Decimal(max(stops, freeze, 0))
    if min_dist > 0 and stop_distance < min_dist:
        return (
            f"Stop distance {stop_distance} below broker min "
            f"{min_dist} (stops/freeze)"
        )
    return None


def evaluate_portfolio_allocation(
    *,
    account: AccountRiskState,
    symbol: str,
    stop_distance: Decimal | None,
    positions: Sequence[MT5Position] | None = None,
    new_direction: str = "",
    new_confidence: int = 0,
    entry: Decimal | None = None,
    atr: Decimal | None = None,
    mid_price: Decimal | None = None,
    leverage: Decimal | None = None,
    risk_pct: Decimal | None = None,
    session_risk_multiplier: Decimal | None = None,
    quality_score: int | None = None,
    confidence: int | None = None,
    liquidity_score: int | None = None,
    spread_score: int | None = None,
    trend_confidence: int | None = None,
    quality_reject: bool = False,
    broker: BrokerComplianceSpec | None = None,
    balance: Decimal | None = None,
    used_margin: Decimal | None = None,
    floating_pnl: Decimal | None = None,
    best_open_confidence: int | None = None,
    open_directions: tuple[str, ...] = (),
    open_entries: tuple[Decimal, ...] = (),
    min_entry_distance: Decimal | None = None,
    require_probability_improvement: bool = True,
    config: AiScalpingConfig | None = None,
    ite_config: ITEConfig | None = None,
    log: bool = True,
) -> PortfolioAllocationDecision:
    """Portfolio-aware size + gate. Deterministic; thread-safe via RLock."""
    with _LOCK:
        return _evaluate_portfolio_allocation_unlocked(
            account=account,
            symbol=symbol,
            stop_distance=stop_distance,
            positions=positions,
            new_direction=new_direction,
            new_confidence=new_confidence,
            entry=entry,
            atr=atr,
            mid_price=mid_price,
            leverage=leverage,
            risk_pct=risk_pct,
            session_risk_multiplier=session_risk_multiplier,
            quality_score=quality_score,
            confidence=confidence,
            liquidity_score=liquidity_score,
            spread_score=spread_score,
            trend_confidence=trend_confidence,
            quality_reject=quality_reject,
            broker=broker,
            balance=balance,
            used_margin=used_margin,
            floating_pnl=floating_pnl,
            best_open_confidence=best_open_confidence,
            open_directions=open_directions,
            open_entries=open_entries,
            min_entry_distance=min_entry_distance,
            require_probability_improvement=require_probability_improvement,
            config=config,
            ite_config=ite_config,
            log=log,
        )


def _evaluate_portfolio_allocation_unlocked(
    *,
    account: AccountRiskState,
    symbol: str,
    stop_distance: Decimal | None,
    positions: Sequence[MT5Position] | None,
    new_direction: str,
    new_confidence: int,
    entry: Decimal | None,
    atr: Decimal | None,
    mid_price: Decimal | None,
    leverage: Decimal | None,
    risk_pct: Decimal | None,
    session_risk_multiplier: Decimal | None,
    quality_score: int | None,
    confidence: int | None,
    liquidity_score: int | None,
    spread_score: int | None,
    trend_confidence: int | None,
    quality_reject: bool,
    broker: BrokerComplianceSpec | None,
    balance: Decimal | None,
    used_margin: Decimal | None,
    floating_pnl: Decimal | None,
    best_open_confidence: int | None,
    open_directions: tuple[str, ...],
    open_entries: tuple[Decimal, ...],
    min_entry_distance: Decimal | None,
    require_probability_improvement: bool,
    config: AiScalpingConfig | None,
    ite_config: ITEConfig | None,
    log: bool,
) -> PortfolioAllocationDecision:
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    ite = ite_config or DEFAULT_ITE_CONFIG
    pos_list = list(positions or [])
    book = build_portfolio_book(
        account=account,
        positions=pos_list,
        balance=balance,
        used_margin=used_margin,
        floating_pnl=floating_pnl,
        leverage=leverage,
        risk_per_trade_pct=risk_pct or cfg.risk_per_trade_pct,
        config=cfg,
        ite_config=ite,
    )

    canon = normalize_book_symbol(symbol)
    gname = correlation_group_name(canon)
    sym_exp = book.symbol_exposure.get(canon, Decimal("0"))
    corr_exp = (
        book.correlated_exposure.get(gname, Decimal("0")) if gname else Decimal("0")
    )
    sec_exp = book.sector_exposure.get(sector_for(canon), Decimal("0"))
    cur_exp = book.currency_exposure.get(currency_for(canon), Decimal("0"))
    corr_score = correlation_score_for(
        candidate_symbol=canon,
        book=book,
        max_correlated_exposure_pct=cfg.max_correlated_exposure_pct,
    )

    def _reject(
        reason: str,
        *,
        sizing: DynamicSizingDecision | None = None,
        pyramid: AddTradeDecision | None = None,
    ) -> PortfolioAllocationDecision:
        evidence = {
            "timestamp": book.timestamp,
            "balance": str(book.balance),
            "equity": str(book.equity),
            "free_margin": (
                str(book.free_margin) if book.free_margin is not None else None
            ),
            "floating_pnl": str(book.floating_pnl),
            "risk_pct": str(risk_pct or cfg.risk_per_trade_pct),
            "preferred_equity_tier": (
                sizing.equity_tier.to_dict() if sizing is not None else None
            ),
            "suggested_lot": str(sizing.suggested_lot) if sizing else "0",
            "calculated_lot": str(sizing.calculated_lot) if sizing else "0",
            "final_lot": "0",
            "broker_limits": broker.to_dict() if broker else None,
            "ai_score": confidence,
            "quality_score": quality_score,
            "portfolio_exposure": str(book.exposure_pct),
            "symbol_exposure": str(sym_exp),
            "margin_usage": (
                str(book.margin_usage_pct)
                if book.margin_usage_pct is not None
                else None
            ),
            "correlation_score": str(corr_score),
            "rejection_reason": reason,
        }
        decision = PortfolioAllocationDecision(
            allow=False,
            approved_lots=Decimal("0"),
            book=book,
            sizing=sizing,
            pyramid=pyramid,
            correlation_score=corr_score,
            correlation_group=gname,
            symbol_exposure_pct=sym_exp,
            correlated_exposure_pct=corr_exp,
            sector_exposure_pct=sec_exp,
            currency_exposure_pct=cur_exp,
            rejection_reason=reason,
            evidence=evidence,
        )
        if log:
            logger.warning(
                "portfolio_risk_engine_v2_decision",
                allow=False,
                reason=reason,
                symbol=canon,
                equity=str(book.equity),
                exposure=str(book.exposure_pct),
            )
        return decision

    # Broker compliance — never force entries
    blocked = _broker_blocks_new_entry(broker)
    if blocked:
        return _reject(blocked)

    stop_bad = _stop_distance_ok(stop_distance=stop_distance, spec=broker)
    if stop_bad:
        return _reject(stop_bad)

    # Max positions per symbol
    max_per_sym = int(getattr(cfg, "max_positions_per_symbol", 2) or 2)
    sym_count = book.positions_per_symbol.get(canon, 0)
    if sym_count >= max_per_sym > 0:
        return _reject(
            f"Max positions per symbol ({sym_count}>={max_per_sym}) for {canon}"
        )

    # Portfolio / margin / correlation / symbol caps (override trade requests)
    # Project post-trade exposure using configured risk unit for the new leg.
    proposed_risk = (
        risk_pct if risk_pct is not None and risk_pct > 0 else cfg.risk_per_trade_pct
    )
    projected_sym = sym_exp + proposed_risk
    projected_corr = corr_exp + proposed_risk
    projected_sec = sec_exp + proposed_risk
    projected_cur = cur_exp + proposed_risk
    projected_port = book.exposure_pct + proposed_risk

    ite_max_dd = Decimal(str(ite.max_daily_loss_pct))
    blocked_lim, why_lim = check_portfolio_sizing_limits(
        open_positions=book.open_positions,
        max_open_positions=int(cfg.max_open_trades),
        daily_loss_pct=book.daily_loss_pct,
        max_daily_loss_pct=ite_max_dd,
        exposure_pct=projected_port,
        max_exposure_pct=cfg.max_daily_exposure_pct,
        margin_usage_pct=book.margin_usage_pct,
        max_margin_usage_pct=cfg.max_margin_usage_pct,
        symbol_exposure_pct=projected_sym,
        max_symbol_exposure_pct=cfg.max_symbol_exposure_pct,
        correlated_exposure_pct=projected_corr,
        max_correlated_exposure_pct=cfg.max_correlated_exposure_pct,
    )
    if blocked_lim:
        return _reject(f"portfolio_limit:{why_lim or 'caps'}")

    # Sector soft cap (same budget as correlated unless tighter)
    max_sector = getattr(cfg, "max_sector_exposure_pct", None) or (
        cfg.max_correlated_exposure_pct
    )
    if projected_sec >= max_sector > 0:
        return _reject(f"Sector exposure {projected_sec}% at max {max_sector}%")

    max_currency = getattr(cfg, "max_currency_exposure_pct", None) or (
        cfg.max_daily_exposure_pct
    )
    if projected_cur >= max_currency > 0:
        return _reject(f"Currency exposure {projected_cur}% at max {max_currency}%")

    # Winner-only pyramiding / never average into losers
    same_sym_profits: list[Decimal] = []
    same_dir_profits: list[Decimal] = []
    dir_u = (new_direction or "").upper()
    for p in pos_list:
        psym = normalize_book_symbol(str(getattr(p, "symbol", "") or ""))
        pside = str(getattr(p, "side", "") or "").upper()
        upnl = _position_unrealized(p)
        if psym == canon:
            same_sym_profits.append(upnl)
            if dir_u and pside == dir_u:
                same_dir_profits.append(upnl)

    pyramid = may_add_scalping_trade(
        open_positions=book.open_positions,
        max_open=int(cfg.max_open_trades),
        new_confidence=new_confidence or (confidence or 0),
        best_open_confidence=best_open_confidence,
        new_direction=new_direction,
        open_directions=open_directions or tuple(account.open_directions),
        entry=entry,
        open_entries=open_entries or tuple(account.open_entries),
        min_entry_distance=min_entry_distance,
        require_improvement=require_probability_improvement and book.open_positions > 0,
        min_confidence_delta=int(cfg.min_confidence_delta_for_add),
        open_profits=tuple(same_sym_profits),
        require_unrealized_profit=bool(getattr(cfg, "pyramid_winners_only", True))
        and book.open_positions > 0
        and sym_count > 0,
        same_direction_profits=tuple(same_dir_profits),
    )
    if not pyramid.allow:
        return _reject(pyramid.reason, pyramid=pyramid)

    # Dynamic sizing (v2) — never fixed lots
    min_lot = broker.min_lot if broker else cfg.broker_min_lot
    lot_step = broker.lot_step if broker else cfg.broker_lot_step
    max_lot = broker.max_lot if broker else cfg.broker_max_lot
    cs = broker.contract_size if broker else contract_size_for_symbol(canon)

    previous_lot: Decimal | None = None
    vols = [
        _d(getattr(p, "volume", 0))
        for p in pos_list
        if normalize_book_symbol(str(getattr(p, "symbol", "") or "")) == canon
        and _d(getattr(p, "volume", 0)) > 0
    ]
    if vols:
        previous_lot = max(vols)

    sizing = calculate_dynamic_lots_v2(
        equity=book.equity,
        balance=book.balance,
        free_margin=book.free_margin,
        stop_distance=stop_distance,
        atr=atr if atr is not None else account.atr,
        mid_price=mid_price if mid_price is not None else account.mid_price,
        leverage=leverage,
        risk_pct=risk_pct or cfg.risk_per_trade_pct,
        contract_size=cs,
        min_lot=min_lot,
        lot_step=lot_step,
        max_lot=max_lot,
        session_risk_multiplier=session_risk_multiplier,
        daily_exposure_used_pct=book.exposure_pct,
        portfolio_exposure_pct=book.exposure_pct,
        symbol_open_risk_pct=sym_exp,
        quality_score=quality_score,
        confidence=confidence,
        liquidity_score=liquidity_score,
        spread_score=spread_score,
        trend_confidence=trend_confidence,
        quality_reject=quality_reject,
        previous_final_lot=previous_lot,
        max_margin_usage_pct=cfg.max_margin_usage_pct,
        max_symbol_exposure_pct=cfg.max_symbol_exposure_pct,
        lot_growth_max_step_pct=cfg.lot_growth_max_step_pct,
        config=cfg,
        log=log,
    )
    if not sizing.valid:
        return _reject(
            sizing.rejection_reason or sizing.reason,
            sizing=sizing,
            pyramid=pyramid,
        )

    # Re-check margin after proposed lot (portfolio override)
    if (
        mid_price is not None
        and mid_price > 0
        and book.free_margin is not None
        and sizing.final_lot > 0
    ):
        lev = leverage if leverage is not None and leverage > 0 else Decimal("1000")
        need = margin_required(
            volume=sizing.final_lot,
            price=mid_price,
            leverage=lev,
            contract_size=cs,
        )
        if need > book.free_margin:
            return _reject(
                f"Insufficient free margin for lot {sizing.final_lot} "
                f"(need={need} free={book.free_margin})",
                sizing=sizing,
                pyramid=pyramid,
            )

    evidence = {
        "timestamp": book.timestamp,
        "balance": str(book.balance),
        "equity": str(book.equity),
        "free_margin": (
            str(book.free_margin) if book.free_margin is not None else None
        ),
        "floating_pnl": str(book.floating_pnl),
        "risk_pct": str(sizing.risk_pct),
        "preferred_equity_tier": sizing.equity_tier.to_dict(),
        "suggested_lot": str(sizing.suggested_lot),
        "calculated_lot": str(sizing.calculated_lot),
        "final_lot": str(sizing.final_lot),
        "broker_limits": broker.to_dict() if broker else None,
        "ai_score": confidence,
        "quality_score": quality_score,
        "portfolio_exposure": str(book.exposure_pct),
        "symbol_exposure": str(sym_exp),
        "margin_usage": (
            str(book.margin_usage_pct) if book.margin_usage_pct is not None else None
        ),
        "correlation_score": str(corr_score),
        "correlation_group": gname,
        "rejection_reason": None,
        "members": (sorted(correlation_group_members(canon) or ()) if gname else []),
    }
    decision = PortfolioAllocationDecision(
        allow=True,
        approved_lots=sizing.final_lot,
        book=book,
        sizing=sizing,
        pyramid=pyramid,
        correlation_score=corr_score,
        correlation_group=gname,
        symbol_exposure_pct=sym_exp,
        correlated_exposure_pct=corr_exp,
        sector_exposure_pct=sec_exp,
        currency_exposure_pct=cur_exp,
        rejection_reason=None,
        evidence=evidence,
    )
    if log:
        logger.info(
            "portfolio_risk_engine_v2_decision",
            allow=True,
            symbol=canon,
            lots=str(sizing.final_lot),
            equity=str(book.equity),
            exposure=str(book.exposure_pct),
            quality_band=sizing.quality_band,
            correlation_score=str(corr_score),
        )
    return decision
