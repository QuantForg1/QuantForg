# Incident: customer action switched the shared platform MT5 terminal

**When:** 16 Nov 2026, 23:46:53 UTC (17 Nov 01:46 Cairo).
**Severity:** Critical (isolation). **Impact:** none financial.

## What happened

1. A customer (role `trader`, user `8ae4b619…`) opened Broker Accounts. The page called `POST /api/v1/weltrade/restore-profile` on mount.
2. That endpoint drove the **shared platform terminal**:
   - `POST /session/disconnect`: the owner's Weltrade LIVE account 12439799 was logged out.
   - `POST /session/connect`: the terminal logged into the customer's XM LIVE account 450397410 (balance $0).
3. The owner engine then refused to bind (`mt5_session_heal_skipped_login_mismatch`, `login_owned_by_other_user`).

## Why nothing traded

- Live Trading Control was **PAUSED** and `orders_may_submit=false`.
- No positions were open on either account.

## Root cause

The `/weltrade/*`, `/mt5/connect|disconnect` and `/broker-connections/validate` session endpoints accepted any signed-in user. They drive the single platform terminal that serves the owner LIVE account.

## Fix

- **#340:** these endpoints require OWNER or ADMIN (`403 SHARED_TERMINAL_OWNER_ONLY`).
- **#341:** customer Connect now saves the account (encrypted) for a dedicated worker terminal and never touches the platform terminal.

## Open

- **Owner action A13:** restore the platform terminal to Weltrade 12439799 (Broker → Connect/Restore as the owner). I did not run it; the action was not explicitly approved.
- **Customer account 450397410** (XM LIVE) is stored under the customer. LIVE customer execution stays off (`MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED` is not enabled), and auto-assignment covers DEMO only.
