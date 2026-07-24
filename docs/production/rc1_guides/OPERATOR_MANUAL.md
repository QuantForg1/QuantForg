# QuantForg RC1 — Operator Manual

## Purpose

Prove, with measurable evidence, that QuantForg is consistently profitable, stable, and safe **before** increasing capital.

## What operators do

1. Run **Production Checklist** (`GET /ite/reliability/rc1`) — expect PASS / WARNING / FAIL per subsystem.
2. Run **Smoke Test** (`POST /ite/reliability/rc1/smoke`) — connectivity only; **never places real trades**.
3. Review **Live Statistics** and **Go Live Score** on the RC1 desk.
4. Keep **Paper / Demo / Live** results separate — never mix.
5. Use **Capital Scaling Advisor** for suggestions only — never auto-applied.
6. Prefer **14–28 consecutive successful trading days** before scale-up.

## Hard locks

- Smoke never places orders
- Never auto-scale capital
- No new strategies / experimental production logic in RC1
