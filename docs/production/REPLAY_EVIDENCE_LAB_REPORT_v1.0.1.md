# QuantForg v1.0.1 — Institutional Replay & Evidence Lab

**Generated:** 2026-07-22T21:13:29Z
**Scope:** Historical replay + segregated evidence lanes. Never fabricates metrics. Never modifies strategy, risk, safety, execution, or Performance Intelligence.

## Evidence summary

```json
{
  "bars_loaded": 3,
  "replay_opportunities": 3,
  "live_records": 1,
  "demo_records": 1,
  "research_records": 2,
  "no_trade_observations": 2,
  "overall_confidence": "insufficient",
  "gates_passed": false,
  "may_recommend_strategy_changes": false
}
```

## Replay report

```json
{
  "status": "available",
  "bars_loaded": 3,
  "opportunities_recorded": 3,
  "opportunities": [
    {
      "timestamp": "2026-07-20T08:00:00+00:00",
      "session": "london",
      "market_regime": "trend",
      "trend": "bullish",
      "bos": true,
      "choch": false,
      "liquidity_sweep": true,
      "order_block": true,
      "fair_value_gap": false,
      "confluence_score": 92.0,
      "decision": "BUY",
      "no_trade_reason": null,
      "direction": "BUY",
      "entry": 2402.0,
      "exit": 2410.0,
      "stop_loss": null,
      "take_profit": null,
      "rr": 2.0,
      "hold_time": 300.0,
      "bars_after": null,
      "symbol": "XAUUSD",
      "source": "replay",
      "research_only": true,
      "bar_index": 0
    },
    {
      "timestamp": "2026-07-20T08:05:00+00:00",
      "session": "london",
      "market_regime": "high_volatility",
      "trend": "bullish",
      "bos": false,
      "choch": true,
      "liquidity_sweep": false,
      "order_block": false,
      "fair_value_gap": true,
      "confluence_score": 78.0,
      "decision": "NO_TRADE",
      "no_trade_reason": "spread too wide",
      "direction": "BUY",
      "entry": 2408.0,
      "exit": null,
      "stop_loss": 2400.0,
      "take_profit": 2420.0,
      "rr": null,
      "hold_time": null,
      "bars_after": [
        {
          "high": 2415.0,
          "low": 2405.0
        },
        {
          "high": 2418.0,
          "low": 2399.0
        }
      ],
      "symbol": "XAUUSD",
      "source": "replay",
      "research_only": true,
      "bar_index": 1
    },
    {
      "timestamp": "2026-07-21T14:00:00+00:00",
      "session": "new_york",
      "market_regime": "range",
      "trend": "neutral",
      "bos": false,
      "choch": false,
      "liquidity_sweep": true,
      "order_block": true,
      "fair_value_gap": true,
      "confluence_score": 84.0,
      "decision": "NO_TRADE",
      "no_trade_reason": "mtf_not_aligned",
      "direction": "SELL",
      "entry": 2390.0,
      "exit": null,
      "stop_loss": 2398.0,
      "take_profit": 2375.0,
      "rr": null,
      "hold_time": null,
      "bars_after": [
        {
          "high": 2392.0,
          "low": 2380.0
        },
        {
          "high": 2385.0,
          "low": 2374.0
        }
      ],
      "symbol": "XAUUSD",
      "source": "replay",
      "research_only": true
    }
  ]
}
```

## Evidence coverage report

```json
{
  "status": "available",
  "lanes": {
    "live": 1,
    "demo": 1,
    "replay": 3,
    "research": 2
  },
  "total_records": 7,
  "never_mix_evidence_lanes": true,
  "note": "Live, Demo, Replay, and Research are stored separately",
  "thresholds": {
    "min_live_closed_trades": 50,
    "min_replay_opportunities": 500,
    "min_no_trade_observations": 100
  },
  "gate_status": false
}
```

## Confidence report

```json
{
  "status": "available",
  "overall_confidence": "insufficient",
  "kpis": [
    {
      "name": "replay_win_rate",
      "value": 1.0,
      "sample_size": 1,
      "confidence": "insufficient",
      "coverage": 0.02,
      "required_sample": 50,
      "status": "available"
    },
    {
      "name": "replay_opportunity_count",
      "value": 3,
      "sample_size": 3,
      "confidence": "insufficient",
      "coverage": 0.006,
      "required_sample": 500,
      "status": "available"
    },
    {
      "name": "no_trade_rate",
      "value": 0.6667,
      "sample_size": 3,
      "confidence": "insufficient",
      "coverage": 0.03,
      "required_sample": 100,
      "status": "available"
    }
  ],
  "lane_samples": {
    "live_closed_trades": {
      "sample_size": 1,
      "confidence": "insufficient",
      "coverage": 0.02
    },
    "replay_opportunities": {
      "sample_size": 3,
      "confidence": "insufficient",
      "coverage": 0.006
    },
    "no_trade_observations": {
      "sample_size": 2,
      "confidence": "insufficient",
      "coverage": 0.02
    }
  },
  "note": "Confidence is advisory \u2014 never upgrades fabricated samples"
}
```

## Evidence gates

```json
{
  "status": "available",
  "thresholds": {
    "min_live_closed_trades": 50,
    "min_replay_opportunities": 500,
    "min_no_trade_observations": 100
  },
  "checks": [
    {
      "id": "live_closed_trades",
      "label": "Live closed trades",
      "observed": 1,
      "required": 50,
      "passed": false
    },
    {
      "id": "replay_opportunities",
      "label": "Replay opportunities",
      "observed": 3,
      "required": 500,
      "passed": false
    },
    {
      "id": "no_trade_observations",
      "label": "NO_TRADE observations",
      "observed": 2,
      "required": 100,
      "passed": false
    }
  ],
  "all_passed": false,
  "may_recommend_strategy_changes": false,
  "advisory_only": true,
  "never_auto_modifies_strategy": true,
  "note": "Strategy-change recommendations remain blocked until all evidence gates pass \u2014 gates are advisory and never mutate production"
}
```

## Counterfactual (research only)

```json
{
  "research_only": true,
  "feeds_production_kpis": false,
  "no_trade_count": 2,
  "result_histogram": {
    "sl_first": 1,
    "tp_first": 1
  }
}
```

## Open questions

- Which evidence lane is the bottleneck for gate clearance?

## Recommendations (never auto-applied)

- Evidence gate blocked: need 50 live closed trades (have 1)
- Evidence gate blocked: need 500 replay opportunities (have 3)
- Evidence gate blocked: need 100 no_trade observations (have 2)
- Do not recommend production strategy changes until all evidence gates pass
- Research: 1 NO_TRADE counterfactuals hit SL first (research only — do not feed live KPIs)
- Research: 1 NO_TRADE counterfactuals hit TP first (research only — do not feed live KPIs)
- Overall confidence is insufficient — expand sample before acting on KPIs
- Never auto-modify strategy, risk, safety, execution, or Performance IQ

## Hard locks

- never_modifies_strategy: True
- never_modifies_risk_safety_execution: True
- never_modifies_performance_intelligence: True
- never_fabricates_metrics: True
- counterfactual_research_only: True
- never_mix_evidence_lanes: True

