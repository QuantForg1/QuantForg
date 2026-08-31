"""Read-only catalog of strategy settings vs the live SCALPING_V1 path.

Does not mutate ITE, Risk, Safety, OMS, or control-plane values.
Recommendations are research-only.
"""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.profiles.scalping_v1 import (
    SCALPING_V1,
)
from app.domain.institutional_trading.config import (
    MAX_DAILY_LOSS_PCT,
    ITEConfig,
)
from app.domain.institutional_trading.operations.probability_selector import (
    OPPORTUNITY_SCORE_THRESHOLD,
)


def _row(
    *,
    setting: str,
    source: str,
    default: Any,
    live: Any,
    consumer: str,
    path: str,
    legacy: bool,
    duplicated: bool,
    unused: bool,
    conflict: bool,
    action: str,
    status: str,
    actual_effect: str | None = None,
    safe_to_change: bool = False,
) -> dict[str, Any]:
    return {
        "SETTING": setting,
        "SOURCE": source,
        "DEFAULT": default,
        "LIVE_VALUE": live,
        "ACTUAL_CONSUMER": consumer,
        "CONSUMER": consumer,
        "ACTUAL_EFFECT": actual_effect or consumer,
        "PRODUCTION_PATH": path,
        "LEGACY": legacy,
        "DUPLICATED": duplicated,
        "UNUSED": unused,
        "CONFLICT": conflict,
        "SAFE_TO_CHANGE": safe_to_change,
        "REASON": action,
        "RECOMMENDED_FUTURE_ACTION": action,
        "STATUS": status,
        "LEGACY_OR_ACTIVE": "LEGACY" if legacy else "ACTIVE",
    }


def audit_news_protection() -> dict[str, Any]:
    """Classify news protection without enabling it or fetching a calendar."""
    ite_default = bool(ITEConfig().news_protection_enabled)
    scalp_flag = bool(SCALPING_V1.news_protection_enabled)
    fail_closed = bool(
        getattr(SCALPING_V1, "news_fail_closed_without_feed", False)
        or getattr(DEFAULT_AI_SCALPING_CONFIG, "news_fail_closed_without_feed", False)
    )
    url = ""
    try:
        from core.config.settings import get_settings

        url = str(getattr(get_settings(), "economic_calendar_feed_url", "") or "").strip()
    except Exception:
        url = ""

    # Live ITE copies SCALPING_V1.news_protection_enabled via ite_config_from_scalping.
    live_flag = scalp_flag
    calendar_configured = bool(url)
    if calendar_configured and live_flag:
        status = "ACTIVE"
    elif not calendar_configured:
        status = "UNWIRED"
    elif live_flag:
        status = "INACTIVE"
    else:
        status = "UNUSED"

    currently_vetoes = False
    if calendar_configured and live_flag:
        currently_vetoes = "UNKNOWN"
    enabling = (
        "YES if a calendar feed is present: NewsProtection.evaluate would block "
        "new entries in high-impact windows. Without a feed, fail-open "
        f"(fail_closed_without_feed={fail_closed}) does not veto; fail-closed "
        "would pause all new entries. This task did not enable it."
    )
    return {
        "STATUS": status,
        "ITEConfig_default": ite_default,
        "SCALPING_V1": scalp_flag,
        "authoritative_live_flag_after_ite_config_from_scalping": live_flag,
        "defined_at": [
            "ITEConfig.news_protection_enabled (default False)",
            "AiScalpingConfig / SCALPING_V1.news_protection_enabled (True)",
            "ite_config_from_scalping copies SCALPING_V1 onto ITEConfig",
        ],
        "consumed_by": (
            "InstitutionalAnalysisPipeline.analyze → NewsProtection.evaluate; "
            "InstitutionalTradingAnalysisService.analyze_bars attaches a calendar "
            "adapter only when ECONOMIC_CALENDAR_FEED_URL is set"
        ),
        "calendar_provider": (
            "EconomicCalendarNewsAdapter + ConfiguredHttpEconomicCalendar"
            if calendar_configured
            else None
        ),
        "calendar_url_configured": calendar_configured,
        "production_receives_news_events": (
            "UNKNOWN" if calendar_configured else False
        ),
        "fail_closed_without_feed": fail_closed,
        "currently_vetoes_entries": currently_vetoes,
        "dead_configuration": status in {"UNWIRED", "UNUSED", "INACTIVE"},
        "enabling_would_alter_trading": enabling,
        "this_task_did_not_enable": True,
        "HTTP_risk_check_news_rule": "n/a",
    }


def build_strategy_settings_audit() -> dict[str, Any]:
    ite = ITEConfig()
    news = audit_news_protection()
    rows = [
        _row(
            setting="Opportunity threshold",
            source="probability_selector.OPPORTUNITY_SCORE_THRESHOLD",
            default=70,
            live=OPPORTUNITY_SCORE_THRESHOLD,
            consumer="scoring / probability selector / sniper eligibility",
            path="probability_selector → sniper / TAKE eligibility",
            legacy=False,
            duplicated=False,
            unused=False,
            conflict=False,
            action="Keep 70. Do not lower to increase frequency.",
            status="AUTHORITATIVE_LIVE",
            actual_effect="TAKE requires opportunity_score >= 70 after present-only renormalization.",
            safe_to_change=False,
        ),
        _row(
            setting="Directional edge margin",
            source="SCALPING_V1.direction_edge_margin",
            default=5,
            live=SCALPING_V1.direction_edge_margin,
            consumer="ai_scalping.direction.decide_scalping_direction",
            path="SCALPING_V1 → decide_scalping_direction (LTF abs(buy−sell))",
            legacy=False,
            duplicated=False,
            unused=False,
            conflict=False,
            action="Keep 5. LTF edge is authoritative, not totals.",
            status="AUTHORITATIVE_LIVE",
            actual_effect="BUY/SELL only when LTF core_buy > core_sell + 5 (or reverse). Totals do not decide.",
            safe_to_change=False,
        ),
        _row(
            setting="Daily loss cap",
            source="institutional_trading.config.MAX_DAILY_LOSS_PCT",
            default="40.0",
            live=str(MAX_DAILY_LOSS_PCT),
            consumer="OMS / ITE / live account risk tracker",
            path="MAX_DAILY_LOSS_PCT → ITEConfig.max_daily_loss_pct → OMS",
            legacy=False,
            duplicated=False,
            unused=False,
            conflict=False,
            action="Keep 40.0%. Do not raise.",
            status="AUTHORITATIVE_LIVE",
            actual_effect="OMS/ITE halt new entries when daily loss reaches 40.0%.",
            safe_to_change=False,
        ),
        _row(
            setting="Max open trades",
            source="SCALPING_V1.max_open_trades + align_live_scalp_cap",
            default=10,
            live=SCALPING_V1.max_open_trades,
            consumer="control plane / ITE runtime",
            path="SCALPING_V1.max_open_trades → align_live_scalp_cap → live cap",
            legacy=False,
            duplicated=True,
            unused=False,
            conflict=True,
            action="Do not change without explicit approval. ITEConfig default 1 is leftover.",
            status="AUTHORITATIVE_LIVE",
        ),
        _row(
            setting="Max open trades (ITEConfig default)",
            source="ITEConfig.max_open_trades",
            default=1,
            live=ite.max_open_trades,
            consumer="unused when SCALPING_V1 is applied",
            path="ITEConfig dataclass default; overwritten by ite_config_from_scalping",
            legacy=True,
            duplicated=True,
            unused=True,
            conflict=True,
            action="Document only. Do not treat 1 as live.",
            status="LEGACY_DEFAULT",
        ),
        _row(
            setting="Trading mode",
            source="SCALPING_V1.trading_mode vs ITEConfig.trading_mode",
            default="swing (ITEConfig) / scalping (SCALPING_V1)",
            live=SCALPING_V1.trading_mode,
            consumer="AI scalping profile",
            path="ite_config_from_scalping sets trading_mode=scalping",
            legacy=False,
            duplicated=True,
            unused=False,
            conflict=True,
            action="Live is scalping. ITEConfig swing is leftover default.",
            status="DUAL_SOURCE",
        ),
        _row(
            setting="Quality / confluence",
            source="SCALPING_V1 adaptive bands vs ITEConfig 80/80",
            default="ITEConfig 80/80",
            live=f"q={SCALPING_V1.normal_vol.quality}/c={SCALPING_V1.normal_vol.confidence}",
            consumer="ITE diagnostics required_* vs scalping adaptive bands",
            path="SCALPING_V1.normal_vol → ite_config_from_scalping min_* scores",
            legacy=False,
            duplicated=True,
            unused=False,
            conflict=True,
            action="Do not collapse without a dedicated config task.",
            status="DUAL_SOURCE",
        ),
        _row(
            setting="RR",
            source="SCALPING_V1.min_expected_rr / fixed_tp_r",
            default="1.20",
            live=str(SCALPING_V1.min_expected_rr),
            consumer="sniper RR gate / TP",
            path="SCALPING_V1.min_expected_rr = fixed_tp_r → sniper RR gate",
            legacy=False,
            duplicated=False,
            unused=False,
            conflict=False,
            action="Keep 1.20. Do not loosen.",
            status="AUTHORITATIVE_LIVE",
        ),
        _row(
            setting="News protection",
            source="SCALPING_V1 True vs ITEConfig False",
            default=False,
            live=SCALPING_V1.news_protection_enabled,
            consumer=str(news.get("consumed_by")),
            path="pipeline.NewsProtection.evaluate; calendar only if ECONOMIC_CALENDAR_FEED_URL",
            legacy=False,
            duplicated=True,
            unused=news.get("STATUS") in {"UNWIRED", "UNUSED", "INACTIVE"},
            conflict=True,
            action="Do not enable as a silent veto until a calendar is wired.",
            status=str(news.get("STATUS") or "UNWIRED"),
        ),
        _row(
            setting="Session filter",
            source="ITEConfig.allowed_sessions TRADABLE_SESSIONS_24_7",
            default="24/7 named sessions; weekend/off-hours blocked",
            live="24/7 named sessions; weekend/off-hours blocked",
            consumer="session_filter",
            path="SessionFilter.evaluate in InstitutionalAnalysisPipeline",
            legacy=False,
            duplicated=False,
            unused=False,
            conflict=False,
            action="No change. Do not infer session profitability from a London-only tape.",
            status="AUTHORITATIVE_LIVE",
        ),
        _row(
            setting="Sniper independent families",
            source="sniper_entry len(independent) >= 2 + structural family",
            default=">=2 independent + structure family",
            live=">=2 independent + structure family",
            consumer="sniper_entry.evaluate_sniper_entry",
            path="sniper_entry.evaluate_sniper_entry",
            legacy=False,
            duplicated=False,
            unused=False,
            conflict=False,
            action="Do not weaken.",
            status="AUTHORITATIVE_LIVE",
        ),
        _row(
            setting="ITEConfig min_confluence / min_quality",
            source="ITEConfig 80 / 80",
            default="80/80",
            live=f"{ite.min_confluence_score}/{ite.min_trade_quality_score}",
            consumer="diagnostics display; live scalping uses adaptive bands",
            path="ITEConfig dataclass default; overwritten on scalping profile apply",
            legacy=True,
            duplicated=True,
            unused=True,
            conflict=True,
            action="Research-only. Do not apply 80 as a hidden second gate.",
            status="LEGACY_DEFAULT",
        ),
        _row(
            setting="Risk per trade",
            source="SCALPING_V1.risk_per_trade_pct",
            default=str(DEFAULT_AI_SCALPING_CONFIG.risk_per_trade_pct),
            live=str(SCALPING_V1.risk_per_trade_pct),
            consumer="position sizing / OMS policy",
            path="SCALPING_V1 → ite_config_from_scalping.risk_per_trade_pct",
            legacy=False,
            duplicated=False,
            unused=False,
            conflict=False,
            action="Do not increase leverage.",
            status="AUTHORITATIVE_LIVE",
        ),
        _row(
            setting="Quality floors (structure/momentum/liquidity/PA)",
            source="SCALPING_V1.min_*_score",
            default="60/55/55/45",
            live=(
                f"structure={SCALPING_V1.min_structure_score} "
                f"momentum={SCALPING_V1.min_momentum_score} "
                f"liquidity={SCALPING_V1.min_liquidity_score} "
                f"pa={SCALPING_V1.min_pa_confluence_score}"
            ),
            consumer="AI scalping hard gates",
            path="SCALPING_V1 min_*_score → scalping evaluators",
            legacy=False,
            duplicated=False,
            unused=False,
            conflict=False,
            action="Do not lower floors to manufacture trades.",
            status="AUTHORITATIVE_LIVE",
        ),
    ]
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "never_changes_live_settings": True,
        "settings": rows,
        "news_protection": news,
        "LIVE_EFFECTIVE_CONFIG": [r for r in rows if r.get("STATUS") == "AUTHORITATIVE_LIVE"],
        "LEGACY_CONFIG": [r for r in rows if r.get("LEGACY") or r.get("STATUS") == "LEGACY_DEFAULT"],
        "RESEARCH_ONLY_CONFIG": [
            r
            for r in rows
            if r.get("STATUS") in {"UNWIRED", "DUAL_SOURCE"} or r.get("UNUSED")
        ],
        "UNWIRED_CONFIG": [r for r in rows if r.get("STATUS") == "UNWIRED"],
        "authoritative_call_chain": (
            "SCALPING_V1 is applied through ite_config_from_scalping. "
            "Opportunity 70 lives in probability_selector. "
            "Directional edge 5 lives in SCALPING_V1.direction_edge_margin → direction.py. "
            "ITEConfig dataclass defaults are leftovers unless copied."
        ),
    }
