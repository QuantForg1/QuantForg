# RC1 — Architecture

Baseline commit: `17d5f83` (RC1). Hardening follows quality-over-quantity.

## Runtime path

```
Browser (Next.js) → Railway API (FastAPI) → MT5 Gateway (Windows) → Broker MT5
                 ↘ Supabase Postgres (audits, RLS, OMS state)
Cloudflare Tunnel fronts the Windows gateway hostname.
```

## Layers

| Layer | Responsibility |
| --- | --- |
| Presentation | FastAPI routers, Next.js desks |
| Application | Use cases (order validation, risk, safety, gateway submit) |
| Domain | Entities, enums, policies — no I/O |
| Infrastructure | Postgres, Redis, MT5 client, Cloudflare probes |

## Eight primary surfaces

Terminal · Book · Research · Counsel · Journal · Broker · Inbox · Settings

`/ops` is an admin operations surface (not a ninth product desk).

## Execution Audit Engine

Immutable rows in `execution_audits`. Unique `(user_id, request_id, stage)`.

Recorded stages on the live path: `validation` → `risk` → `safety` → `submit` (+ `replay` when applicable).

`manage` / `cancel` are reserved enum values. Close/history economics live in Journal deals — not fabricated audit stages.

## Hard constraints (RC1)

- Do not change OMS contracts, execution logic, or broker behaviour for polish work.
- Real telemetry or explicit “Not available” — never mock KPIs.
- Design Bible (ADR-0022) binds UI.
