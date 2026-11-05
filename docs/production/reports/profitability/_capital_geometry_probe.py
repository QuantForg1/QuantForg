"""One-shot capital + min-lot geometry probe (read-only)."""

from __future__ import annotations

import json
import os
import urllib.request
from decimal import Decimal
from pathlib import Path

from app.domain.institutional_trading.operations.min_lot_feasibility import (
    evaluate_min_lot_feasibility,
    lot_dollar_risk,
    max_allowed_stop_at_min_lot,
    min_lot_needed_pct,
)


def _load_token() -> str:
    existing = (os.environ.get("MT5_GATEWAY_TOKEN") or "").strip()
    if existing:
        return existing
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("MT5_GATEWAY_TOKEN="):
            return s.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("MT5_GATEWAY_TOKEN missing")


def _get(path: str, token: str) -> dict:
    req = urllib.request.Request(
        f"https://gateway.quantforg.com{path}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Gateway-Token": token,
            "X-QuantForg-Gateway-Token": token,
            "User-Agent": "QuantForg-CapitalVerify/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    token = _load_token()
    account = _get("/account", token)
    positions = _get("/positions", token)
    session = _get("/session/status", token)
    symbol = _get("/symbols/XAUUSD", token)
    quote = _get("/quotes/XAUUSD", token)

    equity = Decimal(str(account["equity"]))
    balance = Decimal(str(account["balance"]))
    hard = Decimal("20")
    min_lot = Decimal(str(symbol["volume_min"]))
    cs = Decimal(str(symbol["contract_size"]))
    tick_size = Decimal(str(symbol["tick_size"]))
    tick_value = Decimal(str(symbol["tick_value"]))
    bid = Decimal(str(quote["bid"]))
    ask = Decimal(str(quote["ask"]))
    spread = ask - bid

    max_loss = (equity * hard / Decimal("100")).quantize(Decimal("0.01"))
    max_stop = max_allowed_stop_at_min_lot(
        equity=equity,
        hard_max_risk_pct=hard,
        min_lot=min_lot,
        contract_size=cs,
        tick_size=tick_size,
        tick_value=tick_value,
    )

    stops = [
        Decimal("2.0"),
        Decimal("3.0"),
        Decimal("4.0"),
        Decimal("5.065"),
        Decimal("5.5"),
        Decimal("6.0"),
        max_stop,
        Decimal("7.0"),
        Decimal("10.0"),
    ]
    rows = []
    for stop in stops:
        feas = evaluate_min_lot_feasibility(
            equity=equity,
            stop_distance=stop,
            hard_max_risk_pct=hard,
            min_lot=min_lot,
            contract_size=cs,
            tick_size=tick_size,
            tick_value=tick_value,
        )
        rows.append(
            {
                "stop": str(stop),
                "dollar_risk": str(
                    lot_dollar_risk(
                        min_lot,
                        stop_distance=stop,
                        contract_size=cs,
                        tick_size=tick_size,
                        tick_value=tick_value,
                    )
                ),
                "needed_pct": str(
                    min_lot_needed_pct(
                        stop_distance=stop,
                        equity=equity,
                        min_lot=min_lot,
                        contract_size=cs,
                        tick_size=tick_size,
                        tick_value=tick_value,
                    )
                ),
                "classification": feas.classification,
                "infeasible": feas.infeasible,
            }
        )

    # Prior blocker comparison
    old_equity = Decimal("14.92")
    prior_stop = Decimal("5.065")
    prior = evaluate_min_lot_feasibility(
        equity=old_equity,
        stop_distance=prior_stop,
        hard_max_risk_pct=hard,
        min_lot=min_lot,
        contract_size=cs,
        tick_size=tick_size,
        tick_value=tick_value,
    )
    now_same_stop = evaluate_min_lot_feasibility(
        equity=equity,
        stop_distance=prior_stop,
        hard_max_risk_pct=hard,
        min_lot=min_lot,
        contract_size=cs,
        tick_size=tick_size,
        tick_value=tick_value,
    )

    out = {
        "account": {
            "login": account.get("login"),
            "server": account.get("server"),
            "currency": account.get("currency"),
            "balance": str(balance),
            "equity": str(equity),
            "margin": str(account.get("margin")),
            "free_margin": str(account.get("free_margin")),
            "profit": str(account.get("profit")),
            "leverage": account.get("leverage"),
            "trade_allowed": account.get("trade_allowed"),
            "deposit_vs_prior_14_92": str(balance - Decimal("14.92")),
        },
        "positions_count": len(positions.get("items") or []),
        "session": {
            "connected": session.get("connected"),
            "trade_allowed": (session.get("health") or {}).get("trade_allowed"),
            "mt5_autotrading_enabled": (session.get("health") or {}).get(
                "mt5_autotrading_enabled"
            ),
            "degraded": (session.get("health") or {}).get("degraded"),
        },
        "xauusd": {
            "volume_min": str(min_lot),
            "volume_step": str(symbol.get("volume_step")),
            "contract_size": str(cs),
            "tick_size": str(tick_size),
            "tick_value": str(tick_value),
            "stops_level": symbol.get("stops_level"),
            "freeze_level": symbol.get("freeze_level"),
            "bid": str(bid),
            "ask": str(ask),
            "spread": str(spread),
            "market_open": symbol.get("market_open"),
        },
        "owner_risk_pct": str(hard),
        "max_monetary_risk_20pct": str(max_loss),
        "max_allowed_stop_at_min_lot": str(max_stop),
        "geometry_rows": rows,
        "prior_blocker_stop_5_065": {
            "at_equity_14_92": {
                "classification": prior.classification,
                "infeasible": prior.infeasible,
            },
            "at_current_equity": {
                "classification": now_same_stop.classification,
                "infeasible": now_same_stop.infeasible,
            },
        },
    }
    path = Path("docs/production/reports/profitability/capital_geometry_probe.json")
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
