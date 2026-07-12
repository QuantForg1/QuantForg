# Branch Strategy

QuantForg uses a **trunk-based** workflow with short-lived feature branches.

## Branches

| Branch | Purpose |
|---|---|
| `main` | Production-ready lineage; protected |
| `feature/<ticket>-<slug>` | New capability |
| `fix/<ticket>-<slug>` | Bug fix |
| `docs/<slug>` | Documentation / ADR / governance |
| `chore/<slug>` | Tooling, CI, deps |
| `release/<x.y.z>` | Release preparation when needed |

## Rules

1. Branch from latest `main`; rebase or merge `main` frequently.
2. Keep branches short-lived (prefer < 3 days of active work).
3. One primary concern per branch/PR.
4. **No force-push to `main`.** Force-push to personal feature branches only
   if needed and never after others base work on them.
5. Delete remote feature branches after merge.
6. Hotfixes: `fix/` branch → PR → `main` → tag release per
   [ReleasePolicy.md](ReleasePolicy.md).

## Protection (recommended)

- Require PR reviews (CODEOWNERS).
- Require green CI (`make check` equivalent).
- Disallow direct commits to `main`.

## Mapping to sprints

Sprint work may span multiple PRs. Prefer vertical slices (engine + tests +
docs) over long-lived sprint branches.
