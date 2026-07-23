# Institutional Execution Validation Report

- Generated at: `2026-07-23T16:09:04.597820+00:00`
- Symbol: `XAUUSD`
- Window: **60** days · evaluations **18** · equity **10000** · bars **mt5_gateway:http://127.0.0.1:8765:m15_bars=3987:span_days=59.8**
- Live `order_send` called: **False**
- Strategy / thresholds / risk / safety modified: **False** / **False** / **False** / **False**
- Production gates: Q≥80 · C≥80 · min lot 0.01 · `ite-v1.0.0`

## Verdict

**YES** — at least one production-quality historical setup was found and the complete offline execution pipeline reached Broker fill.

## Execution traces

### Setup 1

- as_of: `2026-06-29T20:15:00+00:00`
- session: `new_york`
- action: **SELL** · Q=83 · C=82 · lots=0.06
- MTF aligned: `True` (score=90)
- pipeline_complete: **True** · decision: `EXECUTE_TRADE`

| Stage | Status | Detail |
|---|---|---|
| Market Data | PASS | bars as_of=2026-06-29T20:15:00+00:00 spread=0.30 |
| Signal Generation | PASS | action=SELL id=ff4aadf8-9f1e-43ed-b818-92c2028bcef6 |
| MTF Alignment | PASS | aligned=True score=90 |
| Quality | PASS | 83 >= 80 |
| Confluence | PASS | 82 >= 80 |
| Risk | PASS | approved_lots=0.06 (>= 0.01) |
| Safety | PASS | status=Enabled |
| Execution Decision | EXECUTE_TRADE | SELL lots=0.06 |
| OMS | PASS | outcome=success ticket=700001 |
| MT5 Gateway | Order Sent (simulated/offline) | gateway_status=order_sent |
| Broker | Order Filled (simulated/offline) | deal=800001 retcode=10009 |

### Setup 2

- as_of: `2026-06-30T18:45:00+00:00`
- session: `new_york`
- action: **SELL** · Q=83 · C=83 · lots=0.05
- MTF aligned: `True` (score=92)
- pipeline_complete: **True** · decision: `EXECUTE_TRADE`

| Stage | Status | Detail |
|---|---|---|
| Market Data | PASS | bars as_of=2026-06-30T18:45:00+00:00 spread=0.30 |
| Signal Generation | PASS | action=SELL id=4d63dbf2-ddc5-4388-92c0-24bdc78be53f |
| MTF Alignment | PASS | aligned=True score=92 |
| Quality | PASS | 83 >= 80 |
| Confluence | PASS | 83 >= 80 |
| Risk | PASS | approved_lots=0.05 (>= 0.01) |
| Safety | PASS | status=Enabled |
| Execution Decision | EXECUTE_TRADE | SELL lots=0.05 |
| OMS | PASS | outcome=success ticket=700001 |
| MT5 Gateway | Order Sent (simulated/offline) | gateway_status=order_sent |
| Broker | Order Filled (simulated/offline) | deal=800001 retcode=10009 |

### Setup 3

- as_of: `2026-07-02T18:15:00+00:00`
- session: `new_york`
- action: **BUY** · Q=83 · C=83 · lots=0.03
- MTF aligned: `True` (score=92)
- pipeline_complete: **True** · decision: `EXECUTE_TRADE`

| Stage | Status | Detail |
|---|---|---|
| Market Data | PASS | bars as_of=2026-07-02T18:15:00+00:00 spread=0.30 |
| Signal Generation | PASS | action=BUY id=11eaa07a-0028-4580-b0e8-951b9d0e749b |
| MTF Alignment | PASS | aligned=True score=92 |
| Quality | PASS | 83 >= 80 |
| Confluence | PASS | 83 >= 80 |
| Risk | PASS | approved_lots=0.03 (>= 0.01) |
| Safety | PASS | status=Enabled |
| Execution Decision | EXECUTE_TRADE | BUY lots=0.03 |
| OMS | PASS | outcome=success ticket=700001 |
| MT5 Gateway | Order Sent (simulated/offline) | gateway_status=order_sent |
| Broker | Order Filled (simulated/offline) | deal=800001 retcode=10009 |

## Reject tallies (search window)

- `action=NO_TRADE`: 15
