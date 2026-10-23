# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Graphito: teacher decision-support for academic integrity in C/C++ assignments (IPN/ESCOM thesis project, docs and UI are in Spanish). It scores a submission on two channels and fuses them:

- **Channel A (semantic):** Tree-sitter DFG + GraphCodeBERT with a LoRA adapter, compared against reference/previous solutions via ChromaDB.
- **Channel B (stylometry):** CharCNN detecting LLM-generated code style.
- **Fusion:** `models/fusion.py` combines both and computes an asymmetric discrepancy index. The teacher makes the final call (human-in-the-loop).

## Commands

Full stack (Postgres 16, ChromaDB, backend, frontend) via Docker; `start.ps1` / `start.sh` copy `.env.example` to `.env` if missing, then run `docker compose up --build`:

```bash
docker compose up --build
```

Backend (run from `backend/`; Swagger at http://localhost:8000/docs):

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
python apply_migrations.py   # applies migrations/migration_features.sql (idempotent DDL)
```

Frontend (run from `frontend/`; dev server on :5173):

```bash
npm install
npm run dev
npm run build
npm run lint
```

Tests (pytest; no pytest.ini, so cwd matters):

```bash
pytest tests/ backend/tests/ -v
pytest backend/tests/test_api_flow.py::<test_name> -v   # single test
```

- `backend/tests/` are API tests; `conftest.py` puts `backend/` on `sys.path`, uses in-memory SQLite (`aiosqlite`), `StubInferenceEngine`, and an in-memory vector store, so no Postgres/Chroma/models are needed.
- Root `tests/` cover the ML side (DFG parser, CharCNN robustness, calibration, e2e analysis). `benchmark_semantic.py` is a benchmark, not a test.
- `scripts/` holds `benchmark_student_archetypes.py` (writes `benchmark_archetypes_results.json`), `build_deploy_artifacts.py` (writes `models/deploy/`), `reindex_references.py` and `generate_tt_figures.py` (requires `--charcnn-run` and `--gcb-run`; reads `runs/*/metrics.json`).

## Architecture

**Backend** (`backend/app/`) is Clean/Hexagonal: `domain` (entities, ports `InferencePort` and `VectorStorePort`) → `application` (`orchestrator/analysis_orchestrator.py`, `services/`) → `infrastructure` (SQLAlchemy async models/session, inference engines, ChromaDB) → `presentation` (FastAPI `api/v1/endpoints`, Pydantic v2 `schemas`, `deps.py`). Routers are wired in `presentation/api/v1/api.py` and mounted under `/api/v1` in `main.py`.

**Analysis pipeline:** `AnalysisOrchestrator` runs S1–S7 (normalize/Tree-sitter → DFG + GraphCodeBERT → Chroma lookup → CharCNN → fusion/discrepancy → severity flags BAJA/MEDIA/ALTA/CRITICA → persist). `POST /analysis/run` supports `async_mode`. Batch uploads and groups go through `batch_analysis_service.py` and `group_service.py`; XAI output through `xai_service.py`.

**Inference is swappable via `INFERENCE_MODE`** (`STUB` default | `REAL`), chosen in `infrastructure/inference/__init__.py`. `real_engine.py` loads the top-level `models/` package by inserting the project root into `sys.path`; in Docker `./models` is mounted read-only at `/models`. Use `STUB` unless you are working on the real models. `REAL` loads the sha256-verified artifacts in `models/deploy/` (see its README); if they fail to load, `/health` reports `inference_ready=false` and analysis returns 503, never a stub fallback. The secondary GraphCodeBERT signal is `v2_norm` plus the trained LoRA adapter listed in the manifest (`gcb.adapter`, merged without `peft`); `GCB_ADAPTER_ENABLED=false` returns to zero-shot, and either way the references must be reindexed (the Chroma collection name carries the adapter identity). `models/fusion.py` is research-only.

**Config** is `backend/app/config.py` (pydantic-settings, reads `.env`, case-sensitive). Notable: `USE_CHROMA_SERVER` (embedded persistent Chroma at `CHROMA_PERSIST_DIRECTORY` vs. server at `CHROMA_HOST:CHROMA_PORT`; compose uses the server on 8000 inside the network, 8001 on the host) and `DEMO_MODE`.

**Schema management is split:** `main.py`'s lifespan runs `Base.metadata.create_all` (new tables only). Column or table changes to existing tables must be added to `migrations/migration_features.sql` and applied with `apply_migrations.py`; `create_all` will not alter them.

**Frontend** (`frontend/src/`): React + TypeScript + Vite + Tailwind. All HTTP goes through `lib/api.ts`. `IS_DEMO_MODE` (`VITE_DEMO_MODE=true`) makes `api.ts` and some components return mock data from `lib/demoData.ts` with no backend, and skips login. API base URL is `VITE_API_URL` (default `http://localhost:8000/api/v1`). Feature folders: `components/{batch,groups,xai,code}`, pages in `pages/`.

## Other

- `Documentacion/Documento/` is the LaTeX thesis (IEEEtran); `Documentacion/guias_implementacion/` has design guides. `sdd/` and `.atl/` are workflow tooling, not app code.
- `backend/chroma_data/` and `models/*` weights are local state; do not commit changes there.
