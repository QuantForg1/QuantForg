# Unpublished local source preserved on 2026-10-29

This directory keeps local QuantForg source that was not already the same bytes as `origin/main`. The copies are historical working-tree files. They are not imported by the application. The live modules on this branch stay at the published implementations.

`origin/main` `111f2aa6fa04ebd0eff1d27010c733a5bfb662a9` is the merge of pull request #115. Its tree matches recovery commit `1c7589b277b179d78a9f236324ff9351dc0fcbea`. This branch starts there.

## Live modules that stay published

- `services/mt5_gateway/order_guard.py` still has `OWNER_MAX_ENTRY_VOLUME = 0.01`. The local guard accepted any volume above 0, omitted the open-Gold-position block, omitted the working-pending block, and priced planned loss without the published spread and slippage terms. That file is only under `files/services/mt5_gateway/order_guard.py`.
- Scalping config still starts at 0.50% per trade, clamps any higher request to 0.75%, and keeps 5.00% exposure caps. The local checkout proposed 9% per trade and 9% exposure. Those assignments are not applied here.
- Dynamic sizing still halts at daily loss `>=` cap and still uses the 0.75% hard ceiling. The local unique diff changed that comparison to `>` and raised the ceiling to 9%.
- `min_lot_feasibility.py` still treats a zero dollar cap as a ceiling input. The local unique diff treated a zero cap as no fixed dollar cap.
- Weekly-loss rejection in the published risk-lock test stays a rejection. The local test wanted weekly loss to become non-blocking telemetry.
- The execution bridge still checks the kill switch before the decision hash is reserved and again immediately before OMS submit.

## Reviewed module added on the live path

`app/domain/institutional_trading/owner_risk_policy.py` is the local helper for a 9% planned-risk cap and a 19% daily-loss measurement. Nothing in the order guard, sizer, or daily-loss lock imports it. Exact 9% and exact 19% are inside the helper's allowance. The next step above either limit is not. A non-positive cap in the helper does not invent a halt. Published `OWNER_DAILY_LOSS_PCT` remains 19% and `OWNER_MAX_LOT` remains 0.01.

## Isolated full-day commit

Local commit `c3030d5e7469836cbd8efeaa7a8936e23f9a3a2b` (`feat/full-day-session`) is preserved as its own branch, `archive/full-day-session-c3030d5e`, at that same SHA. It is not merged into this branch or into `main`. Current `origin/main` already evaluates 00:00–23:59 UTC. Applying `c3030d5e` onto current main would bring the rest of that old history with it.

## Files under `files/`

35 local source files, including the two files that were untracked (`owner_risk_policy.py` and `tests/unit/test_order_guard.py`). Several tracked copies are older than `origin/main` and conflict with published safety code. They are stored here so the bytes are not dropped. They must not replace the live files.

## Excluded from this branch

- `frontend/package-lock.json`: the only unique difference is the lockfile version string `1.0.0` to `1.0.1`. `package.json` already matches `origin/main`.
- `docs/production/validation/**`, gateway logs, `watchdog.state`, `.cursor/settings.json`, and the accidental `$null` file.
- `.env`, credentials, gateway tokens, account data, caches, and virtual environments.
- Backup ref `refs/backup/local-main-dirty-20261029` (`ce521044dcd1cdbd76a093db5a1c97f7aeb2a0a3`) remains local. It is a stash of the dirty checkout, not a source commit to publish.
- Local `main` at `37b5ce98` stays unpublished. It is 38 commits behind the pre-merge main and is not a candidate to push.
