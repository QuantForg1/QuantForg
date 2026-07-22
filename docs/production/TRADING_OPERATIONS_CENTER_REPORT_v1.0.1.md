# QuantForg v1.0.1 — Institutional Trading Operations Center

**Generated:** 2026-07-22T21:32:40Z
**Scope:** Ops brief, checklist, EOD/weekly/monthly reviews, alerts. Never fabricates metrics. Never modifies strategy, risk, safety, execution, Performance IQ, or Evidence Lab.

## Operational summary

```json
{
  "checklist": {
    "all_passed": false,
    "passed": 7,
    "total": 10,
    "failures": [
      {
        "key": "execution_enabled",
        "label": "Execution Enabled",
        "why": "Execution Enabled failed (current: False)",
        "how_to_resolve": "Set Railway EXECUTION_ENABLED=true; confirm MT5_GATEWAY_BASE_URL; redeploy API (no HTTP route can flip this flag)",
        "value": "False"
      },
      {
        "key": "ops_live",
        "label": "Ops LIVE",
        "why": "Ops LIVE failed (current: SHADOW)",
        "how_to_resolve": "Promote Ops mode SHADOW \u2192 CANARY \u2192 LIVE via POST /ite/ops/launch-readiness/promote (Demo cert required)",
        "value": "SHADOW"
      },
      {
        "key": "evidence_healthy",
        "label": "Evidence Healthy",
        "why": "Evidence Healthy failed (current: gates=blocked; confidence=insufficient)",
        "how_to_resolve": "Ingest live closed trades and replay opportunities into Evidence Lab; raise confidence above insufficient before treating KPIs as stable",
        "value": "gates=blocked; confidence=insufficient"
      }
    ]
  },
  "alerts": 3,
  "executive": {
    "status": "available",
    "operations_status": {
      "all_passed": false,
      "passed_count": 7,
      "total": 10,
      "failures": [
        {
          "key": "execution_enabled",
          "label": "Execution Enabled",
          "why": "Execution Enabled failed (current: False)",
          "how_to_resolve": "Set Railway EXECUTION_ENABLED=true; confirm MT5_GATEWAY_BASE_URL; redeploy API (no HTTP route can flip this flag)",
          "value": "False"
        },
        {
          "key": "ops_live",
          "label": "Ops LIVE",
          "why": "Ops LIVE failed (current: SHADOW)",
          "how_to_resolve": "Promote Ops mode SHADOW \u2192 CANARY \u2192 LIVE via POST /ite/ops/launch-readiness/promote (Demo cert required)",
          "value": "SHADOW"
        },
        {
          "key": "evidence_healthy",
          "label": "Evidence Healthy",
          "why": "Evidence Healthy failed (current: gates=blocked; confidence=insufficient)",
          "how_to_resolve": "Ingest live closed trades and replay opportunities into Evidence Lab; raise confidence above insufficient before treating KPIs as stable",
          "value": "gates=blocked; confidence=insufficient"
        }
      ]
    },
    "performance": {
      "trades": 3,
      "win_rate": 0.6667,
      "profit_factor": 4.3333,
      "expectancy": 10.0
    },
    "evidence": {
      "live_records": 3,
      "replay_opportunities": 12,
      "gates_passed": false
    },
    "confidence": {
      "overall": "insufficient"
    },
    "risk": {
      "maximum_drawdown_pct": 23.0769,
      "recovery_factor": 1.3,
      "note": "From supplied performance risk metrics only"
    },
    "execution": {
      "execution_enabled": false,
      "ops_mode": "SHADOW",
      "checklist_all_passed": false
    },
    "outstanding_actions": [
      "Resolve Execution Enabled: Set Railway EXECUTION_ENABLED=true; confirm MT5_GATEWAY_BASE_URL; redeploy API (no HTTP route can flip this flag)",
      "Resolve Ops LIVE: Promote Ops mode SHADOW \u2192 CANARY \u2192 LIVE via POST /ite/ops/launch-readiness/promote (Demo cert required)",
      "Resolve Evidence Healthy: Ingest live closed trades and replay opportunities into Evidence Lab; raise confidence above insufficient before treating KPIs as stable",
      "Ops alert [high]: Low confidence",
      "Ops alert [medium]: Replay backlog",
      "Ops alert [low]: Repeated NO_TRADE causes",
      "Evidence gates blocked \u2014 grow live/replay/NO_TRADE samples (do not change strategy)",
      "Confidence is insufficient \u2014 treat KPIs as provisional until samples grow"
    ],
    "open_alert_count": 3
  }
}
```

## Daily brief

```json
{
  "status": "available",
  "trading_date": "2026-07-22",
  "expected_sessions": [
    "london",
    "new_york",
    "overlap"
  ],
  "high_impact_news": {
    "status": "available",
    "items": [
      {
        "title": "US CPI",
        "impact": "high",
        "time": "12:30Z"
      }
    ],
    "count": 1,
    "note": "From supplied economic calendar only \u2014 never fabricated"
  },
  "current_market_regime": "trend",
  "volatility_expectation": "normal",
  "evidence_status": {
    "status": "available",
    "live_records": 3,
    "demo_records": 1,
    "replay_opportunities": 12,
    "research_records": 2,
    "no_trade_observations": 3,
    "overall_confidence": "insufficient",
    "gates_passed": false
  },
  "open_operational_alerts": [
    {
      "code": "low_confidence",
      "severity": "high",
      "title": "Low confidence",
      "detail": "Overall confidence is 'insufficient'",
      "suggests_strategy_change": false
    },
    {
      "code": "replay_backlog",
      "severity": "medium",
      "title": "Replay backlog",
      "detail": "Replay coverage 0.024 below threshold \u2014 ingest more historical opportunities",
      "suggests_strategy_change": false
    },
    {
      "code": "repeated_no_trade",
      "severity": "low",
      "title": "Repeated NO_TRADE causes",
      "detail": "Recurring causes: spread too wide\u00d72 (ops awareness only)",
      "suggests_strategy_change": false
    }
  ],
  "open_alert_count": 3,
  "advisory_only": true,
  "note": "Brief uses supplied ops/evidence/calendar facts only"
}
```

## Checklist

```json
{
  "status": "available",
  "all_passed": false,
  "passed_count": 7,
  "total": 10,
  "items": [
    {
      "key": "gateway_connected",
      "label": "Gateway Connected",
      "passed": true,
      "value": "True",
      "why": "",
      "how_to_resolve": "",
      "status": "pass"
    },
    {
      "key": "broker_connected",
      "label": "Broker Connected",
      "passed": true,
      "value": "True",
      "why": "",
      "how_to_resolve": "",
      "status": "pass"
    },
    {
      "key": "mt5_logged_in",
      "label": "MT5 Logged In",
      "passed": true,
      "value": "True",
      "why": "",
      "how_to_resolve": "",
      "status": "pass"
    },
    {
      "key": "market_open",
      "label": "Market Open",
      "passed": true,
      "value": "True",
      "why": "",
      "how_to_resolve": "",
      "status": "pass"
    },
    {
      "key": "xauusd_ready",
      "label": "XAUUSD Ready",
      "passed": true,
      "value": "True",
      "why": "",
      "how_to_resolve": "",
      "status": "pass"
    },
    {
      "key": "risk_ready",
      "label": "Risk Ready",
      "passed": true,
      "value": "True",
      "why": "",
      "how_to_resolve": "",
      "status": "pass"
    },
    {
      "key": "safety_ready",
      "label": "Safety Ready",
      "passed": true,
      "value": "True",
      "why": "",
      "how_to_resolve": "",
      "status": "pass"
    },
    {
      "key": "execution_enabled",
      "label": "Execution Enabled",
      "passed": false,
      "value": "False",
      "why": "Execution Enabled failed (current: False)",
      "how_to_resolve": "Set Railway EXECUTION_ENABLED=true; confirm MT5_GATEWAY_BASE_URL; redeploy API (no HTTP route can flip this flag)",
      "status": "fail"
    },
    {
      "key": "ops_live",
      "label": "Ops LIVE",
      "passed": false,
      "value": "SHADOW",
      "why": "Ops LIVE failed (current: SHADOW)",
      "how_to_resolve": "Promote Ops mode SHADOW \u2192 CANARY \u2192 LIVE via POST /ite/ops/launch-readiness/promote (Demo cert required)",
      "status": "fail"
    },
    {
      "key": "evidence_healthy",
      "label": "Evidence Healthy",
      "passed": false,
      "value": "gates=blocked; confidence=insufficient",
      "why": "Evidence Healthy failed (current: gates=blocked; confidence=insufficient)",
      "how_to_resolve": "Ingest live closed trades and replay opportunities into Evidence Lab; raise confidence above insufficient before treating KPIs as stable",
      "status": "fail"
    }
  ],
  "failures": [
    {
      "key": "execution_enabled",
      "label": "Execution Enabled",
      "why": "Execution Enabled failed (current: False)",
      "how_to_resolve": "Set Railway EXECUTION_ENABLED=true; confirm MT5_GATEWAY_BASE_URL; redeploy API (no HTTP route can flip this flag)",
      "value": "False"
    },
    {
      "key": "ops_live",
      "label": "Ops LIVE",
      "why": "Ops LIVE failed (current: SHADOW)",
      "how_to_resolve": "Promote Ops mode SHADOW \u2192 CANARY \u2192 LIVE via POST /ite/ops/launch-readiness/promote (Demo cert required)",
      "value": "SHADOW"
    },
    {
      "key": "evidence_healthy",
      "label": "Evidence Healthy",
      "why": "Evidence Healthy failed (current: gates=blocked; confidence=insufficient)",
      "how_to_resolve": "Ingest live closed trades and replay opportunities into Evidence Lab; raise confidence above insufficient before treating KPIs as stable",
      "value": "gates=blocked; confidence=insufficient"
    }
  ],
  "note": "Checklist is advisory readiness \u2014 never bypasses Risk/Safety"
}
```

## End-of-day

```json
{
  "status": "available",
  "trades": 3,
  "win_rate": 0.6667,
  "profit_factor": 4.3333,
  "expectancy": 10.0,
  "drawdown": 23.0769,
  "session_breakdown": {
    "status": "available",
    "overall": {
      "status": "available",
      "trade_count": 3,
      "win_rate": 0.6667,
      "expectancy": 10.0,
      "profit_factor": 4.3333,
      "avg_duration_seconds": 3800.0,
      "average_rr": 0.8667,
      "net_pnl": 30.0
    },
    "sessions": {
      "sydney": {
        "status": "empty",
        "trade_count": 0,
        "win_rate": null,
        "expectancy": null,
        "profit_factor": null,
        "avg_duration_seconds": null,
        "average_rr": null,
        "net_pnl": null
      },
      "tokyo": {
        "status": "empty",
        "trade_count": 0,
        "win_rate": null,
        "expectancy": null,
        "profit_factor": null,
        "avg_duration_seconds": null,
        "average_rr": null,
        "net_pnl": null
      },
      "london": {
        "status": "available",
        "trade_count": 1,
        "win_rate": 1.0,
        "expectancy": 25.0,
        "profit_factor": null,
        "avg_duration_seconds": 4200.0,
        "average_rr": 2.1,
        "net_pnl": 25.0
      },
      "new_york": {
        "status": "available",
        "trade_count": 1,
        "win_rate": 0.0,
        "expectancy": -9.0,
        "profit_factor": 0.0,
        "avg_duration_seconds": 2400.0,
        "average_rr": -0.9,
        "net_pnl": -9.0
      },
      "overlap": {
        "status": "available",
        "trade_count": 1,
        "win_rate": 1.0,
        "expectancy": 14.0,
        "profit_factor": null,
        "avg_duration_seconds": 4800.0,
        "average_rr": 1.4,
        "net_pnl": 14.0
      },
      "off_hours": {
        "status": "empty",
        "trade_count": 0,
        "win_rate": null,
        "expectancy": null,
        "profit_factor": null,
        "avg_duration_seconds": null,
        "average_rr": null,
        "net_pnl": null
      }
    },
    "note": "Sessions evaluated separately \u2014 never mixed"
  },
  "no_trade_summary": {
    "status": "available",
    "total_decisions": 3,
    "no_trade_count": 3,
    "no_trade_rate": 1.0,
    "sample_reasons": [
      "spread too wide",
      "spread too wide",
      "mtf_not_aligned"
    ],
    "assessment": "No Trade path exists in TradeDecisionEngine; loss-reduction proof requires paired counterfactual replay",
    "reason_histogram": {
      "spread too wide": 2,
      "mtf_not_aligned": 1
    },
    "estimated_bad_trades_avoided": {
      "count_proxy": 3,
      "status": "research_only",
      "note": "Proxy count of NO_TRADE decisions with risk/quality reasons \u2014 not realized PnL; never fabricates savings"
    },
    "research_only": true
  },
  "replay_coverage": {
    "replay_opportunities": 12,
    "coverage": 0.024
  },
  "evidence_growth": {
    "live_records": 3,
    "demo_records": 1,
    "replay_opportunities": 12,
    "research_records": 2,
    "no_trade_observations": 3
  },
  "note": "EOD aggregates supplied Performance IQ + Evidence Lab facts only",
  "never_fabricates_metrics": true
}
```

## Weekly review

```json
{
  "status": "available",
  "current_week": {
    "label": "current_week",
    "status": "available",
    "trades": 3,
    "win_rate": 0.6667,
    "profit_factor": 4.3333,
    "expectancy": 10.0,
    "drawdown": 23.0769,
    "net_pnl": 30.0
  },
  "previous_week": {
    "label": "previous_week",
    "status": "available",
    "trades": 2,
    "win_rate": 0.5,
    "profit_factor": 0.6667,
    "expectancy": -2.0,
    "drawdown": 150.0,
    "net_pnl": -4.0
  },
  "improvements": [
    "Win rate: 0.5 \u2192 0.6667 (\u0394 +0.1667)",
    "Profit factor: 0.6667 \u2192 4.3333 (\u0394 +3.6666)",
    "Expectancy: -2.0 \u2192 10.0 (\u0394 +12.0)",
    "Drawdown: 150.0 \u2192 23.0769 (\u0394 -126.9231)",
    "Net P/L: -4.0 \u2192 30.0 (\u0394 +34.0)"
  ],
  "regressions": [],
  "unknowns": [],
  "advisory_only": true,
  "never_suggests_strategy_changes": true
}
```

## Monthly review

```json
{
  "status": "available",
  "performance": {
    "trades": 3,
    "win_rate": 0.6667,
    "profit_factor": 4.3333,
    "expectancy": 10.0,
    "drawdown": 23.0769,
    "net_pnl": 30.0
  },
  "risk": {
    "maximum_drawdown_pct": 23.0769,
    "recovery_factor": 1.3,
    "note": "From supplied performance risk metrics only"
  },
  "execution_quality": {
    "status": "unavailable",
    "note": "Execution quality not supplied \u2014 never fabricated"
  },
  "evidence_growth": {
    "live_records": 3,
    "replay_opportunities": 12,
    "research_records": 2,
    "no_trade_observations": 3,
    "gates_passed": false
  },
  "confidence_growth": {
    "overall_confidence": "insufficient",
    "lane_samples": {
      "live_closed_trades": {
        "sample_size": 3,
        "confidence": "insufficient",
        "coverage": 0.06
      },
      "replay_opportunities": {
        "sample_size": 12,
        "confidence": "insufficient",
        "coverage": 0.024
      },
      "no_trade_observations": {
        "sample_size": 3,
        "confidence": "insufficient",
        "coverage": 0.03
      }
    }
  },
  "open_research_topics": [
    "Clear Evidence Lab gates before strategy-change research",
    "Grow sample size to raise overall confidence"
  ],
  "advisory_only": true,
  "never_suggests_strategy_changes": true
}
```

## Operational alerts

```json
{
  "status": "available",
  "alert_count": 3,
  "alerts": [
    {
      "code": "low_confidence",
      "severity": "high",
      "title": "Low confidence",
      "detail": "Overall confidence is 'insufficient'",
      "suggests_strategy_change": false
    },
    {
      "code": "replay_backlog",
      "severity": "medium",
      "title": "Replay backlog",
      "detail": "Replay coverage 0.024 below threshold \u2014 ingest more historical opportunities",
      "suggests_strategy_change": false
    },
    {
      "code": "repeated_no_trade",
      "severity": "low",
      "title": "Repeated NO_TRADE causes",
      "detail": "Recurring causes: spread too wide\u00d72 (ops awareness only)",
      "suggests_strategy_change": false
    }
  ],
  "never_suggests_strategy_changes": true,
  "note": "Alerts are operational only \u2014 never strategy-change proposals"
}
```

## Recommendations (ops only — never strategy changes)

- Resolve Execution Enabled: Set Railway EXECUTION_ENABLED=true; confirm MT5_GATEWAY_BASE_URL; redeploy API (no HTTP route can flip this flag)
- Resolve Ops LIVE: Promote Ops mode SHADOW → CANARY → LIVE via POST /ite/ops/launch-readiness/promote (Demo cert required)
- Resolve Evidence Healthy: Ingest live closed trades and replay opportunities into Evidence Lab; raise confidence above insufficient before treating KPIs as stable
- Ops alert [high]: Low confidence
- Ops alert [medium]: Replay backlog
- Ops alert [low]: Repeated NO_TRADE causes
- Evidence gates blocked — grow live/replay/NO_TRADE samples (do not change strategy)
- Confidence is insufficient — treat KPIs as provisional until samples grow
- Recommendations are operational only — never modify strategy, risk, safety, execution, Performance IQ, or Evidence Lab

## Hard locks

- never_modifies_strategy: True
- never_modifies_risk_safety_execution: True
- never_modifies_performance_intelligence: True
- never_modifies_replay_evidence_lab: True
- never_fabricates_metrics: True
- recommendations_only: True
- never_suggests_strategy_changes: True

