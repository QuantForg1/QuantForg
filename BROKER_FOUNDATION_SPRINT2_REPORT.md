# Broker Foundation Sprint 2 Report

**Status:** Complete  
**Scope:** Credential encryption (AES-256-GCM), connection health, automatic reconnect, capability discovery, diagnostics APIs, domain events, reversible migrations  
**Out of scope (unchanged):** MT5 live adapter, live trading execution, AI  

Sprint 1 catalogue / accounts / connections APIs, Clean Architecture, Supabase, Authentication, and User Platform are preserved.

---

## Summary

Sprint 2 hardens Broker Foundation operational readiness without implementing any live broker sockets:

| Feature | Delivered |
|---------|-----------|
| AES-256-GCM credential encryption + key rotation | Yes |
| Connection health monitor (latency, heartbeat, uptime, reconnects) | Yes |
| Automatic reconnect manager (backoff, limits, cooldown, events) | Yes |
| Capability discovery (`market_data`, `history`, …) | Yes |
| Health + diagnostics REST endpoints | Yes |
| Domain events | Yes |
| Reversible migrations + RLS | Yes |
| Unit tests + quality gates | Green |

---

## 1. Credential Encryption

**Module:** `core/security/credential_encryption.py`

- **Algorithm:** AES-256-GCM (256-bit key derived via SHA-256 from app secret + version)
- **Envelope:** `v2:<key_version>:<base64url(nonce || ciphertext||tag)>`
- **Service:** `CredentialEncryptionService.encrypt / decrypt / rotate / secure_repr`
- **Rotation:** `ENCRYPTION_KEY_VERSION` + optional `CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS`
- **Legacy:** Sprint 1 Fernet tokens remain decryptable
- **Safety:** `BrokerCredential.to_dict()` never exposes ciphertext or plaintext; `secure_repr` redacts secrets

`encrypt_secret` / `decrypt_secret` in `core/security/crypto.py` default to AES-256-GCM while preserving call-site compatibility.

---

## 2. Connection Health Monitor

**Entity:** `app/domain/entities/broker_health.py` → `BrokerConnectionHealth`  
**Service:** `app/application/services/broker_health.py` → `ConnectionHealthMonitor`

Tracks:

- `latency_ms`
- `last_heartbeat_at`
- `last_successful_connection_at`
- `reconnect_attempts`
- `uptime_seconds` / `connected_since`
- `status` (`healthy` | `degraded` | `unhealthy` | `unknown`)
- `last_error`

Persisted via `broker_connection_health` (UoW `health` repo; in-memory for local/tests).

---

## 3. Automatic Reconnect Manager

**Service:** `AutomaticReconnectManager` with `ReconnectPolicy`

- Exponential backoff (`base * 2^(n-1)`, capped)
- Retry limits (`max_attempts`)
- Cooldown after exhaustion
- Reconnect bookkeeping events on state

Hooked from connect success / failure and disconnect (no live sockets — domain scheduling only).

---

## 4. Capability Discovery

**Port:** `BrokerCapabilityDiscoveryPort` (additive; does not break `BrokerAdapterPort`)  
**Helpers:** `default_capabilities_for_platform`, `discover_adapter_capabilities`  
**Placeholders:** `PlaceholderBrokerAdapter.discover_capabilities()`

Advertised codes now include:

- `market_data`
- `history`

plus Sprint 1 codes (`connect`, `orders`, `positions`, `account_info`, `symbols`, …).

---

## 5. Broker Diagnostics / Health API

| Method | Path | Notes |
|--------|------|--------|
| `GET` | `/api/v1/brokers/{id}/health` | Aggregated status, latency, uptime, reconnect count, last error, capabilities |
| `GET` | `/api/v1/brokers/{id}/diagnostics` | Health + per-connection snapshots, reconnect state, discovered capabilities |

Auth: authenticated users (same pattern as catalogue read). Existing Sprint 1 routes unchanged.

---

## 6. Domain Events

| Event | `event_type` |
|-------|----------------|
| `BrokerHeartbeatReceived` | `broker.heartbeat_received` |
| `BrokerHealthChanged` | `broker.health_changed` |
| `BrokerReconnected` | `broker.reconnected` |
| `BrokerConnectionLost` | `broker.connection_lost` |

Exported from `app.domain.events`.

---

## 7. Database

| Migration | Purpose |
|-----------|---------|
| `20260712142000_broker_health.sql` | `encryption_key_version` on credentials; expand capability CHECK; create `broker_connection_health` |
| `20260712142100_broker_health_rls.sql` | RLS owner-via-account policies |
| `down/20260712142000_broker_health.down.sql` | Reversible down |
| `down/20260712142100_broker_health_rls.down.sql` | Reversible RLS down |

Audit logging for broker mutations remains via `RecordAuditEventUseCase` (Sprint 1 pattern).

---

## 8. Configuration

```env
SECRET_KEY=...
ENCRYPTION_KEY_VERSION=1
# CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS=old-secret-1,old-secret-2
```

Documented in `.env.example`.

---

## 9. Testing & Quality Gates

**New unit tests**

- `tests/unit/test_credential_encryption.py`
- `tests/unit/test_broker_health.py`
- `tests/unit/test_broker_capability_discovery.py`

**Commands (all green)**

```bash
ruff check app core tests
black --check app core tests
mypy app core
pytest
```

Result at Sprint 2 completion: **212 passed, 2 skipped**, coverage **≥ 60%** (≈78%).

---

## 10. Architecture Notes

- Clean Architecture layers preserved (domain → application → infrastructure → presentation)
- Sprint 1 APIs preserved; health/diagnostics are additive under `/brokers/{id}/...`
- Supabase + Auth + User Platform untouched
- Placeholder adapters still raise `NotImplementedError` for live methods — **no MT5 adapter started**

---

## Explicit Non-Goals (Stop Here)

- Do **not** implement MT5 Adapter
- Do **not** implement live trading
- Do **not** implement AI

Sprint 2 ends with this report.
