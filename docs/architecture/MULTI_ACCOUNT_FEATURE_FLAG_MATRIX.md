# Multi-account feature-flag and execution safety matrix

| Flag / gate | Production value | Effect when false | Effect when true |
|---|---|---|---|
| `MULTI_ACCOUNT_DISPATCH_ENABLED` | **false** | Plans may classify eligibility; delivery suppressed | May mark `queued` in dry-run planner only; still no OMS unless LIVE submit also enabled in a future wired path |
| `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED` | **false** | LIVE submit denied | **Forbidden for this phase** — requires separate Owner authorization |

## Module safety (Phase 5.1 / 6)

| Module | Can evaluate eligibility | Can enqueue LIVE | Can call `order_send` |
|---|---|---|---|
| `multi_account_eligibility_service` | Yes (dry-run) | No | No |
| `multi_account_dispatch_dry_run` | Yes (via eligibility) | No (`delivery_suppressed=true`, `live_ok` forced False) | No |

## External dependencies (not provisioned here)

- Windows VPS / hosts for per-user MT5 workers (Owner authorization required)
- Durable Postgres dispatch queue migration
- Staging identities for demo fan-out
- Authenticated demo evidence before any Exness/HFM claims
