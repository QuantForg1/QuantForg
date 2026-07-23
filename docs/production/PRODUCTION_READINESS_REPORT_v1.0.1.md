# QuantForg v1.0.1 — Production Readiness Report

**Generated:** 2026-07-22T22:30:56.566630Z
**Decision:** READY FOR CONTROLLED DEMO

## Operational snapshot

```json
{
  "status": "available",
  "source": "auto_trading_status",
  "facts": {
    "gateway": false,
    "broker": false,
    "mt5": false,
    "ops_mode": "SHADOW",
    "execution_enabled": false,
    "kill_switch_armed": false
  },
  "evidence_gates": {
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
        "observed": 0,
        "required": 50,
        "passed": false
      },
      {
        "id": "replay_opportunities",
        "label": "Replay opportunities",
        "observed": 0,
        "required": 500,
        "passed": false
      },
      {
        "id": "no_trade_observations",
        "label": "NO_TRADE observations",
        "observed": 0,
        "required": 100,
        "passed": false
      }
    ],
    "all_passed": false,
    "may_recommend_strategy_changes": false,
    "advisory_only": true,
    "never_auto_modifies_strategy": true,
    "note": "Strategy-change recommendations remain blocked until all evidence gates pass \u2014 gates are advisory and never mutate production"
  },
  "confidence": {
    "status": "available",
    "observability_overall": "degraded",
    "alert_count": 0
  },
  "observability": {
    "status": "available",
    "observability_overall": "degraded",
    "alert_count": 0
  },
  "governance": {
    "status": "available",
    "record_count": 0,
    "append_only": true,
    "immutable": true
  },
  "warehouse": {
    "status": "available",
    "total_records": 0,
    "read_only": true
  },
  "performance_iq": {
    "status": "module_present",
    "note": "advisory; journals only"
  },
  "replay_lab": {
    "status": "module_present",
    "evidence_gates": {
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
          "observed": 0,
          "required": 50,
          "passed": false
        },
        {
          "id": "replay_opportunities",
          "label": "Replay opportunities",
          "observed": 0,
          "required": 500,
          "passed": false
        },
        {
          "id": "no_trade_observations",
          "label": "NO_TRADE observations",
          "observed": 0,
          "required": 100,
          "passed": false
        }
      ],
      "all_passed": false,
      "may_recommend_strategy_changes": false,
      "advisory_only": true,
      "never_auto_modifies_strategy": true,
      "note": "Strategy-change recommendations remain blocked until all evidence gates pass \u2014 gates are advisory and never mutate production"
    },
    "note": "never override evidence gates"
  }
}
```

## Known limitations

- Evidence gates must pass before strategy-change recommendations
- Controlled Live requires OWNER promote + EXECUTION_ENABLED + Demo cert
- Wall-clock soak evidence remains operational (not claimed here)
- Process-local stores reset on restart unless durable backends configured

## Outstanding actions

- Restore connectivity / promote via official ops path (see Launch Readiness) (gateway: FAIL)
- Restore connectivity / promote via official ops path (see Launch Readiness) (broker: FAIL)
- Restore connectivity / promote via official ops path (see Launch Readiness) (mt5: FAIL)
- Promote SHADOW→CANARY→LIVE via official OWNER path only (ops_mode: FAIL)
- Set EXECUTION_ENABLED=true on Railway and restart API (execution_enabled: FAIL)
- Accumulate live closed trades / replay opportunities / NO_TRADE observations to threshold (evidence_gates: FAIL)
- Clear evidence gates before claiming high confidence (confidence: FAIL)

