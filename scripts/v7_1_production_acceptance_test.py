#!/usr/bin/env python3
"""QuantForg v7.1 Production Acceptance Test (PAT) verifier.

Verification only — does not change strategy, risk, quality gates, or features.
Never fabricates LIVE readiness. Emits PASS / FAIL / BLOCKED per test.
"""

from __future__ import annotations

import json
import os
import socket
import statistics
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

Status = Literal["PASS", "FAIL", "BLOCKED"]
EXPECTED_UNIVERSE = {
    "XAUUSD",
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "NAS100",
    "US30",
    "BTCUSD",
    "ETHUSD",
}


def _http_json(url: str, timeout: float = 8.0) -> tuple[bool, Any]:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return True, json.loads(raw)
            except json.JSONDecodeError:
                return True, {"raw": raw[:500], "status": getattr(resp, "status", None)}
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _run_pytest(paths: list[str]) -> tuple[bool, str]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-o",
        "addopts=",
        "-q",
        "--tb=line",
        *paths,
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, out[-4000:]


def _opp(
    symbol: str,
    *,
    reject: bool = False,
    confidence: int = 88,
    quality: int = 90,
    direction: str = "BUY",
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "reject": reject,
        "reject_reason": "no edge" if reject else None,
        "ai_confidence": confidence,
        "trade_quality": quality,
        "direction": direction,
        "expected_rr": "1.6",
        "market_regime": "strong_trend",
        "spread_score": 90,
        "liquidity": 85,
        "atr_pct": "0.90",
        "execution_health_ok": True,
        "setup_family": "bos_continuation",
        "reasons": ("pat",),
    }


def check_test1_startup() -> dict[str, Any]:
    issues: list[str] = []
    evidence: dict[str, Any] = {}

    gw_ok, gw = _http_json("http://127.0.0.1:8765/health")
    api_ok, api = _http_json(
        "https://quantforg-production.up.railway.app/api/v1/health", timeout=15
    )
    local_api = _port_open("127.0.0.1", 8000)
    fe = _port_open("127.0.0.1", 3000)
    evidence["gateway_local"] = {
        "ok": gw_ok,
        "body": gw if gw_ok else None,
        "err": None if gw_ok else gw,
    }
    evidence["api_prod"] = {
        "ok": api_ok,
        "body": api if api_ok else None,
        "err": None if api_ok else api,
    }
    evidence["local_backend_port"] = local_api
    evidence["local_frontend_port"] = fe

    from app.domain.institutional_trading.ai_scalping.broker_profile_store import (
        get_broker_profile_store,
    )
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )
    from app.domain.institutional_trading.ai_scalping.continuous_operation import (
        ContinuousOperationController,
    )

    profile = get_broker_profile_store().load()
    evidence["broker_profile"] = profile.to_public_dict() if profile else None
    evidence["continuous_enabled"] = (
        DEFAULT_AI_SCALPING_CONFIG.continuous_operation_enabled
    )
    evidence["version"] = DEFAULT_AI_SCALPING_CONFIG.version

    ctrl = ContinuousOperationController(config=DEFAULT_AI_SCALPING_CONFIG)
    ctrl.mark_startup_resume()
    snap = ctrl.tick(gateway_ok=gw_ok, mt5_ok=False, oms_ok=True, feed_ok=gw_ok)
    evidence["startup_tick"] = snap.to_dict()
    if not snap.resumed_positions:
        issues.append("startup resume flag not set")
    if not DEFAULT_AI_SCALPING_CONFIG.continuous_operation_enabled:
        issues.append("continuous_operation_enabled is false")
    if not snap.heartbeats:
        issues.append("heartbeat snapshot empty")

    from app.domain.institutional_trading.execution import decision_hash_store as dhs

    evidence["decision_hash_module"] = bool(dhs)

    issues.append(
        "full FE/BE/Gateway/MT5 restart cycle not executed in this harness "
        f"(gw={gw_ok}, api_prod={api_ok}, fe_port={fe}, be_port={local_api}, "
        f"profile={'yes' if profile else 'no'})"
    )
    structural = [
        i
        for i in issues
        if "not executed" not in i and "restart cycle" not in i
    ]
    status: Status = "FAIL" if structural else "BLOCKED"
    return {
        "id": "TEST_1_SYSTEM_STARTUP",
        "status": status,
        "issues": issues,
        "evidence": evidence,
    }


def check_test2_mt5_reconnect() -> dict[str, Any]:
    issues: list[str] = []
    evidence: dict[str, Any] = {}
    from app.domain.institutional_trading.ai_scalping.continuous_operation import (
        ContinuousOperationController,
    )
    from app.domain.institutional_trading.reliability.recovery import (
        RecoveryOrchestrator,
    )

    hits: list[str] = []

    def mt5() -> bool:
        hits.append("mt5")
        return True

    ctrl = ContinuousOperationController()
    ctrl.bind_reconnects(mt5=mt5)
    events = ctrl.heal_dependencies(mt5_ok=False)
    evidence["heal_events"] = events
    evidence["mt5_reconnect_called"] = "mt5" in hits
    if "mt5" not in hits:
        issues.append("MT5 reconnect callback not invoked")

    orch = RecoveryOrchestrator()
    try:
        orch.retry_order_send()  # type: ignore[attr-defined]
        issues.append("order_send retry must remain forbidden")
    except RuntimeError:
        evidence["order_send_retry_forbidden"] = True
    except AttributeError:
        evidence["order_send_retry_forbidden"] = "no retry_order_send (safe)"

    gw_ok, gw = _http_json("http://127.0.0.1:8765/health")
    evidence["gateway"] = {"ok": gw_ok, "body": gw if gw_ok else gw}
    issues.append(
        "automatic reconnect code path verified; physical MT5 disconnect/"
        "reconnect not executed"
    )
    structural = [i for i in issues if "not executed" not in i]
    status: Status = "FAIL" if structural else "BLOCKED"
    return {
        "id": "TEST_2_MT5_RECONNECT",
        "status": status,
        "issues": issues,
        "evidence": evidence,
    }


def check_test3_gateway_failure() -> dict[str, Any]:
    issues: list[str] = []
    evidence: dict[str, Any] = {}
    from app.domain.institutional_trading.ai_scalping.continuous_operation import (
        ContinuousOperationController,
    )

    hits: list[str] = []

    def gw() -> bool:
        hits.append("gateway")
        return True

    ctrl = ContinuousOperationController()
    ctrl.bind_reconnects(gateway=gw)
    events = ctrl.heal_dependencies(gateway_ok=False)
    evidence["heal_events"] = events
    evidence["gateway_reconnect_called"] = "gateway" in hits
    if "gateway" not in hits:
        issues.append("gateway reconnect callback not invoked")

    live_ok, live = _http_json("http://127.0.0.1:8765/health")
    evidence["gateway_live"] = {"ok": live_ok, "body": live if live_ok else live}
    issues.append("gateway stop/start not executed by harness")
    structural = [i for i in issues if "not executed" not in i]
    status: Status = "FAIL" if structural else "BLOCKED"
    return {
        "id": "TEST_3_GATEWAY_FAILURE",
        "status": status,
        "issues": issues,
        "evidence": evidence,
    }


def check_test4_market_closed() -> dict[str, Any]:
    issues: list[str] = []
    evidence: dict[str, Any] = {}
    from app.domain.institutional_trading.ai_scalping.continuous_operation import (
        ContinuousOperationController,
    )

    ctrl = ContinuousOperationController()
    pause = ctrl.evaluate_new_entry_pause(market_open=False)
    evidence["pause"] = pause.to_dict()
    if not pause.pause_new_entries:
        issues.append("market closed did not pause new entries")
    if not pause.manage_open_positions:
        issues.append("open positions must remain managed when market closed")
    snap = ctrl.tick(market_open=False, gateway_ok=True, mt5_ok=True)
    evidence["tick_alive"] = bool(snap.heartbeats)
    if not snap.heartbeats:
        issues.append("scanner/heartbeat died on market closed")
    status: Status = "PASS" if not issues else "FAIL"
    return {
        "id": "TEST_4_MARKET_CLOSED",
        "status": status,
        "issues": issues,
        "evidence": evidence,
    }


def check_test5_multi_asset() -> dict[str, Any]:
    issues: list[str] = []
    evidence: dict[str, Any] = {}
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
        DEFAULT_SCALPING_UNIVERSE,
    )
    from app.domain.institutional_trading.ai_scalping.portfolio_scanner import (
        scan_multi_asset_portfolio,
    )

    uni = set(DEFAULT_SCALPING_UNIVERSE)
    evidence["universe"] = sorted(uni)
    if uni != EXPECTED_UNIVERSE:
        issues.append(
            f"universe mismatch: {sorted(uni)} vs {sorted(EXPECTED_UNIVERSE)}"
        )

    opps = [
        _opp(s, reject=(s == "XAUUSD"), confidence=70 + i, quality=71 + i)
        for i, s in enumerate(sorted(EXPECTED_UNIVERSE))
    ]
    for o in opps:
        if o["symbol"] == "EURUSD":
            o["ai_confidence"] = 95
            o["trade_quality"] = 96
            o["reject"] = False
            o["direction"] = "SELL"
    result = scan_multi_asset_portfolio(opps)
    best_sym = (result.best or {}).get("symbol") if result.best else None
    ranked0 = result.ranked[0].get("symbol") if result.ranked else None
    evidence["best_symbol"] = best_sym
    evidence["ranked0"] = ranked0
    evidence["ranked_symbols"] = [r.get("symbol") for r in (result.ranked or [])]
    if best_sym != "EURUSD" and ranked0 != "EURUSD":
        issues.append(f"ranking did not choose EURUSD; best={best_sym}")
    evidence["config_version"] = DEFAULT_AI_SCALPING_CONFIG.version
    status: Status = "PASS" if not issues else "FAIL"
    return {
        "id": "TEST_5_MULTI_ASSET",
        "status": status,
        "issues": issues,
        "evidence": evidence,
    }


def check_test6_max_open() -> dict[str, Any]:
    issues: list[str] = []
    evidence: dict[str, Any] = {}
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )
    from app.domain.institutional_trading.ai_scalping.portfolio_risk import (
        aggregate_portfolio_risk,
    )
    from app.domain.institutional_trading.ai_scalping.portfolio_scanner import (
        check_portfolio_limits,
    )
    from app.domain.institutional_trading.decision_models import AccountRiskState

    cfg = DEFAULT_AI_SCALPING_CONFIG
    evidence["max_open_trades"] = cfg.max_open_trades
    evidence["max_daily_exposure_pct"] = str(cfg.max_daily_exposure_pct)
    evidence["risk_per_trade_pct"] = str(cfg.risk_per_trade_pct)
    if cfg.max_open_trades != 5:
        issues.append(f"max_open_trades={cfg.max_open_trades}, expected 5")

    account = AccountRiskState(
        equity=Decimal("10000"), daily_pnl=Decimal("0"), open_positions=4
    )
    snap = aggregate_portfolio_risk(account, config=cfg)
    evidence["snap_4_open"] = snap.to_dict()
    blocked, why = check_portfolio_limits(
        open_positions=snap.open_positions,
        max_open_positions=snap.max_open_positions,
        daily_loss_pct=snap.daily_loss_pct,
        max_daily_loss_pct=snap.max_daily_loss_pct,
        exposure_pct=snap.exposure_pct,
        max_exposure_pct=snap.max_exposure_pct,
    )
    evidence["blocked_at_exposure"] = blocked
    evidence["block_why"] = why
    if snap.exposure_pct != snap.max_exposure_pct:
        issues.append(f"expected exposure at ceiling; got {snap.exposure_pct}")

    account_loss = AccountRiskState(
        equity=Decimal("10000"),
        daily_pnl=Decimal("-300"),
        open_positions=1,
    )
    snap_loss = aggregate_portfolio_risk(account_loss, config=cfg)
    evidence["snap_daily_loss"] = snap_loss.to_dict()
    if snap_loss.daily_loss_pct <= 0:
        issues.append("daily loss pct not computed for negative PnL")
    status: Status = "PASS" if not issues else "FAIL"
    return {
        "id": "TEST_6_MAX_OPEN",
        "status": status,
        "issues": issues,
        "evidence": evidence,
    }


def check_test7_position_management() -> dict[str, Any]:
    issues: list[str] = []
    evidence: dict[str, Any] = {}
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )
    from app.domain.institutional_trading.management.models import ManageActionKind
    from app.domain.institutional_trading.production_hardening import (
        position_recovery,
    )

    cfg = DEFAULT_AI_SCALPING_CONFIG
    evidence["partial_tp_enabled"] = cfg.partial_tp_enabled
    evidence["break_even_at_r"] = str(cfg.break_even_at_r)
    evidence["time_stop_minutes"] = cfg.time_stop_minutes
    actions = {a.value for a in ManageActionKind}
    evidence["management_actions"] = sorted(actions)
    for need in ("break_even", "time_stop", "trail", "partial_close"):
        if need not in actions:
            issues.append(f"missing management action: {need}")
    if not cfg.partial_tp_enabled:
        issues.append("partial_tp_enabled is false")
    if not hasattr(position_recovery, "persist_pme_state"):
        issues.append("persist_pme_state missing")
    if not hasattr(position_recovery, "recover_positions_from_mt5"):
        issues.append("recover_positions_from_mt5 missing")

    from app.domain.institutional_trading.management import policies as ppolicies

    # Policies own BE / trail / partial / time / edge / vol exits (not engine.py)
    src = Path(ppolicies.__file__).read_text(encoding="utf-8")
    for token in (
        "trail",
        "time_stop",
        "break_even",
        "partial",
        "momentum fade",
        "volatility collapse",
    ):
        if token not in src.lower():
            issues.append(f"PME policies missing token: {token}")

    issues.append(
        "PME feature presence verified; live reconnect continuity not "
        "physically verified"
    )
    structural = [i for i in issues if "not physically" not in i]
    status: Status = "FAIL" if structural else "BLOCKED"
    return {
        "id": "TEST_7_POSITION_MANAGEMENT",
        "status": status,
        "issues": issues,
        "evidence": evidence,
    }


def check_test8_session() -> dict[str, Any]:
    issues: list[str] = []
    evidence: dict[str, Any] = {}
    session_path = ROOT / "frontend" / "src" / "lib" / "auth" / "session.ts"
    text = session_path.read_text(encoding="utf-8")
    evidence["remember_me"] = "REMEMBER" in text or "remember" in text
    evidence["localStorage"] = "localStorage" in text
    evidence["sessionStorage"] = "sessionStorage" in text
    evidence["refresh_token"] = "REFRESH" in text or "refresh" in text
    if not evidence["localStorage"] or not evidence["refresh_token"]:
        issues.append("session persistence contract incomplete")

    from app.application.services.weltrade_integration import (
        WeltradeIntegrationService,
    )

    evidence["restore_methods"] = [
        m
        for m in (
            "restore_from_persisted_profile",
            "load_persisted_broker_profile",
            "_persist_broker_runtime_profile",
        )
        if hasattr(WeltradeIntegrationService, m)
    ]
    if len(evidence["restore_methods"]) < 3:
        issues.append("broker restore API incomplete")
    issues.append(
        "browser refresh/restart/PC restart not executed in this harness"
    )
    structural = [i for i in issues if "not executed" not in i]
    status: Status = "FAIL" if structural else "BLOCKED"
    return {
        "id": "TEST_8_SESSION",
        "status": status,
        "issues": issues,
        "evidence": evidence,
    }


def check_test9_long_run() -> dict[str, Any]:
    """Evaluate wall-clock soak evidence under docs/production/reports/oat_v71."""
    issues: list[str] = []
    evidence: dict[str, Any] = {
        "required_hours": 24,
        "executed_hours": 0,
        "freshness_max_age_hours": 2.0,
    }
    soak_path = (
        ROOT
        / "docs"
        / "production"
        / "reports"
        / "oat_v71"
        / "soak_24h_metrics.jsonl"
    )
    latest_path = (
        ROOT
        / "docs"
        / "production"
        / "reports"
        / "oat_v71"
        / "soak_24h_latest.json"
    )
    evidence["soak_metrics_path"] = str(soak_path)
    evidence["soak_latest_path"] = str(latest_path)
    if not soak_path.is_file():
        issues.append("soak_24h_metrics.jsonl missing — no wall-clock soak evidence")
        return {
            "id": "TEST_9_LONG_RUN",
            "status": "BLOCKED",
            "issues": issues,
            "evidence": evidence,
        }

    rows: list[dict[str, Any]] = []
    for line in soak_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if len(rows) < 2:
        issues.append("soak metrics have fewer than 2 samples")
        return {
            "id": "TEST_9_LONG_RUN",
            "status": "FAIL",
            "issues": issues,
            "evidence": evidence,
        }

    def _parse(ts: str) -> datetime:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    first_ts = str(rows[0].get("ts") or "")
    last_ts = str(rows[-1].get("ts") or "")
    t0 = _parse(first_ts)
    t1 = _parse(last_ts)
    now = datetime.now(UTC)
    duration_h = (t1 - t0).total_seconds() / 3600.0
    age_h = (now - t1).total_seconds() / 3600.0
    gateway_ok = sum(
        1 for r in rows if (r.get("gateway") or {}).get("ok") is True
    )
    gateway_bad = sum(
        1 for r in rows if (r.get("gateway") or {}).get("ok") is False
    )
    connected = sum(
        1 for r in rows if (r.get("gateway") or {}).get("connected") is True
    )
    evidence.update(
        {
            "samples": len(rows),
            "first_ts": first_ts,
            "last_ts": last_ts,
            "executed_hours": round(duration_h, 3),
            "age_hours_since_last_sample": round(age_h, 3),
            "gateway_ok_samples": gateway_ok,
            "gateway_bad_samples": gateway_bad,
            "mt5_connected_samples": connected,
            "stale": age_h > float(evidence["freshness_max_age_hours"]),
            "meets_24h": duration_h >= 24.0,
        }
    )
    if latest_path.is_file():
        try:
            evidence["latest_snapshot"] = json.loads(
                latest_path.read_text(encoding="utf-8")
            )
        except Exception as exc:  # noqa: BLE001
            evidence["latest_snapshot_error"] = str(exc)

    if duration_h < 24.0:
        issues.append(
            f"soak duration {duration_h:.2f}h < required 24h "
            f"(first={first_ts}, last={last_ts}, samples={len(rows)})"
        )
    if age_h > float(evidence["freshness_max_age_hours"]):
        issues.append(
            f"soak evidence STALE — last sample age {age_h:.2f}h "
            f"> {evidence['freshness_max_age_hours']}h "
            f"(last_ts={last_ts}). Claimed longer soaks on operator hosts "
            "are not present in accessible git/workspace evidence."
        )
    if gateway_bad > max(3, len(rows) // 20):
        issues.append(
            f"excessive gateway failures during soak: {gateway_bad}/{len(rows)}"
        )

    if not issues:
        status: Status = "PASS"
    elif evidence["stale"] or duration_h < 24.0:
        # Incomplete or stale wall-clock evidence is a hard fail for acceptance.
        status = "FAIL"
    else:
        status = "FAIL"
    return {
        "id": "TEST_9_LONG_RUN",
        "status": status,
        "issues": issues,
        "evidence": evidence,
    }


def check_test10_performance() -> dict[str, Any]:
    issues: list[str] = []
    evidence: dict[str, Any] = {}
    from app.domain.institutional_trading.ai_scalping.portfolio_scanner import (
        scan_multi_asset_portfolio,
    )

    opps = [_opp(s) for s in sorted(EXPECTED_UNIVERSE)]
    timings: list[float] = []
    for _ in range(20):
        t0 = time.perf_counter()
        scan_multi_asset_portfolio(opps)
        timings.append((time.perf_counter() - t0) * 1000.0)
    evidence["avg_scan_ms"] = round(statistics.mean(timings), 3)
    evidence["p95_scan_ms"] = round(
        sorted(timings)[int(0.95 * (len(timings) - 1))], 3
    )

    latencies: list[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        ok, _ = _http_json("http://127.0.0.1:8765/health", timeout=5)
        if ok:
            latencies.append((time.perf_counter() - t0) * 1000.0)
    evidence["gateway_latency_ms"] = (
        round(statistics.mean(latencies), 2) if latencies else None
    )
    evidence["gateway_reachable"] = bool(latencies)

    try:
        import psutil  # type: ignore

        proc = psutil.Process(os.getpid())
        evidence["verifier_rss_mb"] = round(
            proc.memory_info().rss / (1024 * 1024), 2
        )
        evidence["cpu_percent_sample"] = psutil.cpu_percent(interval=0.5)
    except Exception as exc:  # noqa: BLE001
        evidence["psutil"] = str(exc)

    api_lat: list[float] = []
    for _ in range(3):
        t0 = time.perf_counter()
        ok, _ = _http_json(
            "https://quantforg-production.up.railway.app/api/v1/health",
            timeout=15,
        )
        if ok:
            api_lat.append((time.perf_counter() - t0) * 1000.0)
    evidence["api_health_latency_ms"] = (
        round(statistics.mean(api_lat), 2) if api_lat else None
    )

    if evidence["avg_scan_ms"] > 500:
        issues.append(f"avg scan duration high: {evidence['avg_scan_ms']}ms")

    if not evidence["gateway_reachable"]:
        issues.append("gateway latency not measurable (gateway down)")
        status: Status = "BLOCKED"
    elif issues:
        status = "FAIL"
    else:
        status = "PASS"
        evidence["note"] = (
            "Scan + gateway + API latency sampled; full execution latency "
            "needs live order path metrics"
        )
    return {
        "id": "TEST_10_PERFORMANCE",
        "status": status,
        "issues": issues,
        "evidence": evidence,
    }


def run_mapped_unit_suite() -> dict[str, Any]:
    ok, out = _run_pytest(
        [
            "tests/unit/test_ai_scalping_v7_1_continuous.py",
            "tests/unit/test_ai_scalping_v7_multi_asset.py",
            "tests/unit/test_ai_scalping_v7_production_blockers.py",
            "tests/unit/test_reliability_engineering_suite.py",
            "tests/unit/test_weltrade_integration.py",
        ]
    )
    return {
        "id": "UNIT_SUITE_MAPPED",
        "status": "PASS" if ok else "FAIL",
        "issues": [] if ok else ["mapped unit suite failed"],
        "evidence": {"output_tail": out},
    }


def main() -> int:
    started = datetime.now(UTC).isoformat()
    checks = [
        check_test1_startup,
        check_test2_mt5_reconnect,
        check_test3_gateway_failure,
        check_test4_market_closed,
        check_test5_multi_asset,
        check_test6_max_open,
        check_test7_position_management,
        check_test8_session,
        check_test9_long_run,
        check_test10_performance,
        run_mapped_unit_suite,
    ]
    results = []
    for fn in checks:
        try:
            results.append(fn())
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "id": getattr(fn, "__name__", "unknown"),
                    "status": "FAIL",
                    "issues": [f"exception: {exc}"],
                    "evidence": {},
                }
            )

    statuses = [r["status"] for r in results if str(r["id"]).startswith("TEST_")]
    all_pass = bool(statuses) and all(s == "PASS" for s in statuses)
    any_fail = any(s == "FAIL" for s in statuses)
    report = {
        "title": "QuantForg v7.1 Production Acceptance Test (PAT)",
        "version": "ai-scalping-v7.1.0",
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "results": results,
        "summary": {
            "PASS": sum(1 for s in statuses if s == "PASS"),
            "FAIL": sum(1 for s in statuses if s == "FAIL"),
            "BLOCKED": sum(1 for s in statuses if s == "BLOCKED"),
        },
        "production_accepted": False,
        "declaration": None,
    }
    if all_pass:
        report["production_accepted"] = True
        report["declaration"] = "QUANTFORG v7.1 PRODUCTION ACCEPTED."
    elif any_fail:
        report["declaration"] = (
            "QUANTFORG v7.1 PRODUCTION NOT ACCEPTED — FAIL items must be fixed."
        )
    else:
        report["declaration"] = (
            "QUANTFORG v7.1 PRODUCTION NOT ACCEPTED — BLOCKED live/operator "
            "verifications remain (reconnect soak, 24h run, browser/PC restart)."
        )

    out_dir = ROOT / "docs" / "production" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"v7_1_pat_{stamp}.json"
    latest = out_dir / "v7_1_pat_latest.json"
    text = json.dumps(report, indent=2, default=str)
    path.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    md = ROOT / "docs" / "production" / "V7_1_PRODUCTION_ACCEPTANCE_TEST.md"
    lines = [
        "# QuantForg v7.1 Production Acceptance Test (PAT)",
        "",
        f"Generated: `{report['finished_at']}`",
        "",
        f"**Declaration:** {report['declaration']}",
        "",
        "## Results",
        "",
        "| Test | Status | Issues |",
        "|---|---|---|",
    ]
    for r in results:
        if not str(r["id"]).startswith("TEST_"):
            continue
        iss = "; ".join(r.get("issues") or []) or "—"
        lines.append(f"| {r['id']} | **{r['status']}** | {iss} |")
    lines += [
        "",
        "## Summary",
        "",
        f"- PASS: {report['summary']['PASS']}",
        f"- FAIL: {report['summary']['FAIL']}",
        f"- BLOCKED: {report['summary']['BLOCKED']}",
        "",
        f"Evidence JSON: `{path.relative_to(ROOT).as_posix()}`",
        "",
        "Acceptance rule: **all ten tests must be PASS** (no BLOCKED, no FAIL)",
        "before declaring PRODUCTION ACCEPTED.",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")
    print(text)
    print(f"\nWrote {path}")
    print(report["declaration"])
    return 0 if all_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
