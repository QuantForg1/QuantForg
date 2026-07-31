"""Portfolio Intelligence v2 (AI v8) — predictive warnings before Risk.

Warnings only. Never blocks Risk/PRE/OMS. Never changes limits.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_portfolio_intelligence_v2(
    positions: list[Any] | dict[Any, Any] | None = None,
) -> dict[str, Any]:
    """Forecast heat / concentration / correlation expansion — warnings only."""
    warnings: list[dict[str, Any]] = []
    exposure: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping.portfolio_exposure_intelligence import (  # noqa: E501
            build_portfolio_exposure,
        )

        if positions is None:
            try:
                from app.application.services.institutional_ite_runtime import (
                    get_ite_runtime,
                )

                rt = get_ite_runtime()
                if rt is not None:
                    engine = getattr(
                        getattr(rt, "position_management", None), "engine", None
                    )
                    positions = getattr(engine, "_positions", None)
            except Exception:
                positions = None
        exposure = build_portfolio_exposure(positions)
    except Exception:
        exposure = {"open_positions": 0, "fabricated": False}

    open_n = int(exposure.get("open_positions") or 0)
    long_e = float(exposure.get("long_exposure") or 0)
    short_e = float(exposure.get("short_exposure") or 0)
    net = float(exposure.get("net_exposure") or 0)
    sectors = (
        exposure.get("sector_exposure")
        if isinstance(exposure.get("sector_exposure"), dict)
        else {}
    )
    corr = (
        exposure.get("correlation_risk")
        if isinstance(exposure.get("correlation_risk"), dict)
        else {}
    )

    gross = long_e + short_e
    heat = round(gross, 4)
    if open_n >= 3:
        warnings.append(
            {
                "code": "portfolio_heat",
                "severity": "warn",
                "message": (
                    f"Portfolio heat elevated: {open_n} open positions, "
                    f"gross exposure {gross}."
                ),
            }
        )
    if sectors:
        top_sector, top_val = max(sectors.items(), key=lambda kv: float(kv[1] or 0))
        if gross > 0 and float(top_val) / gross >= 0.6:
            warnings.append(
                {
                    "code": "sector_concentration",
                    "severity": "warn",
                    "message": (
                        f"Sector concentration: {top_sector} holds "
                        f"{round(100 * float(top_val) / gross, 1)}% of gross."
                    ),
                }
            )
    if corr:
        top_corr, top_cval = max(corr.items(), key=lambda kv: float(kv[1] or 0))
        if gross > 0 and float(top_cval) / gross >= 0.5 and open_n >= 2:
            warnings.append(
                {
                    "code": "correlation_expansion",
                    "severity": "warn",
                    "message": (
                        f"Correlation expansion risk in group '{top_corr}' "
                        f"({round(100 * float(top_cval) / gross, 1)}% of gross)."
                    ),
                }
            )
    if abs(net) > 0 and gross > 0 and abs(net) / gross >= 0.85 and open_n >= 2:
        warnings.append(
            {
                "code": "risk_clustering",
                "severity": "warn",
                "message": (
                    f"Directional risk clustering: net/gross="
                    f"{round(abs(net) / gross, 2)}."
                ),
            }
        )

    return {
        "as_of": _iso(),
        "portfolio_heat": heat,
        "open_positions": open_n,
        "net_exposure": net,
        "long_exposure": long_e,
        "short_exposure": short_e,
        "sector_exposure": sectors,
        "correlation_risk": corr,
        "warnings": warnings,
        "warning_count": len(warnings),
        "blocks_risk_engine": False,
        "auto_applies": False,
        "fabricated": False,
        "observe_only": True,
        "note": "Warnings only — existing PRE/Risk limits remain sole enforcement",
    }
