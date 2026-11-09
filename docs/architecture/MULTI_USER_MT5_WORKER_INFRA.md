# Phase 1B — Isolated MT5 Worker Infrastructure

**Branch:** `feat/multi-user-mt5-worker-infra`  
**Depends on:** Phase 1a registry (PR #207)  
**LIVE fan-out flags:** remain `false`

## Architecture (implemented as control-plane + agent interface)

```text
Central QuantForg API (Railway / Linux)
  ├─ Worker Provisioner (idempotent allocate/release)
  ├─ Capacity Manager (host slot ledger)
  ├─ Worker Supervisor (heartbeat / stale / reconnect backoff)
  └─ Encrypted credential store (existing broker_credentials)
           │  authenticated service channel (future HTTP)
           v
Windows worker host(s)  [NOT provisioned by this PR]
  └─ Worker Agent + isolated terminal64 session per user slot
```

Railway **cannot** host MetaTrader 5. Terminals must run on Windows.

Existing Weltrade LIVE singleton (`deploy/mt5_gateway`) is preserved and
separate. Multi-user workers must not replace it until proven.

## Components in this PR

| Component | Code | Running in Production? |
| --- | --- | --- |
| Lifecycle state machine | `worker_lifecycle.py` | N/A (library) |
| Provisioner | `worker_provisioner.py` | In-process / tests only |
| Capacity manager | `capacity.py` | Ledger only |
| Supervisor | `worker_supervisor.py` | In-process / tests only |
| Control plane service | `mt5_worker_control_plane.py` | Not wired to LIVE |
| Agent protocol + mock | `worker_agent_protocol.py` | Mock ≠ real MT5 |
| Windows agent entrypoint | `services/mt5_worker_agent` | Idle until hosts exist |
| Deploy scripts | `deploy/mt5_worker_agent` | Operator-run |
| DB extensions | `20261109140000_mt5_worker_runtime.sql` | Not applied to Prod |

## Windows host options (recommendation)

| Option | Pros | Cons | Fit |
| --- | --- | --- | --- |
| Hetzner / Contabo Windows VPS | Low monthly cost, persistent | Manual ops, variable support | Good for early demo fleet |
| Azure Windows VM | Reliable, scale sets later | Higher cost | Good for production growth |
| AWS EC2 Windows | Familiar, regions | Cost + licensing | Viable |
| Nested Wine/Docker on Linux | Cheap compute | **Unreliable for MT5 trading** | Reject for LIVE |

**Recommendation:** start with **1–2 dedicated Windows VPS** (8–16 GB RAM) in the same region as the Cloudflare tunnel path used today; register them in `worker_hosts`; run one portable MT5 data directory per slot. Do **not** purchase until owner approval.

### Indicative monthly cost (estimates only)

| Scale | Hosts | Est. USD / month |
| --- | --- | --- |
| 4–8 concurrent demo users | 1× 8 GB Windows VPS | ~$20–60 |
| 20–40 users | 2–3× 16 GB | ~$80–200 |
| 100+ users | measured later | unknown until load test |

## Security rules (enforced in code paths)

- No passwords in worker metadata / logs / public status
- Investor/read-only credentials rejected for trade workers
- Tenant ownership on every control-plane call
- Service token required for agent auth
- READY only after AUTHENTICATING → VERIFYING

## What remains before Connect UI

1. Owner-approved Windows host(s) online  
2. Agent ↔ API assignment/poll endpoints (authenticated)  
3. Secure one-time credential delivery to agent  
4. Frontend Broker Connect UX wired to control plane  

## What remains before concurrent demo execution

1. Real demo MT5 auth on ≥3 users (see integration test doc)  
2. Signal dispatcher (still flagged off)  
3. Per-user risk + OMS on workers  
4. Measured capacity / failure drills  
