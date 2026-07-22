# QuantForg v1.0.1 — Institutional Audit Trail & Governance

**Generated:** 2026-07-22T21:50:12Z
**Scope:** Governance only. Append-only immutable audit trail. Never modifies trading behaviour, strategy, risk, safety, execution, Performance IQ, Evidence Lab, or Trading Operations Center.

## Evidence summary

```json
{
  "total_events": 8,
  "critical": 2,
  "warnings": 2,
  "config_changes": 1,
  "trade_version_tags": 1,
  "append_only": true,
  "immutable": true
}
```

## Security

```json
{
  "append_only": true,
  "immutable": true,
  "chronological": true,
  "never_silently_deleted": true,
  "never_silently_modified": true,
  "record_count": 8,
  "rejected_mutations": 0
}
```

## Dashboard counts

```json
{
  "total_events": 8,
  "critical": 2,
  "warnings": 2,
  "config_changes": 1,
  "trade_version_tags": 1
}
```

## Forensic timeline

```json
{
  "status": "available",
  "count": 8,
  "steps": [
    {
      "timestamp": "2026-07-22T09:00:00Z",
      "action": "gateway_connected",
      "category": "gateway",
      "severity": "info",
      "actor": "system",
      "previous_state": "disconnected",
      "new_state": "connected",
      "result": "success",
      "event_id": "66d7cb04-fb60-4cbb-bcd3-df82a9463575"
    },
    {
      "timestamp": "2026-07-22T09:02:00Z",
      "action": "broker_login",
      "category": "broker",
      "severity": "info",
      "actor": "operator.alice",
      "previous_state": "logged_out",
      "new_state": "logged_in",
      "result": "success",
      "event_id": "a0832446-717c-4fa3-9a1e-06ef048323f7"
    },
    {
      "timestamp": "2026-07-22T09:05:00Z",
      "action": "ops_promotion",
      "category": "operations",
      "severity": "warning",
      "actor": "owner.bob",
      "previous_state": "SHADOW",
      "new_state": "CANARY",
      "result": "success",
      "event_id": "19558bf7-7c22-416f-9bcd-5cb3a1839c49"
    },
    {
      "timestamp": "2026-07-22T09:06:00Z",
      "action": "execution_enabled",
      "category": "execution",
      "severity": "critical",
      "actor": "owner.bob",
      "previous_state": "false",
      "new_state": "true",
      "result": "success",
      "event_id": "a41afc83-756e-4617-aa9a-9916043f6eee"
    },
    {
      "timestamp": "2026-07-22T09:07:00Z",
      "action": "trade_version_tagged",
      "category": "strategy",
      "severity": "info",
      "actor": "system",
      "previous_state": null,
      "new_state": "515822",
      "result": "recorded",
      "event_id": "c1d2729d-e057-486f-9a96-f2b2a1e8b130"
    },
    {
      "timestamp": "2026-07-22T09:10:00Z",
      "action": "daily_report_generated",
      "category": "system",
      "severity": "info",
      "actor": "system",
      "previous_state": null,
      "new_state": "generated",
      "result": "success",
      "event_id": "1bfdcc99-6b60-4718-8ea2-301a85adbde4"
    },
    {
      "timestamp": "2026-07-22T09:12:00Z",
      "action": "kill_switch_armed",
      "category": "safety",
      "severity": "critical",
      "actor": "owner.bob",
      "previous_state": "disarmed",
      "new_state": "armed",
      "result": "success",
      "event_id": "a9d1945e-379f-4c93-b710-541f4e5d7c81"
    },
    {
      "timestamp": "2026-07-22T09:15:00Z",
      "action": "evidence_gates_failed",
      "category": "evidence",
      "severity": "warning",
      "actor": "system",
      "previous_state": "unknown",
      "new_state": "failed",
      "result": "recorded",
      "event_id": "da22ee91-7711-4c63-9e79-ac4b8c260bd5"
    }
  ],
  "note": "Chronological forensic replay of audit history \u2014 read-only"
}
```

## Operator accountability

```json
{
  "status": "available",
  "sensitive_actions": 3,
  "by_actor": {
    "owner.bob": 3
  },
  "items": [
    {
      "event_id": "19558bf7-7c22-416f-9bcd-5cb3a1839c49",
      "timestamp": "2026-07-22T09:05:00Z",
      "action": "ops_promotion",
      "actor": "owner.bob",
      "reason": "OWNER-approved canary promote",
      "approval": {
        "required": true,
        "granted_by": "owner.bob"
      },
      "result": "success",
      "previous_state": "SHADOW",
      "new_state": "CANARY"
    },
    {
      "event_id": "a41afc83-756e-4617-aa9a-9916043f6eee",
      "timestamp": "2026-07-22T09:06:00Z",
      "action": "execution_enabled",
      "actor": "owner.bob",
      "reason": "canary execution arm",
      "approval": {
        "required": true,
        "granted_by": "owner.bob"
      },
      "result": "success",
      "previous_state": "false",
      "new_state": "true"
    },
    {
      "event_id": "a9d1945e-379f-4c93-b710-541f4e5d7c81",
      "timestamp": "2026-07-22T09:12:00Z",
      "action": "kill_switch_armed",
      "actor": "owner.bob",
      "reason": "manual safety drill",
      "approval": {
        "required": true,
        "granted_by": "owner.bob"
      },
      "result": "success",
      "previous_state": "disarmed",
      "new_state": "armed"
    }
  ],
  "note": "Who / when / why / approval / result \u2014 governance only"
}
```

## Reports

```json
{
  "daily_audit_report": {
    "report": "daily_audit",
    "event_count": 8
  },
  "weekly_governance_report": {
    "report": "weekly_governance",
    "event_count": 8
  },
  "monthly_compliance_report": {
    "report": "monthly_compliance",
    "event_count": 8
  },
  "critical_event_report": {
    "report": "critical_events",
    "event_count": 2
  },
  "configuration_change_report": {
    "report": "configuration_changes",
    "event_count": 1
  }
}
```

## Recommendations (never auto-applied)

- Review 2 critical governance events (accountability only — no strategy changes)
- Never modify strategy, risk, safety, execution, Performance IQ, Evidence Lab, or Trading Operations Center from governance

## Hard locks

- never_modifies_strategy: True
- never_modifies_risk_safety_execution: True
- never_modifies_performance_intelligence: True
- never_modifies_replay_evidence_lab: True
- never_modifies_trading_operations_center: True
- append_only: True
- immutable_records: True
- never_silently_deleted: True
- never_silently_modified: True
- governance_only: True

