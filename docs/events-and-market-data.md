# Event System & Market Data Foundation (Sprint 4)

Foundation only: domain events, an in-process event bus, immutable market-data
models, and ports. **No MetaTrader, AI, strategies, indicators, trade
execution, REST, or SQL repositories.**

## Components

### Domain events

| Class | Role |
|---|---|
| `DomainEvent` | Immutable event envelope (id, UTC `occurred_at`, correlation). |
| `TickReceived` | A tick observation was accepted. |
| `QuoteUpdated` | A bid/ask quote was accepted. |
| `CandleClosed` | An OHLCV bar closed. |
| `SpreadObserved` | A spread observation was recorded. |
| `MarketSnapshotCaptured` | A multi-symbol snapshot was captured. |
| `MarketDataStored` | A record was confirmed stored via the storage port. |

### Event bus

| Class | Role |
|---|---|
| `EventSubscriber` | Port: declares types + `handle(event)`. |
| `EventPublisherPort` | Port: `publish` / `publish_many`. |
| `EventDispatcherPort` | Port: deliver an event to matching subscribers. |
| `EventBusPort` | Port: subscribe + publish façade. |
| `EventDispatcher` | In-process router (`isinstance` matching). |
| `EventPublisher` | Forwards events to a dispatcher. |
| `BaseEventSubscriber` | Convenience base for adapters. |
| `InProcessEventBus` | Composed local bus (foundation adapter). |

### Market data models (immutable, UTC, Decimal prices)

| Class | Role |
|---|---|
| `Timeframe` | Bar length enum (`M1`…`MN1`) with duration helper. |
| `Tick` | Single price (+ optional volume) for one symbol. |
| `Quote` | Bid/ask pair; derives mid and spread. |
| `Spread` | `ask - bid` observation. |
| `Candle` | OHLCV bar for a symbol + timeframe. |
| `SymbolMarketView` | Per-symbol slice inside a snapshot. |
| `MarketSnapshot` | One or many symbol views at a capture time. |

Multi-symbol support is first-class via `symbol_code` on every observation
and `MarketSnapshot.views`.

### Ports

| Port | Role |
|---|---|
| `MarketDataProviderPort` | Fetch latest ticks/quotes/candles/snapshots. |
| `MarketDataStoragePort` | Persist/retrieve observations (no SQL in contract). |
| `TimeProviderPort` | Supply UTC "now" (injectable clock). |

### Foundation adapters

| Class | Role |
|---|---|
| `InMemoryMarketDataStore` | Process-local `MarketDataStoragePort`. |
| `InMemoryMarketDataProvider` | Provider reading from storage. |
| `UtcTimeProvider` / `FixedTimeProvider` | Real and test clocks. |
| `MarketDataIngestionService` | Application orchestration: validate → store → publish. |

## Explicit non-goals

Venue SDKs, indicator math, strategy logic, order execution, REST APIs,
SQLAlchemy market-data repositories.
