# Order Block Engine (Sprint 8)

Pure domain engine for order blocks, zones, mitigation, breakers, and quality.

**Not included:** trading, AI, MetaTrader, trade signals, indicators, SQL, REST,
or execution.

Package: `app/domain/order_block/`  
Ports: `app/domain/interfaces/order_block.py`  
Events: `app/domain/events/order_block.py`

## Entities (immutable)

| Entity | Why it exists |
|---|---|
| **OrderBlockZone** | Price band of the origin candle (geometry). |
| **OrderBlock** | Last opposing candle before displacement + lifecycle. |
| **OrderBlockQuality** | Descriptive strength metrics (not a signal score). |
| **BreakerBlock** | OB invalidated by opposing close-through. |
| **MitigationBlock** | Price revisit into the OB zone. |
| **OrderBlockSnapshot** | Immutable multi-field view for one symbol + timeframe. |

## Lifecycle state machine

```
DETECTED → VALIDATED → ACTIVE → MITIGATED
                ↓           ↓         ↓
             EXPIRED     BREAKER ←────┘
                            ↓
                         EXPIRED
```

Illegal transitions raise `ValidationError` via `OrderBlock.transition`.

## Services

| Service | Why it exists |
|---|---|
| **OrderBlockDetector** | OB from BOS/CHoCH + last opposing candle. |
| **OrderBlockValidator** | Displacement / integrity gates → ACTIVE or EXPIRED. |
| **MitigationDetector** | Overlap of later bars with active zones. |
| **BreakerDetector** | Close through zone against bias → BREAKER. |
| **OrderBlockStrengthEvaluator** | Attach `OrderBlockQuality` (score/grade). |
| **OrderBlockEngine** | Orchestrate ports → snapshot + events. |

## Ports

| Port | Responsibility |
|---|---|
| `PriceHistoryPort` | Ordered OHLCV bars (shared with liquidity). |
| `MarketStructurePort` | Latest structure snapshot (BOS/CHoCH). |
| `LiquiditySnapshotPort` | Optional liquidity confluence. |
| `OrderBlockRepositoryPort` | Save/load snapshots (no SQL). |

## Events

| Event | When |
|---|---|
| `OrderBlockDetected` | New OB id vs prior snapshot. |
| `OrderBlockValidated` | DETECTED → VALIDATED/ACTIVE. |
| `MitigationDetected` | New mitigation id. |
| `BreakerDetected` | New breaker id. |
| `OrderBlockExpired` | Transition into EXPIRED. |
| `OrderBlockStateChanged` | Any lifecycle state change. |

## Detection rules

- **Bullish OB:** last down-close candle before upward BOS/CHoCH displacement.
- **Bearish OB:** last up-close candle before downward displacement.
- Zone = origin candle high/low; identities via **UUIDv5**.
- Validation requires minimum displacement ratio vs zone range.
- Mitigation: later bar overlaps zone (partial/full by penetration).
- Breaker: later **close** beyond zone against OB bias.

## Design notes

- **Decimal** prices; **UTC** timestamps.
- Multi-symbol / multi-timeframe via `symbol_code` + `timeframe`.
- Snapshots immutable; engine returns `OrderBlockResult(snapshot, events)`.

## Usage (domain only)

```python
engine = OrderBlockEngine(
    prices=price_history,
    structure=structure_port,
    liquidity=optional_liquidity,
    repository=optional_repo,
)
result = await engine.analyze("EURUSD", Timeframe.M15, persist=True)
```

## Tests

- `tests/unit/test_order_block_services.py`
- `tests/unit/test_order_block_engine.py`
- `tests/unit/order_block_fakes.py`
