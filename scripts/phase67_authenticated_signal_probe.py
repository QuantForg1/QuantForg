"""Phase 67 — authenticated production signal verification (sanitized).

Uses QUANTFORG_OWNER_EMAIL/PASSWORD via existing login API.
Never prints passwords, tokens, or cookies.
Never calls OMS / trading start / order endpoints.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = (
    os.environ.get("QUANTFORG_API_URL")
    or os.environ.get("QF_API_BASE")
    or "https://quantforg-production.up.railway.app/api/v1"
).rstrip("/")
EXPECTED_SHA = (
    os.environ.get("QF_EXPECTED_SHA")
    or "81ae7c8fa1de36752a4581296a46fc3c7f334648"
)
OUT = Path(__file__).resolve().parents[1] / "docs" / "production" / "reports" / "phase67_auth_probe.json"


def _req(
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 60,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(  # noqa: S310
        f"{BASE}{path}",
        data=data,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
            return int(resp.status), json.loads(raw) if raw else {}
    except TimeoutError:
        return 504, {"detail": "client_timeout"}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {"detail": raw[:200]}
        except json.JSONDecodeError:
            payload = {"detail": raw[:200]}
        return int(exc.code), payload
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, TimeoutError) or "timed out" in str(exc).lower():
            return 504, {"detail": "client_timeout"}
        return 599, {"detail": f"url_error:{type(exc).__name__}"}
    except OSError as exc:
        if "timed out" in str(exc).lower():
            return 504, {"detail": "client_timeout"}
        return 599, {"detail": f"os_error:{type(exc).__name__}"}


def _num(v: Any) -> float | None:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _safe_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": item.get("symbol") or item.get("broker_symbol"),
        "asset_class": item.get("asset_class"),
        "direction": item.get("direction"),
        "opportunity_score": item.get("opportunity_score"),
        "directional_edge": item.get("directional_edge") or item.get("edge"),
        "RR": item.get("RR") or item.get("rr"),
        "research_rank_score": item.get("research_rank_score"),
        "session": item.get("session"),
        "regime": item.get("regime")
        or ((item.get("pipeline") or {}).get("market_regime") if isinstance(item.get("pipeline"), dict) else None),
        "entry": item.get("entry") or item.get("entry_candidate"),
        "stop_loss": item.get("stop_loss") or item.get("SL_candidate"),
        "take_profit": item.get("take_profit") or item.get("TP_candidate"),
        "freshness": item.get("freshness") or item.get("data_state"),
        "as_of": item.get("as_of") or item.get("time_generated"),
        "research_only": item.get("research_only"),
        "authorizes_trade": item.get("authorizes_trade"),
    }


def main() -> int:
    report: dict[str, Any] = {
        "phase": 67,
        "base": BASE,
        "expected_sha": EXPECTED_SHA,
        "probed_at": datetime.now(UTC).isoformat(),
        "auth": {"method": "owner_email_password_login", "token_printed": False},
        "live_orders_attempted": False,
        "oms_endpoints_called": False,
    }

    code, version = _req("GET", "/version")
    report["version"] = {
        "http": code,
        "git_commit": (version or {}).get("git_commit") if isinstance(version, dict) else None,
        "match": isinstance(version, dict)
        and version.get("git_commit") == EXPECTED_SHA,
    }
    if not report["version"]["match"]:
        report["verdict"] = "DEPLOYMENT_MISMATCH_STOP"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"status": "DEPLOYMENT_MISMATCH", "version": report["version"]}, indent=2))
        return 2

    email = (os.environ.get("QUANTFORG_OWNER_EMAIL") or "").strip()
    password = (os.environ.get("QUANTFORG_OWNER_PASSWORD") or "").strip()
    report["auth"]["email_present"] = bool(email)
    report["auth"]["password_present"] = bool(password)
    if not email or not password:
        report["AUTHENTICATED_PRODUCTION_PROBE"] = "BLOCKED"
        report["block_reason"] = "owner credentials incomplete"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"AUTHENTICATED_PRODUCTION_PROBE": "BLOCKED"}, indent=2))
        return 1

    login_code, login_body = _req(
        "POST",
        "/auth/login",
        body={"email": email, "password": password},
    )
    token = ""
    if isinstance(login_body, dict):
        token = str(login_body.get("access_token") or login_body.get("access") or "")
    report["auth"]["login_http"] = login_code
    report["auth"]["token_acquired"] = bool(token)
    # Never retain password or token in report.
    if login_code != 200 or not token:
        report["AUTHENTICATED_PRODUCTION_PROBE"] = "BLOCKED"
        report["block_reason"] = f"login_failed_http_{login_code}"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"AUTHENTICATED_PRODUCTION_PROBE": "BLOCKED", "login_http": login_code}, indent=2))
        return 1

    me_code, me = _req("GET", "/auth/me", token=token)
    report["auth"]["me_http"] = me_code
    if isinstance(me, dict):
        report["auth"]["role"] = me.get("role") or me.get("user_role")
        report["auth"]["user_id_present"] = bool(me.get("id") or me.get("user_id"))

    sig_code, signals = _req("GET", "/signals?enabled_only=false", token=token)
    report["signals_http"] = sig_code
    mu_code, universe = _req("GET", "/market-universe", token=token, timeout=90)
    report["market_universe_http"] = mu_code
    # Optional research refresh — soft-fail; never starts live trading.
    ref_code, _refreshed = _req(
        "POST", "/market-universe/refresh", token=token, timeout=45
    )
    report["market_universe_refresh_http"] = ref_code

    if ref_code == 200:
        sig2_code, signals2 = _req("GET", "/signals?enabled_only=false", token=token)
        if sig2_code == 200:
            signals = signals2
            report["signals_http_after_refresh"] = sig2_code
        mu2_code, universe2 = _req(
            "GET", "/market-universe", token=token, timeout=90
        )
        if mu2_code == 200:
            universe = universe2
            report["market_universe_http_after_refresh"] = mu2_code
    else:
        report["market_universe_refresh_note"] = "soft_failed_or_timeout_continued"
        mu2_code = mu_code

    # Drop token from memory ASAP after requests.
    token = ""

    if not isinstance(signals, dict) or sig_code != 200:
        report["AUTHENTICATED_PRODUCTION_PROBE"] = "FAIL"
        report["signals_error"] = signals if isinstance(signals, dict) else {"http": sig_code}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"AUTHENTICATED_PRODUCTION_PROBE": "FAIL", "signals_http": sig_code}, indent=2))
        return 1

    items = [i for i in (signals.get("items") or []) if isinstance(i, dict)]
    ra = signals.get("research_analysis") if isinstance(signals.get("research_analysis"), dict) else {}
    dash = signals.get("dashboard") if isinstance(signals.get("dashboard"), dict) else {}

    by_class = Counter(str(i.get("asset_class") or "UNKNOWN").upper() for i in items)
    by_dir = Counter(str(i.get("direction") or "NONE").upper() for i in items)
    actionable = [i for i in items if str(i.get("direction") or "").upper() in {"BUY", "SELL"}]
    ranked = sorted(
        actionable,
        key=lambda r: (
            _num(r.get("research_rank_score")) is not None,
            _num(r.get("research_rank_score")) or -1,
            _num(r.get("opportunity_score")) or -1,
        ),
        reverse=True,
    )

    report["signal_center"] = {
        "as_of": signals.get("as_of"),
        "source": signals.get("source"),
        "scanner_status": signals.get("scanner_status"),
        "universe_size": signals.get("universe_size"),
        "count": signals.get("count"),
        "broker_required_for_research": signals.get("broker_required_for_research"),
        "research_can_execute": signals.get("research_can_execute"),
        "allow_live_promotion": signals.get("allow_live_promotion"),
        "fabricated": signals.get("fabricated"),
        "research_meta": signals.get("research_meta"),
        "dashboard_buy": dash.get("buy_signals"),
        "dashboard_sell": dash.get("sell_signals"),
        "items_total": len(items),
        "active_buy_sell": len(actionable),
        "by_direction": dict(by_dir),
        "by_asset_class": dict(by_class),
        "top5": [_safe_item(i) for i in ranked[:5]],
        "all_actionable": [_safe_item(i) for i in ranked],
    }
    report["research_analysis"] = {
        "status": ra.get("status"),
        "last_scan_started": ra.get("last_scan_started"),
        "last_scan_completed": ra.get("last_scan_completed"),
        "scan_duration_ms": ra.get("scan_duration_ms"),
        "instruments_discovered": ra.get("instruments_discovered"),
        "instruments_analyzed": ra.get("instruments_analyzed"),
        "signals_generated": ra.get("signals_generated"),
        "catalogue_source": ra.get("catalogue_source"),
        "cycles": ra.get("cycles"),
        "failures": ra.get("failures"),
        "authorizes_trade": ra.get("authorizes_trade"),
        "forwarded_to_oms": ra.get("forwarded_to_oms"),
        "would_submit_order": ra.get("would_submit_order"),
        "second_scanner": ra.get("second_scanner"),
        "last_error": ra.get("last_error"),
    }

    if isinstance(universe, dict) and (mu_code == 200 or mu2_code == 200):
        counts = universe.get("counts") if isinstance(universe.get("counts"), dict) else {}
        by_state = universe.get("by_state") if isinstance(universe.get("by_state"), dict) else {}
        obs = universe.get("observability") if isinstance(universe.get("observability"), dict) else {}
        instruments = [i for i in (universe.get("instruments") or []) if isinstance(i, dict)]
        class_counts = Counter(str(i.get("asset_class") or "UNKNOWN").upper() for i in instruments)
        state_counts = Counter()
        for i in instruments:
            dq = i.get("data_quality") if isinstance(i.get("data_quality"), dict) else {}
            state_counts[str(dq.get("state") or i.get("data_availability") or "UNKNOWN").upper()] += 1
        goldish = [
            i
            for i in instruments
            if "XAU" in str(i.get("canonical_symbol") or i.get("broker_symbol") or "").upper()
        ]
        non_gold_ready = [
            i
            for i in instruments
            if "XAU" not in str(i.get("canonical_symbol") or i.get("broker_symbol") or "").upper()
            and str((i.get("data_quality") or {}).get("state") if isinstance(i.get("data_quality"), dict) else "").upper()
            in {"LIVE", "DATA_READY", "READY"}
        ]
        crypto = [
            i
            for i in instruments
            if str(i.get("asset_class") or "").upper() == "CRYPTO"
        ]
        other = [
            i
            for i in instruments
            if str(i.get("asset_class") or "").upper() == "OTHER"
        ]
        report["universe"] = {
            "catalogue_source": universe.get("catalogue_source"),
            "research_stage": universe.get("research_stage"),
            "counts": counts,
            "by_state_api": by_state,
            "by_class_instruments": dict(class_counts),
            "by_state_instruments": dict(state_counts),
            "instrument_n": len(instruments),
            "gold_instrument_n": len(goldish),
            "non_gold_live_n": len(non_gold_ready),
            "crypto_n": len(crypto),
            "other_n": len(other),
            "crypto_symbols_sample": [
                str(i.get("broker_symbol") or i.get("canonical_symbol"))
                for i in crypto[:20]
            ],
            "other_symbols_sample": [
                str(i.get("broker_symbol") or i.get("canonical_symbol"))
                for i in other[:20]
            ],
            "observability": {
                "symbol_count": obs.get("symbol_count"),
                "symbols_scored": obs.get("symbols_scored"),
                "research_signal_count": obs.get("research_signal_count"),
                "catalogue_source": obs.get("catalogue_source"),
            },
            "authorizes_trade": universe.get("authorizes_trade"),
            "ALLOW_LIVE_PROMOTION": universe.get("ALLOW_LIVE_PROMOTION"),
        }
    else:
        report["universe"] = {"http": mu_code, "error": True}

    # Quality checks on actionable signals
    quality = {"valid": 0, "incomplete": 0, "suspicious_xau_copy": 0, "issues": []}
    xau_prices = {
        (_safe_item(i).get("entry"), _safe_item(i).get("stop_loss"), _safe_item(i).get("take_profit"))
        for i in ranked
        if "XAU" in str(i.get("symbol") or "").upper()
    }
    for i in ranked:
        row = _safe_item(i)
        issues: list[str] = []
        if row.get("authorizes_trade") is True:
            issues.append("authorizes_trade_true")
        if row.get("direction") not in {"BUY", "SELL"}:
            issues.append("bad_direction")
        opp = _num(row.get("opportunity_score"))
        edge = _num(row.get("directional_edge"))
        if opp is None and edge is None and row.get("research_rank_score") is None:
            issues.append("missing_scores")
            quality["incomplete"] += 1
        prices = (row.get("entry"), row.get("stop_loss"), row.get("take_profit"))
        if (
            "XAU" not in str(row.get("symbol") or "").upper()
            and prices in xau_prices
            and any(p is not None for p in prices)
        ):
            issues.append("possible_xau_price_copy")
            quality["suspicious_xau_copy"] += 1
        if not issues:
            quality["valid"] += 1
        else:
            quality["issues"].append({"symbol": row.get("symbol"), "issues": issues})
    report["signal_quality"] = quality

    report["invariants"] = {
        "research_can_execute": signals.get("research_can_execute") is False,
        "allow_live_promotion": signals.get("allow_live_promotion") is False,
        "broker_required_for_research": signals.get("broker_required_for_research") is False,
        "fabricated": signals.get("fabricated") is not True,
        "research_analysis_authorizes_trade": ra.get("authorizes_trade") is False,
        "research_analysis_forwarded_to_oms": ra.get("forwarded_to_oms") is False,
        "live_orders_attempted": False,
        "oms_endpoints_called": False,
    }

    report["AUTHENTICATED_PRODUCTION_PROBE"] = "PASS"
    report["SIGNALS_LIVE"] = True
    report["LIVE_BROKER_VERIFIED"] = (
        isinstance(report.get("universe"), dict)
        and report["universe"].get("catalogue_source") == "LIVE_BROKER"
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    # Console summary only — no secrets.
    summary = {
        "AUTHENTICATED_PRODUCTION_PROBE": "PASS",
        "VERSION_MATCH": report["version"]["match"],
        "PRODUCTION_SHA": report["version"]["git_commit"],
        "ROBOT_STATUS": ra.get("status"),
        "LAST_SCAN_COMPLETED": ra.get("last_scan_completed"),
        "INSTRUMENTS_DISCOVERED": ra.get("instruments_discovered"),
        "INSTRUMENTS_ANALYZED": ra.get("instruments_analyzed"),
        "SIGNALS_GENERATED": ra.get("signals_generated"),
        "CATALOGUE_SOURCE": (report.get("universe") or {}).get("catalogue_source"),
        "UNIVERSE_BY_CLASS": (report.get("universe") or {}).get("by_class_instruments"),
        "UNIVERSE_BY_STATE": (report.get("universe") or {}).get("by_state_instruments"),
        "ACTIVE_BUY_SELL": len(actionable),
        "BY_DIRECTION": dict(by_dir),
        "BY_CLASS_SIGNALS": dict(by_class),
        "TOP5": report["signal_center"]["top5"],
        "INVARIANTS": report["invariants"],
        "LIVE_BROKER_VERIFIED": report["LIVE_BROKER_VERIFIED"],
        "REPORT_PATH": str(OUT),
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
