# Phase 2 — Trading Execution & Automation 2.0 (freeze citation)

**Owner approval:** Product owner ordered Phase 2 Execution & Automation 2.0
(Signals ↔ Terminal handoff, OMS/Risk honesty, multi-broker isolation monitoring,
prefs tighten-only on LIVE). Explicit authorization to touch OMS / Risk Engine /
PME manage surfaces / execution UI **only** for the gap list in the approved plan.

**Non-goals preserved:**
- No ITE / AI Decision / Scalping / Portfolio redesign
- No second VPS; Weltrade Program Files LIVE protected
- No fabricated `trade_allowed`
- No LIVE test `order_send`
- Production execution flags unchanged by this release unless separately ordered
- Design Freeze: Terminal wiring/usability only (RC4 inheritance), no restyle

**Regression gate:** `pytest -m trading_core` must pass before merge.
