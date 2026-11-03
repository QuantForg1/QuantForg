# Strategy loss root-cause — Phase 2 (matched MT5)

**Source:** Live MT5 gateway deal history, magic `260720` (QuantForg).  
**Method:** Position-id grouping for closed-trade P&amp;L; comment prefix for path attribution only.  
**Not claimed:** Guaranteed future edge. Strategy pack IDs were historically **not** in MT5 comments.

## Matched window (~60 trading days)

| Cohort | Closed | W / L | Net (broker profit field) | Avg W / Avg L | PF | Expectancy |
|--------|--------|-------|---------------------------|---------------|----|------------|
| ALL QF | ~74 | 28 / 46 | ≈ **−58.73** | asymmetric | ≈0.68 | negative |
| M1 (`m1:` comments) | ~28 | 10 / 18 | ≈ **−18.38** | wins &lt; losses | ≈0.56 | ≈ **−0.66** |
| Primary / ITE (non-`m1:`) | ~46 | 18 / 28 | ≈ **−40.35** | wins &lt; losses | ≈0.71 | negative |

Earlier 30-day snapshot (14W / 15L, net ≈ −9.61, avg +1.45 / −2.00) remains consistent with **asymmetric R** and heavy `m1:mom-buy-*` comments.

## Established root cause (M1)

Evidence supports **negative expectancy from geometry + momentum-chase entries**, not a single execution bug:

1. **Average loser exceeds average winner** (~1R stop vs smaller realized winners) → expectancy negative at observed ~36% win rate.
2. Comment sample dominated by **`m1:mom-buy-`** — momentum entries that reverse before TP.
3. Losses are **not M1-only**: primary / ITE cohort is also net-negative under the prior low RR floor (0.50) and multi-position book.
4. Slippage / commission in the feed are often 0; net after realistic costs would not reverse the sign of M1 expectancy.

## Attribution gap (closing)

- MT5 comment format preserved (`m1:{signal_id}` / primary hash).
- Fill metadata now stamps `strategy_id` for primary OMS path **and** M1 submit (`m1_micro`) into `StrategyStatsBook` via `remember_fill_metadata` — not inferred from comments alone.

## Owner guidance (no silent flag change)

**Recommend suspending `m1_live_submit`** (Admin → Off) while M1 matched expectancy remains negative.  
Do **not** flip deployment env / policy automatically. Five-pack SOE profiles stay separate from research-only / M1.

## Phase-2 policy sync (code defaults)

| Field | Owner target | Enforcement |
|-------|--------------|-------------|
| risk / ceiling | 20% / 20% | unchanged |
| daily halt | 48% | unchanged |
| weekly / overall DD | 0% = **off** | unchanged |
| aggregate open risk | 30% | unchanged |
| max concurrent | **1** | tightened from 5 |
| min / preferred RR | **1.50 / 2.00** | tightened from 0.50 / 1.50 |
| min trade quality | **75** | tightened from 70 |
| max lot / ATR / mandatory SL | 0.01 / 1.0 / true | unchanged |
| grid / martingale / averaging | false | unchanged |

SOE bumped to **soe-v1.2.0** (net RR floor, freshness, false-breakout / exhaustion evidence gates). Prefer `NO_TRADE` over weak setups.
