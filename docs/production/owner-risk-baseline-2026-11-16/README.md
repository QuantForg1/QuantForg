# Owner risk baseline — 2026-11-16

Status: **PROPOSED. Not merged, not deployed, no data changed.**

LIVE was re-enabled by the owner on 15 Nov 2026, 23:45 UTC (audit: DISABLED → READY_FOR_REVIEW → ARMED → ENABLED, operator P7 PROVIDER). It is running on the pre-#295 code. On 16 Nov the owner chose to leave it running. Nothing in this release changes `live_trading_state`, the kill switch or the auto-trading run state.

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
2. Deploy to Railway, with no position open. The LIVE state is not changed.
3. Run `apply.sql` (G1). The pre-apply state is already exported in `rollback_pre_apply_state.json`. Check the SELECT output, then COMMIT.
4. Verify in logs: `runtime_policy_applied version=17` and owner rejects use 9/25/1.50/0.45/75.
5. Update the Windows gateway: `GATEWAY_UPDATE.md`.

The Windows gateway also enforces the per-trade and book caps (`services/mt5_gateway/order_guard.py`).
It picks up the new caps only when the gateway on the PC is updated to this code.

## Rollback

- Code: revert the PR and redeploy the previous Railway SHA (`3697ce30`).
- Data: `rollback.sql` with `rollback_v16_document.json` (audited v16 document) and
  `rollback_pre_apply_state.json`.
- Gateway: `GATEWAY_UPDATE.md` → Rollback.

## Release evidence (16 Nov 2026)

| # | Check | Result |
|---|---|---|
| 1 | PR diff and CI | Head `70c7266d` on base `798c802f`, mergeable clean. All 7 CI jobs pass (Lint & Format, Type Check, Unit, Trading Core Regression, Integration, Frontend, Design Governance). Local: 4,996 unit tests, 2,199 trading-core tests, frontend tsc and tests green. |
| 2 | Policies on every execution path | Every backend entry (robot and manual `/execution`) goes through `InstitutionalExecutionEngine.run_submit` → `evaluate_owner_entry` and `presend_owner_violations`. This includes Weltrade, the only connected broker. The gateway guard adds the 9% per-trade and book caps once the PC is updated. **Gap (not live):** `multi_account_oms_execution.authorize_worker_execution` does not call the owner guard, and it takes the environment from the job payload (default `demo`). It has 0 workers and 0 hosts today. It must be fixed in its own PR before DEMO acceptance. |
| 3 | Daily stop, deposits, fail-closed | Tested in `test_owner_daily_budget_and_user_caps.py` (19 tests): pre-trade budget, floating loss, a deposit never forgives a loss, untrusted or missing P/L rejects, user settings can only tighten, read failure rejects. Replays: 2 Nov (`…user_caps.py`) and 16 Nov (`test_owner_baseline_nov16_replay.py`, 22 tests). |
| 4 | DB migration | All 4 UPDATEs EXPLAINed on Production (read-only, index or pkey per row). New values satisfy every CHECK constraint (`planned ≤ 20`, `aggregate ≤ 30`, `daily ≤ 48`, `quality ≥ 70`, `RR ≥ 0.20`, `aggregate ≥ planned`). Only `updated_at` triggers fire. Pre-apply state is exported. |
| 5 | Gateway | `GATEWAY_UPDATE.md`. |
| 6 | LIVE state | **ENABLED** by the owner (see Status), not DISABLED. |

### 16 Nov replay: what the new code would have done

LIVE opened 20 entries on Weltrade-Real from 02:16 to 09:45 UTC. The balance went from about $20.69 to $12.30. Replayed against PR #295, **all 20 are rejected**:

- 20 of 20: planned risk above 9% of equity (`OWNER_SL_RISK`)
- 16 of 20: net RR below 1.50 (`OWNER_MIN_RR`)
- 12 of 20: opened before 07:00 UTC (`OWNER_SESSION`)
- 3 of 20: daily budget (`OWNER_DAILY_BUDGET`); the last entry hit the daily stop (`OWNER_DAILY_STOP`)

### What to expect after release on a $12.30 account

At 0.01 lot, a $1 move in gold is $1 of P/L. With 9% of $12.30, about $1.10 can be at risk per trade, including spread. The robot's stops on 16 Nov were $1.50–$3.50 away. Expect **very few or no entries** until the robot finds tighter setups or the balance grows. This is the policy working as approved, not a fault. The daily stop at 25% is about $3.07, which is two or three losing trades.
