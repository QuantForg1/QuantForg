# Institutional AI Scalping Engine v7 — Multi-Asset Institutional Scalper

Keeps **v6.3** quality floors and risk knobs unchanged.

## Portfolio scanner

`scan_multi_asset_portfolio()` scores the full universe with **independent**
per-symbol:

- quality / confidence
- adaptive cooldown
- spread
- regime
- execution health

Then ranks and returns **only the best** executable opportunity.

If XAUUSD has no edge and EURUSD does → **EURUSD** is selected.

## Symbol ranking

Reuses `rank_scalping_opportunities` (confidence → expected RR → quality).
Portfolio limits can null the best selection without lowering quality gates:

- max open positions
- daily loss
- portfolio exposure

## Scheduler

`MultiAssetScanScheduler` runs **simultaneous** full-universe cycles each tick
(`symbols_for_cycle()` = entire universe). Optional round-robin `focus_symbol`
is for data-fetch prioritization only.

## Universe

XAUUSD · EURUSD · GBPUSD · USDJPY · NAS100 · US30 · BTCUSD · ETHUSD

## Safeguards

- No quality threshold changes vs v6.3
- No risk-per-trade / martingale / grid changes
- Execute only the top opportunity

## Tests

`tests/unit/test_ai_scalping_v7_multi_asset.py`
