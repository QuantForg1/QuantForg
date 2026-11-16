# Owner risk baseline — 2026-11-16

Status: **PROPOSED. Not merged, not deployed, no data changed.** LIVE trading stays DISABLED.

## Baseline

| Limit | Before (Production v16) | Owner baseline |
|---|---|---|
| Planned risk per trade | 20% of equity | **9%** |
| Aggregate open risk | 30% | **9%** (one position) |
| Daily stop | 48% of day-start equity | **25%** |
| Net reward:risk after costs | 0.20 (preferred 0.50) | **1.50** |
| Max spread | 1.00 | **0.45** |
| AI trade quality | 70 | **75** |
| Entry window | 00:00–23:59 every day | **Mon–Fri 07:00–17:00 UTC** |
| Lot / positions | 0.01 / 1 | 0.01 / 1 (unchanged) |
| Martingale / grid / forced | off | off (unchanged) |

## Defects fixed in the same change

1. **Daily stop acted only after the damage.** The halt fired once the realised loss was
   already above the cap, so one more trade could push a day far past it. On 2 Nov 2026
   (no deposit that day) 15 entries opened after the loss was above 48%. The final owner
   guard now checks `realised loss + floating loss + planned risk <= daily stop` before
   every new entry (`daily_budget_violation`).
2. **A deposit erased the day's losses** (`session_pnl_resolution` keeps only post-deposit
   P/L). The new `daily_loss_context` counts every trade closed that UTC day; a deposit
   raises the base, it never forgives a loss.
3. **Unknown daily P/L defaulted to zero.** The final guard now rejects new entries when
   today's P/L cannot be verified from broker deals.
4. **The customer's saved risk was ignored on the live path.** It reached only the
   RiskEngine `max_risk_per_trade_pct`, which fixed-lot sizing never reads, and the
   multi-account path. The final guard now applies the account owner's saved
   `planned_risk_pct` and `daily_loss_pct` (strictest wins). A read failure blocks entries.
5. **A net RR between 1.0 and the floor was only a soft reject** in the scan gates. Below
   the owner floor is now always a hard reject.

Closes and SL/TP management are never blocked by any of these checks.

## Rollout (needs owner approval at each gate)

1. Review and merge the PR (code ceilings alone already enforce the baseline, even with
   the old v16 document, because every `active_*` reader clamps to the code ceiling).
2. Deploy to Railway. Keep `live_trading_state = DISABLED`.
3. Export the four records, then run `apply.sql` (G1). Check the SELECT output, then COMMIT.
4. Verify in logs: `runtime_policy_applied version=17` and owner rejects use 9/25/1.50/0.45/75.
5. Only then, and only on separate written approval (G2), re-enable LIVE.

The Windows gateway also enforces the per-trade and book caps (`services/mt5_gateway/order_guard.py`).
It picks up the new caps only when the gateway on the PC is updated to this code.

## Rollback

- Code: revert the PR and redeploy the previous Railway SHA (`3697ce30`).
- Data: `rollback.sql` with `rollback_v16_document.json` (audited v16 document) and the
  JSON export taken in step 3.
