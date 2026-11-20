# Decision Intelligence completion report

**Date:** 19 November 2026.  
**Branch at authoring:** `feat/trade-explanation`.  
**Production verification of an authenticated paid session:** not performed. This report does not claim the live decision feed was viewed while signed in.

## Release

`origin/main` at the 19 November 2026 recheck is `38f5dc8bf`. `c6953bd34` is an ancestor, not the tip.

The Ready production deployment is `quant-forg-5d6kvxki1` (`dpl_57tTbCYJu9rE86htaBz3DQLL7Dm1`). The build log clones `38f5dc8`. Aliases include `https://www.quantforg.com` and `https://quantforg.com`.

Checked without a signed-in session:

- `GET /learn/decision-lifecycle` on www returned 200.
- `GET /decision-evidence` returned the app shell. That is not a loaded decision report.
- `GET /api/v1/decision-evidence/report` and `/history` returned 401 `missing_token`.
- No paid, unpaid, owner, or admin session was available, so entitlement differences and report contents were not observed in production.

## What this is

Decision Evidence is a read-only projection of the existing Signal Center row and the existing signal-history rows. It does not score, size, authorize, or send orders. It does not call the institutional decision evaluator, the strategy engine, the risk engine, the OMS, or the MT5 gateway.

Endpoints, both GET:

- `/api/v1/decision-evidence/report?symbol=`
- `/api/v1/decision-evidence/history?symbol=&limit=`

`limit` is bounded to 1–50. `symbol` is limited to 32 characters. The router uses the existing Signals subscription dependency. Owner and admin access follows that dependency, including the designated-owner check already used by other owner routes. Unpaid customers receive the existing entitlement response from that dependency. The router is not in the operator-only module list, so a paying customer is not rejected before the subscription check.

History is loaded with `observe=False`. A history read does not write a new snapshot.

## Provenance

| Display | Source | When it is missing |
| --- | --- | --- |
| Decision word | Signal row `direction` / decision field | `Awaiting engine evidence` when the live feed has no row |
| BUY, SELL, WAIT, HOLD, NO_TRADE, EXECUTION_BLOCKED | Stored decision word | Not relabelled. NO_TRADE is not rewritten as REJECT |
| ORDER_SENT | Stored lifecycle | Not treated as FILLED |
| FILLED | Stored lifecycle only | Not inferred from BUY or SELL |
| NOT_REACHED | Stored gate | Result stays `not_performed`. It is not a pass |
| Risk limit | Only a limit stored on that record | `Not available`. A current profile limit is not copied onto an older row |
| Market fields on history | Only fields the history row stored | `Not available`, with `history_note` stating they are not reconstructed from the current market |
| Stale | Pipeline data state STALE, or quote age over 120 seconds | The report says the evidence is stale. It does not refresh it |

Flags on every report: `read_only`, `executes_orders` false, `invents_reasoning` false, `calculates_risk` false, `decision_is_not_an_order` true.

## History limitation

Live signal rows carry market, pipeline, risk-gate, and lifecycle fields. Signal-history rows are thinner: direction, quality, confidence, strategy id, reject reason, blocking gate, factors, and raw score. They do not include a user id. The desk shows that limitation in `history_note` when a history row is selected. It does not backfill spread, ATR, risk, or tickets from the current quote.

## Journal blocker

A durable per-user decision journal was not created.

Signal history cannot support it: rows have no owner, so they cannot be isolated per customer. Adding an append-only journal table would be a new production data store and a schema migration. That migration was not written and was not executed.

Approval still required before any journal table: explicit permission to add an append-only evidence table, a retention period, and an access policy that stores only source ids, timestamps, and fields the platform already recorded.

Proposed shape, not migrated:

- Table `decision_journal_entries`, append-only. Columns: `id`, `user_id` (required, indexed), `source_kind`, `source_id`, `symbol`, `recorded_at`, `copied_fields` (only fields the source row already had), `created_at`.
- Access: the authenticated user can read only rows with their `user_id`. No cross-account list.
- Retention: undefined. A 24-month delete needs a separate decision. No automatic delete is implemented.
- Backfill: none. History rows have no owner, so they cannot be assigned to a customer.
- Rollback: drop the new table only if it has not been used to replace an existing store. Do not delete signal history.
- Privacy: no broker passwords, tokens, or account secrets. Global signal history stays a platform feed, not a personal journal.

## Customer surface

- Page: `/decision-evidence`, behind the existing app shell and the same Signals access gate.
- Links from Signals and AI Trading Intelligence. It is not a new primary rail item.
- `robots.ts` disallows `/decision-evidence`. The authenticated layout is `noindex`.
- Empty, error, and stale states stay in the desk. Missing values stay “Not available”.

## Tests actually run

From the repository virtualenv, 19 November 2026:

- `ruff check` on the decision-evidence and growth modules: passed.
- `pytest tests/unit/test_decision_evidence.py tests/unit/test_growth_intelligence.py`: 19 passed on the GET-only growth router.
- Frontend `decision-evidence.test.ts`, `customer-routes.test.ts`, and `learn-catalog.test.ts`: passed.

`pytest -m trading_core -q --tb=line --no-cov -p no:cacheprovider` finished with exit code 0: 2318 passed, 3328 deselected, 3 xfailed. The xfail cases are the known gold-only markers in `test_cycle_timeout_budget.py` and `test_multi_market_live_execution.py`. The scheduler, strategy engine, risk enforcement, OMS, MT5 gateway, and position management were not edited.

## Not claimed

- No authenticated production session opened the report.
- No order was submitted during these tests.
- No historical risk limit was invented.
- No performance, win rate, or profit figure is produced by this report.
