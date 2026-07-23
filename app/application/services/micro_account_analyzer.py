"""Micro Account Analyzer application service — live broker specs + math.

Never modifies Institutional Mode, Strategy, OMS, Safety, or risk policy.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.atr import compute_atr
from app.domain.institutional_trading.micro_account_analyzer import (
    RISK_LADDER_PCT,
    BrokerLotSpecs,
    analyze_micro_account,
    broker_specs_from_mapping,
    desk_fallback_specs,
    institutional_profile_dict,
    micro_profile_dict,
)
from app.domain.institutional_trading.micro_account_mode import (
    DEFAULT_ATR_STOP_MULTIPLIER,
    DEFAULT_REFERENCE_ATR,
    SUPPORTED_BALANCES,
)
from app.domain.market_data.timeframe import Timeframe
from app.domain.trading.gold_only import GOLD_SYMBOL
from core.logging import get_logger

logger = get_logger(__name__)


def _try_live_broker_specs() -> tuple[BrokerLotSpecs, dict[str, Any]]:
    """Read live XAUUSD specs from MT5 gateway when available."""
    meta: dict[str, Any] = {"attempted": True, "ok": False}

    # 1) Prefer DI-wired adapter (API process).
    try:
        from core.di.container import get_container

        adapter = getattr(get_container(), "mt5_adapter", None)
        if adapter is not None:
            client = getattr(adapter, "client", None) or getattr(
                adapter, "_client", None
            )
            if client is not None:
                adopt = getattr(client, "adopt_existing_session", None)
                if callable(adopt) and not getattr(client, "is_connected", False):
                    try:
                        adopt()
                    except Exception as exc:  # noqa: BLE001
                        meta["adopt_error"] = str(exc)
                if getattr(client, "is_connected", False):
                    info = client.symbol_info(GOLD_SYMBOL)
                    raw = info.to_dict() if hasattr(info, "to_dict") else {}
                    try:
                        specs_fn = getattr(client, "_request", None)
                        if callable(specs_fn):
                            payload = specs_fn("GET", f"/symbols/{GOLD_SYMBOL}")
                            if isinstance(payload, dict) and payload.get(
                                "volume_min"
                            ):
                                raw = {**raw, **payload}
                    except Exception as exc:  # noqa: BLE001
                        meta["specs_endpoint_error"] = str(exc)
                    specs = broker_specs_from_mapping(raw, source="live_broker")
                    meta["ok"] = True
                    meta["via"] = "di_adapter"
                    return specs, meta
    except Exception as exc:  # noqa: BLE001
        meta["di_error"] = str(exc)

    # 2) Direct local gateway (scripts / offline ops without DI).
    try:
        import os
        from pathlib import Path

        from dotenv import load_dotenv

        load_dotenv(Path.cwd() / ".env")
        token = (os.getenv("MT5_GATEWAY_TOKEN") or "").strip()
        base = (
            os.getenv("MT5_GATEWAY_URL")
            or os.getenv("MT5_GATEWAY_BASE_URL")
            or "http://127.0.0.1:8765"
        )
        if token:
            from app.infrastructure.brokers.mt5.gateway_client import (
                GatewayMT5Client,
            )

            client = GatewayMT5Client(base_url=base, token=token)
            if client.adopt_existing_session():
                payload = client._request("GET", f"/symbols/{GOLD_SYMBOL}")  # noqa: SLF001
                if isinstance(payload, dict):
                    specs = broker_specs_from_mapping(
                        payload, source="live_broker"
                    )
                    meta["ok"] = True
                    meta["via"] = "direct_gateway"
                    meta["gateway_url"] = base
                    return specs, meta
            meta["error"] = "gateway_session_not_attached"
        else:
            meta["error"] = "no_MT5_GATEWAY_TOKEN"
    except Exception as exc:  # noqa: BLE001
        logger.warning("micro_analyzer_live_specs_failed", error=str(exc))
        meta["error"] = str(exc)

    return desk_fallback_specs(), meta


def _try_live_atr() -> tuple[Decimal, dict[str, Any]]:
    """Compute M15 ATR from live candles when gateway is available."""
    from app.application.services.ite_cycle_market_context import _rate_to_candle

    meta: dict[str, Any] = {"attempted": True, "ok": False, "timeframe": "M15"}

    def _from_client(client: Any) -> tuple[Decimal, dict[str, Any]] | None:
        if not getattr(client, "is_connected", False):
            return None
        rates = client.copy_rates_from_pos(GOLD_SYMBOL, Timeframe.M15, 0, 80)
        candles = [_rate_to_candle(r) for r in (rates or [])]
        atr = compute_atr(candles, period=14)
        if atr is None or atr <= 0:
            return None
        return atr, {
            "attempted": True,
            "ok": True,
            "timeframe": "M15",
            "bars": len(candles),
            "source": "live_m15",
        }

    try:
        from core.di.container import get_container

        adapter = getattr(get_container(), "mt5_adapter", None)
        client = getattr(adapter, "client", None) if adapter else None
        if client is not None:
            got = _from_client(client)
            if got is not None:
                return got
    except Exception as exc:  # noqa: BLE001
        meta["di_error"] = str(exc)

    try:
        import os
        from pathlib import Path

        from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client
        from dotenv import load_dotenv

        load_dotenv(Path.cwd() / ".env")
        token = (os.getenv("MT5_GATEWAY_TOKEN") or "").strip()
        base = (
            os.getenv("MT5_GATEWAY_URL")
            or os.getenv("MT5_GATEWAY_BASE_URL")
            or "http://127.0.0.1:8765"
        )
        if token:
            client = GatewayMT5Client(base_url=base, token=token)
            if client.adopt_existing_session():
                got = _from_client(client)
                if got is not None:
                    atr, atr_meta = got
                    atr_meta["via"] = "direct_gateway"
                    return atr, atr_meta
            meta["error"] = "gateway_session_not_attached"
        else:
            meta["error"] = "no_MT5_GATEWAY_TOKEN"
    except Exception as exc:  # noqa: BLE001
        meta["error"] = str(exc)

    meta["source"] = "reference_fallback"
    return DEFAULT_REFERENCE_ATR, meta


def run_micro_account_analyzer(
    *,
    balance: Decimal = Decimal("50"),
    risk_pct: Decimal = Decimal("2.00"),
    atr: Decimal | None = None,
    use_live_broker: bool = True,
    use_live_atr: bool = True,
) -> dict[str, Any]:
    """Build analyzer report for Operations → Micro Account Analyzer."""
    generated_at = datetime.now(UTC)
    live_meta: dict[str, Any] = {}
    atr_meta: dict[str, Any] = {}

    if use_live_broker:
        specs, live_meta = _try_live_broker_specs()
    else:
        specs = desk_fallback_specs()
        live_meta = {"attempted": False, "ok": False}

    if atr is not None and atr > 0:
        atr_val = atr
        atr_meta = {"attempted": False, "ok": True, "source": "operator"}
    elif use_live_atr:
        atr_val, atr_meta = _try_live_atr()
        atr_meta["source"] = "live_m15" if atr_meta.get("ok") else "reference_fallback"
    else:
        atr_val = DEFAULT_REFERENCE_ATR
        atr_meta = {"attempted": False, "ok": True, "source": "reference"}

    report = analyze_micro_account(
        balance=balance,
        risk_pct=risk_pct,
        atr=atr_val,
        specs=specs,
        atr_multiplier=DEFAULT_ATR_STOP_MULTIPLIER,
    )
    report["generated_at"] = generated_at.isoformat()
    report["live_broker"] = live_meta
    report["live_atr"] = atr_meta
    report["risk_ladder_pct"] = [str(p) for p in RISK_LADDER_PCT]
    report["supported_balances"] = [str(b) for b in SUPPORTED_BALANCES]
    report["profiles"]["INSTITUTIONAL"] = institutional_profile_dict()
    report["profiles"]["MICRO_ACCOUNT_MODE"] = micro_profile_dict(specs=specs)
    return report


def report_to_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    specs = report.get("broker_specs") or {}
    lines.append("# Micro Account Analyzer — Feasibility Report")
    lines.append("")
    lines.append(f"- Generated: `{report.get('generated_at', '—')}`")
    lines.append(
        f"- Institutional Mode modified: "
        f"**{report.get('institutional_mode_modified')}**"
    )
    lines.append(
        f"- Strategy / OMS / Safety unchanged: "
        f"**{report.get('strategy_oms_safety_unchanged')}**"
    )
    lines.append("")
    lines.append("## Broker specs")
    lines.append("")
    lines.append(
        f"- Source: `{specs.get('source')}` · min_lot={specs.get('volume_min')} · "
        f"step={specs.get('volume_step')} · contract={specs.get('contract_size')} · "
        f"tick_size={specs.get('tick_size')} · tick_value={specs.get('tick_value')}"
    )
    if specs.get("micro_account_compatible"):
        lines.append("- **Micro account compatible** (broker min lot ≤ 0.001)")
    else:
        lines.append(
            "- Standard min lot — not nano; current broker settings unchanged"
        )
    lines.append("")
    lines.append("## Selected analysis")
    lines.append("")
    lines.append(f"- Balance: **${report.get('balance')}**")
    lines.append(f"- Risk %: **{report.get('risk_pct')}%**")
    lines.append(
        f"- ATR={report.get('atr')} · Stop={report.get('atr_stop')} · "
        f"Lots={report.get('calculated_lots')}"
    )
    lines.append(
        f"- Eligible: **{report.get('eligible_label')}** "
        f"({report.get('status')})"
    )
    lines.append(f"- Reason: {report.get('reason')}")
    if report.get("fifty_dollar_clear_statement"):
        lines.append("")
        lines.append(f"**{report['fifty_dollar_clear_statement']}**")
    lines.append("")
    lines.append("## Minimum safe balance (this broker)")
    lines.append("")
    lines.append("| Risk % | Min safe balance | $ risk @ min_lot |")
    lines.append("|---:|---:|---:|")
    for row in report.get("min_safe_balances_by_risk") or []:
        lines.append(
            f"| {row.get('risk_pct')}% | ${row.get('min_safe_balance')} | "
            f"${row.get('dollar_risk_at_min_lot')} |"
        )
    lines.append("")
    lines.append("## Supported balance matrix")
    lines.append("")
    lines.append("| Balance | Status | Lots | Max loss | Reason |")
    lines.append("|---:|---|---:|---:|---|")
    for row in report.get("supported_balance_matrix") or []:
        lines.append(
            f"| ${row.get('balance')} | {row.get('status')} | "
            f"{row.get('calculated_lots')} | ${row.get('max_loss')} | "
            f"{row.get('reason')} |"
        )
    lines.append("")
    return "\n".join(lines)
