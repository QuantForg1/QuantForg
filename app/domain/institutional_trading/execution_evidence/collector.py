"""Build execution evidence from real PVM attempts — observe-only."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from app.domain.institutional_trading.execution_evidence.models import (
    EXECUTION_TIMELINE,
    ExecutionEvidencePackage,
    TimelineStage,
    timeline_source_stages,
)
from app.domain.institutional_trading.production_validation_mode.models import (
    StageStatus,
    ValidationAttempt,
    ValidationStage,
)
from core.logging import get_logger

logger = get_logger(__name__)

_SECRET_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "auth",
        "bearer",
        "private_key",
        "access_key",
        "refresh_token",
        "mt5_password",
        "login_password",
    }
)


def _redact_for_hash(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k).lower()
            secretish = ("password", "secret", "token")
            if key in _SECRET_KEYS or any(s in key for s in secretish):
                out[str(k)] = "[redacted]"
            else:
                out[str(k)] = _redact_for_hash(v)
        return out
    if isinstance(value, list):
        return [_redact_for_hash(v) for v in value]
    return value


def _safe_redacted_dict(value: dict[str, Any] | None) -> dict[str, Any]:
    redacted = _redact_for_hash(value or {})
    return redacted if isinstance(redacted, dict) else {}


def payload_hash(payload: dict[str, Any] | None) -> str | None:
    """Stable SHA-256 of redacted OMS payload — never stores raw secrets."""
    if not payload:
        return None
    try:
        canonical = json.dumps(
            _redact_for_hash(payload),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    except Exception:
        logger.exception("execution_evidence_payload_hash_failed")
        return None


def _git_commit() -> str | None:
    for key in (
        "RAILWAY_GIT_COMMIT_SHA",
        "COMMIT_SHA",
        "GITHUB_SHA",
        "VERCEL_GIT_COMMIT_SHA",
        "GIT_COMMIT",
    ):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    # Prefer deploy env vars only — avoid spawning git on the hot path.
    return None


def _deployment_id() -> str | None:
    for key in (
        "RAILWAY_DEPLOYMENT_ID",
        "RAILWAY_SNAPSHOT_ID",
        "DEPLOYMENT_ID",
        "VERCEL_DEPLOYMENT_ID",
    ):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return None


def _environment() -> str | None:
    for key in ("QUANTFORG_ENV", "APP_ENV", "ENVIRONMENT", "RAILWAY_ENVIRONMENT"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    try:
        from core.config.settings import get_settings

        settings = get_settings()
        env = getattr(settings, "environment", None) or getattr(
            settings, "app_env", None
        )
        return str(env) if env else None
    except Exception:
        return None


def _stage_status(attempt: ValidationAttempt, label: str) -> TimelineStage:
    sources = timeline_source_stages(label)
    best: TimelineStage | None = None
    for key in sources:
        rec = attempt.stages.get(key)
        if rec is None:
            continue
        if isinstance(rec.status, StageStatus):
            status = rec.status.value
        else:
            status = str(rec.status)
        candidate = TimelineStage(
            stage=label,
            status=status,
            latency_ms=rec.latency_ms,
            reason=rec.reason or "",
            timestamp=rec.timestamp,
        )
        if status == StageStatus.FAIL.value:
            return candidate
        if best is None or status == StageStatus.PASS.value:
            best = candidate
    return best or TimelineStage(stage=label, status=StageStatus.PENDING.value)


def _pass(attempt: ValidationAttempt, stage: ValidationStage) -> bool:
    rec = attempt.stages.get(stage.value)
    return rec is not None and rec.status is StageStatus.PASS


def is_eligible_execution(attempt: ValidationAttempt) -> bool:
    """Eligible = real BUY/SELL with broker ticket > 0. Never fabricated."""
    action = (attempt.ai_action or "").upper()
    if action not in {"BUY", "SELL"}:
        return False
    ticket = attempt.mt5.ticket if attempt.mt5 else None
    if ticket is None:
        return False
    try:
        return int(ticket) > 0
    except (TypeError, ValueError):
        return False


def _certificate_eligible(
    attempt: ValidationAttempt, package: ExecutionEvidencePackage
) -> bool:
    if not is_eligible_execution(attempt):
        return False
    if not attempt.accepted:
        return False
    required = (
        ValidationStage.OMS,
        ValidationStage.GATEWAY,
        ValidationStage.MT5,
        ValidationStage.BROKER,
    )
    if not all(_pass(attempt, s) for s in required):
        return False
    return not (package.mt5_ticket is None or int(package.mt5_ticket) <= 0)


def _extract_volume(
    oms_payload: dict[str, Any], broker: dict[str, Any]
) -> str | None:
    for key in ("volume", "lots", "qty", "quantity", "size"):
        if oms_payload.get(key) is not None:
            return str(oms_payload[key])
        if broker.get(key) is not None:
            return str(broker[key])
    return None


def _extract_sl_tp(
    oms_payload: dict[str, Any], broker: dict[str, Any]
) -> tuple[str | None, str | None]:
    sl = oms_payload.get("sl") or oms_payload.get("stop_loss") or broker.get("sl")
    tp = (
        oms_payload.get("tp")
        or oms_payload.get("take_profit")
        or broker.get("tp")
    )
    return (
        str(sl) if sl is not None else None,
        str(tp) if tp is not None else None,
    )


def _gateway_request_id(
    gateway_req: dict[str, Any], gateway_resp: dict[str, Any]
) -> str | None:
    keys = ("request_id", "requestId", "id", "correlation_id", "x_request_id")
    for src in (gateway_resp, gateway_req):
        for key in keys:
            if src.get(key) is not None:
                return str(src[key])
    return None


def _sample_system() -> tuple[float | None, float | None]:
    """Best-effort host metrics; null when unavailable — never invent."""
    try:
        import psutil  # type: ignore[import-untyped]

        cpu = float(psutil.cpu_percent(interval=None))
        mem = float(psutil.virtual_memory().percent)
        return cpu, mem
    except Exception:
        return None, None


def _enrich_trade_from_journals(
    package: ExecutionEvidencePackage,
) -> None:
    """Attach real close/PnL fields when journal exposes them for this ticket."""
    if package.mt5_ticket is None:
        return
    try:
        from app.application.services.institutional_ite_runtime import get_ite_runtime

        runtime = get_ite_runtime()
        if runtime is None:
            return
        journal = getattr(getattr(runtime, "execution", None), "bridge", None)
        journal = getattr(journal, "journal", None)
        if journal is None:
            return
        recent: list[Any] = []
        if hasattr(journal, "recent"):
            recent = list(journal.recent(limit=100) or [])
        elif hasattr(journal, "entries"):
            recent = list(getattr(journal, "entries", []) or [])
        ticket = int(package.mt5_ticket)
        for entry in recent:
            d = (
                entry.to_dict()
                if hasattr(entry, "to_dict")
                else (entry if isinstance(entry, dict) else {})
            )
            if not d:
                continue
            jt = d.get("mt5_ticket") or d.get("ticket")
            try:
                if jt is None or int(jt) != ticket:
                    continue
            except (TypeError, ValueError):
                continue
            # Only fill from real journal fields — never invent PnL
            if d.get("fill_price") is not None and package.entry is None:
                package.entry = str(d.get("fill_price"))
            if d.get("exit_price") is not None:
                package.exit = str(d.get("exit_price"))
            if d.get("gross_pnl") is not None:
                package.gross_pnl = str(d.get("gross_pnl"))
            if d.get("net_pnl") is not None or d.get("profit") is not None:
                package.net_pnl = str(d.get("net_pnl") or d.get("profit"))
            if d.get("swap") is not None:
                package.swap = str(d.get("swap"))
            if d.get("commission") is not None:
                package.commission = str(d.get("commission"))
            if d.get("duration") is not None or d.get("duration_sec") is not None:
                package.duration = str(d.get("duration") or d.get("duration_sec"))
            if d.get("slippage") is not None and package.slippage is None:
                package.slippage = str(d.get("slippage"))
            break
    except Exception:
        logger.exception("execution_evidence_journal_enrich_failed")


def build_evidence_from_attempt(
    attempt: ValidationAttempt,
    *,
    environment: str | None = None,
    commit_sha: str | None = None,
    deployment_id: str | None = None,
) -> ExecutionEvidencePackage | None:
    """Return evidence package only for eligible real BUY/SELL with ticket."""
    if not is_eligible_execution(attempt):
        return None

    oms_payload = dict(attempt.oms.payload) if attempt.oms else {}
    oms_response = dict(attempt.oms.response) if attempt.oms else {}
    gw_req = dict(attempt.gateway.request) if attempt.gateway else {}
    gw_resp = dict(attempt.gateway.response) if attempt.gateway else {}
    broker = dict(attempt.mt5.broker_response) if attempt.mt5 else {}

    sl, tp = _extract_sl_tp(oms_payload, broker)
    volume = _extract_volume(oms_payload, broker)
    fill = attempt.mt5.fill_price if attempt.mt5 else None
    cpu, mem = _sample_system()

    eligibility_rec = attempt.stages.get(ValidationStage.ELIGIBILITY.value)
    eligibility_result = None
    if eligibility_rec is not None:
        eligibility_result = eligibility_rec.status.value
        if eligibility_rec.reason:
            eligibility_result = f"{eligibility_result}: {eligibility_rec.reason}"

    oms_ts = None
    oms_stage = attempt.stages.get(ValidationStage.OMS.value)
    if oms_stage is not None:
        oms_ts = oms_stage.timestamp

    package = ExecutionEvidencePackage(
        validation_id=attempt.validation_id,
        signal_id=attempt.signal_id,
        timestamp=attempt.timestamp,
        environment=environment if environment is not None else _environment(),
        commit_sha=commit_sha if commit_sha is not None else _git_commit(),
        deployment_id=deployment_id if deployment_id is not None else _deployment_id(),
        decision=attempt.ai_action,
        quality_score=attempt.quality_score,
        confidence=attempt.ai_confidence,
        reasons=list(attempt.no_trade_reasons),
        session=attempt.market_session or None,
        symbol=attempt.symbol or None,
        risk_score=attempt.risk_score,
        rr=attempt.expected_rr,
        position_size=volume,
        eligibility_result=eligibility_result,
        oms_submit_timestamp=oms_ts,
        oms_payload_hash=payload_hash(oms_payload),
        oms_response=_safe_redacted_dict(oms_response),
        oms_latency_ms=attempt.oms.latency_ms if attempt.oms else None,
        gateway_request_id=_gateway_request_id(gw_req, gw_resp),
        gateway_http_status=attempt.gateway.http_code if attempt.gateway else None,
        order_send_latency_ms=(
            attempt.gateway.order_send_latency_ms if attempt.gateway else None
        ),
        gateway_latency_ms=(
            attempt.gateway.gateway_latency_ms if attempt.gateway else None
        ),
        mt5_ticket=attempt.mt5.ticket if attempt.mt5 else None,
        mt5_retcode=attempt.mt5.retcode if attempt.mt5 else None,
        mt5_comment=attempt.mt5.comment if attempt.mt5 else None,
        fill_price=fill,
        volume=volume,
        broker_execution_status=(
            "PASS"
            if _pass(attempt, ValidationStage.BROKER)
            else (
                attempt.stages.get(ValidationStage.BROKER.value).status.value
                if attempt.stages.get(ValidationStage.BROKER.value)
                else None
            )
        ),
        slippage=attempt.mt5.slippage if attempt.mt5 else None,
        final_fill=fill,
        entry=fill,
        stop_loss=sl,
        take_profit=tp,
        cpu=cpu,
        memory=mem,
        system_gateway_latency_ms=(
            attempt.gateway.gateway_latency_ms if attempt.gateway else None
        ),
        system_oms_latency_ms=attempt.oms.latency_ms if attempt.oms else None,
        timeline=[_stage_status(attempt, label) for label in EXECUTION_TIMELINE],
        final_result=attempt.final_result,
        accepted=bool(attempt.accepted),
    )
    package.certificate_eligible = _certificate_eligible(attempt, package)
    _enrich_trade_from_journals(package)
    # Prefer stage AI reason when decision reasons are empty.
    if not package.reasons and attempt.ai_action:
        # Capture stage reason from AI if present
        ai_rec = attempt.stages.get(ValidationStage.AI.value)
        if ai_rec and ai_rec.reason:
            package.reasons = [ai_rec.reason]
    return package


def collect_after_finalize(
    attempt: ValidationAttempt,
    *,
    export_dir: Any = None,
    certificate_dir: Any = None,
) -> dict[str, Any] | None:
    """Observe-only side effect after PVM finalize. Swallows errors via caller."""
    from app.domain.institutional_trading.execution_evidence.export import (
        export_evidence_package,
    )

    package = build_evidence_from_attempt(attempt)
    if package is None:
        return None
    paths = export_evidence_package(
        package,
        export_dir=export_dir,
        certificate_dir=certificate_dir,
    )
    return {
        "validation_id": package.validation_id,
        "ticket": package.mt5_ticket,
        "certificate_eligible": package.certificate_eligible,
        "paths": paths,
        "observe_only": True,
    }
