"""RMIP modules — real-world context only; never invents market or macro data."""

from __future__ import annotations

from datetime import UTC, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from app.domain.real_market_intelligence_platform.config import RmipConfig
from app.domain.real_market_intelligence_platform.types import (
    ModuleResult,
    RmipInput,
)

MISSING = "MISSING DATA"
SESSIONS = ("sydney", "tokyo", "london", "new_york")
IMPORTANCE_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
}


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _missing(module: str, detail: str) -> ModuleResult:
    return ModuleResult(
        module=module,
        status="missing_data",
        score=None,
        recommendation=MISSING,
        reasons=(detail, "Never fabricates macroeconomic or market data"),
        details={"verdict": MISSING},
    )


def _parse_clock(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (ValueError, TypeError):
        return None


def _normalize_importance(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if not s:
        return None
    aliases = {
        "l": "low",
        "m": "medium",
        "h": "high",
        "c": "critical",
        "med": "medium",
    }
    s = aliases.get(s, s)
    if s in IMPORTANCE_RANK:
        if s.isdigit():
            return {1: "low", 2: "medium", 3: "high", 4: "critical"}[int(s)]
        return s
    return None


def economic_calendar(inp: RmipInput, config: RmipConfig) -> ModuleResult:
    _ = config
    events = [e for e in (inp.economic_events or []) if isinstance(e, dict)]
    if not events:
        return _missing(
            "economic_calendar",
            "No economic_events supplied — feed unavailable or empty",
        )

    normalized: list[dict[str, Any]] = []
    missing_fields: list[str] = []
    max_rank = 0
    for i, e in enumerate(events[:200]):
        name = e.get("name") or e.get("event") or e.get("title")
        currency = e.get("currency")
        importance = _normalize_importance(e.get("importance"))
        scheduled = e.get("scheduled_time") or e.get("time") or e.get("datetime")
        previous = e.get("previous")
        forecast = e.get("forecast")
        actual = e.get("actual")
        row = {
            "name": str(name) if name is not None else None,
            "currency": str(currency) if currency is not None else None,
            "importance": importance,
            "scheduled_time": str(scheduled) if scheduled is not None else None,
            "previous": previous if previous is not None else None,
            "forecast": forecast if forecast is not None else None,
            "actual": actual if actual is not None else None,
        }
        for field in ("name", "currency", "importance", "scheduled_time"):
            if row[field] is None:
                missing_fields.append(f"event[{i}].{field}")
        if importance:
            max_rank = max(max_rank, IMPORTANCE_RANK[importance])
        # Never invent previous/forecast/actual
        normalized.append(row)

    risk_map = {0: "LOW", 1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "CRITICAL"}
    market_risk = risk_map[max_rank] if max_rank else "LOW"
    # If every event lacks importance, risk is unknown — not guessed as LOW
    if max_rank == 0 and all(
        e.get("importance") is None for e in normalized
    ):
        market_risk = MISSING

    return ModuleResult(
        module="economic_calendar",
        status="available",
        score=Decimal(str(len(normalized))),
        recommendation=f"Market Risk Level: {market_risk}",
        reasons=(
            "Ingested scheduled macroeconomic events from caller feed only",
            "Never guesses missing previous/forecast/actual",
        ),
        details={
            "events": normalized,
            "market_risk_level": market_risk,
            "event_count": len(normalized),
            "missing_fields": missing_fields[:50],
            "never_guesses_missing_values": True,
        },
    )


def session_intelligence(inp: RmipInput, config: RmipConfig) -> ModuleResult:
    _ = config
    now = _parse_clock(inp.clock_utc)
    hint = (inp.session_hint or "").strip().lower().replace(" ", "_")
    hint = hint.replace("-", "_")
    aliases = {"ny": "new_york", "newyork": "new_york"}
    hint = aliases.get(hint, hint)

    if now is None and hint not in SESSIONS and not hint:
        return _missing(
            "session_intelligence",
            "Supply clock_utc and/or session_hint — no invented session",
        )

    t = now.timetz().replace(tzinfo=None) if now else None
    # Approximate major FX session windows in UTC (observational labels only)
    windows = {
        "sydney": (time(21, 0), time(6, 0)),
        "tokyo": (time(0, 0), time(9, 0)),
        "london": (time(7, 0), time(16, 0)),
        "new_york": (time(12, 0), time(21, 0)),
    }

    def _in_window(tm: time, start: time, end: time) -> bool:
        if start <= end:
            return start <= tm < end
        return tm >= start or tm < end

    active: list[str] = []
    if t is not None:
        for name, (start, end) in windows.items():
            if _in_window(t, start, end):
                active.append(name)
    elif hint in SESSIONS:
        active = [hint]

    overlaps = []
    if "sydney" in active and "tokyo" in active:
        overlaps.append("sydney_tokyo")
    if "tokyo" in active and "london" in active:
        overlaps.append("tokyo_london")
    if "london" in active and "new_york" in active:
        overlaps.append("london_new_york")

    opening: list[str] = []
    closing: list[str] = []
    if t is not None:
        cur_mins = t.hour * 60 + t.minute
        for name, (start, end) in windows.items():
            start_mins = start.hour * 60 + start.minute
            end_mins = end.hour * 60 + end.minute
            if abs(cur_mins - start_mins) <= 30:
                opening.append(name)
            if abs(cur_mins - end_mins) <= 30:
                closing.append(name)

    primary = active[0] if len(active) == 1 else (
        overlaps[0].split("_")[-1] if overlaps else (active[0] if active else None)
    )
    if hint in SESSIONS and not active:
        primary = hint
        active = [hint]

    if not active:
        return ModuleResult(
            module="session_intelligence",
            status="missing_data",
            score=None,
            recommendation=MISSING,
            reasons=("Could not resolve session from clock/hint",),
            details={"verdict": MISSING, "clock_utc": inp.clock_utc},
        )

    return ModuleResult(
        module="session_intelligence",
        status="available",
        score=Decimal(str(len(active))),
        recommendation=f"Active: {', '.join(active)}",
        reasons=(
            "Session labels from UTC clock windows and/or supplied hint",
            "Never invents a session without clock or hint",
        ),
        details={
            "active_sessions": active,
            "primary_session": primary,
            "overlap_sessions": overlaps,
            "market_opening_periods": opening,
            "market_closing_periods": closing,
            "clock_utc": now.isoformat() if now else None,
            "session_hint": hint or None,
        },
    )


def volatility_observatory(inp: RmipInput, config: RmipConfig) -> ModuleResult:
    _ = config
    obs = (
        inp.volatility_observations
        if isinstance(inp.volatility_observations, dict)
        else None
    )
    if not obs:
        return _missing(
            "volatility_observatory",
            "No volatility_observations supplied",
        )

    keys = (
        "average_daily_range",
        "current_session_range",
        "atr",
        "spread_expansion",
        "price_acceleration",
    )
    present: dict[str, Any] = {}
    missing: list[str] = []
    for k in keys:
        v = obs.get(k)
        if v is None:
            missing.append(k)
        else:
            present[k] = v if not isinstance(v, (int, float, Decimal)) else str(
                _dec(v) or v
            )

    level_raw = obs.get("level") or obs.get("volatility_level")
    level: str | None = None
    if level_raw is not None:
        s = str(level_raw).strip().lower()
        if s in ("normal", "elevated", "extreme"):
            level = s.capitalize() if s != "normal" else "Normal"
            if s == "elevated":
                level = "Elevated"
            elif s == "extreme":
                level = "Extreme"
            else:
                level = "Normal"

    # Derive level only from explicit ratio if supplied — never invent ATR
    ratio = _dec(obs.get("atr_vs_average_ratio") or obs.get("range_vs_adr_ratio"))
    if level is None and ratio is not None:
        if ratio >= Decimal("2"):
            level = "Extreme"
        elif ratio >= Decimal("1.35"):
            level = "Elevated"
        else:
            level = "Normal"

    if level is None and not present:
        return _missing(
            "volatility_observatory",
            "Observations empty — cannot detect Normal/Elevated/Extreme",
        )

    return ModuleResult(
        module="volatility_observatory",
        status="available" if present or level else "missing_data",
        score=_dec(obs.get("atr")) or Decimal(str(len(present))),
        recommendation=level or MISSING,
        reasons=(
            "Monitors ADR, session range, ATR, spread expansion, acceleration",
            "Never invents missing volatility fields",
        ),
        details={
            "observations": present,
            "volatility_level": level or MISSING,
            "missing_fields": missing,
            "detection": level or MISSING,
        },
    )


def liquidity_observatory(inp: RmipInput, config: RmipConfig) -> ModuleResult:
    _ = config
    obs = (
        inp.liquidity_observations
        if isinstance(inp.liquidity_observations, dict)
        else None
    )
    if not obs:
        return _missing(
            "liquidity_observatory",
            "No liquidity_observations supplied",
        )

    keys = (
        "session_liquidity",
        "daily_high",
        "daily_low",
        "weekly_high",
        "weekly_low",
        "liquidity_sweep",
        "range_compression",
        "expansion",
    )
    present: dict[str, Any] = {}
    missing: list[str] = []
    for k in keys:
        # Accept alternate spellings
        alt = {
            "daily_high": "daily_highs",
            "daily_low": "daily_lows",
            "weekly_high": "weekly_highs",
            "weekly_low": "weekly_lows",
            "liquidity_sweep": "liquidity_sweeps",
        }
        v = obs.get(k)
        if v is None and k in alt:
            v = obs.get(alt[k])
        if v is None:
            missing.append(k)
        else:
            present[k] = v if not isinstance(v, (int, float, Decimal)) else str(
                _dec(v) or v
            )

    quality = obs.get("liquidity_quality") or obs.get("quality")
    if quality is not None:
        quality = str(quality)

    if not present and quality is None:
        return _missing(
            "liquidity_observatory",
            "Liquidity fields absent — nothing to detect",
        )

    return ModuleResult(
        module="liquidity_observatory",
        status="available",
        score=Decimal(str(len(present))),
        recommendation=quality or "Liquidity observations recorded",
        reasons=(
            "Session liquidity, highs/lows, sweeps, compression, expansion",
            "Never invents liquidity structure",
        ),
        details={
            "observations": present,
            "liquidity_quality": quality,
            "missing_fields": missing,
            "detections": {
                "liquidity_sweep": present.get("liquidity_sweep"),
                "range_compression": present.get("range_compression"),
                "expansion": present.get("expansion"),
            },
        },
    )


def market_context_timeline(
    inp: RmipInput,
    modules: dict[str, ModuleResult],
    config: RmipConfig,
) -> ModuleResult:
    econ = modules.get("economic_calendar")
    sess = modules.get("session_intelligence")
    vol = modules.get("volatility_observatory")
    liq = modules.get("liquidity_observatory")

    entry = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "market_regime": inp.regime,
        "volatility": (
            (vol.details or {}).get("volatility_level") if vol else None
        ),
        "liquidity": (
            (liq.details or {}).get("liquidity_quality") if liq else None
        ),
        "economic_events": (
            (econ.details or {}).get("event_count") if econ else None
        ),
        "economic_risk": (
            (econ.details or {}).get("market_risk_level") if econ else None
        ),
        "session": (
            (sess.details or {}).get("primary_session") if sess else None
        ),
        "trend": inp.trend,
        "confidence": inp.confidence,
    }
    # Mark missing keys explicitly — never fill
    for k, v in list(entry.items()):
        if v is None and k != "recorded_at":
            entry[k] = MISSING

    return ModuleResult(
        module="market_context_timeline",
        status="available",
        score=Decimal("1"),
        recommendation="Timeline entry assembled from available context",
        reasons=(
            "Regime, volatility, liquidity, events, session, trend, confidence",
            "Missing fields reported as MISSING DATA",
        ),
        details={
            "entry": entry,
            "max_timeline": config.max_timeline,
            "read_only": True,
        },
    )


def context_scoring(
    inp: RmipInput, modules: dict[str, ModuleResult]
) -> ModuleResult:
    econ = modules.get("economic_calendar")
    sess = modules.get("session_intelligence")
    vol = modules.get("volatility_observatory")
    liq = modules.get("liquidity_observatory")

    inputs_used: list[str] = []
    missing: list[str] = []
    score = Decimal("50")

    economic_risk = MISSING
    if econ and econ.status == "available":
        economic_risk = str(
            (econ.details or {}).get("market_risk_level") or MISSING
        )
        inputs_used.append("economic_calendar")
        if economic_risk == "LOW":
            score += Decimal("10")
        elif economic_risk == "MEDIUM":
            score += Decimal("5")
        elif economic_risk in ("HIGH", "CRITICAL"):
            score -= Decimal("15" if economic_risk == "CRITICAL" else "10")
    else:
        missing.append("economic_calendar")

    session = MISSING
    if sess and sess.status == "available":
        session = str((sess.details or {}).get("primary_session") or MISSING)
        inputs_used.append("session_intelligence")
        score += Decimal("8")
    else:
        missing.append("session_intelligence")

    volatility = MISSING
    if vol and vol.status == "available":
        volatility = str((vol.details or {}).get("volatility_level") or MISSING)
        inputs_used.append("volatility_observatory")
        if volatility == "Normal":
            score += Decimal("10")
            volatility_label = "Healthy"
        elif volatility == "Elevated":
            score += Decimal("2")
            volatility_label = "Elevated"
        elif volatility == "Extreme":
            score -= Decimal("10")
            volatility_label = "Extreme"
        else:
            volatility_label = volatility
        volatility = volatility_label
    else:
        missing.append("volatility_observatory")

    liquidity = MISSING
    if liq and liq.status == "available":
        liquidity = str(
            (liq.details or {}).get("liquidity_quality") or "Observed"
        )
        inputs_used.append("liquidity_observatory")
        score += Decimal("10")
    else:
        missing.append("liquidity_observatory")

    trend = inp.trend if inp.trend else MISSING
    if inp.trend:
        inputs_used.append("trend")
        score += Decimal("5")
    else:
        missing.append("trend")

    # Confidence of the score itself from coverage
    coverage = Decimal(len(inputs_used)) / Decimal("5")
    conf_pct = (coverage * Decimal("100")).quantize(Decimal("0.01"))
    if score < 0:
        score = Decimal("0")
    if score > 100:
        score = Decimal("100")
    # Penalize missing coverage so we never imply full certainty
    score = (score * coverage + Decimal("40") * (1 - coverage)).quantize(
        Decimal("0.01")
    )

    return ModuleResult(
        module="context_scoring",
        status="available" if inputs_used else "missing_data",
        score=score if inputs_used else None,
        recommendation=(
            f"Market Context {score}" if inputs_used else MISSING
        ),
        reasons=(
            "Unified score from supplied modules only",
            "Never invents economic or market inputs",
        ),
        details={
            "market_context": str(score) if inputs_used else MISSING,
            "economic_risk": economic_risk,
            "liquidity": liquidity,
            "session": session,
            "trend": trend,
            "volatility": volatility,
            "score_confidence_pct": str(conf_pct),
            "inputs_used": inputs_used,
            "missing_data": missing,
        },
    )


def operator_intelligence_feed(
    modules: dict[str, ModuleResult],
) -> ModuleResult:
    econ = modules.get("economic_calendar")
    sess = modules.get("session_intelligence")
    vol = modules.get("volatility_observatory")
    liq = modules.get("liquidity_observatory")
    score = modules.get("context_scoring")
    timeline = modules.get("market_context_timeline")

    upcoming = []
    if econ and isinstance((econ.details or {}).get("events"), list):
        upcoming = (econ.details or {})["events"][:10]

    open_risks: list[str] = []
    if econ:
        risk = (econ.details or {}).get("market_risk_level")
        if risk in ("HIGH", "CRITICAL"):
            open_risks.append(f"Economic risk: {risk}")
        if (econ.details or {}).get("missing_fields"):
            open_risks.append("Incomplete economic event fields")
    if vol and (vol.details or {}).get("volatility_level") == "Extreme":
        open_risks.append("Extreme volatility observed")
    for name, mod in (
        ("economic_calendar", econ),
        ("session_intelligence", sess),
        ("volatility_observatory", vol),
        ("liquidity_observatory", liq),
    ):
        if mod is None or mod.status == "missing_data":
            open_risks.append(f"{name}: {MISSING}")

    return ModuleResult(
        module="operator_intelligence_feed",
        status="available",
        score=score.score if score else None,
        recommendation="Operator feed assembled",
        reasons=(
            "Upcoming events, regime, session, vol, liquidity, context, risks",
            "Context only — never places trades",
        ),
        details={
            "upcoming_events": upcoming,
            "current_regime": (
                ((timeline.details or {}).get("entry") or {}).get(
                    "market_regime"
                )
                if timeline
                else MISSING
            ),
            "current_session": (
                (sess.details or {}).get("primary_session")
                if sess and sess.status == "available"
                else MISSING
            ),
            "volatility": (
                (vol.details or {}).get("volatility_level")
                if vol and vol.status == "available"
                else MISSING
            ),
            "liquidity": (
                (liq.details or {}).get("liquidity_quality")
                if liq and liq.status == "available"
                else MISSING
            ),
            "market_context": (
                (score.details or {}).get("market_context")
                if score
                else MISSING
            ),
            "open_risks": open_risks,
        },
    )


def explainability(modules: dict[str, ModuleResult]) -> ModuleResult:
    score = modules.get("context_scoring")
    if not score:
        return _missing("explainability", "context_scoring not available")

    d = score.details or {}
    return ModuleResult(
        module="explainability",
        status="available",
        score=score.score,
        recommendation="Context score explained",
        reasons=(
            "Why / inputs / observations / missing / confidence",
            "Every context score is explainable",
        ),
        details={
            "why": score.recommendation,
            "which_inputs": d.get("inputs_used") or [],
            "which_observations": {
                "economic_risk": d.get("economic_risk"),
                "liquidity": d.get("liquidity"),
                "session": d.get("session"),
                "trend": d.get("trend"),
                "volatility": d.get("volatility"),
            },
            "missing_data": d.get("missing_data") or [],
            "confidence": d.get("score_confidence_pct"),
            "market_context_score": d.get("market_context"),
        },
    )


def historical_context_archive(
    *,
    prior: list[dict[str, Any]],
    audit_id: str,
    snapshot: dict[str, Any],
    archive_event: dict[str, Any] | None,
    config: RmipConfig,
) -> ModuleResult:
    _ = config
    event = archive_event if isinstance(archive_event, dict) else {}
    entry = {
        "id": str(event.get("id") or f"rmip_{uuid4().hex[:10]}"),
        "audit_id": audit_id,
        "recorded_at": datetime.now(UTC).isoformat(),
        "market_context": snapshot.get("market_context"),
        "economic_events": snapshot.get("economic_events"),
        "economic_risk": snapshot.get("economic_risk"),
        "volatility": snapshot.get("volatility"),
        "sessions": snapshot.get("session"),
        "liquidity": snapshot.get("liquidity"),
        "regime": snapshot.get("regime"),
        "comments": str(event.get("comments") or ""),
        "append_only": True,
        "read_only_archive": True,
        "overwrites_prior": False,
    }
    return ModuleResult(
        module="historical_context_archive",
        status="available",
        score=Decimal(str(len(prior) + 1)),
        recommendation="Archive entry prepared (append-only)",
        reasons=(
            "Stores context, events, volatility, sessions, liquidity, regime",
            "Read-only archive — never overwrites prior rows",
        ),
        details={
            "entry": entry,
            "prior_count": len(prior),
            "append_only": True,
            "read_only_archive": True,
        },
    )


def context_api_payload(modules: dict[str, ModuleResult]) -> ModuleResult:
    """Shape the read-only Context API surface from module outputs."""
    econ = modules.get("economic_calendar")
    sess = modules.get("session_intelligence")
    vol = modules.get("volatility_observatory")
    liq = modules.get("liquidity_observatory")
    score = modules.get("context_scoring")
    timeline = modules.get("market_context_timeline")
    feed = modules.get("operator_intelligence_feed")

    return ModuleResult(
        module="context_api",
        status="available",
        score=score.score if score else None,
        recommendation="Read-only Context API payload",
        reasons=(
            "Exposes current/historical/session/risk/vol/liq/timeline/score",
            "READ ONLY — never places trades",
        ),
        details={
            "current_context": (
                (feed.details if feed else None) or MISSING
            ),
            "historical_context": "via /history and archive module",
            "session": (
                (sess.details or {})
                if sess and sess.status == "available"
                else {"verdict": MISSING}
            ),
            "economic_risk": (
                (econ.details or {}).get("market_risk_level")
                if econ
                else MISSING
            ),
            "volatility": (
                (vol.details or {})
                if vol and vol.status == "available"
                else {"verdict": MISSING}
            ),
            "liquidity": (
                (liq.details or {})
                if liq and liq.status == "available"
                else {"verdict": MISSING}
            ),
            "timeline": (
                (timeline.details or {}).get("entry")
                if timeline
                else MISSING
            ),
            "context_score": (
                (score.details or {})
                if score
                else {"verdict": MISSING}
            ),
            "read_only": True,
        },
    )
