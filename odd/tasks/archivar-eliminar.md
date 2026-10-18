# archivar-eliminar

Objective: per-problem actions in Biblioteca (assign to group, archive, delete), archive/delete of groups, and visual consistency of the bulk-upload and create-group modals.

## Tasks
- [x] T1 Backend tests (RED) + `archivado` columns, DDL (section 7c), archive/unarchive/delete endpoints, vector cleanup, catalog re-add
- [ ] T2 Frontend API client (demo-mode blocked writes), shared ConfirmDialog
- [ ] T3 Biblioteca: per-problem menu (group / archive / delete), archived toggle
- [ ] T4 Groups: archive/delete in dropdown, archived toggle
- [ ] T5 Restyle BulkUploadModal and CreateGroupModal like the reference modals
- [ ] T6 Checks: pytest, lint, tsc, build, npm test, browser check

## Notes
- Route: delegated none; inline (single writer).
- After rebuilding: `docker exec graphito-backend python apply_migrations.py` (adds `archivado` to problemas and grupos).
