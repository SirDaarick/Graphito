# Feature: Catálogo de programas ESCOM precargados

## Objective
Add a top-level "Catálogo" section so teachers testing Graphito can pick from 124 preloaded C/C++
programs (grouped by subject and unit) instead of uploading their own. A catalog program acts as
the reference solution; from it the teacher can compare one student code or bulk-upload many.

## Scope / constraints
- Source data: `Programas_ESCOM/Entregable_Ejercicios.json` (124 entries: materia, unidad, nombre_archivo, ruta_original, lenguaje, codigo). Copied to `backend/app/data/catalog_escom.json`; `Programas_ESCOM/` itself is not committed.
- Catalog is shared and read-only. "Using" a program lazily creates, per teacher, one `Problema` (with new `catalogo_id`) plus one REFERENCIA indexed via `ProblemService.add_reference_code`. Idempotent per (teacher, catalog id).
- Schema change goes through `backend/migrations/migration_features.sql` (create_all does not alter tables).
- Branch `feat/catalogo-escom`, cut from `feat/bmi-05-figures`. The working tree has unrelated uncommitted thesis changes: commit only catalog files, by explicit path.
- Artifacts in English; UI copy in Spanish (project convention). Conventional commits, no attribution.
- Planning heuristic ~400 changed lines per task (advisory).

## Tasks
- [x] T1 Backend: JSON copy, loader (`infrastructure/catalog/json_catalog.py`), `Problema.catalogo_id` + migration, `CatalogService`, schemas, endpoints (`GET /catalog`, `GET /catalog/{id}`, `POST /catalog/{id}/use`), router registration, `backend/tests/test_catalog.py` (test-first)
- [x] T2 Frontend: `api.catalog` + types + demo subset, `App.tsx` section state, `Header.tsx` tabs, `pages/Catalogo.tsx`, `components/catalog/CatalogProgramModal.tsx`
- [x] T3 `NewComparisonModal`: optional `initialProblemId`, language from selected problem (was hard-coded `"c"`); `BulkUploadModal` opened with a problem id from the catalog modal
- [ ] T4 Full verification: `pytest backend/tests/ -v`, `npm run lint`, `npm run build`, manual flow

### Iteration 2 (user request 2026-10-18)
- [x] T5 (cd210e0; backend suite 280 passed) Data+backend: keep only 3 subjects (Fundamentos de Programación, Algoritmos y Estructuras de Datos, Análisis y Diseño de Algoritmos; drop Paradigmas, 124 -> 84 programs); add `descripcion` + `tema` per program (authored from the code); `GET /catalog/{id}` returns them, list summary returns `tema`; adopted problem `enunciado` uses the description; `ProblemaResponse.catalogo_id` (Optional); tests updated
- [x] T6 (4db4566; lint, tsc, build, vitest clean; checked in browser against isolated backend) Frontend catalog: all subject and unit sections collapsed by default; modal shows description + syllabus part (unit + topic); single "Agregar a mi biblioteca" button (adopts the program, appears in Biblioteca as a loaded problem), "ya en tu biblioteca" state and card badge; remove the now-unused compare/bulk plumbing from App if unreferenced
- [x] T7 (4db4566) Biblioteca empty state: callout "¿No sabes por dónde empezar?" with a button that navigates to the Catálogo

## Acceptance
- list: 124 entries, 4 subjects, unique ids, no `codigo` in the list payload
- get: includes code; unknown id -> 404; unauthenticated -> 401
- use: creates Problema + REFERENCIA; second call returns the same problem id; C++ entry keeps `cpp`
- UI: Catálogo tab shows grouped programs; both actions open the right modal with the adopted problem selected

## Route
Delegated writer per task (T1 and T2 touch 2+ non-trivial files); parent reads back and spot-checks.
Trigger evidence: T1 = 8+ files, T2 = 6+ files.

## Evidence
- T1 RED: 7 failed / 1 passed (catalog route 404). GREEN: test_catalog.py 8 passed; full backend suite 277 passed (parent spot check).
- Deviation: DDL placed as section 7b in migration_features.sql because test_migration.py requires the `UPDATE reportes_analisis ... engine` statement to stay last.
- Known limit: use_entry is select-then-insert without a unique constraint; two truly concurrent first calls could duplicate.
- T2 and T3 share files, so they go to one frontend writer and one commit.

## Commits
- T1: 943070b feat(catalog): add read-only ESCOM program catalog API with per-teacher adoption

- T2+T3: f266401 feat(catalog): add Catálogo section with program picker, compare and bulk-upload flows
  Evidence: `npm run lint` clean, `tsc -b --noEmit` clean, `npm test` 58 passed (parent spot check). Not clicked through in a browser.

- T4 (partial): real backend (uvicorn, SQLite, STUB engine; Docker Desktop was off) + frontend with demo mode off. Catálogo listed real data (32 programs in first subject); "Comparar un código" on a C++ program preselected it, produced a report; API: 1 problem (cpp), second `use` returned the same id, submission saved as cpp. "Carga masiva" not exercised. Postgres/migration not exercised.
- Found: units list in first-appearance order (III before II) instead of natural order.

## Next step
Sort units naturally; test "Carga masiva"; run `apply_migrations.py` against Postgres.
Untracked `frontend/tsconfig.tsbuildinfo` is a tsc artifact, not committed.
