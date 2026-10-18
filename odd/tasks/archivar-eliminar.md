# archivar-eliminar

Objective: per-problem actions in Biblioteca (assign to group, archive, delete), archive/delete of groups, and visual consistency of the bulk-upload and create-group modals.

## Tasks
- [x] T1 Backend tests (RED) + `archivado` columns, DDL (section 7c), archive/unarchive/delete endpoints, vector cleanup, catalog re-add
- [x] T2 Frontend API client (demo-mode blocked writes), shared ConfirmDialog
- [x] T3 Biblioteca: per-problem menu (group / archive / delete), archived toggle
- [x] T4 Groups: archive/delete in dropdown, archived toggle
- [x] T5 Restyle BulkUploadModal and CreateGroupModal like the reference modals
- [x] T6 Checks: pytest, lint, tsc, build, npm test, browser check

## Notes
- Route: delegated none; inline (single writer).
- After rebuilding: `docker exec graphito-backend python apply_migrations.py` (adds `archivado` to problemas and grupos).

## Evidence
- 849ed03 backend, 2a1e08e library UI, 428899f modal restyle; final fix commit adds api.ts template-literal fix.
- pytest backend/tests: 294 passed; npm lint, tsc, build, test (58) clean; browser check on isolated stack (assign, archive, toggle, delete problem and group, both modals).
