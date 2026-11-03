# Strategy Orchestration Engine (SOE) — v1.0.0

**Status:** Production-ready selection layer (upstream of Risk / OMS / MT5)  
**Does not:** authorize `order_send`, weaken risk gates, enable grid/martingale, or auto-approve LIVE capital.

## Purpose

QuantForg already evaluates five live scalping profiles. SOE makes that evaluation **selective and coordinated**:

1. Evaluate all live-eligible strategies every cycle.
2. Apply independently verified performance influence (deterioration → veto).
3. Detect direction / regime conflicts → prefer **NO_TRADE**.
4. Require confluence **or** a high solo quality/confidence bar.
5. Attach one winner per symbol (never duplicate contradictory positions).
6. Explain why the winner was chosen and why alternatives were rejected.

**Operator priority:** better trades, fewer unnecessary losses — not more trades.

## Live-executable profiles (OMS path)

| ID | Role |
|----|------|
| `smc_scalping` | SMC baseline (structure / OB / FVG / liquidity) |
| `trend_continuation` | Pullback continuation (forbids range/compression) |
| `breakout_scalping` | Volatility expansion breakouts |
| `range_mean_reversion` | Fade extremes (range/compression only) |
| `momentum_scalping` | Momentum confirmation (`min_momentum=65` **enforced**) |

## Analysis-only / not live from catalog

Institutional Alpha v5 (ops enable), M1 micro (unified arbitration), ITE swing mode, Strategy Engine plugins, Alpha Factory / research lab / Scalping AI V2 / ASI, and catalog-only IDs (`ma_cross`, `rsi`, `macd`, `bollinger`, `session_breakout`, `grid`) never gain OMS authority through SOE.

## Insertion point

```
AI scalping score → evaluate_all_strategies → SOE orchestrate
  → attach strategy_id / soe_prefer_no_trade
  → Probability / portfolio rank (SOE veto clears opportunity_eligible)
  → RiskEngine → Eligibility → OMS → MT5
```

Frozen modules (Risk, OMS, MT5 gateway, PME, kill switch, owner limits) are **unchanged authorities**.

## Selectivity rules

| Condition | Result |
|-----------|--------|
| Conflicting BUY vs SELL among passers | `NO_TRADE` |
| Deteriorating strategy (PF/expectancy gates, ≥8 closes) | Influence weight `0` (veto) |
| Solo passer with quality `<82` and confidence `<80` | `NO_TRADE` |
| ≥2 confluent passers with best quality `<74` | `NO_TRADE` |
| Best quality `<70` | `NO_TRADE` |
| `soe_prefer_no_trade` | Cleared from scanner eligibility (no weak unspecialized fallback) |

## Validation / monitoring

- `evaluate_backtest_gate()` — offline OOS / walk-forward floors; **never** `live_auto_authorize=True`.
- `build_strategy_performance_monitor()` — strategy P&L, PF, expectancy, influence, flags.
- Ops: `GET` strategy orchestration monitor (institutional ops router).

## Honest performance note

Local `StrategyStatsBook` may show scans without closed outcomes. Broker net P&L after spread/commission requires connected MT5 `/history`. SOE does **not** invent profitability. Live authorization remains an owner decision after paper validation and green trading-core regression.

## Bug fix included

`StrategyDefinition.min_momentum` / `min_structure` were defined but not applied in `evaluate_strategy`. They are now enforced as **additional** floors (never below SCALPING_V1 config mins).
