# Liquidity Engine (Sprint 7)

Pure domain engine for equal highs/lows, liquidity pools/zones, and sweeps.

**Not included:** trading, AI, MetaTrader, trade signals, classic indicators,
SQL, or REST.

Distinct from Sprint 5 market-context **session** liquidity
(`LiquidityProfile` / `LiquidityLevel`) — this package models **price-level**
liquidity structure.

Package: `app/domain/liquidity/`  
Ports: `app/domain/interfaces/liquidity.py`  
Events: `app/domain/events/liquidity.py`

## Entities (immutable)

| Entity | Why it exists |
|---|---|
| **EqualHighs** | ≥2 swing highs at (near) one price — sell-side liquidity. |
| **EqualLows** | ≥2 swing lows at (near) one price — buy-side liquidity. |
| **LiquidityPool** | Normalised resting liquidity at a price (active/swept). |
| **LiquidityZone** | Price band aggregating pool(s) on one side. |
| **LiquiditySweep** | Wick-through + reclaim of a pool (structural fact). |
| **LiquidityState** | Qualitative bias from active vs swept pools. |
| **LiquiditySnapshot** | Immutable multi-field view for one symbol + timeframe. |

## Services

| Service | Why it exists |
|---|---|
| **EqualHighDetector** | Cluster HIGH swings within tolerance → `EqualHighs`. |
| **EqualLowDetector** | Cluster LOW swings within tolerance → `EqualLows`. |
| **LiquidityZoneBuilder** | Map equals → pools + zones (deterministic IDs). |
| **LiquiditySweepDetector** | Detect high/low sweeps of active pools from candles. |
| **LiquidityEngine** | Orchestrate history → equals → zones → sweeps → snapshot + events. |

## Ports

| Port | Responsibility |
|---|---|
| `PriceHistoryPort` | Load ordered OHLCV bars. |
| `SwingProviderPort` | Supply swings (typically Sprint 6 detector). |
| `MarketStructurePort` | Optional latest structure snapshot. |
| `LiquidityRepositoryPort` | Save/load snapshots (interface only — no SQL). |

## Events

| Event | When |
|---|---|
| `LiquidityPoolDetected` | New pool ID vs prior snapshot. |
| `LiquidityZoneCreated` | New zone ID vs prior snapshot. |
| `LiquiditySweepDetected` | New sweep ID vs prior snapshot. |
| `LiquidityStateChanged` | State kind differs from prior (or first run). |

## Sweep rules

- **Sell-side (equal highs):** later bar with `high > pool` and `close < pool`.
- **Buy-side (equal lows):** later bar with `low < pool` and `close > pool`.
- Only bars **after** the pool’s last forming bar are considered.
- At most one sweep recorded per pool per analysis pass.

## Design notes

- **Decimal** prices via `Price` / `Candle`.
- **Multi-symbol / multi-timeframe** via `symbol_code` + `timeframe`.
- Snapshots are **immutable**; engine returns `LiquidityResult(snapshot, events)`.
- Equal / pool / zone / sweep IDs are deterministic (`uuid5`).

## Usage (domain only)

```python
engine = LiquidityEngine(
    prices=price_history,     # PriceHistoryPort
    swings=swing_provider,    # SwingProviderPort
    structure=optional_ms,    # MarketStructurePort | None
    repository=optional_repo, # LiquidityRepositoryPort | None
    swing_left=2,
    swing_right=2,
)
result = await engine.analyze("EURUSD", Timeframe.M15, persist=True)
# result.snapshot — LiquiditySnapshot
# result.events   — LiquidityPoolDetected | …
```

## Tests

- `tests/unit/test_liquidity_services.py` — equals, zones, sweeps
- `tests/unit/test_liquidity_engine.py` — orchestration, events, multi-symbol
- `tests/unit/liquidity_fakes.py` — in-memory ports + synthetic series
