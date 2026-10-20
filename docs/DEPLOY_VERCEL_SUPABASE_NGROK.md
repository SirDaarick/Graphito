# Deploy: Vercel + ngrok + Supabase

```
Vercel (SPA) --HTTPS--> ngrok static domain --> backend (Docker, REAL models)
                                                  |-- Chroma (Docker volume)
                                                  `-- Supabase Postgres (session pooler)
```

The backend and the models run on your machine (or GPU server). Vercel only serves the static
frontend, so the machine must stay on while the platform is in use.

## 1. Supabase (once)

1. Create a project. Save the database password.
2. Project Settings > Database > Connection string > **Session pooler**. Copy it.
3. Build `DATABASE_URL` for `.env.vercel`:
   `postgresql+asyncpg://postgres.<ref>:<url-encoded-password>@aws-0-<region>.pooler.supabase.com:5432/postgres?ssl=require`

Use the session pooler: the direct host is IPv6-only. If you must use the transaction pooler
(port 6543), also set `DB_POOLER_COMPAT=true`.

Tables are created by the backend at startup; the entrypoint then applies
`backend/migrations/migration_features.sql` (idempotent). Nothing to run by hand.

## 2. ngrok (once)

1. Dashboard > Domains: claim your free static domain (e.g. `your-name.ngrok-free.app`).
2. Dashboard > Your Authtoken: copy it.

## 3. Backend

```bash
cp .env.vercel.example .env.vercel      # fill NGROK_*, JWT_SECRET, DATABASE_URL, CORS_ORIGINS
docker compose -f docker-compose.vercel.yml --env-file .env.vercel up -d --build
```

The first start downloads `microsoft/graphcodebert-base` into the `hf_cache` volume, so it needs
internet and can take a few minutes.

Verify (all three must pass before touching Vercel):

```bash
curl http://127.0.0.1:8000/health
curl https://<NGROK_DOMAIN>/health
```

`inference_ready` must be `true` and `status` must be `healthy`. If it is `degraded`, the response
names the reason (a deploy artifact whose sha256 differs from `models/deploy/manifest.json`, or
GraphCodeBERT not downloaded). The API answers 503 instead of using a stub.

## 4. Vercel

1. Import the repository. **Root Directory: `frontend`** (framework Vite; `frontend/vercel.json`
   already sets build and SPA rewrites).
2. Environment variables (Production):
   - `VITE_API_URL` = `https://<NGROK_DOMAIN>/api/v1`
   - `VITE_DEMO_MODE` = `false`
3. Deploy. Put the resulting `https://<project>.vercel.app` in `CORS_ORIGINS` in `.env.vercel`
   (preview URLs `*.vercel.app` are already accepted) and restart the backend:

```bash
docker compose -f docker-compose.vercel.yml --env-file .env.vercel up -d
```

`VITE_*` variables are baked at build time: changing `VITE_API_URL` needs a Vercel redeploy.

## 5. End-to-end check

Open the Vercel URL, register a teacher, upload a reference and run one analysis. In Supabase >
Table Editor the new user and analysis rows must appear.

## Troubleshooting

| Symptom | Cause |
|---------|-------|
| Login says it cannot reach the backend | tunnel down or `VITE_API_URL` wrong; open `https://<NGROK_DOMAIN>/health` |
| Browser CORS error | Vercel domain missing in `CORS_ORIGINS`, or it is not valid JSON (`["https://..."]`) |
| `/health` degraded, 503 on analysis | deploy artifact changed or GraphCodeBERT not downloaded; read `inference_error` |
| Backend crash: `prepared statement ... already exists` | transaction pooler without `DB_POOLER_COMPAT=true` |
| Backend crash resolving `db.<ref>.supabase.co` | direct host is IPv6-only; use the session pooler URL |

## Rollback

`docker compose -f docker-compose.vercel.yml down` stops the backend and tunnel (volumes kept).
Vercel keeps previous deployments; promote an older one from its dashboard.
