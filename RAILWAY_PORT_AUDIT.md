# Railway Port Mapping Audit

**Date:** 2026-07-13  
**Symptom:** App healthy on `0.0.0.0:8080` but Railway UI shows **Public Domain → Port 8000**.

---

## Exact reason UI shows Port 8000 while container listens on 8080

Railway uses **two different port concepts**:

| Concept | Your deployment |
|---------|-----------------|
| **Runtime `PORT` env** | Railway injects `8080` at deploy time → Uvicorn binds correctly (`bind_probe_ok port=8080`) |
| **Domain target port** | Set when the public domain was created; **pinned to 8000** and does not auto-update |

The domain **target port** was auto-detected from deployment metadata that advertised **8000**:

1. **`ENV PORT=8000` in Dockerfile** (now removed) — Railway “magic port” detection used this when the `*.up.railway.app` domain was first generated.
2. **Previously `EXPOSE 8000`** (already removed) — same detection path.

Result: the edge proxies **public HTTPS → container port 8000**, but nothing listens on 8000; Uvicorn listens on **8080**. In-container `self_check_ok` passes; public URL fails or falls back until target port matches.

`railway.toml` has **no port field** — domain target port is **not** set in config-as-code; it lives on the domain record in the Railway UI.

---

## Files audited and fixed

| File | Issue | Fix |
|------|-------|-----|
| `Dockerfile` | `ENV PORT=8000` advertised wrong port | **Removed** `PORT` from image ENV |
| `Dockerfile` | `EXPOSE 8000` (prior) | Already removed |
| `docker-entrypoint.sh` | `PORT="${PORT:-8000}"` fallback | **Require** `${PORT}`; exit if unset |
| `scripts/railway_self_check.py` | Default `"8000"` | Use `os.environ["PORT"]` only |
| `railway.toml` | No port key (correct) | Documented: do not set `PORT=8000` in service variables |
| `CMD` / `startCommand` | Both use entrypoint → `--port "${PORT}"` | Verified ✓ |

**Not changed (local dev only):** `.env.example`, `docker-compose.yml` — not used by Railway production routing.

---

## Operator steps (Railway dashboard — required once)

1. **Variables:** Delete `PORT` if set to `8000`. Let Railway inject `PORT` automatically.
2. **Networking → Public Domain:** Click **edit** next to the domain → set **target port to `8080`** (match deploy log `bind_probe_ok port=...`).
   - Or **remove and regenerate** the domain after this deploy (without `PORT=8000` in the image).
3. **Redeploy** latest `main` after this commit.
4. **Verify:** Public Domain shows **Port 8080**; `curl https://<domain>/` returns `{"status":"ok"}` with **no** `x-railway-fallback: true`.

---

## Verification checklist

Deploy logs:

```text
quantforg_entrypoint PORT=8080 ...
bind_probe_ok port=8080
self_check_ok status=200
Uvicorn running on http://0.0.0.0:8080
```

Railway UI:

```text
Public Domain: quantforg-production.up.railway.app → Port 8080
```

Public HTTP:

```text
GET / → 200
GET /health → 200
```

---

## Why previous fixes did not update UI port 8000

Startup, middleware, and ASGI changes fixed **in-container** health. The **domain target port** is a separate networking setting; it stays at 8000 until edited in the UI or the domain is regenerated after removing `PORT=8000` from the image metadata.
