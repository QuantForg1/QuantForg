# Phase D — Reversal / AI Exit Integration Design

**Status:** Proposal + offline helpers only — **NOT LIVE-activated**  
**Date:** 2026-11-05  
**Owner approval required** before feeding `structure_broken` / `trend_reversed` / AI flatten into LIVE `PositionManageContext`.

## Problem

`plan_action` already handles `structure_broken`, `trend_reversed`, and AI manage hints, but ITE `_sync_and_manage_open_positions` does not populate those fields. Wiring bare booleans without position-specific, fresh confirmation would risk noise exits.

## Proposed architecture

1. **Offline proposer** — `management/exit_context.py::propose_reversal_exit`  
   - Requires BOS/CHoCH **and** HTF agreement for structural exits.  
   - Treats LTF-only noise as retracement.  
   - Rejects stale data (`data_age_seconds`).  
   - Defers spread spikes to existing PME spread path.  
   - AI fade only with confidence drop **and** momentum below fade threshold.

2. **Shadow logging (optional next step)** — log `shadow_*` fields from `shadow_log_fields` without setting LIVE exit booleans.

3. **LIVE activation (owner-gated)** — only after shadow period:  
   - Set `structure_broken` / `trend_reversed` from proposer when `confidence=high`.  
   - Keep `structure_trend_exits_enabled` configurable (default True for planner when flags set; flags themselves remain unset until approved).  
   - Never place test orders.

## Tests

See `tests/unit/test_pme_broker_confirm_net_be.py::TestExitContextProposal` (BUY reversal, retracement, stale, conflicting TF).

## Owner decision required

- [ ] Approve shadow logging only  
- [ ] Approve LIVE structural exits after N days of shadow  
- [ ] Reject / defer
