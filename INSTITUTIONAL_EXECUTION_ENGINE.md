# Institutional Execution Engine

## Architecture

One pipeline owns all live order paths:

```
Draft → Validation → Risk Check → Execution Check
  → Broker Submission → Broker Acceptance → Broker Fill
  → Portfolio Update → History → Journal → Analytics
```

```
FE (ticket / OMS)
  → POST /execution/check | /submit | /cancel | /manage
  → SubmitExecutionUseCase / CancelExecutionUseCase / ManageExecutionUseCase
  → InstitutionalExecutionEngine
       ├─ MT5OrderValidationService
       ├─ ExecutionSafetyService
       ├─ ExecutionGateway (order_send / order_cancel)  ← EXECUTION_ENABLED gate
       ├─ ExecutionIntelligenceService (lifecycle observe)
       └─ ExecutionJournalStore (in-process blotter)
```

### Security

- `EXECUTION_ENABLED=false` (default) never calls broker send/cancel with live trade capability path still returns `disabled` and HTTP 403 on submit.
- No duplicate broker call sites: gateway is the only `order_send` / `order_cancel` entry used by the engine.
- Locked surfaces untouched: TradingSessionProvider, Broker Workspace, Gateway transport, Cloudflare, Railway, session bind, Dashboard, Portfolio pages, chart panels.

### OMS

| Action | API |
|--------|-----|
| Market / Limit / Stop / Stop Limit | `POST /execution/submit` |
| Cancel pending | `POST /execution/cancel` |
| Close / partial / reverse / modify SLTP / trail / BE | `POST /execution/manage` |

### Observability

- Lifecycle stages force-observed into Execution Intelligence store
- Journal: `GET /execution/journal`
- Analytics KPIs: `GET /execution/analytics` (fill rate, slippage, latency, rejects, cancels, success rate, execution time)

## Files Changed

- `app/domain/execution_engine/*` — pipeline stages, journal, human reasons
- `app/application/services/institutional_execution_engine.py`
- `app/application/use_cases/execution_gateway.py` — submit/cancel/manage via engine
- `app/application/use_cases/execution_safety.py` — human-readable rejects
- `app/application/dto/execution.py` / `app/presentation/schemas/execution.py`
- `app/presentation/dependencies/execution.py` / `app/presentation/routers/execution.py`
- `app/domain/execution_intelligence/analytics.py` — institutional KPIs
- `frontend/src/lib/api/endpoints.ts` — cancel/manage/journal/analytics
- `frontend/src/lib/execution/post-trade-invalidate.ts`
- `frontend/src/components/execution/position-manager.tsx` — manage + reverse
- `frontend/src/components/execution/orders-workspace.tsx` — real cancel API
- `frontend/src/components/execution/order-ticket.tsx` — stage count toast
- `frontend/src/components/workspace/bottom-panel.tsx` — journal + analytics tape
- `tests/unit/test_institutional_execution_engine.py`
- `tests/unit/test_execution_gateway.py`

## Validation

| Check | Result |
|-------|--------|
| pytest unit | **410 passed** |
| frontend typecheck | **pass** |
| frontend lint | **pass** |
| frontend build | **pass** |
| E2E | webServer timeout locally (`npm run start` not reachable in 120s) — suite config present (`e2e/beta-launch.spec.ts`) |

## Commit SHA

`6ef13a9bc82d946ee9f982ca3921f7ad7b55743b`

## Production notes

- Live fills still require `EXECUTION_ENABLED=true` and a trade-capable gateway attach.
- Journal/lifecycle stores are process-scoped (no DB schema change).
- Close/reverse/modify use the same gated `order_send` path; gateway v1 no-trade configurations still block honestly.
