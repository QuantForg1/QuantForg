# QuantForg UI Component Inventory

## Foundations

| Token / primitive | Location | Notes |
|-------------------|----------|-------|
| Color / elevation / grid | `src/app/globals.css` | Dark terminal default + `.light` |
| Typography | `src/app/layout.tsx` | Sora / Manrope / IBM Plex Mono |
| `cn` helpers | `src/lib/utils.ts` | Currency / pct / merge |

## UI kit (`src/components/ui`)

| Component | Purpose |
|-----------|---------|
| `button` | Primary / secondary / ghost / outline / danger |
| `input` | Form fields |
| `label` | Accessible labels |
| `card` (+ header/title/description/content) | Surface containers |
| `badge` | Status tones |
| `skeleton` | Loading placeholders |
| `separator` | Dividers |
| `empty-state` | Zero-data UX |
| `error-boundary` | Route-level failure recovery |

## Layout (`src/components/layout`)

| Component | Purpose |
|-----------|---------|
| `app-shell` | Auth gate + chrome |
| `sidebar` | Sectioned navigation |
| `topbar` | Search affordance + user + logout |
| `command-palette` | ⌘K navigation |
| `page-header` | Title / description / actions |
| `nav-config` | Single source of nav + command items |

## Domain components

| Component | Purpose |
|-----------|---------|
| `charts/equity-chart` | Recharts area equity |
| `dashboard/stat-card` | KPI tiles |
| `trading/order-ticket` | Validate + risk-check form |
| `auth/auth-shell` | Auth page chrome |
| `system/offline-banner` | Connectivity notice |

## Providers

| Provider | Purpose |
|----------|---------|
| `AppProviders` | Theme + Query + Auth + Toaster |
| `AuthProvider` | Session lifecycle |

## Pages

### Marketing
- `/` Landing

### Auth
- `/login` `/register` `/forgot-password` `/verify-email`

### App
- `/dashboard` `/portfolio` `/performance` `/wallet`
- `/brokers` `/mt5` `/risk` `/strategy` `/backtesting` `/paper`
- `/execution` `/orders` `/positions` `/history` `/analytics`
- `/ai` `/notifications` `/settings` `/organizations` `/profile` `/support`
