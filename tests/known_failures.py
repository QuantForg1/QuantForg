"""Tracked known failures — applied as xfail(strict=True) by tests/conftest.py.

Every entry already failed on main (37b5ce98) before FT-4. Strict means a test
that starts passing turns CI red until its entry is removed here, so this list
can only shrink. One GitHub issue per group (see GROUP_ISSUES).

Never add a new test here to make CI green; fix it or ask the owner.
"""

from __future__ import annotations

GROUP_ISSUES: dict[str, str] = {
    "gold-only": (
        "#67 Tests still assert non-Gold " "(FX/crypto/broker-discovered) behaviour"
    ),
    "ui-copy": "#68 Frontend source-string tests pinned to old UI copy",
    "owner-policy": (
        "#69 Tests pinned to the pre-owner 80% / $6-$20 risk policy " "(fixed by FT-1)"
    ),
    "strategy-rr": (
        "#70 SCALPING_V1 min_expected_rr 1.20 vs owner 1.50 " "(ATR-geometry cap)"
    ),
    "infra": (
        "#71 Environment/infra tests " "(PowerShell encoding, Weltrade HTTP, readiness)"
    ),
    "safety-followup": "#72 Canary abnormal OMS outcome must halt auto trading",
}

_G = "tests/unit/"

KNOWN_FAILURES: dict[str, tuple[str, str]] = {
    # --- gold-only: QuantForg trades XAUUSD only; rewrite to assert rejection ---
    _G
    + "test_autonomous_execution_context.py::"
    + "test_mt5_chart_xauusd_does_not_become_execution_symbol": (
        "gold-only",
        "uses NZDUSD_I as execution symbol; rejected by Gold-only",
    ),
    _G
    + "test_autonomous_execution_context.py::"
    + "test_terminal_xauusd_does_not_alter_oms_symbol": (
        "gold-only",
        "uses NZDUSD_I as OMS symbol; rejected by Gold-only",
    ),
    _G
    + "test_cycle_timeout_budget.py::test_fx_and_crypto_remain_in_execution_focus": (
        "gold-only",
        "expects FX/crypto in execution focus",
    ),
    _G
    + "test_market_universe.py::test_registry_discovery_is_not_capped_by_probe_limit": (
        "gold-only",
        "expects >128 discovered desks; Gold-only universe is 1",
    ),
    _G
    + "test_multi_market_live_execution.py::"
    + "test_existing_oms_maps_limit_without_converting_to_market": (
        "gold-only",
        "places EURUSD limit order",
    ),
    _G
    + "test_multi_market_live_execution.py::"
    + "test_parse_order_intent_buy_and_sell_non_gold": (
        "gold-only",
        "parses EURUSD intents",
    ),
    _G
    + "test_symbol_management_and_signals.py::"
    + "test_scalping_enforces_operator_multi_symbol_allowlist": (
        "gold-only",
        "multi-symbol allowlist",
    ),
    _G
    + "test_symbol_management_and_signals.py::"
    + "test_signal_center_uses_live_scan_not_fabricated": (
        "gold-only",
        "expects live multi-asset scan source",
    ),
    _G
    + "test_terminal_symbol_not_in_execution.py::"
    + "test_oms_intent_ignores_a_terminal_view_symbol": (
        "gold-only",
        "non-Gold decision symbol",
    ),
    _G
    + "test_terminal_symbol_not_in_execution.py::"
    + "test_oms_intent_uses_decision_symbol_not_gold_home": (
        "gold-only",
        "non-Gold decision symbol",
    ),
    _G
    + "test_phase61_trader_ux.py::test_execution_universe_remains_broker_discovered": (
        "gold-only",
        "expects MULTI_SYMBOL_ENABLED=true in frontend policy",
    ),
    _G
    + "test_phase61_trader_ux.py::test_markets_shows_full_broker_universe_contract": (
        "gold-only",
        "expects broker-discovered universe copy",
    ),
    # --- ui-copy: assertions grep .tsx sources for copy that changed ---
    _G
    + "test_api_reliability_guards.py::test_api_client_dedupes_health_gets": (
        "ui-copy",
        "greps api client for inflightGets",
    ),
    _G
    + "test_api_reliability_guards.py::test_auth_boot_timeout_bounded": (
        "ui-copy",
        "greps auth context for SESSION_BOOT_TIMEOUT_MS",
    ),
    _G
    + "test_phase59_trader_ux.py::test_single_runtime_and_no_execute_controls": (
        "ui-copy",
        "greps for RESEARCH_SIGNAL copy",
    ),
    _G
    + "test_phase60_trader_ux.py::test_signals_remain_research_only": (
        "ui-copy",
        "greps for 'Strongest edge'",
    ),
    _G
    + "test_phase61_trader_ux.py::test_signals_remain_research_only_and_consistent": (
        "ui-copy",
        "greps for RESEARCH_INDEPENDENT_COPY",
    ),
    _G
    + "test_phase62_trader_ux.py::test_broker_form_stays_password_safe_and_simple": (
        "ui-copy",
        "greps for 'Verify Connection'",
    ),
    _G
    + "test_phase62_trader_ux.py::test_signals_are_broker_independent": (
        "ui-copy",
        "forbids marketUniverseApi import in signals page",
    ),
    _G
    + "test_phase63_trader_ux.py::"
    + "test_analysis_does_not_auto_start_live_trading_robot": (
        "ui-copy",
        "greps for 'never automatic'",
    ),
    _G
    + "test_phase63_trader_ux.py::test_signals_desk_is_broker_independent_and_honest": (
        "ui-copy",
        "forbids marketUniverseApi import in signals desk",
    ),
    # --- owner-policy: fixed by FT-1 (#66); remove when it merges ---
    _G
    + "test_portfolio_risk_engine_v2.py::TestPortfolioBookAndAllocation::"
    + "test_never_force_min_lot": (
        "owner-policy",
        "reason code changed with the $6-$20 band",
    ),
    # --- strategy-rr ---
    _G
    + "test_ai_scalping_v6_1_hardening.py::test_v61_version_preserves_v6_safety": (
        "strategy-rr",
        "min_expected_rr 1.20 != fixed_tp_r 1.50",
    ),
    _G
    + "test_ai_scalping_v6_3_adaptive.py::"
    + "test_v63_version_preserves_quality_and_risk": (
        "strategy-rr",
        "min_expected_rr 1.20 != fixed_tp_r 1.50",
    ),
    # --- infra ---
    _G
    + "test_weltrade_integration.py::TestWeltradeConnectHTTP::"
    + "test_http_gateway_unavailable_returns_503_with_detail": (
        "infra",
        "HTTP mapping of gateway-unavailable changed",
    ),
    _G
    + "test_weltrade_integration.py::TestWeltradeConnectHTTP::"
    + "test_http_login_failure_preserves_original_error": (
        "infra",
        "login failure message mapping changed",
    ),
    _G
    + "test_synthetic_signal_once.py::test_signal_center_marks_test_synthetic_source": (
        "infra",
        "synthetic signal source not projected into signal center",
    ),
    _G
    + "test_synthetic_signal_once.py::"
    + "test_synthetic_signal_once_projects_and_disarms": (
        "infra",
        "synthetic signal projection/disarm",
    ),
    _G
    + "test_production_hardening_v6.py::test_lifecycle_stages_cover_full_path": (
        "infra",
        "lifecycle stage order (FIRST_BLOCKING_GATE vs EXIT)",
    ),
    _G
    + "test_auto_trading_paper_path.py::"
    + "test_paper_auto_trade_path_signal_to_oms_audit": (
        "infra",
        "paper auto-trade path audit",
    ),
    # --- safety-followup: must be fixed before go-live (FT-7) ---
    _G
    + "test_institutional_trading_phase_c.py::TestExecutionBridgePhaseC::"
    + "test_canary_abnormal_oms_halts_auto_trading": (
        "safety-followup",
        "abnormal canary OMS outcome does not reach OMS/halt",
    ),
}
