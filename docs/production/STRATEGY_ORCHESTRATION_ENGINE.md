# Strategy Orchestration Engine (SOE) — v1.1.0

**Status:** Production collaboration layer (upstream of Risk / OMS / MT5)  
**Does not:** authorize `order_send`, weaken risk gates, enable grid/martingale, or auto-approve LIVE capital.

## Purpose

QuantForg evaluates the five live scalping profiles **and** advisory research engines together:

1. Evaluate all LIVE-executable profiles every cycle.
2. Collect advisory votes (factor proxies for RSI/MACD/MA/Bollinger/trend/momentum/breakout/mean-reversion roles).
3. Measure agreement / disagreement — never manufacture consensus.
4. Apply performance influence (deterioration → veto).
5. Raise the evidence bar when advisory engines strongly disagree.
6. Prefer **NO_TRADE** on weak solo setups, cost gates, or conflicts.
7. Select **one** coherent OMS-eligible winner (live pack only).

**Operating objective:** LIVE trading through existing owner gates — not permanent SHADOW. SHADOW remains available; it is not required forever.

## LIVE-executable (may win OMS selection)

`smc_scalping`, `trend_continuation`, `breakout_scalping`, `range_mean_reversion`, `momentum_scalping`

Still require: ops LIVE (or CANARY) + `EXECUTION_ENABLED` + Risk + OMS + MT5 + owner limits.

## Analysis participants (vote only — never OMS winners alone)

Strategy Engine plugin roles via score-factor advisory, Institutional Alpha (ops-gated ranking), M1 micro (unified arbitration), ITE swing confluence, Alpha Factory / Scalping AI V2 / ASI (research).

Catalog-only / forbidden: `session_breakout` as live profile, grid, martingale.

## Attribution

- `strategy_id` stored in in-process fill metadata (`remember_fill_metadata`) — **not** packed into MT5 comment (length/PME compatibility).
- On close, `StrategyStatsBook.record_closed` updates SOE influence when `strategy_id` is present.
- Broker `/history` remains authoritative for net P&L after costs.

## Ops monitor

`GET …/strategy-orchestration-monitor` — strategies, health, eligibility registry, collaboration mode, `auto_authorize_live: false`.

## Honest note

Matched STRATEGY_MATCHED closed-trade ledgers may be empty until fills are attributed. Do not invent strategy P&L. Historical data does not guarantee future profitability.
