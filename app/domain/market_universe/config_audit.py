"""Read-only effective configuration audit.

Never silently normalizes conflicting settings. Never mutates settings.
"""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    FROZEN_DIRECTIONAL_EDGE,
    FROZEN_MIN_RR,
    FROZEN_OPPORTUNITY_THRESHOLD,
    UNKNOWN,
)


def _row(
    *,
    setting: str,
    source: str,
    default: Any,
    effective: Any,
    consumer: str,
    asset_class: str,
    live_or_research: str,
    precedence: str,
    status: str,
    note: str = "",
) -> dict[str, Any]:
    return {
        "SETTING": setting,
        "SOURCE": source,
        "DEFAULT": default,
        "EFFECTIVE_VALUE": effective,
        "CONSUMER": consumer,
        "ASSET_CLASS": asset_class,
        "LIVE/RESEARCH": live_or_research,
        "PRECEDENCE": precedence,
        "STATUS": status,
        "NOTE": note or UNKNOWN,
    }


def build_configuration_audit() -> dict[str, Any]:
    gold_only = True
    force_first = False
    multi_symbol = False
    execution_enabled = UNKNOWN
    try:
        from core.config.settings import get_settings

        settings = get_settings()
        gold_only = bool(getattr(settings, "gold_only_mode", True))
        force_first = bool(getattr(settings, "force_first_trade", False))
        multi_symbol = bool(getattr(settings, "multi_symbol_enabled", False))
        execution_enabled = bool(getattr(settings, "execution_enabled", False))
    except Exception:
        settings = None

    opp = FROZEN_OPPORTUNITY_THRESHOLD
    edge = FROZEN_DIRECTIONAL_EDGE
    rr = FROZEN_MIN_RR
    try:
        from app.domain.institutional_trading.operations.probability_selector import (
            OPPORTUNITY_SCORE_THRESHOLD,
        )

        opp = int(OPPORTUNITY_SCORE_THRESHOLD)
    except Exception:  # noqa: S110  # optional live constant lookup
        pass
    try:
        from app.domain.institutional_trading.ai_scalping.config import (
            DEFAULT_AI_SCALPING_CONFIG,
        )

        edge = int(getattr(DEFAULT_AI_SCALPING_CONFIG, "direction_edge_margin", edge))
    except Exception:  # noqa: S110  # optional live constant lookup
        pass
    try:
        from app.domain.institutional_trading.ai_scalping.profiles.scalping_v1 import (
            SCALPING_V1,
        )

        rr_v = getattr(SCALPING_V1, "min_expected_rr", None) or getattr(
            SCALPING_V1, "fixed_tp_r", None
        )
        if rr_v is not None:
            rr = str(rr_v)
    except Exception:  # noqa: S110  # optional live constant lookup
        pass

    max_open = 10
    daily_loss = "40.0"
    try:
        from app.domain.institutional_trading.ai_scalping.profiles.scalping_v1 import (
            SCALPING_V1 as _SV1,
        )

        max_open = int(getattr(_SV1, "max_open_trades", 10) or 10)
    except Exception:  # noqa: S110  # optional live constant lookup
        pass
    try:
        from app.domain.institutional_trading.config import MAX_DAILY_LOSS_PCT

        daily_loss = str(MAX_DAILY_LOSS_PCT)
    except Exception:  # noqa: S110  # optional live constant lookup
        pass

    shadow_promo = False
    try:
        from app.application.services.shadow_expansion_engine import (
            ALLOW_LIVE_PROMOTION as SHADOW_PROMO,
        )

        shadow_promo = bool(SHADOW_PROMO)
    except Exception:
        shadow_promo = ALLOW_LIVE_PROMOTION

    rows = [
        _row(
            setting="OPPORTUNITY_SCORE_THRESHOLD",
            source="probability_selector.OPPORTUNITY_SCORE_THRESHOLD",
            default=70,
            effective=opp,
            consumer="evaluate_opportunity / sniper / scalp eligibility",
            asset_class="ALL (live gold uses this)",
            live_or_research="LIVE_EFFECTIVE",
            precedence="module constant > any env alias",
            status="LIVE_EFFECTIVE" if opp == 70 else "CONFLICTING",
            note="Frozen. Research must not lower this.",
        ),
        _row(
            setting="DIRECTION_EDGE_MARGIN",
            source="AiScalpingConfig.direction_edge_margin / SCALPING_V1",
            default=5,
            effective=edge,
            consumer="decide_scalping_direction / sniper WAIT_NO_DIRECTIONAL_EDGE",
            asset_class="ALL (live gold uses this)",
            live_or_research="LIVE_EFFECTIVE",
            precedence="SCALPING_V1 / DEFAULT_AI_SCALPING_CONFIG",
            status="LIVE_EFFECTIVE" if edge == 5 else "CONFLICTING",
            note="Frozen. Research must not lower this.",
        ),
        _row(
            setting="MIN_EXPECTED_RR",
            source="scalping_v1 min_expected_rr / fixed_tp_r",
            default="1.20",
            effective=rr,
            consumer="quality_gates / sniper RR pillar",
            asset_class="METALS (live XAUUSD_i)",
            live_or_research="LIVE_EFFECTIVE",
            precedence="SCALPING_V1",
            status="LIVE_EFFECTIVE" if str(rr).startswith("1.2") else "CONFLICTING",
        ),
        _row(
            setting="GOLD_ONLY_MODE",
            source="settings.gold_only_mode (production finalize forces True)",
            default=True,
            effective=gold_only,
            consumer="gold_only.autonomous_execution_symbols / scanner clamp",
            asset_class="METALS",
            live_or_research="LIVE_EFFECTIVE",
            precedence="production finalize > env GOLD_ONLY_MODE",
            status="LIVE_EFFECTIVE",
            note="Research universe does not lift this mandate.",
        ),
        _row(
            setting="MULTI_SYMBOL_ENABLED",
            source="settings.multi_symbol_enabled",
            default=False,
            effective=multi_symbol,
            consumer="execution_universe / scanner (still gold-clamped when gold-only)",
            asset_class="ALL",
            live_or_research="LIVE_EFFECTIVE" if not gold_only else "UNUSED",
            precedence="production finalize forces False when gold-only",
            status="UNUSED" if gold_only else "LIVE_EFFECTIVE",
        ),
        _row(
            setting="FORCE_FIRST_TRADE",
            source="settings.force_first_trade / force_first_trade.py",
            default=False,
            effective=force_first,
            consumer="ITE / execution (permanently disabled)",
            asset_class="ALL",
            live_or_research="LIVE_EFFECTIVE",
            precedence="production finalize + module hard-disable",
            status="LIVE_EFFECTIVE" if not force_first else "CONFLICTING",
        ),
        _row(
            setting="ALLOW_LIVE_PROMOTION",
            source="shadow_expansion_engine.ALLOW_LIVE_PROMOTION",
            default=False,
            effective=shadow_promo,
            consumer="shadow expansion / market universe research",
            asset_class="ALL",
            live_or_research="RESEARCH",
            precedence="module constant (False)",
            status="RESEARCH_ONLY",
            note="Never a live OMS toggle. False is the safety contract.",
        ),
        _row(
            setting="EXECUTION_ENABLED",
            source="settings.execution_enabled",
            default=UNKNOWN,
            effective=execution_enabled,
            consumer="OMS / gateway",
            asset_class="METALS (live)",
            live_or_research="LIVE_EFFECTIVE",
            precedence="settings",
            status="LIVE_EFFECTIVE",
            note="Market-universe research never toggles this.",
        ),
        _row(
            setting="MAX_OPEN_TRADES",
            source="SCALPING_V1.max_open_trades",
            default=10,
            effective=max_open,
            consumer="portfolio / scalp planner",
            asset_class="ALL (live gold book)",
            live_or_research="LIVE_EFFECTIVE",
            precedence="SCALPING_V1",
            status="LIVE_EFFECTIVE" if int(max_open) == 10 else "CONFLICTING",
            note="Research must not change this.",
        ),
        _row(
            setting="MAX_DAILY_LOSS_PCT",
            source="institutional_trading.config.MAX_DAILY_LOSS_PCT",
            default="40.0",
            effective=daily_loss,
            consumer="Risk / daily loss lock",
            asset_class="ALL",
            live_or_research="LIVE_EFFECTIVE",
            precedence="ITE / Risk",
            status="LIVE_EFFECTIVE"
            if str(daily_loss).startswith("40")
            else "CONFLICTING",
            note="Research must not change this.",
        ),
        _row(
            setting="never_prefer_buy_only",
            source="market_universe opportunity board / research scanner",
            default=True,
            effective=True,
            consumer="research ranking",
            asset_class="ALL",
            live_or_research="RESEARCH",
            precedence="research contract",
            status="RESEARCH_ONLY",
        ),
        _row(
            setting="RESEARCH_UNIVERSE",
            source="app.domain.market_universe",
            default="catalogue-driven",
            effective="catalogue-driven",
            consumer="Market Universe Registry / opportunity board",
            asset_class="ALL",
            live_or_research="RESEARCH",
            precedence="broker catalogue > seed lists",
            status="RESEARCH_ONLY",
            note="Observational. Not the autonomous execution universe.",
        ),
        _row(
            setting="NEWS_PROTECTION",
            source="strategy_settings_audit.audit_news_protection",
            default="UNWIRED",
            effective=UNKNOWN,
            consumer="ITE / scalping news flag (not enabled by this layer)",
            asset_class="ALL",
            live_or_research="LIVE_EFFECTIVE",
            precedence="calendar URL + SCALPING_V1.news_protection_enabled",
            status="UNWIRED",
            note="Do not silently pretend news protection is active.",
        ),
    ]

    try:
        from app.application.services.strategy_settings_audit import (
            audit_news_protection,
        )

        news = audit_news_protection()
        for row in rows:
            if row["SETTING"] == "NEWS_PROTECTION":
                row["EFFECTIVE_VALUE"] = news.get("STATUS", UNKNOWN)
                row["STATUS"] = str(news.get("STATUS") or "UNWIRED")
    except Exception:  # noqa: S110  # optional news audit lookup
        pass

    conflicting = [r for r in rows if r["STATUS"] == "CONFLICTING"]
    duplicated = [
        "OPPORTUNITY 70 also copied in funnel/shadow telemetry (must stay aligned)",
        "EDGE 5 also copied in funnel/shadow telemetry (must stay aligned)",
    ]
    return {
        "advisory_only": True,
        "mutates_settings": False,
        "silently_normalizes_conflicts": False,
        "rows": rows,
        "conflicting": conflicting,
        "duplicated": duplicated,
        "legacy": [
            "Funnel/shadow telemetry copies of Opportunity 70 and Edge 5 "
            "(must stay aligned; not a second live gate)"
        ],
        "unused": [r for r in rows if r["STATUS"] == "UNUSED"],
        "unwired": [r for r in rows if r["STATUS"] == "UNWIRED"],
        "research_only": [r for r in rows if r["STATUS"] == "RESEARCH_ONLY"],
        "live_effective": [r for r in rows if r["STATUS"] == "LIVE_EFFECTIVE"],
        "n": len(rows),
    }
