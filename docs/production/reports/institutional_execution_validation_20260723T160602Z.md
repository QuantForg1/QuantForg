# Institutional Execution Validation Report

- Generated at: `2026-07-23T16:05:59.403559+00:00`
- Symbol: `XAUUSD`
- Window: **90** days · evaluations **5** · equity **10000** · bars **synthetic_deterministic**
- Live `order_send` called: **False**
- Strategy / thresholds / risk / safety modified: **False** / **False** / **False** / **False**
- Production gates: Q≥80 · C≥80 · min lot 0.01 · `ite-v1.0.0`

## Verdict

**YES** — at least one production-quality historical setup was found and the complete offline execution pipeline reached Broker fill.

## Execution traces

### Setup 1

- as_of: `2026-05-04T08:45:00+00:00`
- session: `london`
- action: **BUY** · Q=90 · C=90 · lots=0.45
- MTF aligned: `True` (score=92)
- pipeline_complete: **True** · decision: `EXECUTE_TRADE`

| Stage | Status | Detail |
|---|---|---|
| Market Data | PASS | bars as_of=2026-05-04T08:45:00+00:00 spread=0.30 |
| Signal Generation | PASS | action=BUY id=9dc58cad-df9c-43ea-bff9-c3c726da19e0 |
| MTF Alignment | PASS | aligned=True score=92 |
| Quality | PASS | 90 >= 80 |
| Confluence | PASS | 90 >= 80 |
| Risk | PASS | approved_lots=0.45 (>= 0.01) |
| Safety | PASS | status=Enabled |
| Execution Decision | EXECUTE_TRADE | BUY lots=0.45 |
| OMS | PASS | outcome=success ticket=700001 |
| MT5 Gateway | Order Sent (simulated/offline) | gateway_status=order_sent |
| Broker | Order Filled (simulated/offline) | deal=800001 retcode=10009 |

### Setup 2

- as_of: `2026-05-05T08:15:00+00:00`
- session: `london`
- action: **SELL** · Q=87 · C=80 · lots=0.45
- MTF aligned: `True` (score=70)
- pipeline_complete: **True** · decision: `EXECUTE_TRADE`

| Stage | Status | Detail |
|---|---|---|
| Market Data | PASS | bars as_of=2026-05-05T08:15:00+00:00 spread=0.30 |
| Signal Generation | PASS | action=SELL id=f92cdc94-2634-4612-92ea-7ed0a219e266 |
| MTF Alignment | PASS | aligned=True score=70 |
| Quality | PASS | 87 >= 80 |
| Confluence | PASS | 80 >= 80 |
| Risk | PASS | approved_lots=0.45 (>= 0.01) |
| Safety | PASS | status=Enabled |
| Execution Decision | EXECUTE_TRADE | SELL lots=0.45 |
| OMS | PASS | outcome=success ticket=700001 |
| MT5 Gateway | Order Sent (simulated/offline) | gateway_status=order_sent |
| Broker | Order Filled (simulated/offline) | deal=800001 retcode=10009 |

### Setup 3

- as_of: `2026-05-05T12:45:00+00:00`
- session: `london`
- action: **SELL** · Q=87 · C=80 · lots=0.44
- MTF aligned: `True` (score=70)
- pipeline_complete: **True** · decision: `EXECUTE_TRADE`

| Stage | Status | Detail |
|---|---|---|
| Market Data | PASS | bars as_of=2026-05-05T12:45:00+00:00 spread=0.30 |
| Signal Generation | PASS | action=SELL id=54934978-f99a-4fb4-af19-4cf71e570972 |
| MTF Alignment | PASS | aligned=True score=70 |
| Quality | PASS | 87 >= 80 |
| Confluence | PASS | 80 >= 80 |
| Risk | PASS | approved_lots=0.44 (>= 0.01) |
| Safety | PASS | status=Enabled |
| Execution Decision | EXECUTE_TRADE | SELL lots=0.44 |
| OMS | PASS | outcome=success ticket=700001 |
| MT5 Gateway | Order Sent (simulated/offline) | gateway_status=order_sent |
| Broker | Order Filled (simulated/offline) | deal=800001 retcode=10009 |

## Reject tallies (search window)

- `action=NO_TRADE`: 2
