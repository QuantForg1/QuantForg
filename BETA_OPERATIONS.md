# Beta Operations

Operator runbook for QuantForg Closed Beta.

## Environment flags

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_BETA_MODE=true` | Require invite unlock |
| `NEXT_PUBLIC_BETA_INVITE_CODE` | Shared invite (rotate as needed) |
| `NEXT_PUBLIC_MAINTENANCE_MODE` | Maintenance gate |
| `NEXT_PUBLIC_READ_ONLY_MODE` | Block mutating trading UI |
| `NEXT_PUBLIC_FEEDBACK_WEBHOOK_URL` | Optional feedback sink |
| `EXECUTION_ENABLED=false` | Keep live order_send off for beta |
| `MT5_USE_MOCK` | Prefer `false` only on Windows live hosts |

## Daily checklist

- [ ] Review feedback ring (`qf.ops.feedback.v1` / webhook)  
- [ ] Check `/ops` and `/cloud-ops` health  
- [ ] Confirm no unexpected `EXECUTION_ENABLED`  
- [ ] Triage MT5 gateway heartbeats if gateways registered  
- [ ] Update `/whats-new` curated notes when shipping beta builds  

## Incident posture

1. Enable maintenance mode if needed.  
2. Communicate via Support + email.  
3. Prefer paper-only guidance until connectivity restored.  
4. Never invent market data or fake certifications.

## Related

- `BETA_ONBOARDING.md`  
- `BETA_FEEDBACK_PLAN.md`  
- `BETA_CHECKLIST.md`  
- `GATEWAY_DEPLOYMENT.md`
