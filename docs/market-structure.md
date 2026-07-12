# Market Structure Engine (Sprint 6)

Pure domain engine for swing structure, BOS/CHoCH, and qualitative trend.

**Not included:** trading, AI, MetaTrader, trade signals, classic indicators
(RSI/MACD/…), SQL, or REST.

Package: `app/domain/market_structure/`  
Ports: `app/domain/interfaces/market_structure.py`  
Events: `app/domain/events/market_structure.py`

## Entities (immutable)

| Entity | Why it exists |
|---|---|
| **SwingPoint** | Confirmed pivot high/low (structure atom). Stable UUID5 identity. |
| **StructureNode** | Swing annotated with HH/HL/LH/LL role in sequence. |
| **TrendState** | Qualitative up/down/range/unknown from structure roles. |
| **BreakOfStructure** | With-trend break of a prior swing (continuation fact). |
| **ChangeOfCharacter** | Against-trend break (character-change fact). |
| **StructureSnapshot** | Immutable multi-field view for one symbol + timeframe. |

## Services

| Service | Why it exists |
|---|---|
| **SwingDetector** | Fractal left/right pivot detection (`SwingDetectorPort`). |
| **StructureAnalyzer** | Build HH/HL/LH/LL nodes; detect BOS/CHoCH from closes. |
| **TrendClassifier** | Classify trend from recent structure roles (`TrendAnalyzerPort`). |
| **MarketStructureEngine** | Orchestrate series → swings → structure → trend → snapshot + events. |

## Ports

| Port | Responsibility |
|---|---|
| `PriceSeriesPort` | Load ordered OHLCV bars. |
| `SwingDetectorPort` | Detect swings from candles. |
| `TrendAnalyzerPort` | Classify trend from nodes. |
| `StructureRepositoryPort` | Save/load snapshots (interface only — no SQL). |

## Events

| Event | When |
|---|---|
| `SwingDetected` | New swing ID vs prior snapshot. |
| `StructureChanged` | Every successful analysis pass. |
| `BreakOfStructureDetected` | New BOS vs prior snapshot. |
| `ChangeOfCharacterDetected` | New CHoCH vs prior snapshot. |
| `TrendChanged` | Trend direction differs from prior (or first run). |

## Structure rules

- **Swing:** bar extreme strictly greater/less than `left` and `right` neighbours.
- **Roles:** successive same-kind swings → HH/HL/LH/LL (or EQH/EQL).
- **Uptrend BOS:** close above a prior swing high; **CHoCH:** close below a prior swing low.
- **Downtrend BOS:** close below a prior swing low; **CHoCH:** close above a prior swing high.
- **Range / unknown:** no BOS/CHoCH emitted.

## Design notes

- **Decimal** prices via existing `Price` VO / `Candle` model.
- **Multi-symbol / multi-timeframe** via `symbol_code` + `timeframe` on every record.
- Snapshots are **immutable**; engine returns `MarketStructureResult(snapshot, events)`.
- Swing IDs are deterministic (`uuid5`) so re-analysis can suppress duplicate events.

## Usage (domain only)

```python
engine = MarketStructureEngine(
    prices=price_series,       # PriceSeriesPort
    swings=SwingDetector(),
    trends=TrendClassifier(),
    repository=optional_repo,  # StructureRepositoryPort | None
    swing_left=2,
    swing_right=2,
)
result = await engine.analyze("EURUSD", Timeframe.M15, persist=True)
# result.snapshot  — StructureSnapshot
# result.events    — SwingDetected | StructureChanged | …
```

## Tests

- `tests/unit/test_market_structure_services.py` — detector, analyzer, classifier
- `tests/unit/test_market_structure_engine.py` — orchestration, events, multi-symbol
- `tests/unit/market_structure_fakes.py` — in-memory ports + synthetic series
