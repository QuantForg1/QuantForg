# RC1 — Runbooks

## R1 — Execution success drop

1. Open `/ops` → RC1 Execution Telemetry.
2. Note Execution Reject %, Risk Reject %, Gateway/MT5 availability.
3. Inspect `/ops/audit` and `GET /execution/audits` for failing stages.
4. If risk rejects elevated: review risk policy — do not disable risk.
5. If submit fails with gateway down: follow Gateway runbook.

## R2 — Gateway unavailable

1. Verify tunnel + Windows gateway process.
2. Hit gateway `/health`.
3. Confirm Railway env `MT5_GATEWAY_BASE_URL`.
4. Confirm token rotation did not desync Railway vs gateway.

## R3 — Telemetry empty

1. Confirm admin JWT.
2. Confirm `execution_audits` table exists and RLS policies allow service inserts.
3. Place a paper/safe validation path trade in staging to seed stages.
4. Daily P/L shows “Not available” by design — use Journal deals.

## R4 — Security advisor WARN

1. Prefer revoke anon EXECUTE on SECURITY DEFINER helpers.
2. Do not disable RLS to silence advisors.
3. Enable leaked-password protection in Supabase Auth dashboard when ready.
