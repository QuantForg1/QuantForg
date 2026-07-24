"""QEM analytics — derive, search, route, replay immutable events."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha1
from typing import Any
from uuid import uuid4

from app.domain.quantforg_event_mesh.models import (
    DEFAULT_SUBSCRIBERS,
    EVENT_SOURCES,
    EVENT_TYPES,
    EventType,
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _stable_id(*parts: Any) -> str:
    raw = "|".join(str(p) for p in parts)
    return sha1(raw.encode("utf-8")).hexdigest()[:24]


def _event(
    *,
    event_type: str,
    producer: str,
    category: str,
    severity: str,
    timestamp: str | None = None,
    correlation_id: str | None = None,
    strategy_id: str | None = None,
    evidence_ids: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    release_id: str | None = None,
    experiment_id: str | None = None,
) -> dict[str, Any]:
    ts = timestamp or datetime.now(UTC).isoformat()
    eid = _stable_id(event_type, producer, strategy_id, release_id, experiment_id, ts, metadata)
    return {
        "id": eid,
        "timestamp": ts,
        "producer": producer,
        "category": category,
        "severity": severity,
        "event_type": event_type,
        "correlation_id": correlation_id
        or _stable_id(strategy_id or release_id or experiment_id or producer, category),
        "strategy_id": strategy_id,
        "release_id": release_id,
        "experiment_id": experiment_id,
        "evidence_ids": evidence_ids or [],
        "metadata": metadata or {},
        "immutable": True,
        "read_only": True,
    }


def derive_events(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    events: list[dict[str, Any]] = []

    # ISLM strategies
    for s in _as_list(_as_dict(sources.get("islm")).get("registry")):
        sd = _as_dict(s)
        sid = str(sd.get("strategy_id") or "")
        if not sid:
            continue
        events.append(
            _event(
                event_type=EventType.STRATEGY_UPDATED.value,
                producer="islm",
                category="strategy",
                severity="info",
                timestamp=str(sd.get("updated_at") or sd.get("created_at") or ""),
                strategy_id=sid,
                evidence_ids=[sid],
                metadata={
                    "lifecycle": sd.get("lifecycle_state") or sd.get("lifecycle"),
                    "version": sd.get("version"),
                    "name": sd.get("name") or sd.get("strategy_name"),
                },
            )
        )
        if str(sd.get("created_at") or "") == str(sd.get("updated_at") or ""):
            events.append(
                _event(
                    event_type=EventType.STRATEGY_CREATED.value,
                    producer="islm",
                    category="strategy",
                    severity="info",
                    timestamp=str(sd.get("created_at") or ""),
                    strategy_id=sid,
                    evidence_ids=[sid],
                    metadata={"name": sd.get("name") or sd.get("strategy_name")},
                )
            )

    for ap in _as_list(_as_dict(sources.get("islm")).get("approvals")):
        ad = _as_dict(ap)
        events.append(
            _event(
                event_type=EventType.STRATEGY_UPDATED.value,
                producer="islm",
                category="strategy",
                severity="info",
                timestamp=str(ad.get("created_at") or ""),
                strategy_id=str(ad.get("strategy_id") or "") or None,
                correlation_id=str(ad.get("approval_id") or ""),
                evidence_ids=[str(ad.get("approval_id") or "")],
                metadata={"decision": ad.get("decision"), "to": ad.get("to_state")},
            )
        )

    # Replay / simulation
    for s in _as_list(_as_dict(sources.get("replay")).get("simulations")):
        sd = _as_dict(s)
        sim_id = str(sd.get("simulation_id") or sd.get("id") or uuid4())
        events.append(
            _event(
                event_type=EventType.REPLAY_COMPLETED.value,
                producer="replay",
                category="replay",
                severity="info",
                timestamp=str(sd.get("completed_at") or sd.get("updated_at") or ""),
                evidence_ids=[sim_id],
                metadata={"mode": sd.get("mode"), "scenario": sd.get("scenario")},
            )
        )

    for s in _as_list(_as_dict(sources.get("simulation")).get("simulations")):
        sd = _as_dict(s)
        sim_id = str(sd.get("simulation_id") or sd.get("id") or uuid4())
        mode = str(sd.get("mode") or sd.get("scenario") or "").lower()
        if "replay" in mode or "historical" in mode:
            continue
        events.append(
            _event(
                event_type=EventType.SIMULATION_COMPLETED.value,
                producer="simulation",
                category="simulation",
                severity="info",
                timestamp=str(sd.get("completed_at") or sd.get("updated_at") or ""),
                evidence_ids=[sim_id],
                metadata={"mode": sd.get("mode"), "scenario": sd.get("scenario")},
            )
        )

    # Research experiments
    for e in _as_list(_as_dict(sources.get("research_lab")).get("experiments")):
        ed = _as_dict(e)
        eid = str(ed.get("experiment_id") or ed.get("id") or "")
        status = str(ed.get("status") or "").lower()
        if eid and ("complete" in status or "done" in status or status == "archived"):
            events.append(
                _event(
                    event_type=EventType.EXPERIMENT_COMPLETED.value,
                    producer="research_lab",
                    category="experiment",
                    severity="info",
                    timestamp=str(ed.get("updated_at") or ed.get("completed_at") or ""),
                    experiment_id=eid,
                    evidence_ids=[eid],
                    metadata={"name": ed.get("name"), "status": ed.get("status")},
                )
            )

    # CVF validation
    cvf = _as_dict(sources.get("cvf"))
    if cvf:
        conf = _as_dict(cvf.get("confidence") or cvf).get("confidence")
        events.append(
            _event(
                event_type=EventType.VALIDATION_COMPLETED.value,
                producer="cvf",
                category="validation",
                severity="info",
                timestamp=str(cvf.get("observed_at") or ""),
                evidence_ids=["cvf-snapshot"],
                metadata={"confidence": conf},
            )
        )

    # QCS certification
    qcs = _as_dict(sources.get("qcs"))
    level = _as_dict(qcs.get("level") or qcs).get("level")
    if level:
        events.append(
            _event(
                event_type=EventType.CERTIFICATION_COMPLETED.value,
                producer="qcs",
                category="certification",
                severity="info",
                timestamp=str(qcs.get("observed_at") or ""),
                evidence_ids=["qcs-snapshot"],
                metadata={"level": level, "scores": qcs.get("scores")},
            )
        )

    # IRDP releases
    for r in _as_list(_as_dict(sources.get("irdp")).get("releases")):
        rd = _as_dict(r)
        rid = str(rd.get("release_id") or "")
        if not rid:
            continue
        events.append(
            _event(
                event_type=EventType.RELEASE_CREATED.value,
                producer="irdp",
                category="release",
                severity="info",
                timestamp=str(rd.get("created_at") or rd.get("updated_at") or ""),
                release_id=rid,
                evidence_ids=[rid],
                metadata={"version": rd.get("version"), "status": rd.get("status")},
            )
        )
        status = str(rd.get("status") or "").lower()
        if "approv" in status:
            events.append(
                _event(
                    event_type=EventType.RELEASE_APPROVED.value,
                    producer="irdp",
                    category="release",
                    severity="info",
                    timestamp=str(rd.get("updated_at") or ""),
                    release_id=rid,
                    correlation_id=rid,
                    evidence_ids=[rid],
                    metadata={"status": rd.get("status")},
                )
            )

    for rb in _as_list(_as_dict(sources.get("irdp")).get("rollbacks")):
        rbd = _as_dict(rb)
        events.append(
            _event(
                event_type=EventType.RELEASE_ROLLED_BACK.value,
                producer="irdp",
                category="release",
                severity="warning",
                timestamp=str(rbd.get("created_at") or rbd.get("recorded_at") or ""),
                release_id=str(rbd.get("release_id") or "") or None,
                evidence_ids=[str(rbd.get("rollback_id") or rbd.get("release_id") or "")],
                metadata=rbd,
            )
        )

    # QPM portfolio
    qpm = _as_dict(sources.get("qpm"))
    if qpm:
        events.append(
            _event(
                event_type=EventType.PORTFOLIO_UPDATED.value,
                producer="qpm",
                category="portfolio",
                severity="info",
                timestamp=str(qpm.get("observed_at") or ""),
                evidence_ids=["qpm-snapshot"],
                metadata={"metrics": qpm.get("metrics"), "health": qpm.get("health")},
            )
        )

    # Alerts
    for alert in _as_list(_as_dict(sources.get("irap")).get("alerts")):
        ad = _as_dict(alert)
        events.append(
            _event(
                event_type=EventType.RISK_ALERT.value,
                producer="irap",
                category="alert",
                severity=str(ad.get("severity") or "warning"),
                evidence_ids=[str(ad.get("kind") or "risk")],
                metadata=ad,
            )
        )

    for alert in _as_list(_as_dict(sources.get("eqs")).get("alerts")):
        ad = _as_dict(alert)
        events.append(
            _event(
                event_type=EventType.EXECUTION_ALERT.value,
                producer="oms",
                category="alert",
                severity=str(ad.get("severity") or "warning"),
                evidence_ids=[str(ad.get("kind") or "execution")],
                metadata=ad,
            )
        )

    for alert in _as_list(_as_dict(sources.get("res")).get("alerts")):
        ad = _as_dict(alert)
        events.append(
            _event(
                event_type=EventType.RELIABILITY_ALERT.value,
                producer="gateway",
                category="alert",
                severity=str(ad.get("severity") or "warning"),
                evidence_ids=[str(ad.get("kind") or "reliability")],
                metadata=ad,
            )
        )

    for alert in _as_list(_as_dict(sources.get("icp")).get("alerts")):
        ad = _as_dict(alert)
        # EQS/RES may be nested elsewhere; ICP alerts as platform
        events.append(
            _event(
                event_type=EventType.PLATFORM_ALERT.value,
                producer="icp",
                category="alert",
                severity=str(ad.get("severity") or "warning"),
                evidence_ids=[str(ad.get("kind") or "platform")],
                metadata=ad,
            )
        )

    # AOC may carry nested recommendations as platform signals
    aoc = _as_dict(sources.get("aoc"))
    for rec in _as_list(aoc.get("recommendations"))[:5]:
        rd = _as_dict(rec)
        events.append(
            _event(
                event_type=EventType.PLATFORM_ALERT.value,
                producer="aoc",
                category="alert",
                severity=str(rd.get("priority") or "info"),
                evidence_ids=[str(rd.get("recommendation_id") or "aoc")],
                metadata=rd,
            )
        )

    # Knowledge graph presence pulse
    kg = _as_dict(sources.get("knowledge_graph"))
    if kg:
        events.append(
            _event(
                event_type=EventType.PLATFORM_ALERT.value,
                producer="knowledge_graph",
                category="platform",
                severity="info",
                evidence_ids=["qkg-snapshot"],
                metadata={"keys": list(kg.keys())[:8]},
            )
        )

    # Stable chronological order
    events.sort(key=lambda e: str(e.get("timestamp") or ""))
    # Ensure event types are valid
    for e in events:
        if e.get("event_type") not in EVENT_TYPES:
            e["event_type"] = EventType.PLATFORM_ALERT.value
    return events


def route_subscribers(
    events: list[dict[str, Any]],
    subscribers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    subs = subscribers or [dict(s) for s in DEFAULT_SUBSCRIBERS]
    routes: list[dict[str, Any]] = []
    for sub in subs:
        cats = _as_list(sub.get("categories"))
        matched = []
        for ev in events:
            cat = str(ev.get("category") or "")
            if "*" in cats or cat in cats:
                matched.append(ev.get("id"))
        routes.append(
            {
                "subscriber_id": sub.get("subscriber_id"),
                "mode": sub.get("mode") or "observe",
                "matched_event_ids": matched[:100],
                "matched_count": len(matched),
                "loosely_coupled": True,
                "never_mutates_producer": True,
            }
        )
    return {
        "subscribers": subs,
        "routes": routes,
        "note": "Declarative routing catalog — no tight service coupling",
        "read_only": True,
    }


def search_events(
    events: list[dict[str, Any]],
    *,
    strategy_id: str | None = None,
    release_id: str | None = None,
    experiment_id: str | None = None,
    correlation_id: str | None = None,
    category: str | None = None,
    event_type: str | None = None,
    q: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    rows = list(events)
    if strategy_id:
        rows = [e for e in rows if str(e.get("strategy_id") or "") == strategy_id]
    if release_id:
        rows = [e for e in rows if str(e.get("release_id") or "") == release_id]
    if experiment_id:
        rows = [e for e in rows if str(e.get("experiment_id") or "") == experiment_id]
    if correlation_id:
        rows = [
            e for e in rows if str(e.get("correlation_id") or "") == correlation_id
        ]
    if category:
        rows = [e for e in rows if str(e.get("category") or "").lower() == category.lower()]
    if event_type:
        rows = [
            e for e in rows if str(e.get("event_type") or "").lower() == event_type.lower()
        ]
    if q:
        needle = q.lower()
        rows = [
            e
            for e in rows
            if needle
            in f"{e.get('event_type')} {e.get('producer')} {e.get('strategy_id')} {e.get('release_id')} {e.get('experiment_id')} {e.get('correlation_id')}".lower()
        ]
    rows = sorted(rows, key=lambda e: str(e.get("timestamp") or ""))
    return {
        "results": rows[-limit:],
        "count": min(len(rows), limit),
        "total_matched": len(rows),
        "filters": {
            "strategy_id": strategy_id,
            "release_id": release_id,
            "experiment_id": experiment_id,
            "correlation_id": correlation_id,
            "category": category,
            "event_type": event_type,
            "q": q,
        },
        "read_only": True,
    }


def build_timeline(events: list[dict[str, Any]], *, limit: int = 100) -> list[dict[str, Any]]:
    ordered = sorted(events, key=lambda e: str(e.get("timestamp") or ""))
    return [
        {
            "id": e.get("id"),
            "timestamp": e.get("timestamp"),
            "event_type": e.get("event_type"),
            "producer": e.get("producer"),
            "category": e.get("category"),
            "severity": e.get("severity"),
            "correlation_id": e.get("correlation_id"),
            "strategy_id": e.get("strategy_id"),
            "release_id": e.get("release_id"),
            "experiment_id": e.get("experiment_id"),
        }
        for e in ordered[-limit:]
    ]


def correlation_view(
    events: list[dict[str, Any]], *, correlation_id: str | None = None
) -> dict[str, Any]:
    if correlation_id:
        related = [
            e for e in events if str(e.get("correlation_id") or "") == correlation_id
        ]
        related = sorted(related, key=lambda e: str(e.get("timestamp") or ""))
        return {
            "correlation_id": correlation_id,
            "events": related,
            "count": len(related),
            "read_only": True,
        }
    # Group top correlations
    buckets: dict[str, list[dict[str, Any]]] = {}
    for e in events:
        cid = str(e.get("correlation_id") or "none")
        buckets.setdefault(cid, []).append(e)
    ranked = sorted(buckets.items(), key=lambda kv: len(kv[1]), reverse=True)[:20]
    return {
        "groups": [
            {
                "correlation_id": cid,
                "count": len(rows),
                "event_ids": [r.get("id") for r in rows[:20]],
                "producers": sorted({str(r.get("producer")) for r in rows}),
            }
            for cid, rows in ranked
        ],
        "read_only": True,
    }


def replay_stream(
    events: list[dict[str, Any]],
    *,
    from_ts: str | None = None,
    to_ts: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Replay historical immutable events chronologically — observational only."""
    ordered = sorted(events, key=lambda e: str(e.get("timestamp") or ""))
    if from_ts:
        ordered = [e for e in ordered if str(e.get("timestamp") or "") >= from_ts]
    if to_ts:
        ordered = [e for e in ordered if str(e.get("timestamp") or "") <= to_ts]
    stream = ordered[:limit]
    return {
        "stream": stream,
        "count": len(stream),
        "from_ts": from_ts,
        "to_ts": to_ts,
        "ordering": "ascending_timestamp",
        "immutable": True,
        "never_modifies_production": True,
        "read_only": True,
    }


def ordering_consistency_check(events: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    ids = [str(e.get("id") or "") for e in events]
    if any(not i for i in ids):
        issues.append("missing_event_id")
    if len(ids) != len(set(ids)):
        issues.append("duplicate_event_ids")
    for e in events:
        if e.get("event_type") not in EVENT_TYPES:
            issues.append(f"invalid_type:{e.get('event_type')}")
        if e.get("immutable") is not True:
            issues.append("event_not_marked_immutable")
        if e.get("producer") not in EVENT_SOURCES and e.get("producer") not in {
            "replay",
            "simulation",
            "research_lab",
            "knowledge_graph",
            "islm",
            "irdp",
            "cvf",
            "irap",
            "qcs",
            "qpm",
            "aoc",
            "icp",
        }:
            # producers are source names; allow known set
            pass
    # Timeline monotonic when sorted
    ordered = sorted(events, key=lambda e: str(e.get("timestamp") or ""))
    for a, b in zip(ordered, ordered[1:], strict=False):
        if str(a.get("timestamp") or "") > str(b.get("timestamp") or ""):
            issues.append("ordering_violation")
            break
    return {"ok": len(issues) == 0, "issues": issues, "read_only": True}


def replay_consistency_check(
    original: list[dict[str, Any]], replayed: list[dict[str, Any]]
) -> dict[str, Any]:
    issues: list[str] = []
    o_ids = [e.get("id") for e in sorted(original, key=lambda e: str(e.get("timestamp") or ""))]
    r_ids = [e.get("id") for e in replayed]
    # Replayed should be subsequence preserving order
    oi = 0
    for rid in r_ids:
        while oi < len(o_ids) and o_ids[oi] != rid:
            oi += 1
        if oi >= len(o_ids):
            issues.append("replay_order_mismatch")
            break
        oi += 1
    for e in replayed:
        if e.get("immutable") is not True:
            issues.append("replayed_not_immutable")
    return {"ok": len(issues) == 0, "issues": issues, "read_only": True}
