# QUANTFORG PR #188 — LIVE Strategy Performance Dashboard & Monitoring

**Date:** 2026-11-06  
**Instrument:** XAUUSD  
**Baseline:** PR #186/`8b7d2db0` · docs PR #187/`4657b0ca`  
**Scope:** Observability dashboard only — **no** LIVE decision, risk, cascade, M1-submit, or reverse-entry changes.

---

## 1. Existing implementation inspected

| Area | Finding |
| --- | --- |
| Working tree | Unrelated untracked ops report JSON under `docs/production/reports/*` left untouched; only `post168_monitor_probe.json` was dirty and was not staged |
| Nav / IA | Eight primary desks unchanged; ops deep-links via `nav-config` `OPS_HREF_PREFIXES` + Admin Safety |
| Attribution API | `GET /ite/ops/strategy-attribution-performance` (OWNER/ADMIN) from PR #186 |
| Performance engine | `performance_monitor.build_post182_performance_monitor` — reused, not duplicated in frontend |
| UI pattern | Cloned `StrategyDiagnosticsWorkspace` + `MetricCard` / `OpsPanel` / `DeskBarChart` (recharts) |
| Design system | RC4 charcoal + cyan tokens; IBM Plex mono for metrics |

---

## 2. Dashboard sections created

Route: **`/strategy-performance`** (ops deep-link; not a new primary rail desk)

1. Overview — closed trades, realized net P&L, PF, win rate, avg win/loss, expectancy, max DD, consecutive losses, attribution coverage  
2. Reporting period toggles — post-#182 / post-#180–pre-#182 / pre-#180  
3. BUY / SELL comparison  
4. Five-pack strategy scorecards + comparison chart  
5. Unattributed trades (never guessed)  
6. Capital protection (active anchors, store trust, reversal-like closes)  
7. M1 evaluation (explicit LIVE submit OFF; signals ≠ trades)

---

## 3. Data sources and endpoints

| Source | Role |
| --- | --- |
| `GET /ite/ops/strategy-attribution-performance` | Primary authenticated payload |
| `performance_monitor.py` | Server-side scorecards / periods / protection / M1 block |
| `iteOpsApi.strategyAttributionPerformance()` | Frontend client |
| View model | `frontend/src/lib/strategy-attribution-performance.ts` — formatting only |

---

## 4. Account separation

- Live login from attribution store snapshot drives `broker_login`.  
- Account **12260878** is never merged with **12479147** without an explicit combined label (API note preserved in UI).  
- Period buckets remain separate.

---

## 5. Financial metric definitions

- **Realized net P&L** — sum of durable broker-confirmed close outcomes (`net_pnl`).  
- **Unrealized P&L** — explicitly **not included** (`null` + UI “Not included”).  
- **Profit factor / expectancy / win rate / avg win/loss / max DD** — from `profitability_metrics.build_performance_scorecard`.  
- Incomplete costs remain disclosed; missing commission/swap is not treated as profitable zero.

---

## 6. Attribution handling

- Five-pack IDs only when `strategy_id` is bound.  
- Unattributed bucket keeps `strategy_id: null`.  
- Classifications: Positive / Negative / Promising but insufficient sample / Insufficient attribution / Insufficient data.  
- Sample size shown with every conclusion; insufficient data visually distinct from zero performance.

---

## 7. M1 reporting limitations

- M1 micro may evaluate while **M1 LIVE OMS submission remains OFF**.  
- Dashboard does **not** present M1 signal counts as completed trades or profitability.  
- Broker-confirmed M1 fills are labelled “Not claimed” until durable M1 fill attribution exists.

---

## 8. Tests and results

| Suite | Result |
| --- | --- |
| `test_pr188_*` + `test_pr186_*` | **11 passed** |
| `strategy-attribution-performance.test.ts` | **ok** |
| `tsc --noEmit` | **clean** |
| Frontend ESLint | **pass** |
| Frontend production build | **pass** |
| Ruff (touched Python) | **pass** |

---

## 9. Production verification

| Check | Expected |
| --- | --- |
| Railway `/health.commit` | Unchanged trading semantics (may advance only if backend payload deploy) |
| `/ready` | ok |
| Vercel production | `/strategy-performance` reachable for OWNER/ADMIN |
| LIVE flags | Cascades ON · M1 submit OFF · reverse entry OFF |

*(Fill exact commit SHAs after deploy.)*

---

## 10. Confirmation — trading behavior unchanged

- Risk 20% / daily halt 48% / max lot 0.01 / Q≥70 / min RR 0.20 / preferred 0.50 / concurrent 1 / aggregate 30% / mandatory SL — **unchanged**.  
- BUY/SELL cascade, LIVE reversal exits — **unchanged**.  
- M1 LIVE submit — **OFF**.  
- Automatic reverse entry — **OFF**.  
- Dashboard is advisory (`mutates_engines=false`, `advisory_only=true`).

ACCURATE DATA FIRST · CLEAR PERFORMANCE SECOND · OPTIMIZATION ONLY WHEN EVIDENCE SUPPORTS IT.
