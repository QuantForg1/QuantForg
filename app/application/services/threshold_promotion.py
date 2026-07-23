"""Threshold Promotion — controlled operator workflow (never auto-applies).

Production baseline: Quality 80 / Confluence 80
Candidate:           Quality 70 / Confluence 75

Explicit approval required. Hot-swaps ITEConfig overlay without mutating
DEFAULT_ITE_CONFIG. Creates rollback point 80/80. Post-promotion monitoring
raises warnings only — never auto-rollbacks.
"""

from __future__ import annotations

import subprocess
from collections import deque
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.operations.models import OperatorIdentity

PRODUCTION_QUALITY = 80
PRODUCTION_CONFLUENCE = 80
CANDIDATE_QUALITY = 70
CANDIDATE_CONFLUENCE = 75
MONITOR_WINDOW = 500

# Material degradation vs validated baseline (warning only).
_DEG_REL = 0.15  # 15% relative worsening
_DEG_DD_PP = 2.0  # absolute drawdown percentage points


def _git_commit_hash() -> str | None:
    try:
        root = Path(__file__).resolve().parents[3]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        )
        return out.strip() or None
    except Exception:
        return None


def build_overlay(
    *,
    quality: int,
    confluence: int,
    version: str | None = None,
) -> ITEConfig:
    """Frozen copy of production ITEConfig with gate overrides only."""
    return replace(
        DEFAULT_ITE_CONFIG,
        min_trade_quality_score=int(quality),
        min_confluence_score=int(confluence),
        config_version=version
        or f"ite-gates-q{quality}-c{confluence}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
    )


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@dataclass
class ThresholdPromotionStore:
    """In-process promotion state + 500-cycle monitor (durable via ops_state)."""

    _lock: Lock = field(default_factory=Lock, repr=False)
    active_quality: int = PRODUCTION_QUALITY
    active_confluence: int = PRODUCTION_CONFLUENCE
    config_version: str = "ite-gates-baseline-q80-c80"
    rollback_quality: int = PRODUCTION_QUALITY
    rollback_confluence: int = PRODUCTION_CONFLUENCE
    rollback_version: str = "ite-gates-rollback-q80-c80"
    promoted: bool = False
    last_promotion: dict[str, Any] | None = None
    last_rollback: dict[str, Any] | None = None
    audit_trail: list[dict[str, Any]] = field(default_factory=list)
    # Validated baseline metrics from Candidate Validation (optional seed)
    validated_baseline: dict[str, Any] = field(default_factory=dict)
    # Post-promotion cycle samples (max 500)
    _monitor: deque[dict[str, Any]] = field(default_factory=deque, repr=False)
    monitor_warnings: list[dict[str, Any]] = field(default_factory=list)
    _hydrated: bool = False

    def __post_init__(self) -> None:
        self._monitor = deque(maxlen=MONITOR_WINDOW)

    def to_persist(self) -> dict[str, Any]:
        with self._lock:
            return {
                "active_quality": self.active_quality,
                "active_confluence": self.active_confluence,
                "config_version": self.config_version,
                "rollback_quality": self.rollback_quality,
                "rollback_confluence": self.rollback_confluence,
                "rollback_version": self.rollback_version,
                "promoted": self.promoted,
                "last_promotion": self.last_promotion,
                "last_rollback": self.last_rollback,
                "audit_trail": list(self.audit_trail)[-100:],
                "validated_baseline": dict(self.validated_baseline),
                "monitor_warnings": list(self.monitor_warnings)[-50:],
            }

    def hydrate(self, payload: dict[str, Any] | None) -> None:
        if not payload or not isinstance(payload, dict):
            return
        with self._lock:
            if self._hydrated:
                return
            self.active_quality = int(
                payload.get("active_quality", PRODUCTION_QUALITY)
            )
            self.active_confluence = int(
                payload.get("active_confluence", PRODUCTION_CONFLUENCE)
            )
            self.config_version = str(
                payload.get("config_version") or self.config_version
            )
            self.rollback_quality = int(
                payload.get("rollback_quality", PRODUCTION_QUALITY)
            )
            self.rollback_confluence = int(
                payload.get("rollback_confluence", PRODUCTION_CONFLUENCE)
            )
            self.rollback_version = str(
                payload.get("rollback_version") or self.rollback_version
            )
            self.promoted = bool(payload.get("promoted", False))
            lp = payload.get("last_promotion")
            self.last_promotion = lp if isinstance(lp, dict) else None
            lr = payload.get("last_rollback")
            self.last_rollback = lr if isinstance(lr, dict) else None
            trail = payload.get("audit_trail")
            if isinstance(trail, list):
                self.audit_trail = [t for t in trail if isinstance(t, dict)]
            base = payload.get("validated_baseline")
            if isinstance(base, dict):
                self.validated_baseline = dict(base)
            warns = payload.get("monitor_warnings")
            if isinstance(warns, list):
                self.monitor_warnings = [w for w in warns if isinstance(w, dict)]
            self._hydrated = True

    def active_overlay(self) -> ITEConfig:
        with self._lock:
            return build_overlay(
                quality=self.active_quality,
                confluence=self.active_confluence,
                version=self.config_version,
            )

    def _append_audit(self, entry: dict[str, Any]) -> None:
        self.audit_trail.append(entry)
        if len(self.audit_trail) > 500:
            self.audit_trail = self.audit_trail[-500:]


_STORE: ThresholdPromotionStore | None = None
_STORE_LOCK = Lock()


def get_threshold_promotion_store() -> ThresholdPromotionStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = ThresholdPromotionStore()
            try:
                from app.application.services.ops_state_persistence import (
                    load_ops_state,
                )

                state = load_ops_state()
                payload = state.get("threshold_promotion")
                if isinstance(payload, dict):
                    _STORE.hydrate(payload)
            except Exception:
                pass
        return _STORE


def reset_threshold_promotion_store() -> None:
    global _STORE
    with _STORE_LOCK:
        _STORE = ThresholdPromotionStore()


def apply_overlay_to_runtime(overlay: ITEConfig) -> dict[str, Any]:
    """Hot-swap decision pipeline + diagnostics config. No engine restart."""
    applied: dict[str, Any] = {
        "pipeline": False,
        "diagnostics": False,
        "runtime_present": False,
    }
    try:
        from app.application.services.institutional_ite_runtime import get_ite_runtime

        runtime = get_ite_runtime()
        if runtime is not None:
            applied["runtime_present"] = True
            runtime.decision_pipeline.config = overlay
            applied["pipeline"] = True
    except Exception:
        pass
    try:
        from app.application.services.strategy_diagnostics import (
            get_strategy_diagnostics_store,
        )

        store = get_strategy_diagnostics_store()
        store._config = overlay  # noqa: SLF001 — intentional research/ops overlay
        applied["diagnostics"] = True
    except Exception:
        pass
    # Ensure DEFAULT remains untouched
    assert DEFAULT_ITE_CONFIG.min_trade_quality_score == PRODUCTION_QUALITY
    assert DEFAULT_ITE_CONFIG.min_confluence_score == PRODUCTION_CONFLUENCE
    return applied


def _persist(store: ThresholdPromotionStore) -> None:
    try:
        from app.application.services.ops_state_persistence import save_ops_state

        save_ops_state({"threshold_promotion": store.to_persist()})
    except Exception:
        pass


def _load_candidate_validation_summary() -> dict[str, Any]:
    """Best-effort load of latest candidate validation evidence (read-only)."""
    root = Path(__file__).resolve().parents[3]
    path = root / "docs" / "production" / "reports" / "candidate_validation_latest.json"
    if not path.is_file():
        return {"status": "missing", "path": str(path)}
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"status": "invalid"}
        return {
            "status": "available",
            "generated_at": data.get("generated_at"),
            "decision": data.get("decision"),
            "comparison": data.get("comparison"),
            "production": data.get("production"),
            "candidate": data.get("candidate"),
            "path": str(path),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def status_payload() -> dict[str, Any]:
    store = get_threshold_promotion_store()
    # Ensure runtime matches store if process restarted with hydrated overlay
    overlay = store.active_overlay()
    apply_overlay_to_runtime(overlay)
    evidence = _load_candidate_validation_summary()
    with store._lock:
        monitoring = _compute_monitoring_locked(store)
        return {
            "schema_version": "1.0.0",
            "never_auto_promotes": True,
            "never_auto_rollbacks": True,
            "default_baseline_immutable": True,
            "production": {
                "label": "Current Production (active)",
                "quality": store.active_quality,
                "confluence": store.active_confluence,
                "config_version": store.config_version,
                "is_baseline": (
                    store.active_quality == PRODUCTION_QUALITY
                    and store.active_confluence == PRODUCTION_CONFLUENCE
                ),
            },
            "candidate": {
                "label": "Candidate",
                "quality": CANDIDATE_QUALITY,
                "confluence": CANDIDATE_CONFLUENCE,
            },
            "rollback_point": {
                "quality": store.rollback_quality,
                "confluence": store.rollback_confluence,
                "config_version": store.rollback_version,
                "always_80_80": (
                    store.rollback_quality == PRODUCTION_QUALITY
                    and store.rollback_confluence == PRODUCTION_CONFLUENCE
                ),
            },
            "promoted": store.promoted,
            "last_promotion": store.last_promotion,
            "last_rollback": store.last_rollback,
            "audit_trail": list(reversed(store.audit_trail[-25:])),
            "research_evidence": evidence,
            "candidate_validation_report": evidence,
            "monitoring": monitoring,
            "workflow_steps": [
                "1. Operator reviews evidence",
                "2. Operator explicitly approves promotion (confirmed=true)",
                "3. Persist new configuration version",
                "4. Hot-swap Quality=70 / Confluence=75 without restart",
                "5. Record UTC timestamp, operator, previous/new thresholds, reason, evidence, commit hash",
            ],
        }


def promote_candidate(
    *,
    operator: OperatorIdentity,
    reason: str,
    confirmed: bool,
    evidence_reference: str | None = None,
) -> dict[str, Any]:
    """Explicit promotion to Q70/C75. Never runs without confirmed=true."""
    if not confirmed:
        raise ValueError("operator confirmation required — promotion not applied")
    reason_clean = (reason or "").strip()
    if len(reason_clean) < 8:
        raise ValueError("reason required (min 8 characters)")

    store = get_threshold_promotion_store()
    now = datetime.now(UTC)
    commit = _git_commit_hash()
    evidence = evidence_reference or "candidate_validation_latest.json"
    version = (
        f"ite-gates-q{CANDIDATE_QUALITY}-c{CANDIDATE_CONFLUENCE}-"
        f"{now.strftime('%Y%m%dT%H%M%SZ')}"
    )

    with store._lock:
        prev_q = store.active_quality
        prev_c = store.active_confluence
        prev_v = store.config_version
        # Always freeze rollback point at production 80/80
        store.rollback_quality = PRODUCTION_QUALITY
        store.rollback_confluence = PRODUCTION_CONFLUENCE
        store.rollback_version = "ite-gates-rollback-q80-c80"
        store.active_quality = CANDIDATE_QUALITY
        store.active_confluence = CANDIDATE_CONFLUENCE
        store.config_version = version
        store.promoted = True
        store._monitor.clear()
        store.monitor_warnings = []
        # Seed validated baseline from evidence if present
        ev = _load_candidate_validation_summary()
        cand_metrics = ((ev.get("candidate") or {}) if isinstance(ev, dict) else {}).get(
            "metrics"
        )
        if isinstance(cand_metrics, dict):
            store.validated_baseline = dict(cand_metrics)
        record = {
            "id": str(uuid4()),
            "utc_timestamp": now.isoformat(),
            "operator": operator.display_name or str(operator.user_id),
            "operator_id": str(operator.user_id),
            "previous_thresholds": {"quality": prev_q, "confluence": prev_c},
            "new_thresholds": {
                "quality": CANDIDATE_QUALITY,
                "confluence": CANDIDATE_CONFLUENCE,
            },
            "reason": reason_clean,
            "evidence_reference": evidence,
            "commit_hash": commit,
            "config_version": version,
            "rollback_point": {
                "quality": PRODUCTION_QUALITY,
                "confluence": PRODUCTION_CONFLUENCE,
            },
            "action": "threshold_promote",
        }
        store.last_promotion = record
        store._append_audit(record)

    overlay = build_overlay(
        quality=CANDIDATE_QUALITY,
        confluence=CANDIDATE_CONFLUENCE,
        version=version,
    )
    applied = apply_overlay_to_runtime(overlay)
    _persist(store)

    # Mirror into control-plane audit when available
    try:
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )

        get_control_plane().audit.record(
            operator=operator,
            action="threshold_promote",
            old_value=f"{prev_q}/{prev_c}",
            new_value=f"{CANDIDATE_QUALITY}/{CANDIDATE_CONFLUENCE}",
            reason=reason_clean,
            now=now,
        )
    except Exception:
        pass

    return {
        "ok": True,
        "promoted": True,
        "auto_applied_without_confirmation": False,
        "record": record,
        "hot_swap": applied,
        "rollback_point": {
            "quality": PRODUCTION_QUALITY,
            "confluence": PRODUCTION_CONFLUENCE,
        },
        "active": {
            "quality": CANDIDATE_QUALITY,
            "confluence": CANDIDATE_CONFLUENCE,
            "config_version": version,
        },
        "default_ite_config_unchanged": True,
    }


def rollback_to_production(
    *,
    operator: OperatorIdentity,
    reason: str,
    confirmed: bool,
) -> dict[str, Any]:
    """Single-click rollback to 80/80 with audit. Never automatic."""
    if not confirmed:
        raise ValueError("operator confirmation required — rollback not applied")
    reason_clean = (reason or "").strip() or "operator_rollback_to_80_80"

    store = get_threshold_promotion_store()
    now = datetime.now(UTC)
    commit = _git_commit_hash()
    version = f"ite-gates-rollback-q80-c80-{now.strftime('%Y%m%dT%H%M%SZ')}"

    with store._lock:
        prev_q = store.active_quality
        prev_c = store.active_confluence
        store.active_quality = PRODUCTION_QUALITY
        store.active_confluence = PRODUCTION_CONFLUENCE
        store.config_version = version
        store.promoted = False
        record = {
            "id": str(uuid4()),
            "utc_timestamp": now.isoformat(),
            "operator": operator.display_name or str(operator.user_id),
            "operator_id": str(operator.user_id),
            "previous_thresholds": {"quality": prev_q, "confluence": prev_c},
            "new_thresholds": {
                "quality": PRODUCTION_QUALITY,
                "confluence": PRODUCTION_CONFLUENCE,
            },
            "reason": reason_clean,
            "evidence_reference": "rollback_point_80_80",
            "commit_hash": commit,
            "config_version": version,
            "action": "threshold_rollback",
        }
        store.last_rollback = record
        store._append_audit(record)

    overlay = build_overlay(
        quality=PRODUCTION_QUALITY,
        confluence=PRODUCTION_CONFLUENCE,
        version=version,
    )
    applied = apply_overlay_to_runtime(overlay)
    _persist(store)

    try:
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )

        get_control_plane().audit.record(
            operator=operator,
            action="threshold_rollback",
            old_value=f"{prev_q}/{prev_c}",
            new_value=f"{PRODUCTION_QUALITY}/{PRODUCTION_CONFLUENCE}",
            reason=reason_clean,
            now=now,
        )
    except Exception:
        pass

    return {
        "ok": True,
        "rolled_back": True,
        "auto_rollback": False,
        "record": record,
        "hot_swap": applied,
        "active": {
            "quality": PRODUCTION_QUALITY,
            "confluence": PRODUCTION_CONFLUENCE,
            "config_version": version,
        },
    }


def observe_cycle(cycle: dict[str, Any]) -> None:
    """Record one live cycle into the 500-window monitor when promoted."""
    store = get_threshold_promotion_store()
    with store._lock:
        if not store.promoted:
            return
        quality = cycle.get("quality") if isinstance(cycle.get("quality"), dict) else {}
        confluence = (
            cycle.get("confluence") if isinstance(cycle.get("confluence"), dict) else {}
        )
        sample = {
            "recorded_at": cycle.get("recorded_at"),
            "executed": bool(cycle.get("executed")),
            "rejected": bool(cycle.get("rejected")),
            "decision_action": cycle.get("decision_action"),
            "quality": quality.get("score"),
            "confluence": confluence.get("total"),
            "latency_ms": cycle.get("latency_ms"),
        }
        # Optional outcome fields if present on enriched cycles
        for key in (
            "win",
            "r_multiple",
            "net_pnl",
            "holding_time_sec",
        ):
            if key in cycle:
                sample[key] = cycle[key]
        store._monitor.append(sample)
        warning = _evaluate_degradation_locked(store)
        if warning is not None:
            store.monitor_warnings.append(warning)
            if len(store.monitor_warnings) > 100:
                store.monitor_warnings = store.monitor_warnings[-100:]


def _compute_monitoring_locked(store: ThresholdPromotionStore) -> dict[str, Any]:
    samples = list(store._monitor)
    n = len(samples)
    executed = sum(1 for s in samples if s.get("executed"))
    rejected = sum(1 for s in samples if s.get("rejected"))
    execution_rate = round(100.0 * executed / n, 2) if n else None
    wins = [s for s in samples if s.get("win") is True]
    losses = [s for s in samples if s.get("win") is False]
    closed = wins + losses
    win_rate = (len(wins) / len(closed)) if closed else None
    pnls = [_f(s.get("net_pnl")) for s in closed]
    pnls_f = [p for p in pnls if p is not None]
    gross_win = sum(p for p in pnls_f if p > 0)
    gross_loss = abs(sum(p for p in pnls_f if p < 0))
    pf = (gross_win / gross_loss) if gross_loss > 0 else None
    expectancy = None
    if win_rate is not None and pnls_f:
        avg_win = (
            (sum(p for p in pnls_f if p > 0) / len([p for p in pnls_f if p > 0]))
            if any(p > 0 for p in pnls_f)
            else 0.0
        )
        avg_loss = (
            (abs(sum(p for p in pnls_f if p < 0)) / len([p for p in pnls_f if p < 0]))
            if any(p < 0 for p in pnls_f)
            else 0.0
        )
        expectancy = win_rate * avg_win - (1.0 - win_rate) * avg_loss
    rs = [_f(s.get("r_multiple")) for s in samples]
    rs_f = [r for r in rs if r is not None]
    lats = [_f(s.get("latency_ms")) for s in samples]
    lats_f = [x for x in lats if x is not None]
    # Equity DD from pnl series when available
    max_dd = None
    if pnls_f:
        eq = peak = 0.0
        max_dd = 0.0
        for p in pnls_f:
            eq += p
            peak = max(peak, eq)
            dd = (peak - eq) / peak * 100.0 if peak > 0 else 0.0
            max_dd = max(max_dd, dd)

    live = {
        "cycles_observed": n,
        "window": MONITOR_WINDOW,
        "execution_rate_pct": execution_rate,
        "executed": executed,
        "rejected": rejected,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "profit_factor": round(pf, 4) if pf is not None else None,
        "expectancy": round(expectancy, 6) if expectancy is not None else None,
        "drawdown_pct": round(max_dd, 4) if max_dd is not None else None,
        "average_rr": round(sum(rs_f) / len(rs_f), 4) if rs_f else None,
        "average_latency_ms": round(sum(lats_f) / len(lats_f), 3) if lats_f else None,
        "note": (
            "Win/PF/Expectancy/DD require enriched cycle outcomes; "
            "execution rate and latency always available from live diagnostics."
        ),
    }
    return {
        "active": store.promoted,
        "validated_baseline": dict(store.validated_baseline),
        "live": live,
        "warnings": list(store.monitor_warnings)[-10:],
        "never_auto_rollback": True,
    }


def _evaluate_degradation_locked(
    store: ThresholdPromotionStore,
) -> dict[str, Any] | None:
    """Raise warning only when live metrics materially degrade vs baseline."""
    if len(store._monitor) < 30:
        return None  # insufficient sample
    mon = _compute_monitoring_locked(store)
    live = mon.get("live") or {}
    base = store.validated_baseline or {}
    issues: list[str] = []

    def worse_lower_is_bad(live_v: float | None, base_v: float | None, name: str) -> None:
        if live_v is None or base_v is None or base_v == 0:
            return
        if live_v < base_v * (1.0 - _DEG_REL):
            issues.append(
                f"{name} degraded: live={live_v} vs baseline={base_v}"
            )

    worse_lower_is_bad(
        _f(live.get("profit_factor")), _f(base.get("profit_factor")), "profit_factor"
    )
    worse_lower_is_bad(
        _f(live.get("expectancy")), _f(base.get("expectancy")), "expectancy"
    )
    worse_lower_is_bad(
        _f(live.get("win_rate")), _f(base.get("win_rate")), "win_rate"
    )
    worse_lower_is_bad(
        _f(live.get("average_rr")), _f(base.get("average_rr")), "average_rr"
    )
    # Drawdown: higher is worse
    live_dd = _f(live.get("drawdown_pct"))
    base_dd = _f(base.get("maximum_drawdown_pct"))
    if live_dd is not None and base_dd is not None:
        cap = max(base_dd * (1.0 + _DEG_REL), base_dd + _DEG_DD_PP)
        if live_dd > cap:
            issues.append(
                f"drawdown worsened: live={live_dd} vs baseline={base_dd} (cap={cap})"
            )

    if not issues:
        return None
    return {
        "utc_timestamp": datetime.now(UTC).isoformat(),
        "severity": "warning",
        "auto_rollback": False,
        "cycles_observed": live.get("cycles_observed"),
        "issues": issues,
        "message": (
            "Post-promotion metrics materially degraded versus validated baseline. "
            "Warning only — never auto-rollback. Operator may rollback manually."
        ),
    }
