# Application Layer (Sprint 3)

Use cases orchestrate domain aggregates through **ports only** (Dependency
Inversion). No SQL, REST, MetaTrader, AI, or trading engines.

## Architecture rule

```
use case  →  UnitOfWorkPort / AppInfoPort / HealthCheckPort  →  (adapters later)
     ↓
   DTOs out
```

## Use cases

| Use case | Why it exists |
|---|---|
| **RegisterUserUseCase** | Onboard a pending user; enforces unique email. |
| **ActivateLicenseUseCase** | Transition a PENDING/SUSPENDED license to ACTIVE (entitlement gate). |
| **CreateBrokerUseCase** | Register broker catalogue metadata (no MT/API credentials). |
| **ConnectTradingAccountUseCase** | Bind an active user to a usable broker account; prevent duplicates. |
| **OpenTradingSessionUseCase** | Start a session when user is active and account is tradable. |
| **CloseTradingSessionUseCase** | Gracefully close an open session with an optional reason. |
| **CreateSignalRecordUseCase** | Persist a signal *record* against a tradable symbol — does not generate signals. |
| **ValidateRiskProfileUseCase** | Check proposed risk/leverage/positions against stored limits — no orders. |
| **RecordAuditEventUseCase** | Append an immutable audit trail entry. |
| **GetHealthUseCase** | Aggregate `HealthCheckPort` probes into a readiness DTO. |
| **GetVersionUseCase** | Expose app identity via `AppInfoPort`. |

## Ports introduced

- `UserRepositoryPort`, `LicenseRepositoryPort`, `BrokerRepositoryPort`, …
- `UnitOfWorkPort` / `UnitOfWorkFactory`
- `AppInfoPort`

## Explicit non-goals

Infrastructure repository implementations, REST routers for these use cases,
SQLAlchemy mappings, trading execution, AI, MetaTrader.
