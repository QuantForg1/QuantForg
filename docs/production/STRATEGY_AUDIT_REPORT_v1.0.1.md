# QuantForg v1.0.1 — XAUUSD Strategy Audit Report

**Generated:** 2026-07-22T20:37:58Z
**Scope:** Strategy evidence audit only. No architecture, AI, Risk, Safety, or Execution Pipeline changes. Never auto-modifies production strategy.

## Verdict

Feature-complete ITE SMC stack is logically consistent. Live statistical power for session/regime exit quality remains limited until more tagged trades and decisions are supplied. Recommendations only.

## Evidence summary

```json
{
  "completed_trades": 0,
  "decisions": 0,
  "signal_facts_supplied": true,
  "recommendation_count": 15,
  "component_findings": 13,
  "source": "read_only_xauusd_strategy_audit"
}
```

## Component audit

- **Smart Money Concepts** (`consistent`): SMC is a composite of Structure + Liquidity + OB + FVG + MTF trend via ConfluenceEngine; requires an active OB or FVG zone
  - Evidence: `app/domain/institutional_trading/confluence.py (no_smc_zone)`
- **BOS** (`consistent`): Break of Structure detected on primary TF (H1); contributes structure factor; directional bias from latest BOS
  - Evidence: `market_structure/structure_analyzer.py + confluence structure`
- **CHOCH** (`consistent`): Change of Character tracked alongside BOS; both raise structure score when present — ensure direction agrees with MTF bias
  - Evidence: `market_structure models + confluence factors['structure']`
- **Order Blocks** (`consistent`): OB engine validates/mitigates/breaks zones; confluence requires active OB or FVG for tradable direction
  - Evidence: `order_block/* + confluence order_blocks branch`
- **Fair Value Gaps** (`consistent`): FVG detector + fill/invalidation/quality; pairs with OB as SMC zone requirement
  - Evidence: `fair_value_gap/* + confluence fvgs branch`
- **Liquidity Sweeps** (`consistent`): Sweeps/pools/equal H/L feed liquidity factor; sweeps score higher than pools alone
  - Evidence: `liquidity/sweep_detector.py + confluence liquidity`
- **Market Structure** (`consistent`): Swing → BOS/CHoCH → trend snapshot; pipeline order Structure before Liquidity/OB/FVG
  - Evidence: `institutional_trading/pipeline.py`
- **Trend Filter** (`consistent`): MTF hierarchy H4/H1/M15/M5; H4 must agree with H1 or confluence rejects mtf_not_aligned
  - Evidence: `trend_engine.py + confluence MTF gate`
- **Session Filter** (`consistent`): Default allowed sessions: london, new_york, london_ny_overlap. Sydney/Tokyo classified but excluded from ITE entries by default
  - Evidence: `session_filter.py + ITEConfig.allowed_sessions`
- **Volatility Filter** (`gap`): ATR soft/hard factors in confluence + robot volatility filter; qualitative VolatilityProfileResolver is observational — ensure live ATR always supplied on status polls
  - Evidence: `confluence ATR factors + ai_trading_robot/filters.py`
- **Frontend strategy toggles** (`ui_only`): localStorage module toggles (SMC/BOS/CHOCH/OB/FVG/Sweep) do not gate ConfluenceEngine — cosmetic arming only; risk of operator believing modules are independently wired
  - Evidence: `frontend/src/lib/auto-trading/strategy-modules.ts`
- **Dual signal paths** (`complexity`): Boolean StrategyRuntime preconditions exist alongside full ITE ConfluenceEngine — potential duplicated/conflicting signal surfaces if both are operator-facing
  - Evidence: `strategy_runtime.py vs institutional_decision_pipeline.py`
- **News Protection** (`gap`): news_protection_enabled=False until calendar feed wired — news regime evidence cannot be claimed
  - Evidence: `ITEConfig.news_protection_enabled`

## Signal quality (example / supplied facts)

**Signal Quality 92 / 100** (`high_confidence`)

Reason: Trend aligned (MTF); BOS present; Liquidity sweep confirmed; SMC order block aligned; Fair value gap present; Session filter passed; Spread acceptable; Volatility filter passed; SMC aligned

## Entry quality

```json
{
  "status": "insufficient_data",
  "message": "No completed trades supplied \u2014 never fabricates entry quality"
}
```

## Exit quality

```json
{
  "status": "insufficient_data",
  "message": "No completed trades supplied \u2014 never fabricates exit quality"
}
```

## No Trade quality

```json
{
  "status": "insufficient_data",
  "message": "No decision journal supplied \u2014 cannot prove No Trade reduced losses",
  "recommendation": "Need more No-Trade / reject decision samples tagged"
}
```

## Session performance (never mixed)

```json
{
  "status": "insufficient_data",
  "buckets": {},
  "note": "Sessions never mixed \u2014 each bucket is independent"
}
```

## Market regime (never mixed)

```json
{
  "status": "insufficient_data",
  "buckets": {},
  "note": "Regimes never mixed \u2014 each bucket is independent"
}
```

## Recommendations (only — never auto-applied)

- Need more Sydney evidence (have 0, want >=20)
- Need more Tokyo evidence (have 0, want >=20)
- Need more London evidence (have 0, want >=20)
- Need more New York evidence (have 0, want >=20)
- Need more Overlap evidence (have 0, want >=20)
- Need more Trend samples (have 0, want >=15)
- Need more Range samples (have 0, want >=15)
- Need more High Volatility samples (have 0, want >=15)
- Need more Low Volatility samples (have 0, want >=15)
- Need more News samples (have 0, want >=10)
- Need more completed XAUUSD trade samples (have 0, want >=50)
- Need more Decision Engine NO_TRADE / WATCH samples for refusal quality
- Clarify operator UX: frontend strategy toggles are preferences only
- Prefer single operator-facing signal path (ITE Confluence) to avoid duplicated signals
- Need more News replay once calendar blackout is wired

## Human review

### Strengths

- Deterministic SMC confluence with MTF alignment hard gate
- OB or FVG zone required — reduces naked structure entries
- Session filter defaults to London / New York / Overlap only
- Trade quality score (0-100) with explicit reject band
- NO_TRADE / WATCH decisions exist before OMS
- PME exit ladder (BE / partial / trail) is separate from entry logic

### Weaknesses

- Frontend strategy toggles do not wire into ConfluenceEngine
- Dual signal surfaces (StrategyRuntime vs ITE) add complexity
- News protection disabled — news regime unproven
- Sparse live journals limit session/regime statistical power
- ATR volatility may be unevaluated on status-only polls

### Unknowns

- Realized RR by session without tagged live deals
- Whether No Trade decisions reduced losses (needs counterfactual replay)
- Sydney/Tokyo edge if sessions were ever enabled
- Stop-out causes distribution without exit_cause tags

### Open questions

- Should operator UI hide localStorage toggles or bind them read-only to ITE?
- Minimum sample size per session before expanding allowed_sessions?
- When should news_protection_enabled flip after calendar certification?
- Is StrategyRuntime still needed for operator desks?

### Future replay plan

- Replay London-only XAUUSD bars with confluence journal export
- Replay New York + Overlap separately — never mix buckets
- Tagged News blackout replay once calendar feed is certified
- Trend vs Range labeled walk-forward with fixed ITEConfig
- No-Trade counterfactual: apply rejected signals hypothetically offline

## Hard locks

- never_auto_modifies_strategy: true
- never_modifies_risk_safety_execution: true
- never_auto_applies: true

