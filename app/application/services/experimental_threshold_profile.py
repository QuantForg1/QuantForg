"""EXPERIMENTAL_75 threshold profile — temporary overlay (never mutates DEFAULT).

Institutional production default remains Quality=80 / Confluence=80 in
``DEFAULT_ITE_CONFIG``. This module hot-swaps a versioned ITEConfig overlay
only when an operator explicitly activates EXPERIMENTAL_75 (Q75/C75).

- Explicit activation + audit log
- One-click rollback to Q80/C80
- Live monitoring for 100 eligible evaluations
- Auto-generates EXPERIMENTAL_THRESHOLD_REPORT (never auto-promotes)
- Does not touch Risk Engine, Safety, OMS, min-lot, or position sizing
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from app.application.services.threshold_promotion import (
    PRODUCTION_CONFLUENCE,
    PRODUCTION_QUALITY,
    apply_overlay_to_runtime,
    build_overlay,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.operations.models import OperatorIdentity

PROFILE_ID = "EXPERIMENTAL_75"
EXPERIMENTAL_QUALITY = 75
EXPERIMENTAL_CONFLUENCE = 75
EVAL_TARGET = 100
BADGE_LABEL = "Experimental Profile Active (Q75/C75)"

_REPORT_DIR = (
    Path(__file__).resolve().parents[3] / "docs" / "production" / "reports"
)


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


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _assert_default_frozen() -> None:
    assert DEFAULT_ITE_CONFIG.min_trade_quality_score == PRODUCTION_QUALITY
    assert DEFAULT_ITE_CONFIG.min_confluence_score == PRODUCTION_CONFLUENCE


@dataclass
class ExperimentalThresholdStore:
    """In-process experimental overlay state (durable via ops_state)."""

    _lock: Lock = field(default_factory=Lock, repr=False)
    active: bool = False
    profile_id: str = PROFILE_ID
    config_version: str = "ite-gates-baseline-q80-c80"
    activated_at: str | None = None
    activated_by: str | None = None
    evaluations: int = 0
    report_generated: bool = False
    last_report: dict[str, Any] | None = None
    last_activation: dict[str, Any] | None = None
    last_rollback: dict[str, Any] | None = None
    audit_trail: list[dict[str, Any]] = field(default_factory=list)
    _samples: deque[dict[str, Any]] = field(default_factory=deque, repr=False)
    _hydrated: bool = False

    def __post_init__(self) -> None:
        self._samples = deque(maxlen=EVAL_TARGET)

    def to_persist(self) -> dict[str, Any]:
        with self._lock:
            return {
                "active": self.active,
                "profile_id": self.profile_id,
                "config_version": self.config_version,
                "activated_at": self.activated_at,
                "activated_by": self.activated_by,
                "evaluations": self.evaluations,
                "report_generated": self.report_generated,
                "last_report": self.last_report,
                "last_activation": self.last_activation,
                "last_rollback": self.last_rollback,
                "audit_trail": list(self.audit_trail)[-100:],
                "samples": list(self._samples),
            }

    def hydrate(self, payload: dict[str, Any] | None) -> None:
        if not payload or not isinstance(payload, dict):
            return
        with self._lock:
            if self._hydrated:
                return
            self.active = bool(payload.get("active", False))
            self.profile_id = str(payload.get("profile_id") or PROFILE_ID)
            self.config_version = str(
                payload.get("config_version") or self.config_version
            )
            self.activated_at = (
                str(payload["activated_at"])
                if payload.get("activated_at")
                else None
            )
            self.activated_by = (
                str(payload["activated_by"])
                if payload.get("activated_by")
                else None
            )
            self.evaluations = int(payload.get("evaluations") or 0)
            self.report_generated = bool(payload.get("report_generated", False))
            lr = payload.get("last_report")
            self.last_report = lr if isinstance(lr, dict) else None
            la = payload.get("last_activation")
            self.last_activation = la if isinstance(la, dict) else None
            rb = payload.get("last_rollback")
            self.last_rollback = rb if isinstance(rb, dict) else None
            trail = payload.get("audit_trail")
            if isinstance(trail, list):
                self.audit_trail = [t for t in trail if isinstance(t, dict)]
            samples = payload.get("samples")
            if isinstance(samples, list):
                self._samples = deque(
                    (s for s in samples if isinstance(s, dict)),
                    maxlen=EVAL_TARGET,
                )
            self._hydrated = True

    def active_overlay(self) -> ITEConfig:
        with self._lock:
            if not self.active:
                return build_overlay(
                    quality=PRODUCTION_QUALITY,
                    confluence=PRODUCTION_CONFLUENCE,
                    version=self.config_version,
                )
            return build_overlay(
                quality=EXPERIMENTAL_QUALITY,
                confluence=EXPERIMENTAL_CONFLUENCE,
                version=self.config_version,
            )

    def _append_audit(self, entry: dict[str, Any]) -> None:
        self.audit_trail.append(entry)
        if len(self.audit_trail) > 500:
            self.audit_trail = self.audit_trail[-500:]


_STORE: ExperimentalThresholdStore | None = None
_STORE_LOCK = Lock()


def get_experimental_threshold_store() -> ExperimentalThresholdStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = ExperimentalThresholdStore()
            try:
                from app.application.services.ops_state_persistence import (
                    load_ops_state,
                )

                state = load_ops_state()
                payload = state.get("experimental_threshold_profile")
                if isinstance(payload, dict):
                    _STORE.hydrate(payload)
            except Exception:
                pass
        return _STORE


def reset_experimental_threshold_store() -> None:
    """Test helper — clears singleton and blocks stale ops_state re-hydrate."""
    global _STORE
    with _STORE_LOCK:
        _STORE = ExperimentalThresholdStore()
        _STORE._hydrated = True
        try:
            from app.application.services.ops_state_persistence import save_ops_state

            save_ops_state({"experimental_threshold_profile": _STORE.to_persist()})
        except Exception:
            pass


def is_experimental_active() -> bool:
    return bool(get_experimental_threshold_store().active)


def _persist(store: ExperimentalThresholdStore) -> None:
    try:
        from app.application.services.ops_state_persistence import save_ops_state

        save_ops_state({"experimental_threshold_profile": store.to_persist()})
    except Exception:
        pass


def _control_plane_audit(
    *,
    operator: OperatorIdentity,
    action: str,
    old_value: str,
    new_value: str,
    reason: str,
    now: datetime,
) -> None:
    try:
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )

        get_control_plane().audit.record(
            operator=operator,
            action=action,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            now=now,
        )
    except Exception:
        pass


def activate_experimental_75(
    *,
    operator: OperatorIdentity,
    reason: str,
    confirmed: bool,
) -> dict[str, Any]:
    """Operator-gated activation of EXPERIMENTAL_75 (Q75/C75)."""
    if not confirmed:
        raise ValueError("operator confirmation required — experimental profile not activated")
    reason_clean = (reason or "").strip()
    if len(reason_clean) < 8:
        raise ValueError("reason required (min 8 characters)")

    # Conflict with candidate 70/75 promotion
    try:
        from app.application.services.threshold_promotion import (
            get_threshold_promotion_store,
        )

        promo = get_threshold_promotion_store()
        if promo.promoted and (
            promo.active_quality != EXPERIMENTAL_QUALITY
            or promo.active_confluence != EXPERIMENTAL_CONFLUENCE
        ):
            raise ValueError(
                "threshold promotion candidate is active — rollback 70/75 before "
                "activating EXPERIMENTAL_75"
            )
    except ValueError:
        raise
    except Exception:
        pass

    store = get_experimental_threshold_store()
    now = datetime.now(UTC)
    commit = _git_commit_hash()
    version = (
        f"ite-gates-experimental-q{EXPERIMENTAL_QUALITY}-c{EXPERIMENTAL_CONFLUENCE}-"
        f"{now.strftime('%Y%m%dT%H%M%SZ')}"
    )

    with store._lock:
        if store.active:
            raise ValueError("EXPERIMENTAL_75 is already active")
        prev_q = PRODUCTION_QUALITY
        prev_c = PRODUCTION_CONFLUENCE
        store.active = True
        store.config_version = version
        store.activated_at = now.isoformat()
        store.activated_by = operator.display_name or str(operator.user_id)
        store.evaluations = 0
        store.report_generated = False
        store.last_report = None
        store._samples.clear()
        record = {
            "id": str(uuid4()),
            "utc_timestamp": now.isoformat(),
            "operator": operator.display_name or str(operator.user_id),
            "operator_id": str(operator.user_id),
            "action": "experimental_75_activate",
            "profile_id": PROFILE_ID,
            "previous_thresholds": {"quality": prev_q, "confluence": prev_c},
            "new_thresholds": {
                "quality": EXPERIMENTAL_QUALITY,
                "confluence": EXPERIMENTAL_CONFLUENCE,
            },
            "reason": reason_clean,
            "commit_hash": commit,
            "config_version": version,
            "default_ite_config_unchanged": True,
            "auto_promote": False,
        }
        store.last_activation = record
        store._append_audit(record)

    overlay = build_overlay(
        quality=EXPERIMENTAL_QUALITY,
        confluence=EXPERIMENTAL_CONFLUENCE,
        version=version,
    )
    applied = apply_overlay_to_runtime(overlay)
    _assert_default_frozen()
    _persist(store)
    _control_plane_audit(
        operator=operator,
        action="experimental_75_activate",
        old_value=f"{prev_q}/{prev_c}",
        new_value=f"{EXPERIMENTAL_QUALITY}/{EXPERIMENTAL_CONFLUENCE}",
        reason=reason_clean,
        now=now,
    )

    return {
        "ok": True,
        "activated": True,
        "profile_id": PROFILE_ID,
        "badge": BADGE_LABEL,
        "auto_applied_without_confirmation": False,
        "never_modifies_default_ite_config": True,
        "record": record,
        "hot_swap": applied,
        "active": {
            "quality": EXPERIMENTAL_QUALITY,
            "confluence": EXPERIMENTAL_CONFLUENCE,
            "config_version": version,
        },
        "eval_target": EVAL_TARGET,
        "default_ite_config": {
            "quality": DEFAULT_ITE_CONFIG.min_trade_quality_score,
            "confluence": DEFAULT_ITE_CONFIG.min_confluence_score,
        },
    }


def rollback_experimental_to_production(
    *,
    operator: OperatorIdentity,
    reason: str,
    confirmed: bool,
) -> dict[str, Any]:
    """One-click rollback to Institutional Q80/C80. Never automatic."""
    if not confirmed:
        raise ValueError("operator confirmation required — rollback not applied")
    reason_clean = (reason or "").strip() or "operator_rollback_experimental_to_80_80"

    store = get_experimental_threshold_store()
    now = datetime.now(UTC)
    commit = _git_commit_hash()
    version = f"ite-gates-rollback-q80-c80-{now.strftime('%Y%m%dT%H%M%SZ')}"

    with store._lock:
        was_active = store.active
        prev_q = EXPERIMENTAL_QUALITY if was_active else PRODUCTION_QUALITY
        prev_c = EXPERIMENTAL_CONFLUENCE if was_active else PRODUCTION_CONFLUENCE
        store.active = False
        store.config_version = version
        record = {
            "id": str(uuid4()),
            "utc_timestamp": now.isoformat(),
            "operator": operator.display_name or str(operator.user_id),
            "operator_id": str(operator.user_id),
            "action": "experimental_75_rollback",
            "profile_id": PROFILE_ID,
            "previous_thresholds": {"quality": prev_q, "confluence": prev_c},
            "new_thresholds": {
                "quality": PRODUCTION_QUALITY,
                "confluence": PRODUCTION_CONFLUENCE,
            },
            "reason": reason_clean,
            "commit_hash": commit,
            "config_version": version,
            "evaluations_at_rollback": store.evaluations,
            "auto_rollback": False,
        }
        store.last_rollback = record
        store._append_audit(record)

    overlay = build_overlay(
        quality=PRODUCTION_QUALITY,
        confluence=PRODUCTION_CONFLUENCE,
        version=version,
    )
    applied = apply_overlay_to_runtime(overlay)
    _assert_default_frozen()
    _persist(store)
    _control_plane_audit(
        operator=operator,
        action="experimental_75_rollback",
        old_value=f"{prev_q}/{prev_c}",
        new_value=f"{PRODUCTION_QUALITY}/{PRODUCTION_CONFLUENCE}",
        reason=reason_clean,
        now=now,
    )

    return {
        "ok": True,
        "rolled_back": True,
        "auto_rollback": False,
        "badge": None,
        "record": record,
        "hot_swap": applied,
        "active": {
            "quality": PRODUCTION_QUALITY,
            "confluence": PRODUCTION_CONFLUENCE,
            "config_version": version,
        },
        "default_ite_config_unchanged": True,
    }


def _is_eligible_cycle(cycle: dict[str, Any]) -> bool:
    """Eligible live evaluation: scored analysis cycle (not empty/off-hours noise)."""
    quality = cycle.get("quality") if isinstance(cycle.get("quality"), dict) else {}
    confluence = (
        cycle.get("confluence") if isinstance(cycle.get("confluence"), dict) else {}
    )
    q = quality.get("score")
    c = confluence.get("total")
    if q is None and c is None:
        return False
    session = cycle.get("session") if isinstance(cycle.get("session"), dict) else {}
    if session.get("allowed") is False:
        return False
    return True


def _metrics_from_samples(samples: list[dict[str, Any]], *, label: str) -> dict[str, Any]:
    n = len(samples)
    signals = sum(1 for s in samples if s.get("signal"))
    executed = sum(1 for s in samples if s.get("executed"))
    rejected = sum(1 for s in samples if s.get("rejected"))
    reasons = Counter(
        str(s.get("rejection_reason") or "unknown")
        for s in samples
        if s.get("rejected") and s.get("rejection_reason")
    )
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
    max_dd = None
    if pnls_f:
        eq = peak = 0.0
        max_dd = 0.0
        for p in pnls_f:
            eq += p
            peak = max(peak, eq)
            dd = (peak - eq) / peak * 100.0 if peak > 0 else 0.0
            max_dd = max(max_dd, dd)

    return {
        "label": label,
        "evaluations": n,
        "signals_generated": signals,
        "trades_executed": executed,
        "rejected": rejected,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "profit_factor": round(pf, 4) if pf is not None else None,
        "expectancy": round(expectancy, 6) if expectancy is not None else None,
        "drawdown_pct": round(max_dd, 4) if max_dd is not None else None,
        "average_rr": round(sum(rs_f) / len(rs_f), 4) if rs_f else None,
        "rejection_reasons": [
            {"reason": r, "count": c} for r, c in reasons.most_common(20)
        ],
        "note": (
            "Win/PF/Expectancy/DD require enriched cycle outcomes when available; "
            "signals/executions/rejections always tracked."
        ),
    }


def _build_recommendation(
    experimental: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    exp_signals = int(experimental.get("signals_generated") or 0)
    base_signals = int(baseline.get("signals_generated") or 0)
    exp_exec = int(experimental.get("trades_executed") or 0)
    base_exec = int(baseline.get("trades_executed") or 0)
    execution_increased = exp_exec > base_exec or exp_signals > base_signals

    # Performance: prefer expectancy / PF / win_rate when present; else signal lift alone is insufficient
    perf_scores: list[bool] = []
    for key, higher_better in (
        ("expectancy", True),
        ("profit_factor", True),
        ("win_rate", True),
        ("average_rr", True),
        ("drawdown_pct", False),
    ):
        ev = _f(experimental.get(key))
        bv = _f(baseline.get(key))
        if ev is None or bv is None:
            continue
        if higher_better:
            perf_scores.append(ev >= bv)
        else:
            perf_scores.append(ev <= bv)

    if perf_scores:
        performance_improved = sum(perf_scores) >= (len(perf_scores) / 2.0)
    else:
        # No outcome enrichment — do not claim improvement; prefer revert
        performance_improved = False

    if performance_improved and execution_increased:
        recommendation = "Keep 75/75"
        summary = (
            "Experimental 75/75 increased execution and showed equal-or-better "
            "outcome metrics vs shadow 80/80 in this window. Operator approval "
            "still required — never auto-promoted."
        )
    else:
        recommendation = "Revert to 80/80"
        summary = (
            "Insufficient evidence that 75/75 improves performance vs baseline "
            "80/80 (or outcomes not enriched). Recommend revert to Institutional "
            "Q80/C80. Operator approval still required — never auto-promoted."
        )

    return {
        "execution_increased": execution_increased,
        "performance_improved": performance_improved,
        "recommendation": recommendation,
        "summary": summary,
        "auto_promoted": False,
        "operator_approval_required": True,
    }


def generate_experimental_threshold_report(
    store: ExperimentalThresholdStore | None = None,
) -> dict[str, Any]:
    """Build EXPERIMENTAL_THRESHOLD_REPORT from collected samples."""
    store = store or get_experimental_threshold_store()
    with store._lock:
        samples = list(store._samples)
        evaluations = store.evaluations
        activated_at = store.activated_at
        config_version = store.config_version

    experimental_view = [_experimental_view(s) for s in samples]
    baseline_view = [_baseline_shadow_view(s) for s in samples]
    exp_metrics = _metrics_from_samples(experimental_view, label="EXPERIMENTAL_75 (Q75/C75)")
    base_metrics = _metrics_from_samples(baseline_view, label="Baseline shadow (Q80/C80)")
    decision = _build_recommendation(exp_metrics, base_metrics)

    report = {
        "schema_version": "1.0.0",
        "report_type": "EXPERIMENTAL_THRESHOLD_REPORT",
        "generated_at": datetime.now(UTC).isoformat(),
        "profile_id": PROFILE_ID,
        "eval_target": EVAL_TARGET,
        "evaluations": evaluations,
        "activated_at": activated_at,
        "config_version": config_version,
        "default_ite_config_unchanged": True,
        "default_baseline": {
            "quality": PRODUCTION_QUALITY,
            "confluence": PRODUCTION_CONFLUENCE,
        },
        "experimental": {
            "quality": EXPERIMENTAL_QUALITY,
            "confluence": EXPERIMENTAL_CONFLUENCE,
        },
        "comparison": {
            "experimental": exp_metrics,
            "baseline_80_80": base_metrics,
        },
        "execution_increased": decision["execution_increased"],
        "performance_improved": decision["performance_improved"],
        "recommendation": decision["recommendation"],
        "recommendation_detail": decision,
        "never_auto_promotes": True,
        "risk_safety_oms_unchanged": True,
    }
    return report


def _experimental_view(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal": bool(sample.get("experimental_signal")),
        "executed": bool(sample.get("executed")),
        "rejected": bool(sample.get("rejected")),
        "rejection_reason": sample.get("rejection_reason"),
        "win": sample.get("win"),
        "net_pnl": sample.get("net_pnl"),
        "r_multiple": sample.get("r_multiple"),
    }


def _baseline_shadow_view(sample: dict[str, Any]) -> dict[str, Any]:
    """Would this cycle have signaled under Institutional 80/80?"""
    return {
        "signal": bool(sample.get("baseline_signal")),
        "executed": bool(sample.get("baseline_would_execute")),
        "rejected": not bool(sample.get("baseline_signal")),
        "rejection_reason": sample.get("baseline_reject_reason"),
        "win": sample.get("win") if sample.get("baseline_signal") else None,
        "net_pnl": sample.get("net_pnl") if sample.get("baseline_signal") else None,
        "r_multiple": (
            sample.get("r_multiple") if sample.get("baseline_signal") else None
        ),
    }


def _write_report_files(report: dict[str, Any]) -> dict[str, str]:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_body = json.dumps(report, indent=2) + "\n"
    latest = _REPORT_DIR / "EXPERIMENTAL_THRESHOLD_REPORT.json"
    stamped = _REPORT_DIR / f"experimental_threshold_report_{stamp}.json"
    latest.write_text(json_body, encoding="utf-8")
    stamped.write_text(json_body, encoding="utf-8")

    md = report_to_markdown(report)
    md_path = _REPORT_DIR / "EXPERIMENTAL_THRESHOLD_REPORT.md"
    md_path.write_text(md, encoding="utf-8")
    (_REPORT_DIR / f"experimental_threshold_report_{stamp}.md").write_text(
        md, encoding="utf-8"
    )
    return {
        "json": str(latest),
        "markdown": str(md_path),
        "stamped_json": str(stamped),
    }


def report_to_markdown(report: dict[str, Any]) -> str:
    exp = (report.get("comparison") or {}).get("experimental") or {}
    base = (report.get("comparison") or {}).get("baseline_80_80") or {}
    detail = report.get("recommendation_detail") or {}
    lines = [
        "# EXPERIMENTAL_THRESHOLD_REPORT",
        "",
        f"- Generated: `{report.get('generated_at')}`",
        f"- Profile: `{report.get('profile_id')}`",
        f"- Evaluations: **{report.get('evaluations')}** / {report.get('eval_target')}",
        f"- DEFAULT_ITE_CONFIG unchanged: **{report.get('default_ite_config_unchanged')}**",
        f"- Auto-promoted: **{detail.get('auto_promoted', False)}**",
        "",
        "## Comparison vs 80/80",
        "",
        "| Metric | Experimental 75/75 | Baseline 80/80 |",
        "|---|---:|---:|",
        f"| Signals generated | {exp.get('signals_generated')} | {base.get('signals_generated')} |",
        f"| Trades executed | {exp.get('trades_executed')} | {base.get('trades_executed')} |",
        f"| Win rate | {exp.get('win_rate')} | {base.get('win_rate')} |",
        f"| Profit factor | {exp.get('profit_factor')} | {base.get('profit_factor')} |",
        f"| Expectancy | {exp.get('expectancy')} | {base.get('expectancy')} |",
        f"| Drawdown % | {exp.get('drawdown_pct')} | {base.get('drawdown_pct')} |",
        f"| Average RR | {exp.get('average_rr')} | {base.get('average_rr')} |",
        "",
        "## Decision inputs",
        "",
        f"- Execution increased: **{report.get('execution_increased')}**",
        f"- Performance improved: **{report.get('performance_improved')}**",
        "",
        "## Recommendation",
        "",
        f"**{report.get('recommendation')}**",
        "",
        detail.get("summary") or "",
        "",
        "Operator approval is still required. This report never auto-promotes.",
        "",
    ]
    return "\n".join(lines)


def observe_experimental_cycle(cycle: dict[str, Any]) -> None:
    """Record one eligible live evaluation while EXPERIMENTAL_75 is active."""
    store = get_experimental_threshold_store()
    with store._lock:
        if not store.active:
            return
        if store.report_generated and store.evaluations >= EVAL_TARGET:
            return
        if not _is_eligible_cycle(cycle):
            return

        quality = cycle.get("quality") if isinstance(cycle.get("quality"), dict) else {}
        confluence = (
            cycle.get("confluence") if isinstance(cycle.get("confluence"), dict) else {}
        )
        q = int(quality.get("score") or 0)
        c = int(confluence.get("total") or 0)
        action = str(cycle.get("decision_action") or "").upper()
        trade_action = action in {"BUY", "SELL"}
        executed = bool(cycle.get("executed"))
        rejected = bool(cycle.get("rejected")) or action in {"NO_TRADE", "WATCH", ""}

        # Experimental path (live gates are 75/75 while active)
        experimental_signal = trade_action and q >= EXPERIMENTAL_QUALITY and c >= EXPERIMENTAL_CONFLUENCE
        # Shadow Institutional 80/80
        baseline_signal = trade_action and q >= PRODUCTION_QUALITY and c >= PRODUCTION_CONFLUENCE
        baseline_reject_reason = None
        if not baseline_signal:
            if q < PRODUCTION_QUALITY or c < PRODUCTION_CONFLUENCE:
                baseline_reject_reason = (
                    f"below_baseline_gates q={q} c={c} need "
                    f"{PRODUCTION_QUALITY}/{PRODUCTION_CONFLUENCE}"
                )
            else:
                baseline_reject_reason = f"action={action or 'none'}"

        rejection_reason = None
        if rejected or not experimental_signal:
            reasons = cycle.get("rejection_reasons") or cycle.get("reasons") or []
            if isinstance(reasons, list) and reasons:
                rejection_reason = "; ".join(str(r) for r in reasons[:5])
            elif q < EXPERIMENTAL_QUALITY or c < EXPERIMENTAL_CONFLUENCE:
                rejection_reason = f"below_experimental_gates q={q} c={c}"
            else:
                rejection_reason = f"action={action or 'none'}"

        sample = {
            "recorded_at": cycle.get("recorded_at") or datetime.now(UTC).isoformat(),
            "quality": q,
            "confluence": c,
            "decision_action": action,
            "experimental_signal": experimental_signal,
            "baseline_signal": baseline_signal,
            "baseline_would_execute": bool(baseline_signal and executed),
            "baseline_reject_reason": baseline_reject_reason,
            "executed": bool(executed and experimental_signal),
            "rejected": not experimental_signal,
            "rejection_reason": rejection_reason,
        }
        for key in ("win", "r_multiple", "net_pnl"):
            if key in cycle:
                sample[key] = cycle[key]

        store._samples.append(sample)
        store.evaluations += 1
        should_report = (
            store.evaluations >= EVAL_TARGET and not store.report_generated
        )

    if should_report:
        report = generate_experimental_threshold_report(store)
        paths = _write_report_files(report)
        report["paths"] = paths
        with store._lock:
            store.report_generated = True
            store.last_report = report
            store._append_audit(
                {
                    "id": str(uuid4()),
                    "utc_timestamp": datetime.now(UTC).isoformat(),
                    "action": "experimental_threshold_report_generated",
                    "profile_id": PROFILE_ID,
                    "evaluations": store.evaluations,
                    "recommendation": report.get("recommendation"),
                    "auto_promoted": False,
                    "paths": paths,
                }
            )
        _persist(store)


def status_payload() -> dict[str, Any]:
    """Operations status for Experimental Threshold Profile."""
    store = get_experimental_threshold_store()
    # Keep runtime aligned when experimental is active
    if store.active:
        apply_overlay_to_runtime(store.active_overlay())
        _assert_default_frozen()

    with store._lock:
        samples = list(store._samples)
        monitoring = {
            "evaluations": store.evaluations,
            "eval_target": EVAL_TARGET,
            "remaining": max(0, EVAL_TARGET - store.evaluations),
            "report_generated": store.report_generated,
            "experimental": _metrics_from_samples(
                [_experimental_view(s) for s in samples],
                label="EXPERIMENTAL_75",
            ),
            "baseline_shadow_80_80": _metrics_from_samples(
                [_baseline_shadow_view(s) for s in samples],
                label="Baseline 80/80",
            ),
        }
        return {
            "schema_version": "1.0.0",
            "profile_id": PROFILE_ID,
            "badge": BADGE_LABEL if store.active else None,
            "badge_visible": store.active,
            "active": store.active,
            "experimental_gates": {
                "quality": EXPERIMENTAL_QUALITY,
                "confluence": EXPERIMENTAL_CONFLUENCE,
            },
            "institutional_default": {
                "quality": PRODUCTION_QUALITY,
                "confluence": PRODUCTION_CONFLUENCE,
                "frozen": True,
                "default_ite_config_quality": DEFAULT_ITE_CONFIG.min_trade_quality_score,
                "default_ite_config_confluence": DEFAULT_ITE_CONFIG.min_confluence_score,
            },
            "config_version": store.config_version,
            "activated_at": store.activated_at,
            "activated_by": store.activated_by,
            "monitoring": monitoring,
            "last_activation": store.last_activation,
            "last_rollback": store.last_rollback,
            "last_report": store.last_report,
            "audit_trail": list(reversed(store.audit_trail[-25:])),
            "never_auto_promotes": True,
            "never_modifies_risk_safety_oms": True,
            "never_modifies_default_ite_config": True,
            "one_click_rollback_to": "Q80/C80",
        }
