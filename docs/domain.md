# Domain Model (Sprint 2)

Pure business domain for QuantForg. **No database, REST, repositories, SQL,
trading engines, AI, indicators, or MetaTrader code.**

## Design choices

| Concern | Choice |
|---|---|
| Entities | Mutable dataclasses with identity, factories, invariants, lifecycle methods |
| Value objects | Frozen Pydantic v2 models (validate on construction) |
| Enums | `StrEnum` for JSON-friendly vocabularies |
| Errors | `ValidationError` (invariants), `ConflictError` (illegal state transitions) |
| Money / prices | `Decimal` only — floats are rejected |

## Entities and why they exist

| Entity | Why it exists |
|---|---|
| **User** | Platform identity — who can act. Owns email, role, status lifecycle. |
| **License** | Commercial entitlement — which tier a user may use, and for how long. |
| **Broker** | Catalogue of brokerage venues accounts can bind to (no MT/API creds). |
| **TradingAccount** | A user's account at a broker — the root for orders/positions/sessions. |
| **TradingSession** | Connection window to an account (active/idle/closed). |
| **Symbol** | Tradable instrument metadata (code, currencies, pip size). |
| **Order** | Intent to buy/sell with validated type/side/qty and status machine. |
| **Position** | Current market exposure with open/reduce/close lifecycle. |
| **Trade** | Immutable historical fill/ledger record. |
| **Signal** | Time-bounded direction suggestion *record* (not generation). |
| **RiskProfile** | Declared risk limits for a user/account (not a risk engine). |
| **StrategyMetadata** | Strategy *catalogue* entry (name/version/schema) — not strategy logic. |
| **AuditLog** | Append-only forensic event for who did what, when. |

## Value objects

`EmailAddress`, `Money`, `CurrencyCode`, `Price`, `Quantity`, `Percentage`,
`SymbolCode`, `AccountNumber`, `PersonName`, `EntitySlug`, `Leverage`,
`VersionLabel`, `PipSize`, `Confidence`.

## Explicit non-goals (this sprint)

- Order matching / execution against a venue
- P&L / margin / liquidation calculations
- Indicator formulas
- Strategy algorithms
- AI signal generation
- MetaTrader bridges
- Persistence or HTTP APIs
