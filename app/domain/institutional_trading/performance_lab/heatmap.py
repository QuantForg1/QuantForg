"""Portfolio heatmap — exposure, correlation, risk, confidence, PnL."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PortfolioHeatmapStore:
    cells: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def update_from_positions(
        self,
        positions: list[dict[str, Any]],
        *,
        correlation: dict[str, Any] | None = None,
        confidence_by_symbol: dict[str, Any] | None = None,
        realized_pnl: float | None = None,
    ) -> None:
        corr = correlation or {}
        conf = confidence_by_symbol or {}
        cells: list[dict[str, Any]] = []
        for p in positions:
            sym = str(p.get("symbol") or "")
            exposure = float(p.get("remaining_volume") or p.get("volume") or 0)
            unrealized = float(p.get("unrealized_pnl") or p.get("pnl") or 0)
            # Correlation heat: max abs corr vs other open symbols
            row = corr.get(sym) if isinstance(corr.get(sym), dict) else {}
            corr_heat = 0.0
            if isinstance(row, dict):
                vals = []
                for k, v in row.items():
                    if k.upper() == sym.upper():
                        continue
                    try:
                        vals.append(abs(float(v)))
                    except Exception:
                        continue
                corr_heat = max(vals) if vals else 0.0
            ai_conf = conf.get(sym)
            try:
                ai_conf_f = float(ai_conf) if ai_conf is not None else None
            except Exception:
                ai_conf_f = None
            cells.append(
                {
                    "symbol": sym,
                    "exposure": exposure,
                    "correlation": round(corr_heat, 3),
                    "risk_allocation": round(exposure, 4),
                    "ai_confidence": ai_conf_f,
                    "unrealized_pnl": unrealized,
                    "realized_pnl": realized_pnl,
                    # Heat intensities 0–100 for UI
                    "heat_exposure": min(100, int(abs(exposure) * 200)),
                    "heat_correlation": min(100, int(corr_heat * 100)),
                    "heat_pnl": min(100, int(abs(unrealized) * 2)),
                }
            )
        with self._lock:
            self.cells = cells

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "cells": list(self.cells),
                "count": len(self.cells),
            }


_STORE: PortfolioHeatmapStore | None = None
_LOCK = threading.Lock()


def get_portfolio_heatmap_store() -> PortfolioHeatmapStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = PortfolioHeatmapStore()
        return _STORE
