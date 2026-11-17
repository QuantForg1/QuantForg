# Customer onboarding & support readiness

Statuses: COMPLETE_VERIFIED · IMPLEMENTED_NOT_VERIFIED · MISSING ·
OWNER_ACTION_REQUIRED · BLOCKED_EXTERNAL

This is the operator playbook for first-customer support. It does **not**
authorize LIVE trading, Gateway restart, DEMO load tests, or GitHub billing
changes.

## Safety locks (always)

| Lock | Status |
|---|---|
| Robot / Live Trading Control | PAUSED; automatic resume disabled (#350) |
| Shared platform terminal | Owner/admin only; customers never claim/restore it (#340–#361) |
| LIVE orders / positions | Do not submit or modify |
| Gateway recovery `a150730e` | Ready only; restart needs separate owner authorization |
| Concurrent capacity numbers | Do not invent; wait for A14 DEMO + A5 supervisor |

## Onboarding path (customer)

1. Register / verify email / sign in (auth OTP/MFA already Production-verified).
2. Open **Broker Accounts** → choose broker → enter DEMO or LIVE credentials
   (customer types passwords; support never asks for them in chat).
3. Expected customer outcomes:
   - `QUEUED_FOR_TERMINAL` + banner *Queued for a QuantForg trading terminal*
     when vault assignment is `pending_terminal` (needs worker supervisor A5).
   - Connect / Reconnect / Disconnect / Change Account operate on the **vault**
     only for customers (never the shared gateway).
4. Robot Control Center shows the customer's own account once a worker slot
   binds; platform Weltrade LIVE login must remain unchanged on
   `gateway.quantforg.com/health`.

## Support triage

| Symptom | Likely cause | Safe action |
|---|---|---|
| Customer sees Connect form while saved | Session unknown / API slow | Retry; check `/qf-api/health/live` |
| Queued forever | Worker supervisor not running (A5) | Confirm `worker_hosts` / `execution_workers`; do not attach customer to owner gateway |
| 403 on connect/attach/submit | Shared-terminal owner guard | Expected for customers; explain dedicated terminal |
| Balance/Equity blank | History hang / gateway stall | Broker page should still show balance without history (#352); Gateway recovery is owner-only |
| Wrong MT5 login on gateway | Shared-terminal incident class | Stop; verify `gateway…/health` login; owner restore only |

## Monitoring (read-only)

| Check | Pass |
|---|---|
| `www.quantforg.com/qf-api/health` | `status=ok`, commit matches intended tip |
| `www.quantforg.com/qf-api/health/live` | Fast `ok` |
| `gateway.quantforg.com/health` | Weltrade **12439799** preserved until owner says otherwise; heartbeat ≤ 60 s |
| Railway deploy | SUCCESS for tip SHA |
| Vercel `frontend` + `quant-forg` | SUCCESS for tip SHA; www runtime markers for Broker UX |

## Gaps still OWNER_ACTION_REQUIRED

- **A5** worker supervisor on Windows host
- **A14** test customer + DEMO accounts for 8-broker acceptance (§4 of infra report)
- **GW** authorize Gateway recovery when Trade tab is FLAT
- **A10** NOWPayments live checkout (kept closed until approved)
