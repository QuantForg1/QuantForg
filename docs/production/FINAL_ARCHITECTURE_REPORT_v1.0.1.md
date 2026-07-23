# QuantForg v1.x Final Architecture Report

**Generated:** 2026-07-22T22:30:56.566630Z
**Platform version:** 1.0.1

Architecture is feature-complete for the institutional advisory stack:
Performance IQ, Replay & Evidence Lab, Trading Operations Center,
Audit Governance, Institutional Data Warehouse, Institutional Observability.

Trading Strategy / Risk / Safety / Execution remain protected baselines.

## Inventory

```json
[
  {
    "id": "strategy",
    "label": "Trading Strategy / Decision",
    "present": true,
    "healthy": true,
    "version": "1.0.1",
    "dependencies": [
      "app.domain.institutional_trading.trade_decision"
    ],
    "readiness": "ready",
    "detail": "module importable"
  },
  {
    "id": "risk",
    "label": "Risk Engine",
    "present": true,
    "healthy": true,
    "version": "1.0.1",
    "dependencies": [
      "app.domain.institutional_trading.eligibility"
    ],
    "readiness": "ready",
    "detail": "module importable"
  },
  {
    "id": "safety",
    "label": "Safety / Kill Switch",
    "present": true,
    "healthy": true,
    "version": "1.0.1",
    "dependencies": [
      "app.domain.institutional_trading.execution.kill_switch"
    ],
    "readiness": "ready",
    "detail": "module importable"
  },
  {
    "id": "execution",
    "label": "Execution Pipeline",
    "present": true,
    "healthy": true,
    "version": "1.0.1",
    "dependencies": [
      "app.domain.institutional_trading.operations.control_plane"
    ],
    "readiness": "ready",
    "detail": "module importable"
  },
  {
    "id": "performance_iq",
    "label": "Performance Intelligence",
    "present": true,
    "healthy": true,
    "version": "1.0.1",
    "dependencies": [
      "app.domain.performance_intelligence"
    ],
    "readiness": "ready",
    "detail": "module importable"
  },
  {
    "id": "replay_evidence_lab",
    "label": "Replay & Evidence Lab",
    "present": true,
    "healthy": true,
    "version": "1.0.1",
    "dependencies": [
      "app.domain.replay_evidence_lab"
    ],
    "readiness": "ready",
    "detail": "module importable"
  },
  {
    "id": "trading_operations_center",
    "label": "Trading Operations Center",
    "present": true,
    "healthy": true,
    "version": "1.0.1",
    "dependencies": [
      "app.domain.trading_operations_center"
    ],
    "readiness": "ready",
    "detail": "module importable"
  },
  {
    "id": "audit_governance",
    "label": "Audit Trail & Governance",
    "present": true,
    "healthy": true,
    "version": "1.0.1",
    "dependencies": [
      "app.domain.audit_governance"
    ],
    "readiness": "ready",
    "detail": "module importable"
  },
  {
    "id": "warehouse",
    "label": "Institutional Data Warehouse",
    "present": true,
    "healthy": true,
    "version": "1.0.1",
    "dependencies": [
      "app.domain.institutional_data_warehouse"
    ],
    "readiness": "ready",
    "detail": "module importable"
  },
  {
    "id": "observability",
    "label": "Institutional Observability",
    "present": true,
    "healthy": true,
    "version": "1.0.1",
    "dependencies": [
      "app.domain.institutional_observability"
    ],
    "readiness": "ready",
    "detail": "module importable"
  },
  {
    "id": "launch_readiness",
    "label": "Launch Readiness",
    "present": true,
    "healthy": true,
    "version": "1.0.1",
    "dependencies": [
      "app.application.services.launch_readiness"
    ],
    "readiness": "ready",
    "detail": "module importable"
  }
]
```

## Registered advisory routers

```json
{
  "registered": [
    "performance_intelligence",
    "replay_evidence_lab",
    "trading_operations_center",
    "audit_governance",
    "institutional_data_warehouse",
    "institutional_observability"
  ],
  "missing": []
}
```

