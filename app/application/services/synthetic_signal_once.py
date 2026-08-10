"""One-shot TEST/SYNTHETIC Signal Center injection — monitoring only.

Safety contract:
- Writes exclusively to the observe-only multi-asset scan cache used by Signal Center.
- Never calls ExecutionBridge, OMS, order_send, execute-now, or ITE handoff mutation.
- Never sets eligible_symbols / best_symbol for execution handoff.
- Never enables FORCE_FIRST_TRADE, ALLOW_RISK_LOCK_OVERRIDE,
  EXECUTION_ENABLED, or MT5_USE_MOCK.
- Arms for exactly one successful inject, then permanently consumes local state.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from app.application.services.institutional_multi_asset_scanner import (
    _store_last_scan,
    get_last_multi_asset_scan,
)
from app.application.services.signal_center_service import list_live_signals
from core.logging import get_logger

logger = get_logger(__name__)

TEST_SOURCE = "TEST_SYNTHETIC"
TEST_NOTE = (
    "TEST/SYNTHETIC — Signal Center monitoring only — "
    "not executable — never forwarded to OMS/MT5"
)
Side = Literal["BUY", "SELL"]

_LOCK = Lock()


def synthetic_signal_state_path() -> Path:
    raw = (os.environ.get("QUANTFORG_SYNTHETIC_SIGNAL_ONCE_STATE_PATH") or "").strip()
    if raw:
        return Path(raw)
    volume = (os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or "").strip()
    if volume:
        return Path(volume) / "synthetic_signal_once_state.json"
    base = Path(os.environ.get("QUANTFORG_DATA_DIR") or "data")
    return base / "synthetic_signal_once_state.json"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _default_state() -> dict[str, Any]:
    # Default DISARMED — operator must arm once. Prevents restart re-arm storms.
    return {
        "armed": False,
        "consumed": False,
        "inject_count": 0,
        "max_injects": 1,
        "last_signal_id": None,
        "last_at": None,
        "last_symbol": None,
        "last_side": None,
        "last_detail": None,
    }


def arm_once(*, confirmed: bool = False) -> dict[str, Any]:
    """Arm exactly one pending inject. Refuses if already consumed."""
    if not confirmed:
        return {
            "ok": False,
            "error": "confirmed must be true",
            "status": status(),
        }
    with _LOCK:
        state = read_state()
        if bool(state.get("consumed")) or int(state.get("inject_count") or 0) >= max(
            1, int(state.get("max_injects") or 1)
        ):
            return {
                "ok": False,
                "error": "synthetic_signal_once already consumed — cannot re-arm",
                "status": status(),
            }
        state["armed"] = True
        state["consumed"] = False
        _write_state(state)
        logger.warning("synthetic_signal_once_armed", remaining=1)
        return {"ok": True, "status": status()}


def read_state() -> dict[str, Any]:
    path = synthetic_signal_state_path()
    if not path.exists():
        return _default_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default_state()
        base = _default_state()
        base.update(data)
        return base
    except Exception:
        logger.exception("synthetic_signal_once_state_read_failed")
        return _default_state()


def _write_state(state: dict[str, Any]) -> None:
    path = synthetic_signal_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def status() -> dict[str, Any]:
    state = read_state()
    remaining = 0
    if bool(state.get("armed")) and not bool(state.get("consumed")):
        used = int(state.get("inject_count") or 0)
        max_n = max(1, int(state.get("max_injects") or 1))
        remaining = max(0, max_n - used)
    return {
        "injection": "OFF" if remaining <= 0 else "ARMED_ONCE",
        "armed": bool(state.get("armed")) and remaining > 0,
        "consumed": bool(state.get("consumed")) or remaining <= 0,
        "inject_count": int(state.get("inject_count") or 0),
        "max_injects": max(1, int(state.get("max_injects") or 1)),
        "remaining": remaining,
        "last_signal_id": state.get("last_signal_id"),
        "last_at": state.get("last_at"),
        "last_symbol": state.get("last_symbol"),
        "last_side": state.get("last_side"),
        "test_source": TEST_SOURCE,
        "execution": {
            "live_orders_allowed_from_this_path": False,
            "oms_submit": "BLOCKED",
            "mt5_order_send": "BLOCKED",
            "force_first_trade": "UNCHANGED",
            "allow_risk_lock_override": "UNCHANGED",
            "execution_enabled": "UNCHANGED",
            "mt5_use_mock": "UNCHANGED",
        },
    }


def _build_payload(*, symbol: str, side: Side, signal_id: str) -> dict[str, Any]:
    as_of = _now_iso()
    row = {
        "symbol": symbol,
        "direction": side,
        "trade_quality": 84,
        "ai_confidence": 81,
        "reject": False,
        "momentum": 72,
        "structure": 78,
        "trend": "TEST",
        "session": "test",
        "strategy": "TEST_SYNTHETIC",
        "strategy_id": "TEST_SYNTHETIC",
        "opportunity_eligible": False,
        "test_synthetic": True,
        "signal_id": signal_id,
        "as_of": as_of,
        "reason": TEST_NOTE,
        "ai_explanation": (
            f"{TEST_NOTE}. signal_id={signal_id}. side={side}. "
            "Pipeline projection check only."
        ),
        "summary": TEST_NOTE,
        "rr": 1.5,
        "expected_hold": 5,
        # Deliberately omit live bid/ask/mid so we do not fabricate broker prices.
        "factors": {
            "momentum": 72,
            "structure": 78,
            "why_buy": TEST_NOTE if side == "BUY" else None,
            "why_sell": TEST_NOTE if side == "SELL" else None,
            "test_synthetic": True,
        },
    }
    return {
        "as_of": as_of,
        "session": "test",
        "universe": [symbol],
        "rows": [row],
        "ranked": [row],
        "scores": [row],
        "best": None,
        "best_symbol": None,
        "eligible_count": 0,
        "eligible_symbols": [],
        "blocked_by_portfolio": False,
        "note": TEST_NOTE,
        "source": TEST_SOURCE,
        "test_synthetic": True,
        "signal_id": signal_id,
        "forced_trades": False,
        "governed_by_existing_ai_and_risk": True,
        "independent_multi_asset": True,
        "execute_only_best": False,
        "version": "test-synthetic-once",
    }


def _dry_run_oms_readiness(*, symbol: str, side: Side) -> dict[str, Any]:
    """Advisory dry-run only — never submits to OMS/MT5."""
    try:
        from app.application.services.institutional_ai_decision import (
            InstitutionalAiDecisionService,
        )

        service = InstitutionalAiDecisionService()
        result = service.evaluate(
            {
                "side": side.lower(),
                "strategy_id": "TEST_SYNTHETIC",
                "technique": None,
                "dry_run": True,
                "equity": 100,
                "stop_distance": 5,
                "consecutive_losses": 0,
                "daily_drawdown_pct": 0,
                "closed_pnls": [],
                "layers": {
                    "trend_aligned": True,
                    "structure_valid": True,
                    "liquidity_ok": True,
                    "order_block_valid": True,
                    "fvg_valid": True,
                    "risk_engine_passed": True,
                    "safety_engine_passed": True,
                },
            }
        )
        return {
            "status": "PASS",
            "mode": "TEST_ONLY_DRY_RUN",
            "submitted": False,
            "forwarded_to_oms": False,
            "mt5_order_send": False,
            "symbol": symbol,
            "side": side,
            "decision": result.get("decision"),
            "dry_run": bool(result.get("dry_run", True)),
            "allow_trade_idea": bool(result.get("allow_trade_idea")),
            "blocked_reasons": list(result.get("blocked_reasons") or []),
            "note": "Dry-run advisory only — live OMS/MT5 path not invoked",
        }
    except Exception as exc:
        logger.exception("synthetic_signal_dry_run_failed")
        return {
            "status": "FAIL",
            "mode": "TEST_ONLY_DRY_RUN",
            "submitted": False,
            "forwarded_to_oms": False,
            "mt5_order_send": False,
            "symbol": symbol,
            "side": side,
            "error": str(exc)[:300],
            "note": "Dry-run failed safely without live submission",
        }


def inject_once(
    *,
    symbol: str = "XAUUSD",
    side: Side = "BUY",
    confirmed: bool = False,
    restore_previous: bool = True,
) -> dict[str, Any]:
    """Inject exactly one TEST/SYNTHETIC Signal Center row, then disarm."""
    if not confirmed:
        return {
            "ok": False,
            "error": "confirmed must be true",
            "status": status(),
            "mt5_order_submitted": False,
            "execution_result": "NOT_SUBMITTED",
        }

    sym = (symbol or "XAUUSD").strip().upper() or "XAUUSD"
    direction: Side = "SELL" if str(side).strip().upper() == "SELL" else "BUY"

    with _LOCK:
        state = read_state()
        used = int(state.get("inject_count") or 0)
        max_n = max(1, int(state.get("max_injects") or 1))
        if (
            bool(state.get("consumed"))
            or not bool(state.get("armed", True))
            or used >= max_n
        ):
            return {
                "ok": False,
                "error": "synthetic_signal_once already consumed — injection OFF",
                "status": status(),
                "mt5_order_submitted": False,
                "execution_result": "NOT_SUBMITTED",
            }

        previous = get_last_multi_asset_scan()
        signal_id = f"TEST-SYNTHETIC-{uuid.uuid4().hex[:12].upper()}"
        payload = _build_payload(symbol=sym, side=direction, signal_id=signal_id)
        _store_last_scan(payload)

        # Consume immediately so a second concurrent call cannot fire.
        state["inject_count"] = used + 1
        state["armed"] = False
        state["consumed"] = True
        state["last_signal_id"] = signal_id
        state["last_at"] = _now_iso()
        state["last_symbol"] = sym
        state["last_side"] = direction
        state["last_detail"] = TEST_NOTE
        _write_state(state)

        projected = list_live_signals(enabled_only=False)
        visible_items = [
            i
            for i in (projected.get("items") or [])
            if str(i.get("symbol") or "").upper() == sym
            and str(i.get("direction") or "").upper() == direction
        ]
        dry_run = _dry_run_oms_readiness(symbol=sym, side=direction)

        restored = False
        if restore_previous:
            if isinstance(previous, dict):
                _store_last_scan(previous)
            else:
                _store_last_scan(
                    {
                        "as_of": _now_iso(),
                        "universe": [],
                        "rows": [],
                        "eligible_symbols": [],
                        "eligible_count": 0,
                        "best_symbol": None,
                        "note": "restored_after_test_synthetic_once",
                        "test_synthetic": False,
                    }
                )
            restored = True

        logger.warning(
            "synthetic_signal_once_injected",
            signal_id=signal_id,
            symbol=sym,
            side=direction,
            restored=restored,
            oms_submitted=False,
            mt5_submitted=False,
        )

        return {
            "ok": True,
            "created": True,
            "count": 1,
            "type": "TEST_SYNTHETIC",
            "signal_id": signal_id,
            "symbol": sym,
            "side": direction,
            "visible_in_signal_center": len(visible_items) >= 1,
            "signal_center_item": visible_items[0] if visible_items else None,
            "signal_center_source": projected.get("source"),
            "fabricated": projected.get("fabricated"),
            "oms_dry_run": dry_run,
            "execution_result": "TEST_ONLY_DRY_RUN",
            "mt5_order_submitted": False,
            "forwarded_to_oms": False,
            "restored_previous_scan": restored,
            "injection_disabled": True,
            "status": status(),
            "safeguards": {
                "force_first_trade": "unchanged",
                "allow_risk_lock_override": "unchanged",
                "execution_enabled": "unchanged",
                "mt5_use_mock": "unchanged",
                "eligible_symbols_forced_empty": True,
                "live_order_path_invoked": False,
            },
        }

