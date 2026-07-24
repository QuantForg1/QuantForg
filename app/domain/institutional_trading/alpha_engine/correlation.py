"""Correlation protection — never open highly correlated book legs."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.institutional_trading.alpha_engine.config import (
    DEFAULT_ALPHA_CONFIG,
    InstitutionalAlphaConfig,
)


@dataclass(frozen=True, slots=True)
class CorrelationDecision:
    allow: bool
    reason: str
    conflicting_symbols: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "allow": self.allow,
            "reason": self.reason,
            "conflicting_symbols": list(self.conflicting_symbols),
        }


def _norm(sym: str) -> str:
    return "".join(ch for ch in (sym or "").upper() if ch.isalnum())


def correlation_group_for(
    symbol: str,
    *,
    config: InstitutionalAlphaConfig | None = None,
) -> tuple[str, ...] | None:
    cfg = config or DEFAULT_ALPHA_CONFIG
    target = _norm(symbol)
    for group in cfg.correlation_groups:
        norms = tuple(_norm(s) for s in group)
        if target in norms:
            return tuple(s.upper() for s in group)
    return None


def may_open_with_correlation(
    *,
    candidate_symbol: str,
    open_symbols: tuple[str, ...] | list[str],
    config: InstitutionalAlphaConfig | None = None,
) -> CorrelationDecision:
    cfg = config or DEFAULT_ALPHA_CONFIG
    if not cfg.correlation_protection:
        return CorrelationDecision(True, "Correlation protection disabled")

    group = correlation_group_for(candidate_symbol, config=cfg)
    if group is None:
        return CorrelationDecision(True, "No correlation group for candidate")

    open_norms = {_norm(s) for s in open_symbols}
    group_norms = {_norm(s) for s in group}
    conflicts = tuple(
        sorted(s for s in open_symbols if _norm(s) in group_norms and _norm(s) != _norm(candidate_symbol))
    )
    open_in_group = sum(1 for s in open_norms if s in group_norms)
    # If candidate already open, counting toward limit is fine
    if open_in_group >= cfg.max_correlated_open and _norm(candidate_symbol) not in open_norms:
        return CorrelationDecision(
            False,
            (
                f"Correlation block: {candidate_symbol} conflicts with open "
                f"{', '.join(conflicts) or 'group peers'} "
                f"(max_correlated_open={cfg.max_correlated_open})"
            ),
            conflicting_symbols=conflicts,
        )
    if conflicts and cfg.max_correlated_open <= 1:
        return CorrelationDecision(
            False,
            f"Correlation block: cannot open {candidate_symbol} with {', '.join(conflicts)}",
            conflicting_symbols=conflicts,
        )
    return CorrelationDecision(True, "Correlation check passed")


def correlation_matrix(
    symbols: tuple[str, ...] | list[str],
    *,
    config: InstitutionalAlphaConfig | None = None,
) -> dict[str, dict[str, float]]:
    """Binary institutional matrix: 1.0 if same correlation group else 0.0 (diag=1)."""
    cfg = config or DEFAULT_ALPHA_CONFIG
    syms = [s.upper() for s in symbols]
    matrix: dict[str, dict[str, float]] = {s: {} for s in syms}
    for a in syms:
        ga = correlation_group_for(a, config=cfg)
        for b in syms:
            if a == b:
                matrix[a][b] = 1.0
                continue
            gb = correlation_group_for(b, config=cfg)
            linked = bool(ga and gb and set(ga) & set(gb) and a in (ga or ()) and b in (gb or ()))
            # Same group membership
            if ga and _norm(b) in {_norm(x) for x in ga}:
                linked = True
            matrix[a][b] = 1.0 if linked else 0.0
    return matrix
