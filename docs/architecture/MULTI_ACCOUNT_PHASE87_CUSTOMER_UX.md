# Phase 8.7 — Customer Multi-Account experience

**Status:** Customer observe-only UX wired to existing APIs.  
LIVE fan-out and multi-account dispatch remain **OFF** by default.

## Surfaces

| Surface | Role |
|---|---|
| Broker desk `CustomerMultiAccountPanel` | Own `/broker-accounts` + `/multi-account/dispatch/status` |
| `GET /api/v1/multi-account/dispatch/status` | Session-scoped jobs, feature-gate + eligibility-engine reasons |
| Admin `/admin/multi-account` | Owner ops only |

## Honesty rules

- Never invent Connected / Verified / Worker Online.
- Never equate broker connection with trading eligibility.
- Never show another customer's accounts or jobs.
- Never return passwords, worker tokens, or sealed envelopes.
- Demo vs Live comes from broker/server metadata only.

## Staging acceptance

```bash
python scripts/staging_phase87_customer_jwt_accept.py
```

Set disposable staging JWTs in `deploy/mt5_worker_agent/local.env` (gitignored):

- `QF_STAGING_CUSTOMER_A_JWT`
- `QF_STAGING_CUSTOMER_B_JWT`

Without those keys, isolation cases remain `NOT_EXERCISED`.

## Demo MT5 prep

```powershell
.\scripts\validate_demo_local_env.ps1
.\deploy\mt5_worker_agent\verify_demo_broker.ps1 -Broker <slug> -Slot demo-a -Env demo
```

Do not place LIVE orders. Keep `QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false`.
