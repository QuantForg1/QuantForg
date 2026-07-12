# MT5 Adapter Sprint 1 Report

**Status:** Complete  
**Scope:** MetaTrader 5 **connection layer only**  
**Date:** 2026-07-12  

## Explicit non-goals (not started)

- Live order execution  
- Positions  
- Market data streaming  
- Strategy execution  
- AI  

Broker Foundation Sprint 2, Authentication, User Platform, Supabase, and existing APIs are preserved.

---

## Summary

| Area | Delivered |
|------|-----------|
| Domain: `MT5Connection`, `MT5Terminal`, `MT5Server`, `MT5AccountInfo` | Yes |
| `MT5Adapter` connection methods | Yes |
| `initialize` / `login` / `shutdown` / `reconnect` | Yes |
| Health: latency, connected, terminal build, server, login status, heartbeat | Yes |
| REST `/api/v1/mt5/*` | Yes |
| Reversible migrations + RLS | Yes |
| Fully mocked MT5 (no real terminal) | Yes |
| Quality gates | Green |

---

## Architecture

```
Presentation  /api/v1/mt5/*
      ↓
Application   MT5Service / use cases
      ↓
Domain        MT5Connection, MT5Terminal, MT5Server, MT5AccountInfo
              MT5ClientPort
      ↓
Infrastructure
   MT5Adapter  →  MockMT5Client  (default / CI)
   BrokerRegistry["mt5"] overwritten at startup
```

Clean Architecture preserved: no MetaTrader5 types in domain or application.

---

## Domain

| Type | Role |
|------|------|
| `MT5Connection` | User connection state, heartbeat, terminal version, history |
| `MT5Terminal` | Local terminal build / path / company |
| `MT5Server` | Broker server metadata |
| `MT5AccountInfo` | Read-only account snapshot |
| `MT5ConnectionStatus` | `disconnected` … `connected` … `error` |

---

## Adapter surface

**Module:** `app/infrastructure/brokers/mt5/`

### Supported

| Method | Notes |
|--------|--------|
| `connect` / `disconnect` | `BrokerAdapterPort` |
| `validate_credentials` | Disposable mock probe |
| `ping` | Latency (ms) |
| `terminal_info` | Build / path / connected |
| `version` | `(major, minor, build)` |
| `account_info` | Read-only |
| `symbols` | Metadata only (no streaming) |
| `health` | Aggregated snapshot |
| `initialize` / `login` / `shutdown` / `reconnect` | Connection lifecycle |

### Explicitly not implemented

| Method | Behaviour |
|--------|-----------|
| `get_orders` | `NotImplementedError` |
| `get_positions` | `NotImplementedError` |

Capabilities advertised **exclude** `orders` and `positions`.

---

## Mock client

`MockMT5Client` implements `MT5ClientPort` entirely in-process:

- No `MetaTrader5` Python package dependency  
- No Windows terminal required  
- Default via `MT5_USE_MOCK=true`  
- Used by CI and unit tests  

---

## Health fields

Exposed via `GET /api/v1/mt5/status` and adapter `health()`:

- `latency_ms`  
- `connected`  
- `terminal_build` / `terminal_version`  
- `server`  
- `login_status`  
- `last_heartbeat_at`  

---

## API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/mt5/status` | Connection health |
| `POST` | `/api/v1/mt5/connect` | Initialize + login |
| `POST` | `/api/v1/mt5/disconnect` | Shutdown |
| `GET` | `/api/v1/mt5/account` | Account snapshot |
| `GET` | `/api/v1/mt5/symbols` | Symbol list |

Auth: authenticated users (`CurrentUser`). Passwords accepted on connect only — never returned.

Broker Foundation routes (`/brokers`, `/broker-accounts`, `/broker-connections`) unchanged. Registry `mt5` entry is the real connection-layer adapter when `MT5_ENABLED=true`.

---

## Database

| Migration | Purpose |
|-----------|---------|
| `20260712143000_mt5_adapter.sql` | `mt5_connections`, `mt5_connection_events` (history, heartbeat, terminal version) |
| `20260712143100_mt5_adapter_rls.sql` | Owner RLS via `current_app_user_id()` |
| Matching `down/*.down.sql` | Fully reversible |

Runtime persistence for Sprint 1 uses in-memory UoW (`MemoryMT5UnitOfWorkFactory`); SQL is ready for Supabase apply.

---

## Configuration

```env
MT5_ENABLED=true
MT5_USE_MOCK=true
MT5_TERMINAL_PATH=
MT5_CONNECT_TIMEOUT_SECONDS=60.0
```

---

## Tests

| File | Coverage |
|------|----------|
| `tests/unit/test_mt5_domain.py` | Entities |
| `tests/unit/test_mt5_adapter.py` | Mock client + adapter |
| `tests/unit/test_mt5_use_cases.py` | Connect / status / account / symbols / disconnect |

### Quality gates

```text
ruff check app core tests     → passed
black --check app core tests  → passed
mypy app core                 → passed
pytest                        → 225 passed, 2 skipped (~78% coverage)
```

---

## Stop line

Sprint 1 ends at the **connection layer**.

Do **not** implement:

- Orders  
- Positions  
- Market data streaming  
- AI  
