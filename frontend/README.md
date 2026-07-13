# QuantForg Frontend

Enterprise web client for the QuantForg production API.

## Quick start

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Scripts

- `npm run dev` — Turbopack dev server
- `npm run build` — production build
- `npm run start` — serve production build
- `npm run lint` — ESLint
- `npm run typecheck` — `tsc --noEmit`

## Docs

- `FRONTEND_IMPLEMENTATION_PLAN.md`
- `FRONTEND_PROGRESS.md`
- `UI_COMPONENT_INVENTORY.md`

## Notes

- Auth tokens are stored in `localStorage` for the SPA session; refresh uses `/auth/refresh`.
- Live trading is never enabled from the UI; execution paths only validate / safety-check unless the API has `EXECUTION_ENABLED=true`.
- Do not commit secrets. Only `NEXT_PUBLIC_*` variables are used in the browser.
