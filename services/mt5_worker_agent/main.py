"""Entrypoint for the Windows MT5 worker agent (local + future VPS).

Modes:
  idle            — token-gated idle loop (no MT5)
  prepare-slots   — copy portable MT5 installs for configured slots
  start-slots     — start portable terminals (no login)
  status          — print slot + resource status (no secrets)
  supervise       — local supervisor heartbeat loop
  connect-demo    — real MT5 login+verify for one slot (requires env creds)
  verify-broker   — eight-broker demo/live verify + evidence write
  reject-demo     — negative credential test (expects failure)
  capacity        — measured host portable-terminal capacity
  queue-status    — capacity wait queue (no secrets)
  railway-ping    — outbound HTTPS health check to Railway/API

Never attaches to the LIVE Program Files terminal by default.
Never enables MULTI_ACCOUNT_LIVE_SUBMIT.
Never provisions a new Windows VPS.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("mt5_worker_agent")


def _token_ok(raw: str | None) -> bool:
    return bool(raw and len(raw.strip()) >= 16)


def cmd_idle() -> int:
    token = os.environ.get("WORKER_SERVICE_TOKEN")
    api = (os.environ.get("QUANTFORG_API_BASE_URL") or "").strip()
    if not _token_ok(token):
        logger.error("WORKER_SERVICE_TOKEN missing or too short — refusing to start")
        return 2
    logger.info(
        "mt5_worker_agent idle api_configured=%s token_len=%s",
        bool(api),
        len(token.strip()) if token else 0,
    )
    while True:
        time.sleep(30)
        logger.info("mt5_worker_agent heartbeat idle=true ready=false")


def cmd_prepare_slots(*, force: bool) -> int:
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor

    sup = LocalWorkerSupervisor()
    result = sup.prepare_all(force=force)
    print(json.dumps(result, indent=2))
    return 0 if all(v.get("ok") for v in result.values()) else 1


def cmd_start_slots() -> int:
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor

    sup = LocalWorkerSupervisor()
    result = sup.start_all_terminals()
    print(json.dumps(result, indent=2))
    return 0 if all(v.get("ok") for v in result.values()) else 1


def cmd_stop_slots() -> int:
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor

    sup = LocalWorkerSupervisor()
    result = sup.stop_all()
    print(json.dumps(result, indent=2))
    return 0


def cmd_status() -> int:
    from services.mt5_worker_agent.host_capacity import measure_host_capacity
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor
    from services.mt5_worker_agent.resources import (
        host_memory_summary,
        sample_terminal_processes,
    )
    from services.mt5_worker_agent.safe_status import public_status_payload
    from services.mt5_worker_agent.slot_queue import snapshot as queue_snapshot

    sup = LocalWorkerSupervisor()
    report = public_status_payload(
        {
            "slots": sup.refresh_status(),
            "terminals": [
                {
                    "pid": s.pid,
                    "exe_path": s.exe_path,
                    "working_set_mb": s.working_set_mb,
                    "cpu_seconds": s.cpu_seconds,
                }
                for s in sample_terminal_processes()
            ],
            "host_memory": host_memory_summary(),
            "capacity": measure_host_capacity().to_dict(),
            "queue": queue_snapshot(),
            "note": (
                "Status only - ready=false until connect-demo succeeds for a slot"
            ),
        }
    )
    print(json.dumps(report, indent=2))
    return 0


def cmd_capacity() -> int:
    from services.mt5_worker_agent.host_capacity import measure_host_capacity

    print(json.dumps(measure_host_capacity().to_dict(), indent=2))
    return 0


def cmd_queue_status() -> int:
    from services.mt5_worker_agent.slot_queue import load_persisted, snapshot

    load_persisted()
    print(json.dumps(snapshot(), indent=2))
    return 0


def cmd_supervise() -> int:
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor

    if not _token_ok(os.environ.get("WORKER_SERVICE_TOKEN")):
        logger.warning(
            "WORKER_SERVICE_TOKEN missing — supervising locally "
            "without Railway heartbeats"
        )
    LocalWorkerSupervisor().run_forever()
    return 0


def cmd_railway_ping() -> int:
    from services.mt5_worker_agent.railway_client import (
        RailwayClientConfig,
        RailwayWorkerClient,
    )

    try:
        client = RailwayWorkerClient(RailwayClientConfig.from_env())
    except ValueError as exc:
        logger.error("railway_config_invalid error=%s", exc)
        return 2
    result = client.health_ping()
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") or result.get("status") == "ok" else 1


def cmd_railway_register() -> int:
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor

    if not _token_ok(os.environ.get("WORKER_SERVICE_TOKEN")):
        logger.error("WORKER_SERVICE_TOKEN missing or too short")
        return 2
    result = LocalWorkerSupervisor().register_with_railway()
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def cmd_railway_heartbeat() -> int:
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor

    if not _token_ok(os.environ.get("WORKER_SERVICE_TOKEN")):
        logger.error("WORKER_SERVICE_TOKEN missing or too short")
        return 2
    sup = LocalWorkerSupervisor()
    reg = sup.register_with_railway()
    if not reg.get("ok"):
        print(json.dumps({"ok": False, "register": reg}, indent=2))
        return 1
    hb = sup.heartbeat_once()
    assign = sup.fetch_assignments()
    print(
        json.dumps(
            {"ok": True, "register": reg, "heartbeat": hb, "assignments": assign},
            indent=2,
        )
    )
    return 0


def cmd_railway_dispatch_poll(*, once: bool = True, ack: bool = True) -> int:
    """Claim next assigned delivery job (delivery only; no order_send)."""
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor
    from services.mt5_worker_agent.railway_client import (
        RailwayClientConfig,
        RailwayWorkerClient,
    )

    if not _token_ok(os.environ.get("WORKER_SERVICE_TOKEN")):
        logger.error("WORKER_SERVICE_TOKEN missing or too short")
        return 2
    client = RailwayWorkerClient(RailwayClientConfig.from_env())
    sup = LocalWorkerSupervisor()
    reg = sup.register_with_railway()
    if not reg.get("ok"):
        print(json.dumps({"ok": False, "register": reg}, indent=2))
        return 1
    results: list[dict[str, Any]] = []
    for slot_id, info in (reg.get("slots") or {}).items():
        if not isinstance(info, dict) or not info.get("ok"):
            continue
        worker_id = str(info.get("worker_id") or "")
        if not worker_id:
            continue
        assign = client.get_assignment(worker_id=worker_id)
        assignment = (
            (assign.get("assignment") or {}) if isinstance(assign, dict) else {}
        )
        user_id = str(assignment.get("user_id") or "")
        account_id = str(assignment.get("broker_account_id") or "")
        if not user_id or not account_id:
            results.append(
                {
                    "slot_id": slot_id,
                    "worker_id": worker_id,
                    "ok": False,
                    "error": "assignment_incomplete",
                }
            )
            continue
        claim = client.dispatch_claim(
            worker_id=worker_id,
            user_id=user_id,
            broker_account_id=account_id,
        )
        entry: dict[str, Any] = {
            "slot_id": slot_id,
            "worker_id": worker_id,
            "claim": claim,
            "live_submit_allowed": False,
        }
        job = claim.get("job") if isinstance(claim, dict) else None
        if ack and isinstance(job, dict) and job.get("intent_id"):
            entry["ack"] = client.dispatch_ack(
                worker_id=worker_id,
                intent_id=str(job["intent_id"]),
                detail="portable_delivery_ack",
            )
        results.append(entry)
        if once and job:
            break
    print(
        json.dumps(
            {"ok": True, "results": results, "live_submit_allowed": False},
            indent=2,
        )
    )
    return 0


def cmd_railway_dispatch_recover() -> int:
    from services.mt5_worker_agent.railway_client import (
        RailwayClientConfig,
        RailwayWorkerClient,
    )

    if not _token_ok(os.environ.get("WORKER_SERVICE_TOKEN")):
        logger.error("WORKER_SERVICE_TOKEN missing or too short")
        return 2
    client = RailwayWorkerClient(RailwayClientConfig.from_env())
    result = client.dispatch_recover()
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def _prepare_slot_terminal(slot_id: str) -> str:
    """Prepare portable install and ensure a warm terminal process.

    Stale saved DEMO logins are cleared inside ``authenticate_and_verify`` before
    ``mt5.initialize(login=..., password=..., server=..., portable=True)``.
    Pre-starting the portable process is required on this host — initialize alone
    frequently returns IPC send/recv/timeout (-10001/-10002/-10005).
    """
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor
    from services.mt5_worker_agent.mt5_session import clear_portable_saved_login
    from services.mt5_worker_agent.slot_manager import (
        prepare_portable_slot,
        slot_status,
        start_slot_terminal,
        stop_slot_terminal,
    )

    prepare_portable_slot(slot_id)
    exe = LocalWorkerSupervisor().terminal_exe_for(slot_id)
    # Drop stale Login/Server from common.ini before the process boots.
    try:
        clear_portable_saved_login(exe)
    except Exception:
        logger.exception("clear_portable_saved_login_failed slot=%s", slot_id)
    already = slot_status(slot_id)
    if already.process_running:
        # Restart so common.ini clear takes effect.
        logger.info(
            "restarting_portable_after_saved_login_clear slot=%s pid=%s",
            slot_id,
            already.pid,
        )
        stop_slot_terminal(slot_id)
        time.sleep(1)
    start_slot_terminal(slot_id)
    # Portable IPC is unreliable while the Weltrade LIVE singleton holds MCP 22346
    # and host RAM/disk are tight — allow a longer warm-up before initialize().
    time.sleep(12)
    return exe


def _persist_and_report_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    """Write local evidence and best-effort report to Railway (no passwords)."""
    from app.domain.broker_connectivity.broker_verification_evidence import (
        ingest_worker_report,
    )

    local = ingest_worker_report(payload)
    railway_result: dict[str, Any] = {"skipped": True}
    try:
        from services.mt5_worker_agent.railway_client import (
            RailwayClientConfig,
            RailwayWorkerClient,
        )

        client = RailwayWorkerClient(RailwayClientConfig.from_env())
        railway_result = client.report_verification(payload)
    except Exception as exc:
        railway_result = {"ok": False, "error": type(exc).__name__}
        logger.warning(
            "railway_verification_report_skipped error=%s", type(exc).__name__
        )
    return {"local_evidence": local, "railway": railway_result}


_BROKER_CHOICES = [
    "weltrade",
    "xm",
    "exness",
    "hfm",
    "justmarkets",
    "ic-markets",
    "pepperstone",
    "fp-markets",
]


def cmd_connect_demo(
    slot_id: str,
    broker: str | None = None,
    *,
    environment: str = "demo",
) -> int:
    """Real MT5 authenticate+verify for one portable slot.

    Requires broker-specific or generic QF_DEMO_* / QF_LIVE_* credentials.
    Never invents success without MetaTrader5 login.
    """
    from services.mt5_worker_agent.broker_demo_adapters import (
        account_type_mismatch,
        classify_environment,
        missing_credential_keys,
        normalize_broker_slug,
        resolve_account_environment,
        resolve_credentials,
        server_matches_broker,
        supported_brokers,
    )
    from services.mt5_worker_agent.host_capacity import can_start_another_portable
    from services.mt5_worker_agent.mt5_session import authenticate_and_verify
    from services.mt5_worker_agent.slot_queue import enqueue

    env_req = "live" if str(environment).lower() == "live" else "demo"
    slug = normalize_broker_slug(broker) if broker else None
    if broker and slug is None:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "unsupported_broker",
                    "supported": list(supported_brokers()),
                },
                indent=2,
            )
        )
        return 2

    from services.mt5_worker_agent.slot_manager import slot_status

    preferred_running = bool(slot_status(slot_id).process_running)
    can_start, capacity_reason = can_start_another_portable()
    # Reuse an already-running preferred portable — do not queue a duplicate start.
    if not can_start and not preferred_running:
        queued = enqueue(
            broker_slug=slug or "unknown",
            environment=env_req,
            slot_preference=slot_id,
        )
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": capacity_reason,
                    "queue": queued,
                    "note": (
                        "Existing Windows host at portable capacity. "
                        "Request queued — no new VPS provisioned."
                    ),
                },
                indent=2,
            )
        )
        return 3
    if preferred_running and not can_start:
        logger.info(
            "reusing_running_portable_slot slot=%s capacity_reason=%s",
            slot_id,
            capacity_reason,
        )

    from typing import Literal as _Lit

    env_lit: _Lit["demo", "live"] = "live" if env_req == "live" else "demo"
    creds = resolve_credentials(slug, environment=env_lit) if slug else None
    if creds is None and not slug:
        # Generic path for backward-compatible connect-demo.
        login_raw = (os.environ.get("QF_DEMO_LOGIN") or "").strip()
        password = os.environ.get("QF_DEMO_PASSWORD") or ""
        server = (os.environ.get("QF_DEMO_SERVER") or "").strip()
        if not login_raw or not password.strip() or not server:
            logger.error(
                "Missing QF_DEMO_LOGIN / QF_DEMO_PASSWORD / QF_DEMO_SERVER — "
                "cannot claim a real authenticated session"
            )
            print(
                json.dumps(
                    {
                        "ok": False,
                        "authenticated_demo_accounts": 0,
                        "error": "demo_credentials_not_provided",
                        "required_env": [
                            "QF_DEMO_LOGIN",
                            "QF_DEMO_PASSWORD",
                            "QF_DEMO_SERVER",
                        ],
                        "or_broker_specific": [
                            "QF_DEMO_EXNESS_*",
                            "QF_DEMO_HFM_*",
                            "QF_DEMO_WELTRADE_*",
                        ],
                    },
                    indent=2,
                )
            )
            return 2
        from services.mt5_worker_agent.broker_demo_adapters import DemoCredentialBundle

        creds = DemoCredentialBundle(
            broker_slug="weltrade",
            environment=classify_environment(server),
            login=login_raw,
            password=password,
            server=server,
        )
    elif creds is None:
        missing = missing_credential_keys(slug or "exness", environment=env_req)
        cred_error = (
            "live_credentials_not_provided"
            if env_req == "live"
            else "demo_credentials_not_provided"
        )
        print(
            json.dumps(
                {
                    "ok": False,
                    "authenticated_demo_accounts": 0,
                    "broker": slug,
                    "environment": env_req,
                    "error": cred_error,
                    "missing_env": missing,
                    "note": (
                        "Provide approved credentials on the Windows host "
                        f"as QF_{'LIVE' if env_req == 'live' else 'DEMO'}_* "
                        "(LIVE never falls back to DEMO). "
                        "Do not invent server names. connectable stays false."
                    ),
                },
                indent=2,
            )
        )
        return 2

    exe = _prepare_slot_terminal(slot_id)
    result = authenticate_and_verify(
        terminal_exe=exe,
        login=int(creds.login),
        password=creds.password,
        server=creds.server,
    )
    broker_ok = True
    if slug and result.ok:
        broker_ok = server_matches_broker(
            broker_slug=creds.broker_slug, server=result.server or creds.server
        )
        result_error = "server_broker_mismatch" if not broker_ok else result.error
    else:
        result_error = result.error

    resolved_env, env_source = resolve_account_environment(
        requested=env_lit,
        credential_environment=creds.environment,
        server=result.server or creds.server,
        trade_mode=result.trade_mode,
    )
    mismatch = account_type_mismatch(
        requested=env_lit,
        resolved=resolved_env,
        trade_mode=result.trade_mode,
    )
    if mismatch:
        result_error = mismatch
        broker_ok = False

    success = bool(result.ok and result.trade_allowed and broker_ok and not mismatch)
    evidence_payload = {
        "ok": success,
        "broker_slug": creds.broker_slug if slug else (slug or "unknown"),
        "environment": resolved_env,
        "environment_source": env_source,
        "requested_environment": env_lit,
        "credential_environment": creds.environment,
        "trade_mode": result.trade_mode,
        "server": result.server or creds.server,
        "login": result.login,
        "trade_allowed": result.trade_allowed,
        "market_data_ok": result.market_data_ok,
        "balance": result.balance,
        "equity": result.equity,
        "currency": result.currency,
        "symbols_total": result.symbols_total,
        "quote_symbol": result.quote_symbol,
        "host_code": os.environ.get("QF_WORKER_HOST_CODE") or "local-windows-1",
        "slot_id": slot_id,
        "source": "windows_mt5_demo_verify",
        "error": result_error if not success else "",
    }
    # Only persist evidence when a broker was explicitly targeted.
    evidence_meta: dict[str, Any] = {}
    if slug:
        if not success:
            evidence_payload["broker_slug"] = slug
        evidence_meta = _persist_and_report_evidence(evidence_payload)

    payload = {
        "ok": success,
        "trade_allowed": result.trade_allowed,
        "market_data_ok": result.market_data_ok,
        "login": result.login,
        "server": result.server,
        "name": result.name,
        "balance": result.balance,
        "equity": result.equity,
        "currency": result.currency,
        "symbols_total": result.symbols_total,
        "quote_symbol": result.quote_symbol,
        "quote_bid": result.quote_bid,
        "trade_mode": result.trade_mode,
        "error": result_error,
        "slot_id": slot_id,
        "broker": slug or creds.broker_slug,
        "environment": resolved_env,
        "environment_source": env_source,
        "requested_environment": env_lit,
        "connectable_promoted": bool(slug and success),
        "evidence": evidence_meta,
        "note": "Password not included. Mock sessions are not used here.",
        "orders_submitted": False,
        "live_trading_enabled": False,
    }
    print(json.dumps(payload, indent=2))
    return 0 if success else 1


def cmd_verify_broker(broker: str, slot_id: str, *, environment: str = "demo") -> int:
    return cmd_connect_demo(slot_id=slot_id, broker=broker, environment=environment)


def cmd_reject_demo(broker: str, slot_id: str, *, environment: str = "demo") -> int:
    """Negative test: deliberately wrong password must fail closed."""
    from services.mt5_worker_agent.broker_demo_adapters import (
        missing_credential_keys,
        normalize_broker_slug,
        resolve_credentials,
        supported_brokers,
    )
    from services.mt5_worker_agent.mt5_session import authenticate_and_verify

    slug = normalize_broker_slug(broker)
    if slug is None:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "unsupported_broker",
                    "supported": list(supported_brokers()),
                },
                indent=2,
            )
        )
        return 2
    env_req = "live" if str(environment).lower() == "live" else "demo"
    creds = resolve_credentials(slug, environment=env_req)
    if creds is None:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "demo_credentials_not_provided",
                    "missing_env": missing_credential_keys(slug, environment=env_req),
                    "note": (
                        "Cannot run invalid-credential rejection "
                        "without a real login/server."
                    ),
                },
                indent=2,
            )
        )
        return 2
    exe = _prepare_slot_terminal(slot_id)
    result = authenticate_and_verify(
        terminal_exe=exe,
        login=int(creds.login),
        password=creds.password + "__invalid__",
        server=creds.server,
    )
    rejected = not result.ok
    print(
        json.dumps(
            {
                "ok": rejected,
                "broker": slug,
                "invalid_credentials_rejected": rejected,
                "error": result.error,
                "credentials_exposed": False,
                "slot_id": slot_id,
            },
            indent=2,
        )
    )
    return 0 if rejected else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mt5_worker_agent")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("idle")
    p_prep = sub.add_parser("prepare-slots")
    p_prep.add_argument("--force", action="store_true")
    sub.add_parser("start-slots")
    sub.add_parser("stop-slots")
    sub.add_parser("status")
    sub.add_parser("supervise")
    sub.add_parser("railway-ping")
    sub.add_parser("railway-register")
    sub.add_parser("railway-heartbeat")
    p_poll = sub.add_parser("railway-dispatch-poll")
    p_poll.add_argument(
        "--no-ack",
        action="store_true",
        help="Claim only; do not ACK (for lease/recovery tests)",
    )
    sub.add_parser("railway-dispatch-recover")
    sub.add_parser("capacity")
    sub.add_parser("queue-status")
    p_conn = sub.add_parser("connect-demo")
    p_conn.add_argument("--slot", default="demo-a")
    p_conn.add_argument(
        "--broker",
        default=None,
        help="Optional broker slug. Writes evidence when set.",
    )
    p_conn.add_argument("--env", default="demo", choices=["demo", "live"])
    p_verify = sub.add_parser("verify-broker")
    p_verify.add_argument("--broker", required=True, choices=_BROKER_CHOICES)
    p_verify.add_argument("--slot", default="demo-a")
    p_verify.add_argument("--env", default="demo", choices=["demo", "live"])
    p_reject = sub.add_parser("reject-demo")
    p_reject.add_argument("--broker", required=True, choices=_BROKER_CHOICES)
    p_reject.add_argument("--slot", default="demo-a")
    p_reject.add_argument("--env", default="demo", choices=["demo", "live"])
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["idle"]
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "idle"
    if command == "idle":
        return cmd_idle()
    if command == "prepare-slots":
        return cmd_prepare_slots(force=bool(args.force))
    if command == "start-slots":
        return cmd_start_slots()
    if command == "stop-slots":
        return cmd_stop_slots()
    if command == "status":
        return cmd_status()
    if command == "capacity":
        return cmd_capacity()
    if command == "queue-status":
        return cmd_queue_status()
    if command == "supervise":
        return cmd_supervise()
    if command == "railway-ping":
        return cmd_railway_ping()
    if command == "railway-register":
        return cmd_railway_register()
    if command == "railway-heartbeat":
        return cmd_railway_heartbeat()
    if command == "railway-dispatch-poll":
        return cmd_railway_dispatch_poll(ack=not bool(getattr(args, "no_ack", False)))
    if command == "railway-dispatch-recover":
        return cmd_railway_dispatch_recover()
    if command == "connect-demo":
        return cmd_connect_demo(
            str(args.slot),
            broker=getattr(args, "broker", None),
            environment=str(getattr(args, "env", "demo")),
        )
    if command == "verify-broker":
        return cmd_verify_broker(
            str(args.broker),
            str(args.slot),
            environment=str(getattr(args, "env", "demo")),
        )
    if command == "reject-demo":
        return cmd_reject_demo(
            str(args.broker),
            str(args.slot),
            environment=str(getattr(args, "env", "demo")),
        )
    parser.error(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
