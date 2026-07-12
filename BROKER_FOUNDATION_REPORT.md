# BROKER_FOUNDATION_REPORT

**Status:** COMPLETE — Sprint 1  
**Date:** 2026-07-12  
**Scope:** Broker abstraction layer only (no MT5 live integration, no trading execution, no AI)

## Architecture

```
Broker  →  Broker Adapter (port)  →  Broker Service  →  Trading Engine (future)
                ↑
          BrokerRegistry
     (MT5/MT4/cTrader/DXtrade placeholders)
```

## Phase checklist

### A — Domain

| Item | Status |
|------|--------|
| Entities: Broker, BrokerAccount, BrokerConnection, BrokerCredential, BrokerCapability, BrokerSession | Done |
| Enums: BrokerType, BrokerStatus, ConnectionStatus (= BrokerConnectionStatus), CredentialStatus | Done |
| VOs: BrokerId, AccountId, ServerName, BrokerRegion | Done |
| Events: BrokerRegistered, BrokerConnected, BrokerDisconnected, CredentialsUpdated, BrokerDeleted | Done |

### B — Ports

`BrokerAdapterPort` methods (interfaces only):

- `connect`, `disconnect`, `validate_credentials`, `refresh_session`
- `list_accounts`, `get_account_info`, `get_balance`, `get_equity`
- `get_symbols`, `get_positions`, `get_orders`

### C — Registry

`BrokerRegistry` registers placeholders on startup:

- `MT5Adapter`, `MT4Adapter`, `CTraderAdapter`, `DXtradeAdapter`

All raise `NotImplementedError` until a future adapter sprint.

### D — Database (reversible)

| Version | Purpose |
|---------|---------|
| `20260712140000` | broker_accounts, credentials, connections, capabilities; brokers.platform_code |
| `20260712140100` | RLS for foundation tables |
| `20260712141000` | broker_sessions + credential status |
| `20260712141100` | broker_sessions RLS |

Down scripts under `supabase/migrations/down/`.

### E — Application use cases

| Sprint name | Implementation |
|-------------|----------------|
| RegisterBroker | `CreateBrokerUseCase` / alias `RegisterBrokerUseCase` |
| DeleteBroker | `DeleteBrokerUseCase` |
| ConnectBroker | `ConnectBrokerUseCase` |
| DisconnectBroker | `DisconnectBrokerUseCase` |
| ValidateBroker | `ValidateBrokerUseCase` |
| ListBrokerAccounts | `ListBrokerAccountsUseCase` |

Plus catalogue/account CRUD and connection list/get.

### F — API

| Path | Notes |
|------|-------|
| `/api/v1/brokers` | Catalogue CRUD |
| `/api/v1/broker-accounts` | Account CRUD (secrets write-only) |
| `/api/v1/broker-connections` | List/get + `/connect`, `/disconnect`, `/validate` |

### G — Validation

```text
ruff check app core tests     → passed
black --check app core tests  → passed
mypy app core                 → passed
pytest (unit)                 → 197 passed, ~79% coverage
```

## Secrets

- Fernet encrypt via `SECRET_KEY` (`encrypt_secret` / `decrypt_secret`)
- API never returns passwords or ciphertext
- Credential rows use `status` (active/rotated/revoked/expired)

## Explicitly out of scope

- Live MT5 / MT4 / cTrader / DXtrade sockets
- Order placement / Trading Engine
- AI

## Key paths

```
app/domain/entities/broker.py
app/domain/entities/broker_integration.py
app/domain/value_objects/broker.py
app/domain/events/broker.py
app/domain/interfaces/broker_adapter.py
app/infrastructure/brokers/registry.py
app/infrastructure/brokers/placeholders.py
app/application/use_cases/broker.py
app/presentation/routers/brokers.py
app/presentation/routers/broker_accounts.py
app/presentation/routers/broker_connections.py
supabase/migrations/2026071214*.sql
tests/unit/test_use_cases_broker.py
```

## Next sprint (not started)

Replace placeholder adapters with a real MT5 adapter implementing `BrokerAdapterPort`.
