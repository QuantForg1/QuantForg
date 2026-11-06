"""PR #181 production evidence probe — no secrets printed."""

from __future__ import annotations

import importlib.util
import json
import os
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
PR180_UTC = datetime(2026, 11, 6, 9, 51, tzinfo=UTC)  # approx merge window


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _owner_token() -> str:
    spec = importlib.util.spec_from_file_location(
        "phase4_monitor", ROOT / "scripts" / "phase4_continuous_monitor.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.obtain_owner_token()


def _api_get(path: str, token: str) -> object:
    base = (
        os.environ.get("API_BASE") or "https://quantforg-production.up.railway.app/api/v1"
    ).rstrip("/")
    req = urllib.request.Request(
        f"{base}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        return {"error": exc.code, "path": path, "body": body}
    except Exception as exc:  # noqa: BLE001
        return {"error": type(exc).__name__, "path": path, "detail": str(exc)[:200]}


def _gw_token() -> str:
    return (
        os.environ.get("MT5_GATEWAY_CALLER_TOKEN")
        or os.environ.get("MT5_GATEWAY_TOKEN")
        or ""
    ).strip()


def _gw_get(path: str, token: str) -> object:
    gw = (os.environ.get("MT5_GATEWAY_BASE_URL") or "https://gateway.quantforg.com").rstrip(
        "/"
    )
    req = urllib.request.Request(
        f"{gw}{path}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Gateway-Token": token,
            "X-QuantForg-Gateway-Token": token,
            "User-Agent": "QuantForg-PR181/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        return {"error": exc.code, "path": path, "body": body}
    except Exception as exc:  # noqa: BLE001
        return {"error": type(exc).__name__, "path": path, "detail": str(exc)[:200]}


def _d(v: object) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:
        return Decimal("0")


def _parse_ts(raw: object) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            # MT5 often uses seconds
            return datetime.fromtimestamp(float(raw), tz=UTC)
        except Exception:
            return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        if text.isdigit():
            return datetime.fromtimestamp(float(text), tz=UTC)
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _mask_login(login: object) -> str:
    s = str(login or "").strip()
    if len(s) < 4:
        return "***"
    return f"***{s[-4:]}"


def _summarize_deals(raw: object) -> dict:
    items: list = []
    if isinstance(raw, dict):
        if raw.get("error"):
            return {"error": raw}
        items = raw.get("items") or raw.get("deals") or []
    elif isinstance(raw, list):
        items = raw
    if not isinstance(items, list):
        return {"unexpected": type(raw).__name__}

    by_pos: dict[int, list] = defaultdict(list)
    trade_rows = []
    for deal in items:
        if not isinstance(deal, dict):
            continue
        entry = str(deal.get("entry") or deal.get("entry_type") or "").upper()
        # Keep trade-like deals; skip balance/credit when obvious
        action = str(deal.get("action") or deal.get("type") or "").upper()
        if "BALANCE" in action or "CREDIT" in action:
            continue
        symbol = str(deal.get("symbol") or "")
        if symbol and "XAU" not in symbol.upper() and "GOLD" not in symbol.upper():
            continue
        pid = int(deal.get("position_id") or deal.get("position") or 0)
        row = {
            "ticket": deal.get("ticket") or deal.get("deal"),
            "position_id": pid,
            "symbol": symbol,
            "side": deal.get("type") or deal.get("action") or deal.get("side"),
            "entry": entry,
            "price": deal.get("price"),
            "profit": deal.get("profit"),
            "commission": deal.get("commission"),
            "swap": deal.get("swap"),
            "volume": deal.get("volume"),
            "time": deal.get("time") or deal.get("time_msc") or deal.get("time_done"),
            "comment": str(deal.get("comment") or "")[:80],
            "magic": deal.get("magic"),
        }
        trade_rows.append(row)
        if pid > 0:
            by_pos[pid].append(row)

    closed: list[dict] = []
    for pid, rows in by_pos.items():
        profits = sum((_d(r.get("profit")) for r in rows), Decimal("0"))
        commissions = sum((_d(r.get("commission")) for r in rows), Decimal("0"))
        swaps = sum((_d(r.get("swap")) for r in rows), Decimal("0"))
        times = [_parse_ts(r.get("time")) for r in rows]
        times_ok = [t for t in times if t is not None]
        first = min(times_ok) if times_ok else None
        last = max(times_ok) if times_ok else None
        net = profits + commissions + swaps
        closed.append(
            {
                "position_id": pid,
                "deal_count": len(rows),
                "net_pnl": str(net),
                "gross_profit": str(profits),
                "commission": str(commissions),
                "swap": str(swaps),
                "first_deal_at": first.isoformat() if first else None,
                "last_deal_at": last.isoformat() if last else None,
                "post_pr180": bool(last and last >= PR180_UTC),
                "comments": sorted({str(r.get("comment") or "") for r in rows if r.get("comment")}),
                "sides": sorted({str(r.get("side") or "") for r in rows}),
            }
        )

    post = [c for c in closed if c.get("post_pr180")]
    pre = [c for c in closed if not c.get("post_pr180")]
    return {
        "deal_rows": len(trade_rows),
        "positions_reconstructed": len(closed),
        "post_pr180_positions": len(post),
        "pre_pr180_positions": len(pre),
        "post_pr180_net_sum": str(
            sum((_d(c["net_pnl"]) for c in post), Decimal("0"))
        ),
        "pre_pr180_net_sum_sample": str(
            sum((_d(c["net_pnl"]) for c in pre), Decimal("0"))
        ),
        "post_pr180_closes": sorted(
            post, key=lambda c: c.get("last_deal_at") or "", reverse=True
        )[:50],
        "recent_closes_all": sorted(
            closed, key=lambda c: c.get("last_deal_at") or "", reverse=True
        )[:30],
    }


def main() -> None:
    _load_env()
    public = {
        "health": _api_get_public("https://quantforg-production.up.railway.app/health"),
        "ready": _api_get_public("https://quantforg-production.up.railway.app/ready"),
        "health_live": _api_get_public(
            "https://quantforg-production.up.railway.app/health/live"
        ),
    }

    owner = _owner_token()
    paths = [
        "/ite/ops/auto-trading",
        "/ite/ops/control-center",
        "/ite/ops/robot-health-monitor",
        "/ite/ops/strategy-orchestration-monitor",
        "/ite/ops/strategy-performance-telemetry",
        "/ite/ops/services-health",
        "/ite/ops/execution-evidence",
        "/ite/ops/noc-command-center",
        "/admin/control/overview",
        "/admin/control/policy",
        "/portfolio",
    ]
    api: dict[str, object] = {}
    for path in paths:
        key = path.strip("/").replace("/", "_")
        api[key] = _api_get(path, owner)

    gw_tok = _gw_token()
    gateway: dict[str, object] = {"token_present": bool(gw_tok)}
    if gw_tok:
        account = _gw_get("/account", gw_tok)
        positions = _gw_get("/positions", gw_tok)
        deals7 = _gw_get("/history/deals?days=7", gw_tok)
        deals2 = _gw_get("/history/deals?days=2", gw_tok)
        gateway["account_summary"] = _account_summary(account)
        gateway["positions_summary"] = _positions_summary(positions)
        gateway["deals_7"] = _summarize_deals(deals7)
        gateway["deals_2"] = _summarize_deals(deals2)

    # Extract flag-relevant slices without dumping huge trees
    flags = _extract_flags(api)

    payload = {
        "probed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "pr180_cutoff_utc": PR180_UTC.isoformat().replace("+00:00", "Z"),
        "public": public,
        "flags": flags,
        "gateway": gateway,
        "api_keys": sorted(api.keys()),
        "api_errors": {
            k: v
            for k, v in api.items()
            if isinstance(v, dict) and v.get("error") is not None
        },
        "robot_health_slim": _slim_robot(api.get("ite_ops_robot-health-monitor")),
        "orchestration_slim": _slim_orch(
            api.get("ite_ops_strategy-orchestration-monitor")
        ),
        "auto_trading_slim": _slim_auto(api.get("ite_ops_auto-trading")),
        "admin_overview_slim": _slim_admin(api.get("admin_control_overview")),
        "policy_slim": _slim_policy(api.get("admin_control_policy")),
        "execution_evidence_slim": _slim_exec(api.get("ite_ops_execution-evidence")),
        "services_health_slim": api.get("ite_ops_services-health"),
    }

    out_path = OUT / "evidence_summary.json"
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    # Persist full API blobs separately for offline analysis (may be large)
    full_path = OUT / "api_raw_slim.json"
    full_path.write_text(
        json.dumps(
            {
                "robot_health": api.get("ite_ops_robot-health-monitor"),
                "orchestration": api.get("ite_ops_strategy-orchestration-monitor"),
                "auto_trading": _trim_auto(api.get("ite_ops_auto-trading")),
                "execution_evidence": api.get("ite_ops_execution-evidence"),
                "control_center": api.get("ite_ops_control-center"),
                "admin_overview": api.get("admin_control_overview"),
                "policy": api.get("admin_control_policy"),
                "portfolio": api.get("portfolio"),
                "telemetry": api.get("ite_ops_strategy-performance-telemetry"),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(out_path)
    print(json.dumps({"flags": flags, "gateway": gateway.get("account_summary"), "deals2": gateway.get("deals_2")}, indent=2, default=str)[:6000])


def _api_get_public(url: str) -> object:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:  # noqa: BLE001
        return {"error": type(exc).__name__, "detail": str(exc)[:160]}


def _account_summary(raw: object) -> dict:
    if not isinstance(raw, dict) or raw.get("error"):
        return {"error": raw}
    login = raw.get("login") or raw.get("account") or (raw.get("account_info") or {}).get(
        "login"
    )
    equity = raw.get("equity") or (raw.get("account_info") or {}).get("equity")
    balance = raw.get("balance") or (raw.get("account_info") or {}).get("balance")
    server = raw.get("server") or (raw.get("account_info") or {}).get("server")
    return {
        "login_masked": _mask_login(login),
        "login_last4": str(login)[-4:] if login else None,
        "equity": equity,
        "balance": balance,
        "server_present": bool(server),
        "trade_allowed": raw.get("trade_allowed")
        or (raw.get("account_info") or {}).get("trade_allowed"),
    }


def _positions_summary(raw: object) -> dict:
    items = []
    if isinstance(raw, dict):
        if raw.get("error"):
            return {"error": raw}
        items = raw.get("items") or raw.get("positions") or []
    elif isinstance(raw, list):
        items = raw
    if not isinstance(items, list):
        return {"unexpected": type(raw).__name__}
    slim = []
    for p in items:
        if not isinstance(p, dict):
            continue
        slim.append(
            {
                "ticket": p.get("ticket") or p.get("position_id"),
                "symbol": p.get("symbol"),
                "side": p.get("type") or p.get("side"),
                "volume": p.get("volume"),
                "price_open": p.get("price_open") or p.get("open_price"),
                "sl": p.get("sl"),
                "tp": p.get("tp"),
                "profit": p.get("profit"),
                "magic": p.get("magic"),
                "comment": str(p.get("comment") or "")[:60],
            }
        )
    return {"count": len(slim), "positions": slim}


def _extract_flags(api: dict[str, object]) -> dict:
    robot = api.get("ite_ops_robot-health-monitor")
    admin = api.get("admin_control_overview")
    policy = api.get("admin_control_policy")
    auto = api.get("ite_ops_auto-trading")
    out: dict[str, object] = {}
    if isinstance(robot, dict) and not robot.get("error"):
        m1 = robot.get("m1") if isinstance(robot.get("m1"), dict) else {}
        out["m1_from_robot_health"] = m1
        pme = robot.get("pme") if isinstance(robot.get("pme"), dict) else {}
        out["pme_from_robot_health"] = {
            k: pme.get(k)
            for k in (
                "live_reversal_exits_enabled",
                "shadow_reversal_exits_enabled",
                "require_broker_sl_confirm",
            )
            if k in pme
        } or pme
    if isinstance(admin, dict) and not admin.get("error"):
        dep = admin.get("deployment") if isinstance(admin.get("deployment"), dict) else {}
        out["admin_commit"] = dep.get("commit_sha")
        out["admin_broker_login_masked"] = (admin.get("broker") or {}).get("account")
        out["admin_execution"] = {
            k: (admin.get("execution") or {}).get(k)
            for k in ("execution_enabled", "ops_mode", "kill_switch_armed")
            if isinstance(admin.get("execution"), dict)
        }
    if isinstance(policy, dict) and not policy.get("error"):
        doc = policy.get("document") if isinstance(policy.get("document"), dict) else policy
        out["policy_m1_micro_enabled"] = doc.get("m1_micro_enabled")
        out["policy_m1_live_submit"] = doc.get("m1_live_submit")
        out["policy_risk_pct"] = doc.get("max_planned_risk_pct")
        out["policy_daily_loss_pct"] = doc.get("daily_loss_pct")
        out["policy_max_lot"] = doc.get("max_lot")
        out["policy_min_quality"] = doc.get("min_trade_quality")
        out["policy_min_rr"] = doc.get("min_reward_risk")
    if isinstance(auto, dict) and not auto.get("error"):
        ex = auto.get("execution_state") if isinstance(auto.get("execution_state"), dict) else {}
        out["auto_status"] = auto.get("status")
        out["auto_allowed"] = auto.get("allowed")
        out["execution_enabled"] = ex.get("execution_enabled")
        out["ops_mode"] = ex.get("ops_mode")
        out["gateway_connected"] = ex.get("gateway_connected")
        out["broker_connected"] = ex.get("broker_connected")
        out["run_state"] = ex.get("auto_trading_run_state")
    return out


def _slim_robot(raw: object) -> dict:
    if not isinstance(raw, dict) or raw.get("error"):
        return {"error": raw}
    robot = raw.get("robot") if isinstance(raw.get("robot"), dict) else {}
    return {
        "as_of": raw.get("as_of"),
        "m1": raw.get("m1"),
        "pme": raw.get("pme"),
        "risk_policy_defaults": raw.get("risk_policy_defaults"),
        "robot": {
            "last_soe_decision": robot.get("last_soe_decision"),
            "last_soe_reasons": robot.get("last_soe_reasons"),
            "last_regime": robot.get("last_regime"),
            "last_symbol": robot.get("last_symbol"),
            "last_cycle_at": robot.get("last_cycle_at"),
            "market_data_fresh": robot.get("market_data_fresh"),
            "cycles_observed": robot.get("cycles_observed"),
        },
        "strategies": [
            {
                "strategy_id": s.get("strategy_id"),
                "status": s.get("operational_status"),
                "scans": s.get("scans"),
                "accepted": s.get("accepted"),
                "rejected": s.get("rejected"),
                "last_direction": s.get("last_direction"),
                "last_quality": s.get("last_quality"),
                "last_reject_reason": str(s.get("last_reject_reason") or "")[:180],
            }
            for s in (raw.get("strategies") or [])
            if isinstance(s, dict)
        ][:20],
        "shadow_exits": raw.get("shadow_exits") or raw.get("pme_shadow_exits"),
        "reversal": raw.get("reversal") or raw.get("live_reversal"),
    }


def _slim_orch(raw: object) -> dict:
    if not isinstance(raw, dict) or raw.get("error"):
        return {"error": raw}
    return {
        "keys": sorted(raw.keys())[:40],
        "unified": raw.get("unified_decision") or raw.get("last_unified_decision"),
        "selected": raw.get("selected_strategy") or raw.get("last_selected_strategy_id"),
        "conflicts": raw.get("conflicts") or raw.get("direction_conflicts"),
        "m1": raw.get("m1") or raw.get("m1_micro"),
    }


def _slim_auto(raw: object) -> dict:
    if not isinstance(raw, dict) or raw.get("error"):
        return {"error": raw}
    return {
        "status": raw.get("status"),
        "allowed": raw.get("allowed"),
        "primary_blocker": raw.get("primary_blocker"),
        "execution_state": raw.get("execution_state"),
        "failed_reasons_sample": (raw.get("failed_reasons") or [])[:10],
    }


def _slim_admin(raw: object) -> dict:
    if not isinstance(raw, dict) or raw.get("error"):
        return {"error": raw}
    return {
        "deployment": raw.get("deployment"),
        "broker": {
            k: (raw.get("broker") or {}).get(k)
            for k in (
                "ownership",
                "gateway_online",
                "mt5_connected",
                "account",
                "account_mode",
                "equity",
                "balance",
                "server",
            )
        },
        "execution": raw.get("execution") or raw.get("live"),
    }


def _slim_policy(raw: object) -> dict:
    if not isinstance(raw, dict) or raw.get("error"):
        return {"error": raw}
    doc = raw.get("document") if isinstance(raw.get("document"), dict) else raw
    keys = [
        "max_planned_risk_pct",
        "daily_loss_pct",
        "max_lot",
        "min_trade_quality",
        "min_reward_risk",
        "preferred_reward_risk",
        "max_concurrent_positions",
        "max_aggregate_open_risk_pct",
        "m1_micro_enabled",
        "m1_live_submit",
        "allow_martingale",
        "allow_grid",
        "allow_average_down",
    ]
    return {k: doc.get(k) for k in keys}


def _slim_exec(raw: object) -> dict:
    if not isinstance(raw, dict) or raw.get("error"):
        return {"error": raw}
    return {
        "keys": sorted(raw.keys())[:50],
        "last_close": raw.get("last_close") or raw.get("recent_closes"),
        "last_entry": raw.get("last_entry") or raw.get("recent_entries"),
        "reversal": raw.get("reversal") or raw.get("shadow_reversal"),
    }


def _trim_auto(raw: object) -> object:
    if not isinstance(raw, dict):
        return raw
    # Drop huge reason histograms if present
    out = dict(raw)
    for heavy in ("reason_groups", "reason_histogram", "cycle_log", "history"):
        if heavy in out and isinstance(out[heavy], (dict, list)):
            out[heavy] = {"trimmed": True, "type": type(out[heavy]).__name__}
    return out


if __name__ == "__main__":
    main()
