# Decision Intelligence completion report

**Date:** 19 November 2026.  
**Branch at authoring:** `feat/trade-explanation`.  
**Production verification of an authenticated paid session:** not performed. This report does not claim the live decision feed was viewed while signed in.

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

## Customer surface

- Page: `/decision-evidence`, behind the existing app shell and the same Signals access gate.
- Links from Signals and AI Trading Intelligence. It is not a new primary rail item.
- `robots.ts` disallows `/decision-evidence`. The authenticated layout is `noindex`.
- Empty, error, and stale states stay in the desk. Missing values stay “Not available”.

## Tests actually run

From the repository virtualenv, 19 November 2026:

- `ruff check` on the decision-evidence service, router, and unit test: passed.
- `pytest tests/unit/test_decision_evidence.py tests/unit/test_growth_intelligence.py`: 21 passed.
- Frontend `decision-evidence.test.ts`, `customer-routes.test.ts`, and `learn-catalog.test.ts`: passed.

Not run: `pytest -m trading_core`. This work does not modify the scheduler, strategy engine, risk enforcement, OMS, MT5 gateway, or position management. The full trading-core suite was not used as a substitute for that review.

## Not claimed

- No authenticated production session opened the report.
- No order was submitted during these tests.
- No historical risk limit was invented.
- No performance, win rate, or profit figure is produced by this report.
