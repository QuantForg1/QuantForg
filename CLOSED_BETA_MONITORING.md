# Closed Beta Monitoring Prep

Prepared surfaces for invite-only beta. Does **not** change locked engines or APIs.

**Owner tools:** `/ops` (dashboard, metrics, alerts, audit) · `/cloud-ops` (gateway HA) · public `/health*`.

---

## 1. Health dashboard

| Probe | Path | Expect |
|-------|------|--------|
| Process live | `GET /health/live` | 200 while process up |
| Ready | `GET /health/ready` | DB/Redis when configured |
| Full | `GET /health` | Aggregated; strict 503 only if `HEALTH_HTTP_STRICT` |
| Ops component | `GET /api/v1/ops/dashboard` | Owner/admin |
| Broker / Weltrade | `/api/v1/weltrade/health`, broker health | Session-aware |
| Gateway | Gateway `GET /health` (+ `/heartbeat` with token) | Windows host |

**Beta operator view:** open `/ops` + `/cloud-ops` every day (see `BETA_OPERATIONS.md`).

---

## 2. Error dashboard

| Source | Where |
|--------|-------|
| Ops alerts evaluation | `/ops` → Alerts |
| Client error ring | `qf.ops.errors.v1` (browser) |
| Optional webhook | Platform error/audit webhooks if configured |
| Desk UI | `DeskError` / toasts — honest unavailable, no mock fills |

**Watch for:** auth fail spikes, gateway 522/523/524, MT5 disconnected alerts, migration failures.

---

## 3. Performance dashboard

| Signal | Source |
|--------|--------|
| Latency / throughput / errors | `GET /api/v1/ops/metrics` (+ `/metrics`) |
| Gateway RTT / heartbeat age | `/cloud-ops` |
| Front-end poll budgets | Desk React Query intervals (typically 20–60s hot paths) |
| DB floor | Cross-region ~180–220ms (known); investigate only if p95 regresses heavily |

---

## 4. Audit logs

| API | Contents |
|-----|----------|
| `GET /api/v1/ops/audit` | Auth, broker, strategy, risk, execution, paper events (admin) |
| Client ring | `qf.ops.audit.v1` |

Retention / export: follow `OPERATIONS_RUNBOOK.md`. Do not log invite codes or broker passwords.

---

## 5. Alert rules (existing + beta playbooks)

Evaluated with ops dashboard refresh (`monitoring` service):

| Rule | Severity | Beta response |
|------|----------|---------------|
| `mt5_disconnected` | Critical | Confirm gateway; enable maintenance if prolonged; paper-only comms |
| `broker_unhealthy` | Critical | `/broker` + gateway health; reconnect path |
| `risk_engine_failures` | Critical | Freeze mutates via read-only mode; investigate |
| `migration_failures` | Critical | Halt deploy; rollback per runbook |
| `strategy_failures` | Warning | Advisory desks only — log + weekly triage |

**Beta wiring checklist (operator):**

- [ ] Owner account can load `/ops` and `/cloud-ops`  
- [ ] Optional Slack/email webhook for feedback + critical alerts  
- [ ] Confirm `EXECUTION_ENABLED=false` appears on advisory desks  
- [ ] Heartbeat age threshold understood for registered gateways  
- [ ] Maintenance mode flag tested once before launch day  

No new alert engines were added for this prep (API freeze).
