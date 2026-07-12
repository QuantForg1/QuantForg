# Market Context Engine (Sprint 5)

Pure domain engine that answers: *what is the market regime right now?*

**Not included:** trading, AI, MetaTrader, indicators, strategies, trade
execution, or infrastructure adapters (ports only).

## Components

| Class | Why it exists |
|---|---|
| **MarketContext** | Aggregate holding session, open/closed state, day type, liquidity & volatility levels, UTC/local times, DST flag. Emits lifecycle events. |
| **MarketClock** | UTC-first clock façade over `ClockPort` with timezone conversion and DST helpers (`zoneinfo`). |
| **SessionResolver** | Maps a UTC instant onto a named session using DST-aware local windows from `SessionPort`. |
| **TradingCalendarService** | Classifies local dates as trading day / weekend / holiday via `CalendarPort`. |
| **LiquidityProfileResolver** | Resolves qualitative liquidity from `LiquidityProfilePort` (no order-book maths). |
| **VolatilityProfileResolver** | Resolves qualitative volatility from `VolatilityProfilePort` (no indicators). |
| **MarketContextEngine** | Orchestrates the above to `build` / `refresh` a `MarketContext`. |

## Ports (interfaces only)

| Port | Responsibility |
|---|---|
| `ClockPort` | Supply UTC `now()`. |
| `SessionPort` | Provide `MarketSessionSchedule` per market. |
| `CalendarPort` | Weekend / holiday facts. |
| `LiquidityProfilePort` | `(session, day_type) → LiquidityProfile`. |
| `VolatilityProfilePort` | `(session, day_type) → VolatilityProfile`. |

## Events

| Event | When |
|---|---|
| `MarketContextCreated` | Context aggregate created. |
| `MarketContextUpdated` | Context refreshed. |
| `SessionChanged` | Resolved session name changed. |
| `MarketOpened` | State became `OPEN`. |
| `MarketClosed` | State became closed/holiday/weekend. |

## Time rules

- All internal instants are timezone-aware **UTC**.
- Local wall times use IANA zones (`Europe/London`, `America/New_York`, …).
- DST is handled by `zoneinfo` (offsets and `is_dst` reflect transitions).

## Immutable models

`SessionWindow`, `MarketSessionSchedule`, `LiquidityProfile`, `VolatilityProfile`
are frozen. `MarketContext` is a mutable aggregate (identity + pending events).
