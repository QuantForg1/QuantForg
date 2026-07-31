"""Multi-asset portfolio scanner — rank all symbols, execute best only (v7).

Preserves v6.3 quality gates and risk limits. Never forces trades.
If XAUUSD has no edge but EURUSD does, EURUSD wins.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.ai_scalping.adaptive_cooldown import (
    resolve_adaptive_cooldown_seconds,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    DEFAULT_SCALPING_UNIVERSE,
    AiScalpingConfig,
)
from app.domain.institutional_trading.ai_scalping.multi_symbol import (
    rank_scalping_opportunities,
)
from app.domain.institutional_trading.ai_scalping.portfolio_risk import (
    PortfolioRiskSnapshot,
    aggregate_portfolio_risk,
)
from app.domain.institutional_trading.ai_scalping.symbol_state import (
    SymbolStateBook,
    get_symbol_state_book,
)
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.decision_models import AccountRiskState


@dataclass(frozen=True, slots=True)
class SymbolScanRow:
    """One symbol's scored opportunity for portfolio ranking."""

    symbol: str
    direction: str
    reject: bool
    confidence: int
    trade_quality: int
    expected_rr: Decimal | None
    spread_score: int
    regime: str | None
    setup_family: str | None
    execution_health_ok: bool
    cooldown_allow: bool
    cooldown_remaining_seconds: float
    reject_reason: str | None = None
    reasons: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "reject": self.reject,
            "ai_confidence": self.confidence,
            "confidence": self.confidence,
            "trade_quality": self.trade_quality,
            "expected_rr": (
                str(self.expected_rr) if self.expected_rr is not None else None
            ),
            "spread_score": self.spread_score,
            "market_regime": self.regime,
            "setup_family": self.setup_family,
            "execution_health_ok": self.execution_health_ok,
            "cooldown_allow": self.cooldown_allow,
            "cooldown_remaining_seconds": round(self.cooldown_remaining_seconds, 2),
            "reject_reason": self.reject_reason,
            "reasons": list(self.reasons),
            **{
                k: v
                for k, v in self.raw.items()
                if k
                not in {
                    "symbol",
                    "direction",
                    "reject",
                    "ai_confidence",
                    "confidence",
                    "trade_quality",
                    "expected_rr",
                    "reject_reason",
                }
            },
        }


@dataclass(frozen=True, slots=True)
class PortfolioScanResult:
    as_of: str
    universe: tuple[str, ...]
    rows: tuple[SymbolScanRow, ...]
    ranked: tuple[dict[str, Any], ...]
    best: dict[str, Any] | None
    blocked_by_portfolio: bool
    portfolio_block_reason: str | None
    open_positions: int
    max_open_positions: int
    daily_loss_pct: Decimal
    exposure_pct: Decimal
    version: str
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "universe": list(self.universe),
            "rows": [r.to_dict() for r in self.rows],
            "ranked": list(self.ranked),
            "best": dict(self.best) if self.best else None,
            "blocked_by_portfolio": self.blocked_by_portfolio,
            "portfolio_block_reason": self.portfolio_block_reason,
            "open_positions": self.open_positions,
            "max_open_positions": self.max_open_positions,
            "daily_loss_pct": str(self.daily_loss_pct),
            "exposure_pct": str(self.exposure_pct),
            "version": self.version,
            "note": self.note,
            "execute_only_best": True,
        }


def _as_decimal(value: Any, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _row_from_score(
    score: dict[str, Any],
    *,
    book: SymbolStateBook,
    config: AiScalpingConfig,
) -> SymbolScanRow:
    symbol = str(score.get("symbol") or "").upper()
    confidence = int(score.get("ai_confidence") or score.get("confidence") or 0)
    quality = int(score.get("trade_quality") or score.get("quality") or 0)
    spread_score = int(score.get("spread_score") or score.get("spread") or 50)
    regime = score.get("market_regime") or score.get("regime")
    setup_family = score.get("setup_family")
    direction = str(score.get("direction") or "NONE").upper()
    reject = bool(score.get("reject"))
    reject_reason = score.get("reject_reason")
    atr_pct = score.get("atr_pct")
    atr_d = _as_decimal(atr_pct) if atr_pct is not None else None

    prior = book.get(symbol)
    health_ok = bool(score.get("execution_health_ok", prior.execution_health_ok))
    book.update_scan(
        symbol,
        quality=quality,
        confidence=confidence,
        regime=str(regime) if regime else None,
        spread_score=spread_score,
        setup_family=str(setup_family) if setup_family else None,
        execution_health_ok=health_ok,
    )
    state = book.get(symbol)

    cd = resolve_adaptive_cooldown_seconds(
        atr_pct=atr_d,
        spread_score=spread_score,
        liquidity_score=int(score.get("liquidity") or 70),
        execution_quality_ok=health_ok,
        recent_rejects=int(score.get("recent_rejects") or state.recent_rejects),
        regime=str(regime) if regime else None,
        config=config,
    )
    scale = Decimal("1.0")
    reg_exec = score.get("regime_execution") or {}
    if isinstance(reg_exec, dict) and reg_exec.get("cooldown_scale") is not None:
        try:
            scale = Decimal(str(reg_exec["cooldown_scale"]))
        except Exception:
            scale = Decimal("1.0")
    scaled = int(Decimal(cd.seconds) * scale)
    scaled = max(config.cooldown_min_seconds, min(config.cooldown_max_seconds, scaled))
    from dataclasses import replace as dc_replace

    cd = dc_replace(cd, seconds=scaled)
    cd_eval = book.evaluate_cooldown(symbol, cd)

    reasons = tuple(score.get("reasons") or ())
    extra_reject: list[str] = []
    if not health_ok:
        extra_reject.append("Symbol execution health degraded")
    if config.adaptive_cooldown_enabled and not cd_eval.allow_new_entry:
        extra_reject.append(
            f"Symbol cooldown active ({cd_eval.remaining_seconds:.0f}s)"
        )

    if extra_reject:
        reject = True
        joined = "; ".join(extra_reject)
        reject_reason = f"{reject_reason}; {joined}" if reject_reason else joined

    rr = score.get("expected_rr")
    return SymbolScanRow(
        symbol=symbol,
        direction=direction,
        reject=reject,
        confidence=confidence,
        trade_quality=quality,
        expected_rr=_as_decimal(rr) if rr is not None else None,
        spread_score=spread_score,
        regime=str(regime) if regime else None,
        setup_family=str(setup_family) if setup_family else None,
        execution_health_ok=health_ok,
        cooldown_allow=cd_eval.allow_new_entry,
        cooldown_remaining_seconds=float(cd_eval.remaining_seconds),
        reject_reason=str(reject_reason) if reject_reason else None,
        reasons=reasons,
        raw=dict(score),
    )


def check_portfolio_limits(
    *,
    open_positions: int,
    max_open_positions: int,
    daily_loss_pct: Decimal,
    max_daily_loss_pct: Decimal,
    exposure_pct: Decimal,
    max_exposure_pct: Decimal,
) -> tuple[bool, str | None]:
    """Return (blocked, reason). Never raises risk ceilings."""
    if open_positions >= max_open_positions:
        return True, (
            f"Max open positions reached ({open_positions}>={max_open_positions})"
        )
    if daily_loss_pct >= max_daily_loss_pct > 0:
        return True, (f"Daily loss limit ({daily_loss_pct}% >= {max_daily_loss_pct}%)")
    if exposure_pct >= max_exposure_pct > 0:
        return True, (
            f"Portfolio exposure limit ({exposure_pct}% >= {max_exposure_pct}%)"
        )
    return False, None


def scan_multi_asset_portfolio(
    scored: list[dict[str, Any]],
    *,
    open_positions: int | None = None,
    daily_loss_pct: Decimal | float | str | None = None,
    exposure_pct: Decimal | float | str | None = None,
    max_open_positions: int | None = None,
    max_daily_loss_pct: Decimal | float | str | None = None,
    max_exposure_pct: Decimal | float | str | None = None,
    account: AccountRiskState | None = None,
    ite_config: ITEConfig | None = None,
    position_risk_pcts: list[Decimal] | tuple[Decimal, ...] | None = None,
    config: AiScalpingConfig | None = None,
    state_book: SymbolStateBook | None = None,
) -> PortfolioScanResult:
    """Scan all symbols independently; rank; select only the best opportunity.

    Portfolio exposure and daily loss are aggregated across ALL symbols
    (via account or explicit portfolio totals) — never per-symbol silos.
    """
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    book = state_book or get_symbol_state_book()
    universe = tuple(cfg.universe or DEFAULT_SCALPING_UNIVERSE)

    agg: PortfolioRiskSnapshot | None = None
    if (
        account is not None
        or open_positions is not None
        or daily_loss_pct is not None
        or exposure_pct is not None
    ):
        agg = aggregate_portfolio_risk(
            account,
            config=cfg,
            ite_config=ite_config,
            position_risk_pcts=position_risk_pcts,
            open_positions_override=open_positions,
        )

    if agg is not None:
        open_n = int(agg.open_positions)
        dd = (
            _as_decimal(daily_loss_pct)
            if daily_loss_pct is not None
            else agg.daily_loss_pct
        )
        exp = (
            _as_decimal(exposure_pct) if exposure_pct is not None else agg.exposure_pct
        )
        max_open = int(
            max_open_positions
            if max_open_positions is not None
            else agg.max_open_positions
        )
        max_dd = _as_decimal(
            max_daily_loss_pct
            if max_daily_loss_pct is not None
            else agg.max_daily_loss_pct
        )
        max_exp = _as_decimal(
            max_exposure_pct if max_exposure_pct is not None else agg.max_exposure_pct
        )
    else:
        open_n = int(open_positions or 0)
        dd = _as_decimal(daily_loss_pct)
        exp = _as_decimal(exposure_pct)
        max_open = int(
            max_open_positions
            if max_open_positions is not None
            else cfg.max_open_trades
        )
        # Institutional ITE daily-loss ceiling — never invent a looser default
        from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG

        max_dd = _as_decimal(
            max_daily_loss_pct
            if max_daily_loss_pct is not None
            else DEFAULT_ITE_CONFIG.max_daily_loss_pct
        )
        max_exp = _as_decimal(
            max_exposure_pct
            if max_exposure_pct is not None
            else cfg.max_daily_exposure_pct
        )

    rows: list[SymbolScanRow] = []
    for raw in scored:
        sym = str(raw.get("symbol") or "").upper()
        if universe and sym and sym not in universe:
            continue
        payload = {**raw, "symbol": sym}
        rows.append(_row_from_score(payload, book=book, config=cfg))

    rank_payload = [r.to_dict() for r in rows]
    ranked_bundle = rank_scalping_opportunities(rank_payload, config=cfg)
    ranked = tuple(ranked_bundle.get("ranked") or ())
    best = ranked_bundle.get("best")

    blocked, block_reason = check_portfolio_limits(
        open_positions=open_n,
        max_open_positions=max_open,
        daily_loss_pct=dd,
        max_daily_loss_pct=max_dd,
        exposure_pct=exp,
        max_exposure_pct=max_exp,
    )
    if blocked:
        best = None

    note = (
        "Execute ONLY the highest-quality symbol opportunity. "
        "Per-symbol quality/cooldown/spread/regime/health are independent. "
        "Exposure and daily loss are portfolio-wide across all symbols. "
        "v6.3 quality and risk floors unchanged."
    )
    if blocked and block_reason:
        note = f"{note} Portfolio block: {block_reason}"

    return PortfolioScanResult(
        as_of=datetime.now(UTC).isoformat(),
        universe=universe,
        rows=tuple(rows),
        ranked=ranked,
        best=dict(best) if best else None,
        blocked_by_portfolio=blocked,
        portfolio_block_reason=block_reason,
        open_positions=open_n,
        max_open_positions=max_open,
        daily_loss_pct=dd,
        exposure_pct=exp,
        version=getattr(cfg, "portfolio_version", None) or cfg.version,
        note=note,
    )
