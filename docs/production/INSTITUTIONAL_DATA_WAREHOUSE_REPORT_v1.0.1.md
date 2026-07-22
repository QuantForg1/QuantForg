# QuantForg v1.0.1 — Institutional Data Warehouse

**Generated:** 2026-07-22T22:04:23Z
**Scope:** Read-only analytics warehouse. Never modifies production records or trading behaviour.

## Evidence summary

```json
{
  "total_records": 18,
  "domains_populated": 13,
  "domains_total": 13,
  "completeness_ratio": 0.5556,
  "cross_domain_correlations": 1,
  "read_only": true
}
```

## Inventory

```json
{
  "status": "available",
  "domains": {
    "market": 1,
    "trades": 2,
    "orders": 1,
    "signals": 1,
    "risk": 1,
    "safety": 1,
    "execution": 2,
    "performance": 1,
    "replay": 2,
    "evidence": 3,
    "governance": 1,
    "configuration": 1,
    "reports": 1
  },
  "total_records": 18,
  "ingest_batches": 13,
  "read_only": true,
  "never_modifies_production_records": true
}
```

## Analytics

```json
{
  "performance_by_strategy_version": {
    "status": "available",
    "by_strategy_version": {
      "v1.0.1": {
        "trades": 2,
        "win_rate": 0.5,
        "net_pnl": 16.0,
        "expectancy": 8.0
      }
    },
    "read_only": true
  },
  "performance_by_session": {
    "status": "available",
    "by_session": {
      "london": {
        "trades": 1,
        "win_rate": 1.0,
        "net_pnl": 25.0,
        "expectancy": 25.0
      },
      "new_york": {
        "trades": 1,
        "win_rate": 0.0,
        "net_pnl": -9.0,
        "expectancy": -9.0
      }
    },
    "read_only": true
  },
  "performance_by_regime": {
    "status": "available",
    "by_regime": {
      "trend": {
        "trades": 1,
        "win_rate": 1.0,
        "net_pnl": 25.0,
        "expectancy": 25.0
      },
      "range": {
        "trades": 1,
        "win_rate": 0.0,
        "net_pnl": -9.0,
        "expectancy": -9.0
      }
    },
    "read_only": true
  },
  "no_trade_analysis": {
    "status": "available",
    "no_trade_count": 1,
    "reason_histogram": {
      "spread too wide": 1
    },
    "read_only": true,
    "note": "Analytics only \u2014 never fabricates avoided PnL"
  },
  "governance_timeline": {
    "status": "available",
    "count": 1,
    "steps": [
      {
        "timestamp": "2026-07-22T09:05:00Z",
        "action": "ops_promotion",
        "actor": "owner.bob",
        "previous_state": "SHADOW",
        "new_state": "CANARY",
        "correlation_id": "corr-idw-demo-1"
      }
    ],
    "read_only": true
  },
  "replay_coverage": {
    "status": "available",
    "replay_records": 2,
    "market_bars": 1,
    "coverage_ratio": 0.004,
    "target_replay_opportunities": 500,
    "read_only": true,
    "note": "Coverage vs advisory threshold of 500 replay opportunities"
  },
  "evidence_growth": {
    "status": "available",
    "total": 3,
    "by_environment": {
      "demo": 3
    },
    "read_only": true
  },
  "risk_event_history": {
    "status": "available",
    "count": 2,
    "events": [
      {
        "timestamp": "2026-07-20T15:01:00Z",
        "domain": "risk",
        "trade_id": null,
        "correlation_id": "corr-idw-demo-1",
        "action": "daily_loss_check",
        "severity": "info"
      },
      {
        "timestamp": "2026-07-22T09:12:00Z",
        "domain": "safety",
        "trade_id": null,
        "correlation_id": "corr-idw-demo-1",
        "action": "kill_switch_armed",
        "severity": "critical"
      }
    ],
    "read_only": true
  },
  "read_only": true
}
```

## Reports

```json
{
  "warehouse_health_report": {
    "report": "warehouse_health",
    "status": "available",
    "total_records": 18,
    "domains": {
      "market": 1,
      "trades": 2,
      "orders": 1,
      "signals": 1,
      "risk": 1,
      "safety": 1,
      "execution": 2,
      "performance": 1,
      "replay": 2,
      "evidence": 3,
      "governance": 1,
      "configuration": 1,
      "reports": 1
    },
    "empty_domains": [],
    "ingest_batches": 13,
    "healthy": true,
    "read_only": true
  },
  "data_coverage_report": {
    "report": "data_coverage",
    "status": "available",
    "coverage": {
      "market": {
        "observed": 1,
        "target": 100,
        "ratio": 0.01
      },
      "trades": {
        "observed": 2,
        "target": 50,
        "ratio": 0.04
      },
      "orders": {
        "observed": 1,
        "target": null,
        "ratio": null
      },
      "signals": {
        "observed": 1,
        "target": null,
        "ratio": null
      },
      "risk": {
        "observed": 1,
        "target": null,
        "ratio": null
      },
      "safety": {
        "observed": 1,
        "target": null,
        "ratio": null
      },
      "execution": {
        "observed": 2,
        "target": null,
        "ratio": null
      },
      "performance": {
        "observed": 1,
        "target": null,
        "ratio": null
      },
      "replay": {
        "observed": 2,
        "target": 500,
        "ratio": 0.004
      },
      "evidence": {
        "observed": 3,
        "target": 100,
        "ratio": 0.03
      },
      "governance": {
        "observed": 1,
        "target": 10,
        "ratio": 0.1
      },
      "configuration": {
        "observed": 1,
        "target": null,
        "ratio": null
      },
      "reports": {
        "observed": 1,
        "target": null,
        "ratio": null
      }
    },
    "read_only": true
  },
  "data_quality_report": {
    "report": "data_quality",
    "status": "available",
    "records_scanned": 18,
    "fully_keyed_records": 10,
    "completeness_ratio": 0.5556,
    "flag_histogram": {
      "missing_strategy_version": 8,
      "missing_risk_version": 8,
      "missing_safety_version": 8,
      "missing_execution_version": 8
    },
    "read_only": true,
    "note": "Missing fields stay null \u2014 never fabricated"
  },
  "correlation_report": {
    "report": "correlation",
    "status": "available",
    "records_with_correlation_id": 18,
    "unique_correlation_ids": 1,
    "cross_domain_correlations": 1,
    "examples": {
      "corr-idw-demo-1": [
        "configuration",
        "evidence",
        "execution",
        "governance",
        "market",
        "orders",
        "performance",
        "replay",
        "reports",
        "risk",
        "safety",
        "signals",
        "trades"
      ]
    },
    "read_only": true
  }
}
```

## Recommendations (never auto-applied)

- Grow market coverage (1/100)
- Grow trades coverage (2/50)
- Grow replay coverage (2/500)
- Grow evidence coverage (3/100)
- Grow governance coverage (1/10)
- Improve version/correlation key completeness on ingested rows
- Warehouse is read-only — never modify production trading systems

## Hard locks

- read_only_warehouse: True
- never_modifies_production_records: True
- never_modifies_strategy: True
- never_modifies_risk_safety_execution: True
- never_modifies_performance_intelligence: True
- never_modifies_replay_evidence_lab: True
- never_modifies_trading_operations_center: True
- never_modifies_audit_governance: True
- analytics_infrastructure_only: True

