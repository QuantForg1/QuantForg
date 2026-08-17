"""Phase D control plane — evidence-gated promotion governance only."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from app.domain.institutional_trading.phase_d.approval import ApprovalStore
from app.domain.institutional_trading.phase_d.canary import (
    CanaryState,
    CanaryStore,
    evaluate_canary_risk,
)
from app.domain.institutional_trading.phase_d.candidate import AlphaCandidateStore
from app.domain.institutional_trading.phase_d.champion_candidate import (
    compare_champion_candidate,
)
from app.domain.institutional_trading.phase_d.change_isolation import (
    validate_change_isolation,
)
from app.domain.institutional_trading.phase_d.config import (
    DEFAULT_PHASE_D_CONFIG,
    PhaseDConfig,
    phase_d_config_from_settings,
)
from app.domain.institutional_trading.phase_d.execution_quality import (
    evaluate_execution_quality,
)
from app.domain.institutional_trading.phase_d.isolation import (
    assert_candidate_cannot_execute,
)
from app.domain.institutional_trading.phase_d.live_comparison import live_ab_state
from app.domain.institutional_trading.phase_d.promotion_gates import (
    evaluate_promotion_gates,
)
from app.domain.institutional_trading.phase_d.rollback import evaluate_rollback_triggers
from app.domain.institutional_trading.phase_d.sample_governance import classify_sample
from app.domain.institutional_trading.phase_d.small_account import evaluate_small_account


@dataclass
class PhaseDControlPlane:
    config: PhaseDConfig = field(default_factory=lambda: DEFAULT_PHASE_D_CONFIG)
    candidates: AlphaCandidateStore = field(default_factory=AlphaCandidateStore)
    canary: CanaryStore = field(default_factory=CanaryStore)
    approvals: ApprovalStore = field(default_factory=ApprovalStore)
    last_gates: dict[str, Any] | None = None
    last_sample: dict[str, Any] | None = None
    last_comparison: dict[str, Any] | None = None
    last_canary_risk: dict[str, Any] | None = None
    last_execution_gate: dict[str, Any] | None = None
    last_small_account: dict[str, Any] | None = None
    last_rollback: dict[str, Any] | None = None
    last_live_ab: dict[str, Any] | None = None
    champion_version: str = "production"
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def __post_init__(self) -> None:
        self.canary.auto_promote_to_live = False
        assert_candidate_cannot_execute(may_execute=self.config.candidate_may_execute)

    def apply_config(self, config: PhaseDConfig) -> None:
        self.config = PhaseDConfig(
            alpha_governance_enabled=config.alpha_governance_enabled,
            promotion_gates_enabled=config.promotion_gates_enabled,
            sample_governance_enabled=config.sample_governance_enabled,
            canary_enabled=config.canary_enabled,
            rollback_enabled=config.rollback_enabled,
            execution_quality_gate_enabled=config.execution_quality_gate_enabled,
            small_account_gate_enabled=config.small_account_gate_enabled,
            candidate_may_execute=False,
            auto_promote_to_live=False,
            auto_degraded_to_shadow=False,
            auto_critical_drift_block_new_entries=False,
            min_total_trades=config.min_total_trades,
            min_oos_trades=config.min_oos_trades,
            min_shadow_trades=config.min_shadow_trades,
            min_live_matched=config.min_live_matched,
            canary_max_symbols=config.canary_max_symbols,
            canary_max_duration_hours=config.canary_max_duration_hours,
            canary_max_exposure_pct=config.canary_max_exposure_pct,
            small_account_equity_floor=config.small_account_equity_floor,
        )
        self.__post_init__()

    def register_candidate(self, **kwargs: Any) -> dict[str, Any]:
        assert_candidate_cannot_execute()
        change = validate_change_isolation(dict(kwargs.get("change_isolation") or {}))
        cand = self.candidates.register(**kwargs)
        if not change["ok"] and cand.status == "PROMOTABLE":
            cand.status = "NOT_PROMOTABLE"
            cand.why_blocked = "change_isolation: " + str(change.get("why_blocked"))
            cand.missing_fields = cand.missing_fields + ("change_isolation",)
        return cand.to_dict()

    def evaluate_candidate(self, candidate_id: str, **sample_kwargs: Any) -> dict[str, Any]:
        cand = self.candidates.get(candidate_id)
        if cand is None:
            return {"result": "PROMOTION_BLOCKED", "why_blocked": "unknown_candidate"}
        sample = classify_sample(
            min_total=self.config.min_total_trades,
            min_oos=self.config.min_oos_trades,
            min_shadow=self.config.min_shadow_trades,
            min_live_matched=self.config.min_live_matched,
            **sample_kwargs,
        )
        self.last_sample = sample
        gates = evaluate_promotion_gates(cand)
        self.last_gates = gates
        if not sample["promotable_by_sample"]:
            return {
                "result": "PROMOTION_BLOCKED",
                "why_blocked": "INSUFFICIENT_SAMPLE",
                "sample": sample,
                "gates": gates,
                "auto_promoted": False,
            }
        return {**gates, "sample": sample}

    def compare(self, **kwargs: Any) -> dict[str, Any]:
        self.last_comparison = compare_champion_candidate(**kwargs)
        return self.last_comparison

    def canary_risk(self, **kwargs: Any) -> dict[str, Any]:
        self.last_canary_risk = evaluate_canary_risk(**kwargs)
        return self.last_canary_risk

    def execution_gate(self, **kwargs: Any) -> dict[str, Any]:
        self.last_execution_gate = evaluate_execution_quality(**kwargs)
        return self.last_execution_gate

    def small_account(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("equity_floor", self.config.small_account_equity_floor)
        self.last_small_account = evaluate_small_account(**kwargs)
        return self.last_small_account

    def request_promotion(
        self, *, candidate_id: str, request_id: str, **sample_kwargs: Any
    ) -> dict[str, Any]:
        """Idempotent promotion request — never auto LIVE."""
        if not self.candidates.claim_promotion_request(request_id):
            return {
                "result": "DUPLICATE_PROMOTION_REQUEST",
                "why_blocked": "replay_or_duplicate",
                "auto_promoted": False,
            }
        cand = self.candidates.get(candidate_id)
        if cand is not None and "total_trades" not in sample_kwargs:
            n = int((cand.research_evidence or {}).get("sample_size") or 0)
            sample_kwargs.setdefault("total_trades", n)
            sample_kwargs.setdefault("oos_trades", n)
            sample_kwargs.setdefault("shadow_trades", n)
            sample_kwargs.setdefault("live_matched", n)
            sample_kwargs.setdefault("regime_coverage", 1 if n else 0)
            sample_kwargs.setdefault("symbol_coverage", len(cand.symbols) or (1 if n else 0))
            sample_kwargs.setdefault("session_coverage", 1 if n else 0)
        eval_result = self.evaluate_candidate(candidate_id, **sample_kwargs)
        if eval_result.get("result") != "GATES_PASSED":
            return eval_result
        rec = self.canary.start(
            candidate_id=candidate_id,
            symbols=list(cand.symbols) if cand else None,
            max_exposure_pct=self.config.canary_max_exposure_pct,
            max_duration_hours=self.config.canary_max_duration_hours,
        )
        self.canary.transition(candidate_id, CanaryState.PROMOTION_REVIEW)
        return {
            "result": "PROMOTION_REVIEW",
            "canary": rec.to_dict(),
            "auto_promoted": False,
            "execution_authority": False,
        }

    def approve_live(self, **kwargs: Any) -> dict[str, Any]:
        """Explicit human approval only — does not enable OMS for candidate."""
        assert_candidate_cannot_execute()
        approval = self.approvals.approve(**kwargs)
        cid = approval.candidate_id
        if cid in self.canary.records:
            # Must be in CANARY_REVIEW for LIVE_APPROVED
            rec = self.canary.records[cid]
            if rec.state is CanaryState.PROMOTION_REVIEW:
                self.canary.transition(cid, CanaryState.CANARY_APPROVED, actor=approval.approval_actor)
                self.canary.transition(cid, CanaryState.CANARY, actor=approval.approval_actor)
                self.canary.transition(cid, CanaryState.CANARY_REVIEW, actor=approval.approval_actor)
            elif rec.state is CanaryState.CANARY_APPROVED:
                self.canary.transition(cid, CanaryState.CANARY, actor=approval.approval_actor)
                self.canary.transition(cid, CanaryState.CANARY_REVIEW, actor=approval.approval_actor)
            elif rec.state is CanaryState.CANARY:
                self.canary.transition(cid, CanaryState.CANARY_REVIEW, actor=approval.approval_actor)
            if self.canary.records[cid].state is CanaryState.CANARY_REVIEW:
                self.canary.transition(
                    cid,
                    CanaryState.LIVE_APPROVED,
                    actor=approval.approval_actor,
                    why_promoted=approval.promotion_reason,
                )
        return {
            "approval": approval.to_dict(),
            "execution_authority": False,
            "note": (
                "APPROVED_FOR_LIVE is a governance record only; "
                "candidate still cannot call OMS until authorized production deploy"
            ),
            "auto_promoted": False,
        }

    def evaluate_rollback(self, **kwargs: Any) -> dict[str, Any]:
        candidate_id = kwargs.pop("candidate_id", None)
        self.last_rollback = evaluate_rollback_triggers(**kwargs)
        if (
            self.last_rollback.get("action") == "ROLLBACK"
            and candidate_id
            and str(candidate_id) in self.canary.records
        ):
            self.canary.transition(
                str(candidate_id),
                CanaryState.SHADOW_ONLY,
                note="automatic_rollback_governance",
                why_rolled_back=self.last_rollback.get("why_rolled_back"),
            )
        return self.last_rollback

    def live_ab(self, **kwargs: Any) -> dict[str, Any]:
        self.last_live_ab = live_ab_state(**kwargs)
        return self.last_live_ab

    def snapshot(self) -> dict[str, Any]:
        # Soft enrich from Phase C — failure must not affect LIVE
        phase_c = None
        try:
            from app.domain.institutional_trading.phase_c import get_phase_c_plane

            phase_c = get_phase_c_plane().snapshot()
        except Exception:
            phase_c = None
        return {
            "phase": "D",
            "mode": "EVIDENCE_GATED_PROMOTION",
            "live_decision_authority": False,
            "candidate_execution_authority": False,
            "auto_promote_to_live": False,
            "config": self.config.to_dict(),
            "champion": {"version": self.champion_version},
            "candidates": self.candidates.snapshot(),
            "gates": self.last_gates,
            "sample": self.last_sample,
            "comparison": self.last_comparison,
            "canary": self.canary.snapshot(),
            "canary_risk": self.last_canary_risk,
            "execution_quality": self.last_execution_gate,
            "small_account": self.last_small_account,
            "rollback": self.last_rollback,
            "approvals": self.approvals.snapshot(),
            "live_ab": self.last_live_ab,
            "phase_c_link": {
                "present": phase_c is not None,
                "challenger_execution_authority": (
                    (phase_c or {}).get("challenger_execution_authority") is True
                ),
            },
            "drift_auto_actions_enabled": False,
        }


_PLANE: PhaseDControlPlane | None = None
_PLANE_LOCK = threading.Lock()


def get_phase_d_plane(*, refresh_config: bool = False) -> PhaseDControlPlane:
    global _PLANE
    with _PLANE_LOCK:
        if _PLANE is None:
            _PLANE = PhaseDControlPlane(config=phase_d_config_from_settings())
        elif refresh_config:
            _PLANE.apply_config(phase_d_config_from_settings())
        return _PLANE


def reset_phase_d_plane_for_tests() -> PhaseDControlPlane:
    global _PLANE
    with _PLANE_LOCK:
        _PLANE = PhaseDControlPlane(config=DEFAULT_PHASE_D_CONFIG)
        return _PLANE
