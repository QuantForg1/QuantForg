"""QKG query layer — search, lineages, evidence chains, root cause, impact."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


def _as_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _index(graph: dict[str, Any]) -> tuple[dict[str, dict], list[dict], dict[str, list], dict[str, list]]:
    nodes = {n["id"]: n for n in _as_list(graph.get("nodes")) if isinstance(n, dict) and n.get("id")}
    edges = [e for e in _as_list(graph.get("edges")) if isinstance(e, dict)]
    out_adj: dict[str, list[dict]] = defaultdict(list)
    in_adj: dict[str, list[dict]] = defaultdict(list)
    for e in edges:
        out_adj[str(e.get("source"))].append(e)
        in_adj[str(e.get("target"))].append(e)
    return nodes, edges, out_adj, in_adj


def search_knowledge(
    graph: dict[str, Any],
    *,
    q: str | None = None,
    node_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    nodes, _, _, _ = _index(graph)
    ql = (q or "").strip().lower()
    out: list[dict[str, Any]] = []
    for n in nodes.values():
        if node_type and str(n.get("type")) != node_type and node_type not in str(n.get("type")):
            # allow partial type match (e.g. "Trade" vs "Trades")
            if node_type.lower() not in str(n.get("type")).lower():
                continue
        if ql:
            blob = " ".join(
                str(x)
                for x in (
                    n.get("id"),
                    n.get("label"),
                    n.get("type"),
                    n.get("source_subsystem"),
                    n.get("properties"),
                )
            ).lower()
            if ql not in blob:
                continue
        out.append(n)
        if len(out) >= limit:
            break
    return out


def relationships_for(
    graph: dict[str, Any],
    node_id: str,
    *,
    direction: str = "both",
    limit: int = 100,
) -> dict[str, Any]:
    nodes, _, out_adj, in_adj = _index(graph)
    node = nodes.get(node_id)
    if not node:
        return {"node": None, "edges": [], "neighbors": []}
    edges: list[dict[str, Any]] = []
    if direction in {"out", "both"}:
        edges.extend(out_adj.get(node_id, []))
    if direction in {"in", "both"}:
        edges.extend(in_adj.get(node_id, []))
    edges = edges[:limit]
    neighbor_ids = set()
    for e in edges:
        neighbor_ids.add(e.get("source"))
        neighbor_ids.add(e.get("target"))
    neighbor_ids.discard(node_id)
    neighbors = [nodes[i] for i in neighbor_ids if i in nodes]
    return {"node": node, "edges": edges, "neighbors": neighbors}


def dependency_viewer(
    graph: dict[str, Any], node_id: str, *, depth: int = 3
) -> dict[str, Any]:
    """Upstream dependencies (incoming edges) up to depth."""
    nodes, _, _, in_adj = _index(graph)
    if node_id not in nodes:
        return {"root": None, "nodes": [], "edges": []}
    seen = {node_id}
    frontier = deque([(node_id, 0)])
    collected_nodes = [nodes[node_id]]
    collected_edges: list[dict[str, Any]] = []
    while frontier:
        cur, d = frontier.popleft()
        if d >= depth:
            continue
        for e in in_adj.get(cur, []):
            src = str(e.get("source"))
            collected_edges.append(e)
            if src not in seen and src in nodes:
                seen.add(src)
                collected_nodes.append(nodes[src])
                frontier.append((src, d + 1))
    return {
        "root": nodes[node_id],
        "nodes": collected_nodes,
        "edges": collected_edges,
        "depth": depth,
    }


def evidence_chain(
    graph: dict[str, Any], node_id: str, *, max_hops: int = 5
) -> dict[str, Any]:
    """Walk derived_from / confirmed_by / generated_by / validated_by chains."""
    preferred = {
        "derived_from",
        "confirmed_by",
        "generated_by",
        "validated_by",
        "observed_in",
        "linked_to",
    }
    nodes, _, out_adj, in_adj = _index(graph)
    if node_id not in nodes:
        return {"start": None, "chain": [], "evidence": []}
    chain: list[dict[str, Any]] = [{"hop": 0, "node": nodes[node_id], "via": None}]
    evidence: list[dict[str, Any]] = []
    cur = node_id
    for hop in range(1, max_hops + 1):
        candidates = list(out_adj.get(cur, [])) + list(in_adj.get(cur, []))
        nxt = None
        for e in candidates:
            if str(e.get("relation")) not in preferred:
                continue
            other = e.get("target") if e.get("source") == cur else e.get("source")
            if other in nodes and other != cur and all(
                step["node"]["id"] != other for step in chain
            ):
                nxt = (other, e)
                break
        if not nxt:
            break
        other, e = nxt
        chain.append({"hop": hop, "node": nodes[other], "via": e})
        evidence.append(e)
        cur = other
    return {
        "start": nodes[node_id],
        "chain": chain,
        "evidence": evidence,
        "length": len(chain),
    }


def recommendation_trace(graph: dict[str, Any], recommendation_id: str) -> dict[str, Any]:
    nodes, _, _, _ = _index(graph)
    # accept raw id or recommendation:id
    candidates = [
        recommendation_id,
        f"recommendation:{recommendation_id}",
    ]
    rid = next((c for c in candidates if c in nodes), None)
    if rid is None:
        # fuzzy
        for nid, n in nodes.items():
            if n.get("type") == "Recommendations" and (
                recommendation_id in nid or recommendation_id in str(n.get("label"))
            ):
                rid = nid
                break
    if rid is None:
        return {"recommendation": None, "trace": [], "relationships": {}}
    rel = relationships_for(graph, rid)
    chain = evidence_chain(graph, rid)
    return {
        "recommendation": nodes[rid],
        "trace": chain.get("chain"),
        "relationships": rel,
        "never_applies_production": True,
    }


def historical_lineage(
    graph: dict[str, Any], node_id: str, *, depth: int = 4
) -> dict[str, Any]:
    """Follow derived_from edges backward (incoming)."""
    nodes, _, _, in_adj = _index(graph)
    if node_id not in nodes:
        return {"root": None, "lineage": []}
    lineage = [{"depth": 0, "node": nodes[node_id]}]
    frontier = deque([(node_id, 0)])
    seen = {node_id}
    while frontier:
        cur, d = frontier.popleft()
        if d >= depth:
            continue
        for e in in_adj.get(cur, []):
            if str(e.get("relation")) not in {"derived_from", "generated_by", "validated_by"}:
                continue
            src = str(e.get("source"))
            if src in seen or src not in nodes:
                continue
            seen.add(src)
            lineage.append({"depth": d + 1, "node": nodes[src], "via": e})
            frontier.append((src, d + 1))
    return {"root": nodes[node_id], "lineage": lineage}


def impact_analysis(
    graph: dict[str, Any], node_id: str, *, depth: int = 3
) -> dict[str, Any]:
    """Downstream impact (outgoing edges)."""
    nodes, _, out_adj, _ = _index(graph)
    if node_id not in nodes:
        return {"root": None, "impacted": [], "edges": []}
    seen = {node_id}
    frontier = deque([(node_id, 0)])
    impacted: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    while frontier:
        cur, d = frontier.popleft()
        if d >= depth:
            continue
        for e in out_adj.get(cur, []):
            edges.append(e)
            tgt = str(e.get("target"))
            if tgt not in seen and tgt in nodes:
                seen.add(tgt)
                impacted.append({"depth": d + 1, "node": nodes[tgt], "via": e})
                frontier.append((tgt, d + 1))
    return {"root": nodes[node_id], "impacted": impacted, "edges": edges}


def root_cause_graph(
    graph: dict[str, Any], node_id: str, *, depth: int = 4
) -> dict[str, Any]:
    """Prefer FAIL/risk/alert upstream paths for root-cause exploration."""
    nodes, _, _, in_adj = _index(graph)
    if node_id not in nodes:
        return {"subject": None, "causes": [], "edges": []}
    causes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    frontier = deque([(node_id, 0)])
    seen = {node_id}
    while frontier:
        cur, d = frontier.popleft()
        if d >= depth:
            continue
        for e in in_adj.get(cur, []):
            edges.append(e)
            src = str(e.get("source"))
            if src in seen or src not in nodes:
                continue
            seen.add(src)
            n = nodes[src]
            score = 0
            blob = f"{n.get('type')} {n.get('label')} {n.get('properties')}".lower()
            if any(k in blob for k in ("fail", "risk", "safety", "alert", "block", "reject")):
                score += 2
            if str(e.get("relation")) in {"affected_by", "contradicted_by", "generated_by"}:
                score += 1
            causes.append({"depth": d + 1, "score": score, "node": n, "via": e})
            frontier.append((src, d + 1))
    causes.sort(key=lambda c: (-c["score"], c["depth"]))
    return {
        "subject": nodes[node_id],
        "causes": causes,
        "edges": edges,
        "primary_root": causes[0]["node"] if causes else None,
    }


def ai_query(
    graph: dict[str, Any],
    question: str,
    *,
    node_id: str | None = None,
) -> dict[str, Any]:
    """Deterministic graph Q&A for AQS / AQC consumers."""
    q = (question or "").strip().lower()
    result: dict[str, Any] = {
        "question": question,
        "advisory_only": True,
        "never_modifies_production": True,
    }
    if node_id:
        if "root cause" in q or "root-cause" in q:
            result["result"] = root_cause_graph(graph, node_id)
            result["capability"] = "root_cause_graph"
            return result
        if "evidence" in q or "chain" in q:
            result["result"] = evidence_chain(graph, node_id)
            result["capability"] = "evidence_chain"
            return result
        if "impact" in q:
            result["result"] = impact_analysis(graph, node_id)
            result["capability"] = "impact_analysis"
            return result
        if "lineage" in q or "history" in q:
            result["result"] = historical_lineage(graph, node_id)
            result["capability"] = "historical_lineage"
            return result
        if "recommend" in q or "trace" in q:
            result["result"] = recommendation_trace(graph, node_id)
            result["capability"] = "recommendation_trace"
            return result
        result["result"] = relationships_for(graph, node_id)
        result["capability"] = "relationship_explorer"
        return result

    # Global search intent
    node_type = None
    for t in (
        "Trades",
        "Signals",
        "Recommendations",
        "Diagnostics",
        "Alerts",
        "Research Experiments",
        "Market Regimes",
    ):
        if t.lower().rstrip("s") in q or t.lower() in q:
            node_type = t
            break
    hits = search_knowledge(graph, q=question if len(question) < 80 else None, node_type=node_type, limit=20)
    if not hits and q:
        # extract keyword
        for token in q.replace("?", "").split():
            if len(token) > 3:
                hits = search_knowledge(graph, q=token, limit=20)
                if hits:
                    break
    result["result"] = {"matches": hits, "count": len(hits)}
    result["capability"] = "knowledge_search"
    return result
