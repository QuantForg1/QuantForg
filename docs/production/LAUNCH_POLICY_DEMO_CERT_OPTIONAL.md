# Policy: Demo Certification optional for LIVE (OWNER-approved)

**Status:** Accepted  
**Date:** 2026-07-23  
**Decision makers:** OWNER  

## Decision

Demo Certification is **no longer a mandatory prerequisite** for Ops Mode `LIVE`.

### Official launch workflow

```
SHADOW
  ↓
CANARY
  ↓
LIVE
```

### Still mandatory (unchanged)

- Gateway Connected  
- Broker Connected  
- MT5 Connected  
- `EXECUTION_ENABLED=true`  
- Owner Authorization (`confirmed=true`)  
- Kill Switch Clear  
- Safety Clear  
- Risk Clear  
- Daily Loss OK  
- Legal mode transitions only (`SHADOW → CANARY → LIVE`)  
- Risk Engine and Safety Engine never bypassed  

### Optional

Demo Certification tooling (`/ite/ops/auto-trading/live-certification/*`) remains available for operator confidence. It is **advisory only** and must not block LIVE promotion.

## Rationale

OWNER approved a permanent production policy change: operational readiness is defined by connectivity, execution enablement, and Risk/Safety launch locks — not by a separate Demo certification gate.

## Consequences

- `OperationsControlPlane.transition_mode(..., LIVE)` no longer checks Demo cert.  
- Launch Readiness treats Demo Certification as `OPTIONAL`.  
- Promote path may advance `SHADOW → CANARY → LIVE` when remaining locks PASS.  
- Orders still execute only after Decision → Risk → Safety → Execution → Broker → MT5.  
- No valid signal ⇒ **NO TRADE** (never fabricate).  
