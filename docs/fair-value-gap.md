# Fair Value Gap Engine (Sprint 9)

Pure domain engine for three-candle fair value gaps, fills, invalidation, and
quality.

**Not included:** trading, AI, MetaTrader, trade signals, indicators, SQL, or
REST.

Package: `app/domain/fair_value_gap/`  
Ports: `app/domain/interfaces/fair_value_gap.py`  
Events: `app/domain/events/fair_value_gap.py`

## Entities (immutable)

| Entity | Why it exists |
|---|---|
| **FairValueGapZone** | Price band of the imbalance (geometry). |
| **GapLifecycle** | State machine position + timestamps + fill ratio. |
| **FairValueGap** | Three-candle FVG with side, zone, lifecycle. |
| **GapFill** | Partial/full fill observation. |
| **GapQuality** | Descriptive strength metrics (not a signal score). |
| **FairValueGapSnapshot** | Immutable view for one symbol + timeframe. |

## Lifecycle state machine

```
DETECTED → ACTIVE → PARTIALLY_FILLED → FILLED
               ↓            ↓
          INVALIDATED ←─────┘
               ↓
            EXPIRED  (also from ACTIVE / PARTIALLY_FILLED / FILLED / INVALIDATED)
```

Illegal transitions raise `ValidationError` via `GapLifecycle.transition` /
`FairValueGap.transition`.

## Services

| Service | Why it exists |
|---|---|
| **FairValueGapDetector** | Geometric 3-candle bullish/bearish FVG detection. |
| **GapFillDetector** | Partial/full fill ratio from later bars. |
| **GapInvalidationDetector** | Opposing close-through → INVALIDATED. |
| **GapQualityEvaluator** | Attach `GapQuality` (score/grade, OB confluence). |
| **FairValueGapEngine** | Orchestrate ports → snapshot + events. |

## Ports

| Port | Responsibility |
|---|---|
| `PriceHistoryPort` | Ordered OHLCV bars (shared). |
| `MarketStructurePort` | Optional structure context. |
| `OrderBlockSnapshotPort` | Optional OB confluence. |
| `FairValueGapRepositoryPort` | Save/load snapshots (no SQL). |

## Events

| Event | When |
|---|---|
| `FairValueGapDetected` | New gap id vs prior snapshot. |
| `GapPartiallyFilled` | New partial fill. |
| `GapFilled` | New full fill. |
| `GapInvalidated` | Gap invalidated. |
| `FairValueGapExpired` | Transition into EXPIRED. |
| `FairValueGapStateChanged` | Any lifecycle state change. |

## Detection rules

- **Bullish FVG:** `candle[i].low > candle[i-2].high` → zone `[left.high, right.low]`.
- **Bearish FVG:** `candle[i].high < candle[i-2].low` → zone `[right.high, left.low]`.
- Identities via **UUIDv5** (symbol, timeframe, side, middle bar, prices).
- **Fill:** later overlap; ratio by penetration into the zone.
- **Invalidate:** bullish close `< zone.low`; bearish close `> zone.high`.

## Design notes

- **Decimal** prices; **UTC** timestamps.
- Multi-symbol / multi-timeframe via `symbol_code` + `timeframe`.
- Snapshots immutable; engine returns `FairValueGapResult(snapshot, events)`.

## Usage (domain only)

```python
engine = FairValueGapEngine(
    prices=price_history,
    structure=optional_structure,
    order_blocks=optional_ob,
    repository=optional_repo,
)
result = await engine.analyze("EURUSD", Timeframe.M15, persist=True)
```

## Tests

- `tests/unit/test_fair_value_gap_services.py`
- `tests/unit/test_fair_value_gap_engine.py`
- `tests/unit/fair_value_gap_fakes.py`
