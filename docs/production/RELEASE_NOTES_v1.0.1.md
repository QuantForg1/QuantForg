# QuantForg v1.0.1 — Release Notes

## Summary

Production optimization sprint on the v1.0.0 baseline. Bug fixes, performance visibility, and reliability improvements only.

**No new trading strategies. No architecture redesign. No new AI modules.**

## Bug fixes

- Reports desk no longer a placeholder — loads `/ecosystem/reports` + `/execution/optimization`
- Auto Trading performance strip no longer hardcodes Profit Factor / Expectancy / Avg R / Hold as permanent `"—"` when live facts exist
- Alert floods reduced via cooldown grouping + occurrence counts

## Performance improvements

- Execution analytics expose latency & slippage percentiles (P50 / P90 / P95 / P99)
- Per-trade timeline fields (decision → submit → ack → fill) when timestamps exist
- Abnormal execution highlighting (latency/slippage outliers + rejects)
- Broker quality composite score from fill / reject / slip / latency / reconnect facts

## Reliability improvements

- Risk trend reports: daily/weekly/monthly drawdown, streaks, average R, largest win/loss
- Session analytics: Sydney, Tokyo, London, New York, overlap — never mixed
- Regime analytics: trend / range / HV / LV / news — never mixed
- Ops alerts return `grouped` payload for operator desks
- Period reports include Performance / Risk / Execution / Reliability / Known Issues / Recommendations

## Migration

None required. Optional: operators should open `/reports` and `/execution/optimization` after deploy.

## Known limitations

- Percentiles / PF / expectancy remain unavailable until enough real attempts/fills exist
- Journal rows without PnL cannot populate risk/session expectancy
- Multi-day soak wall-clock evidence remains operator-owned (see v1.0.0)
