"""QKG builder — construct nodes and edges from read-only sources."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.quant_knowledge_graph.models import NodeType, RelationType


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _nid(prefix: str, raw: Any) -> str:
    return f"{prefix}:{raw}" if raw is not None else f"{prefix}:{uuid4()}"


def _node(
    *,
    node_id: str,
    node_type: NodeType | str,
    label: str,
    props: dict[str, Any] | None = None,
    source_subsystem: str = "unknown",
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": str(node_type),
        "label": label,
        "properties": props or {},
        "source_subsystem": source_subsystem,
    }


def _edge(
    *,
    source: str,
    target: str,
    relation: RelationType | str,
    props: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": f"e:{source}->{relation}->{target}",
        "source": source,
        "target": target,
        "relation": str(relation),
        "properties": props or {},
    }


def build_graph(ctx: dict[str, Any]) -> dict[str, Any]:
    sources = _as_dict(ctx.get("sources"))
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def add_node(n: dict[str, Any]) -> str:
        nodes[n["id"]] = n
        return n["id"]

    def add_edge(e: dict[str, Any]) -> None:
        if e["source"] in nodes and e["target"] in nodes:
            edges.append(e)

    # Strategy hub
    strategy_id = add_node(
        _node(
            node_id="strategy:production",
            node_type=NodeType.STRATEGY,
            label="Production Strategy",
            props={"role": "production"},
            source_subsystem="strategy_intelligence",
        )
    )
    sic = _as_dict(sources.get("sic"))
    for s in _as_list(sic.get("strategies") or sic.get("candidates") or [])[:15]:
        if not isinstance(s, dict):
            continue
        sid = add_node(
            _node(
                node_id=_nid("strategy", s.get("id") or s.get("name")),
                node_type=NodeType.STRATEGY,
                label=str(s.get("name") or s.get("id") or "strategy"),
                props=s,
                source_subsystem="strategy_intelligence",
            )
        )
        add_edge(
            _edge(
                source=sid,
                target=strategy_id,
                relation=RelationType.LINKED_TO,
                props={"via": "sic"},
            )
        )

    # Sessions
    for sess in ("tokyo", "london", "new_york", "overlap"):
        add_node(
            _node(
                node_id=_nid("session", sess),
                node_type=NodeType.SESSION,
                label=sess.replace("_", " ").title(),
                props={"session": sess},
                source_subsystem="portfolio_analytics",
            )
        )

    # Market regimes
    regime = _as_dict(sources.get("regime"))
    current = _as_dict(regime.get("current"))
    cur_name = current.get("current_regime") or regime.get("current_regime") or "UNKNOWN"
    regime_id = add_node(
        _node(
            node_id=_nid("regime", cur_name),
            node_type=NodeType.MARKET_REGIME,
            label=str(cur_name),
            props=current or {"current_regime": cur_name},
            source_subsystem="market_regime_intelligence",
        )
    )
    for r in _as_list(regime.get("history") or sources.get("idw", {}).get("regimes") or [])[
        :25
    ]:
        if not isinstance(r, dict):
            continue
        name = r.get("regime") or r.get("name") or r.get("id")
        rid = add_node(
            _node(
                node_id=_nid("regime", name),
                node_type=NodeType.MARKET_REGIME,
                label=str(name),
                props=r,
                source_subsystem="market_regime_intelligence",
            )
        )
        add_edge(
            _edge(
                source=rid,
                target=regime_id,
                relation=RelationType.LINKED_TO,
                props={"kind": "regime_history"},
            )
        )

    # Signals & trades from IDW
    idw = _as_dict(sources.get("idw"))
    signal_ids: list[str] = []
    for sig in _as_list(idw.get("signals"))[:60]:
        if not isinstance(sig, dict):
            continue
        sid = add_node(
            _node(
                node_id=_nid("signal", sig.get("id") or sig.get("signal_id") or uuid4()),
                node_type=NodeType.SIGNAL,
                label=str(sig.get("symbol") or sig.get("id") or "signal"),
                props=sig,
                source_subsystem="institutional_data_warehouse",
            )
        )
        signal_ids.append(sid)
        add_edge(
            _edge(source=sid, target=strategy_id, relation=RelationType.GENERATED_BY)
        )
        add_edge(
            _edge(source=sid, target=regime_id, relation=RelationType.OBSERVED_IN)
        )
        sess = sig.get("session")
        if sess:
            add_edge(
                _edge(
                    source=sid,
                    target=_nid("session", str(sess).lower().replace(" ", "_")),
                    relation=RelationType.OBSERVED_IN,
                )
            )

    for tr in _as_list(idw.get("trades"))[:60]:
        if not isinstance(tr, dict):
            continue
        tid = add_node(
            _node(
                node_id=_nid("trade", tr.get("id") or tr.get("ticket") or uuid4()),
                node_type=NodeType.TRADE,
                label=str(tr.get("symbol") or tr.get("ticket") or "trade"),
                props=tr,
                source_subsystem="institutional_data_warehouse",
            )
        )
        add_edge(
            _edge(source=tid, target=strategy_id, relation=RelationType.GENERATED_BY)
        )
        add_edge(
            _edge(source=tid, target=regime_id, relation=RelationType.OBSERVED_IN)
        )
        # Link to nearest signal if same symbol
        sym = tr.get("symbol")
        for sid in signal_ids[:20]:
            if nodes[sid]["properties"].get("symbol") == sym:
                add_edge(
                    _edge(
                        source=tid,
                        target=sid,
                        relation=RelationType.DERIVED_FROM,
                        props={"match": "symbol"},
                    )
                )
                break

    # Research experiments & replay jobs
    irl = _as_dict(sources.get("irl"))
    for exp in _as_list(irl.get("experiments"))[:40]:
        if not isinstance(exp, dict):
            continue
        eid = add_node(
            _node(
                node_id=_nid("experiment", exp.get("uuid") or exp.get("id") or uuid4()),
                node_type=NodeType.RESEARCH_EXPERIMENT,
                label=str(exp.get("name") or exp.get("uuid") or "experiment"),
                props=exp,
                source_subsystem="institutional_research_lab",
            )
        )
        add_edge(
            _edge(source=eid, target=strategy_id, relation=RelationType.LINKED_TO)
        )
        verdict = str(exp.get("verdict") or "").lower()
        if "pass" in verdict or "confirm" in verdict:
            add_edge(
                _edge(
                    source=eid,
                    target=strategy_id,
                    relation=RelationType.CONFIRMED_BY,
                )
            )
        elif "reject" in verdict or "fail" in verdict:
            add_edge(
                _edge(
                    source=eid,
                    target=strategy_id,
                    relation=RelationType.CONTRADICTED_BY,
                )
            )

    # Institutional Simulation Engine — every simulation is a knowledge node
    ise = _as_dict(sources.get("ise"))
    for node in _as_list(ise.get("nodes"))[:40]:
        if not isinstance(node, dict):
            continue
        nid = str(node.get("id") or _nid("simulation", uuid4()))
        sid = add_node(
            _node(
                node_id=nid,
                node_type=NodeType.RESEARCH_EXPERIMENT,
                label=str(node.get("label") or "ISE Simulation"),
                props={**(node.get("properties") or {}), "digital_twin": True},
                source_subsystem="institutional_simulation_engine",
            )
        )
        add_edge(
            _edge(source=sid, target=strategy_id, relation=RelationType.DERIVED_FROM)
        )
    for sim in _as_list(ise.get("simulations"))[:40]:
        if not isinstance(sim, dict):
            continue
        nid = _nid("simulation", sim.get("simulation_id") or uuid4())
        if nid in nodes:
            continue
        sid = add_node(
            _node(
                node_id=nid,
                node_type=NodeType.RESEARCH_EXPERIMENT,
                label=str(sim.get("title") or sim.get("mode") or "ISE Simulation"),
                props={
                    "mode": sim.get("mode"),
                    "scenario": sim.get("scenario"),
                    "metrics": sim.get("metrics"),
                    "digital_twin": True,
                },
                source_subsystem="institutional_simulation_engine",
            )
        )
        add_edge(
            _edge(source=sid, target=strategy_id, relation=RelationType.DERIVED_FROM)
        )

    for job in _as_list(irl.get("jobs"))[:30]:
        if not isinstance(job, dict):
            continue
        jid = add_node(
            _node(
                node_id=_nid("replay", job.get("id") or job.get("job_id") or uuid4()),
                node_type=NodeType.REPLAY_JOB,
                label=str(job.get("name") or job.get("id") or "replay"),
                props=job,
                source_subsystem="institutional_research_lab",
            )
        )
        exp_ref = job.get("experiment_id") or job.get("experiment_uuid")
        if exp_ref:
            add_edge(
                _edge(
                    source=jid,
                    target=_nid("experiment", exp_ref),
                    relation=RelationType.DERIVED_FROM,
                )
            )
        add_edge(
            _edge(source=jid, target=strategy_id, relation=RelationType.VALIDATED_BY)
        )

    # Recommendations & reports (AQS)
    aqs = _as_dict(sources.get("aqs"))
    for rec in _as_list(aqs.get("recommendations"))[:60]:
        if not isinstance(rec, dict):
            continue
        rid = add_node(
            _node(
                node_id=_nid("recommendation", rec.get("id") or uuid4()),
                node_type=NodeType.RECOMMENDATION,
                label=str(rec.get("title") or rec.get("id") or "recommendation"),
                props=rec,
                source_subsystem="ai_quant_scientist",
            )
        )
        add_edge(
            _edge(source=rid, target=strategy_id, relation=RelationType.LINKED_TO)
        )
        add_edge(
            _edge(source=rid, target=regime_id, relation=RelationType.AFFECTED_BY)
        )

    for rep in _as_list(aqs.get("reports"))[:15]:
        if not isinstance(rep, dict):
            continue
        rpid = add_node(
            _node(
                node_id=_nid("report", rep.get("report_id") or uuid4()),
                node_type=NodeType.REPORT,
                label=str(rep.get("title") or rep.get("report_id") or "report"),
                props=rep,
                source_subsystem="ai_quant_scientist",
            )
        )
        add_edge(
            _edge(source=rpid, target=strategy_id, relation=RelationType.DERIVED_FROM)
        )

    # Portfolio metrics
    portfolio = _as_dict(sources.get("portfolio"))
    perf = _as_dict(_as_dict(portfolio.get("sections")).get("performance"))
    risk = _as_dict(_as_dict(portfolio.get("sections")).get("risk"))
    metric_id = add_node(
        _node(
            node_id="metric:portfolio",
            node_type=NodeType.PORTFOLIO_METRIC,
            label="Portfolio Metrics",
            props={
                "profit_factor": perf.get("profit_factor") or portfolio.get("profit_factor"),
                "win_rate": perf.get("win_rate_pct") or perf.get("win_rate"),
                "trade_count": perf.get("trade_count") or portfolio.get("trade_count"),
                "max_drawdown_pct": risk.get("max_drawdown_pct"),
            },
            source_subsystem="portfolio_analytics",
        )
    )
    add_edge(
        _edge(source=metric_id, target=strategy_id, relation=RelationType.DERIVED_FROM)
    )
    add_edge(
        _edge(source=metric_id, target=regime_id, relation=RelationType.AFFECTED_BY)
    )

    # Diagnostics → risk/safety events
    diag = _as_dict(sources.get("diagnostics"))
    for i, cycle in enumerate(_as_list(diag.get("cycles") or diag.get("items"))[:30]):
        if not isinstance(cycle, dict):
            continue
        did = add_node(
            _node(
                node_id=_nid("diagnostic", cycle.get("cycle_id") or cycle.get("id") or i),
                node_type=NodeType.DIAGNOSTIC,
                label=f"Cycle {cycle.get('cycle_id') or i}",
                props=cycle,
                source_subsystem="strategy_diagnostics",
            )
        )
        add_edge(
            _edge(source=did, target=strategy_id, relation=RelationType.OBSERVED_IN)
        )
        outcome = str(cycle.get("outcome") or cycle.get("block_reason") or "").lower()
        if "risk" in outcome:
            reid = add_node(
                _node(
                    node_id=_nid("risk", cycle.get("cycle_id") or i),
                    node_type=NodeType.RISK_EVENT,
                    label=f"Risk · {cycle.get('cycle_id') or i}",
                    props={"outcome": outcome, "cycle": cycle.get("cycle_id")},
                    source_subsystem="strategy_diagnostics",
                )
            )
            add_edge(
                _edge(source=did, target=reid, relation=RelationType.GENERATED_BY)
            )
            add_edge(
                _edge(source=reid, target=strategy_id, relation=RelationType.AFFECTED_BY)
            )
        if "safety" in outcome:
            seid = add_node(
                _node(
                    node_id=_nid("safety", cycle.get("cycle_id") or i),
                    node_type=NodeType.SAFETY_EVENT,
                    label=f"Safety · {cycle.get('cycle_id') or i}",
                    props={"outcome": outcome},
                    source_subsystem="strategy_diagnostics",
                )
            )
            add_edge(
                _edge(source=did, target=seid, relation=RelationType.GENERATED_BY)
            )

    # Alerts from ICC
    icc = _as_dict(sources.get("icc"))
    alerts = _as_list(
        icc.get("alerts") or _as_dict(icc.get("sections")).get("alerts") or []
    )
    for i, alert in enumerate(alerts[:40]):
        if not isinstance(alert, dict):
            continue
        aid = add_node(
            _node(
                node_id=_nid("alert", alert.get("id") or i),
                node_type=NodeType.ALERT,
                label=str(alert.get("message") or alert.get("title") or f"alert-{i}"),
                props=alert,
                source_subsystem="institutional_control_center",
            )
        )
        add_edge(
            _edge(source=aid, target=strategy_id, relation=RelationType.LINKED_TO)
        )
        add_edge(
            _edge(source=aid, target=metric_id, relation=RelationType.AFFECTED_BY)
        )

    # Audit as confirming/contradicting evidence links to strategy
    for i, ev in enumerate(_as_list(sources.get("audit"))[:25]):
        if not isinstance(ev, dict):
            continue
        rid = add_node(
            _node(
                node_id=_nid("report", f"audit-{ev.get('id') or i}"),
                node_type=NodeType.REPORT,
                label=str(ev.get("event_type") or ev.get("action") or f"audit-{i}"),
                props=ev,
                source_subsystem="audit_governance",
            )
        )
        add_edge(
            _edge(source=rid, target=strategy_id, relation=RelationType.CONFIRMED_BY)
        )

    node_list = list(nodes.values())
    type_counts: dict[str, int] = {}
    for n in node_list:
        type_counts[n["type"]] = type_counts.get(n["type"], 0) + 1
    rel_counts: dict[str, int] = {}
    for e in edges:
        rel_counts[e["relation"]] = rel_counts.get(e["relation"], 0) + 1

    return {
        "schema_version": "1.0.0",
        "mode": "quant_knowledge_graph",
        "built_at": datetime.now(UTC).isoformat(),
        "nodes": node_list,
        "edges": edges,
        "stats": {
            "node_count": len(node_list),
            "edge_count": len(edges),
            "by_type": type_counts,
            "by_relation": rel_counts,
        },
        "availability": ctx.get("availability") or {},
        "read_only": True,
        "never_modifies_production": True,
    }
