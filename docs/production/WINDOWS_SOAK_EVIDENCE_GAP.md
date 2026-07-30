# Why the verifier cannot see the latest Windows soak artifacts

Generated: 2026-07-30T11:54Z

## Root cause

The acceptance verifier and this cloud agent run against a **Linux git clone**.
The production soak logger writes **only on the Windows host filesystem**:

`C:\Users\P7 PROVIDER\QuantForg\docs\production\reports\oat_v71\soak_24h_metrics.jsonl`

Those Windows-local files are **not automatically synced** into git. The last
committed soak blob on any remote branch ends at:

- first: `2026-07-27T18:35:38Z`
- last: `2026-07-28T10:45:19Z`
- duration: **16.162h**
- age at audit: **~49h stale**

`main` does not contain `oat_v71/soak_24h_metrics.jsonl` at all.

## What we located live (not fabricated)

| Source | Finding |
|---|---|
| `https://gateway.quantforg.com/health` | **Live** — `status=ok`, MT5 `connected=true`, `session=attached`, server `Weltrade-Real`, heartbeat ~now (`2026-07-30T11:52Z`) |
| Gateway token fingerprint `dotenv_path` | Confirms Windows host path `C:\Users\P7 PROVIDER\QuantForg\.env` |
| MT5 Gateway API (`services/mt5_gateway/routers.py`) | Exposes `/health`, session, trade — **no soak/file export route** |
| Local filesystem search | Only stale repo copy under `/workspace/docs/production/reports/oat_v71/` |
| GitHub Actions artifacts | none |
| Railway CLI | unauthorized in this environment |
| Supabase (accessible org project) | Jimvio marketplace schema — **no QuantForg soak tables** |

## Why the verifier looked “blind”

1. **Soak JSONL never imported** after Windows continued logging past 2026-07-28T10:45Z.
2. PAT previously probed only `http://127.0.0.1:8765/health`. On the cloud
   auditor that port is closed, so gateway appeared down even though
   `https://gateway.quantforg.com/health` is healthy.

## Fix applied in verifier (does not invent soak hours)

- Probe gateway candidates: env → `127.0.0.1:8765` → `https://gateway.quantforg.com`
- Soak acceptance still requires the **jsonl wall-clock file** (≥24h, fresh)

## Operator action required to import soak evidence

On the Windows host (PowerShell), from the QuantForg repo:

```powershell
# 1) Confirm latest soak files exist and inspect last lines
Get-Item "docs\production\reports\oat_v71\soak_24h_metrics.jsonl","docs\production\reports\oat_v71\soak_24h_latest.json"
Get-Content "docs\production\reports\oat_v71\soak_24h_latest.json"
Get-Content "docs\production\reports\oat_v71\soak_24h_metrics.jsonl" -Tail 3

# 2) Commit + push so the cloud verifier can see them
git checkout cursor/v7-1-production-stabilization-bc83
git add docs/production/reports/oat_v71/soak_24h_metrics.jsonl `
        docs/production/reports/oat_v71/soak_24h_latest.json
git commit -m "Import Windows v7.1 soak operational evidence"
git push origin cursor/v7-1-production-stabilization-bc83
```

Or run: `scripts/sync_windows_soak_evidence.ps1`

Until that import lands in git, PAT `TEST_9_LONG_RUN` and OAT Step 5 **must remain FAIL**.
