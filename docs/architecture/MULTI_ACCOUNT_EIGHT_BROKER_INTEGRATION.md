# Eight-Broker MT5 Integration

**Status:** Implemented on `feat/eight-broker-justmarkets`  
**Canonical order (everywhere):**

1. Weltrade  
2. XM  
3. Exness  
4. HFM  
5. JustMarkets  
6. IC Markets  
7. Pepperstone  
8. FP Markets  

## JustMarkets

| Item | Value |
|---|---|
| Slug | `justmarkets` |
| Display | JustMarkets |
| LIVE keys | `QF_LIVE_JUSTMARKETS_{LOGIN,PASSWORD,SERVER}` |
| DEMO keys | `QF_DEMO_JUSTMARKETS_{LOGIN,PASSWORD,SERVER}` |
| Server identity | `justmarkets`, `justmarketscy` (post-login `account_info.server`) |
| Candidates (unconfirmed) | `JustMarkets-Demo`, `JustMarkets-Live`, `JustMarkets-Live2`, … — copy exact Personal Area server |

## Credential checker

```powershell
.\deploy\mt5_worker_agent\check_broker_credentials.ps1
```

Uses `python -m services.mt5_worker_agent.check_broker_credentials` (never multiline `poetry run python -c`).  
Output: sanitized status + missing key **names** only. Exit `1` when any row blocked.

## Sequential LIVE verify (auth only)

```powershell
.\deploy\mt5_worker_agent\verify_demo_broker.ps1 -Broker <slug> -Slot demo-a -Env live
```

Portable slots only. Do not touch Weltrade Program Files LIVE singleton.  
`trade_mode=2` required for `VERIFIED_LIVE`. No `order_send`.

## Safety

```text
MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false
FORCE_FIRST_TRADE=false
QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false
```

See also `MULTI_ACCOUNT_PHASE11_LIVE_ACCEPTANCE.md`.
