# Production Validation Report — `val_920c6e0cf36f4b94`

> Observability only. No fabricated trades. Real production events.

- **Timestamp:** 2026-07-30T21:39:34.723062Z
- **Symbol:** XAUUSD
- **Session:** new_york
- **Execution mode:** live
- **Signal ID:** —
- **AI action:** —
- **AI confidence:** —
- **Quality score:** —
- **Confluence:** —
- **MTF alignment:** —
- **Risk score:** —
- **Expected RR:** —
- **Spread:** —
- **ATR:** —

## Pipeline Summary

| Stage | Status | Latency (ms) | Reason |
| --- | --- | --- | --- |
| Scheduler | PASS | 1.00 | tick |
| Market Data | PASS | 12.00 | bars ok |
| Context | PASS | — | snapshot ok |
| AI | FAIL | — | quality below threshold |
| Risk | PASS | — | risk ok |
| Eligibility | FAIL | — | Quality below threshold |
| Execution Bridge | PENDING | — | — |
| OMS | PENDING | — | — |
| Gateway | PENDING | — | — |
| MT5 | PENDING | — | — |
| Broker | PENDING | — | — |
| Position Open | PENDING | — | — |
| Position Close | PENDING | — | — |

## Acceptance

- **Final result:** BLOCKED
- **Accepted:** False
- **Broker ticket:** —
- **Execution latency (ms):** —
- **First blocker:** AI: quality below threshold

## NO_TRADE Reasons (individual)

- Quality below threshold
- Spread
- Session blocked
- Risk

