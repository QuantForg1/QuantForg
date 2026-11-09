# QuantForg — Multi-User MT5 Phase 0 Audit (updated for simplified model)

**Date:** 2026-11-09 (revised)  
**Baseline commit (main):** `d92e17bc`  
**Product rule (authorized):** one active MT5 account per user; many independent users.

## Verdict

Current production LIVE is a **singleton** Weltrade/MT5 gateway session.

Phase 1a builds a **multi-user registry** (one account per user) with worker *assignment* metadata. It does **not** yet provide simultaneous multi-user MT5 LIVE execution.

## LIVE spine (preserved)

```text
ITE runtime → Decision → Owner/Risk → Bridge → OMS → single MT5 gateway → PME
```

Hard ceilings unchanged in `owner_live_limits.py` / `runtime_policy.py`.

## Hard constraint until worker fleet exists

```text
One Windows MT5 terminal / gateway process ↔ one live login at a time
```

Many simultaneous users require **N isolated terminals/workers**, not fan-out on one gateway.

## Registry support (Phase 1a target)

- Many users, each with ≤1 non-revoked `broker_accounts` row
- Global uniqueness of `(broker_id, server, login)` for non-revoked rows
- ≤1 active `execution_workers` assignment per user and per account
- Encrypted credentials; RLS ownership
- Flags: `MULTI_ACCOUNT_DISPATCH_ENABLED=false`, `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false`

## Deliberately disabled

- Multi-user LIVE `order_send` fan-out
- Multiple accounts per user
- Grid / martingale / averaging / M1 LIVE / forced trades
- Raising owner hard ceilings
