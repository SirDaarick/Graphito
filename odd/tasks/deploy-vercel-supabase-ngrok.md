# Deploy: Vercel (frontend) + ngrok tunnel + Supabase (Postgres) + local backend (REAL models)

**Objective:** one production topology that works from `main` without any experiment branch.

```
Vercel (SPA) --HTTPS--> ngrok static domain --> backend:8000 (Docker, INFERENCE_MODE=REAL)
                                                  |-- chroma (Docker, persistent)
                                                  `-- Supabase Postgres (session pooler, IPv4)
```

## Constraints
- Secrets (Supabase URL, ngrok token/domain, JWT secret, Vercel URL) are filled by the user; only templates are committed.
- Experiments stay on their own branches; this branch holds only deploy files.
- Production refuses `ALLOW_UNCALIBRATED` and any stub fallback (already enforced in `config.py`).

## Tasks
- [x] T1 DB engine compatible with Supabase poolers (`DB_POOLER_COMPAT`, `pool_pre_ping`) + test — RED observed (ImportError), GREEN 3/3; 24 passed with test_inference_engines. Full-suite run: 129 passed, 1 timing flake (test_slow_inference_does_not_block_the_loop) that passes in isolation.
- [x] T2 `docker-compose.vercel.yml` (backend + chroma + ngrok, no local postgres/frontend) + `.env.vercel.example` — YAML parsed; `docker compose config` NOT run (env_file access denied in this session).
- [x] T3 `frontend/vercel.json` (SPA rewrites) + frontend env template — JSON valid.
- [x] T4 `docs/DEPLOY_VERCEL_SUPABASE_NGROK.md` runbook (step order, verification, rollback)
- [ ] T5 Land on `main` (user decision: merge strategy)

## Route declaration
All tasks inline: each touches 1-2 small, understood files; evidence fit the inline budget.

## Evidence
- `main` lacks `models/deploy/`, the REAL engine and the migrations (120 commits behind this branch).
- CORS already allows `https://*.vercel.app` (`backend/app/main.py`); `ngrok-skip-browser-warning` already sent by `frontend/src/lib/api.ts`.
- Supabase direct host is IPv6-only; use the **session pooler** (IPv4, port 5432, prepared statements OK).

