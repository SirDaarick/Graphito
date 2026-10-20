# Library fix + similarity report redesign (teacher-facing, plain language)

**Branch:** `fix/library-dictamen-and-report-redesign` (from `main`).

## Problem
1. The library showed "0 comparaciones activas" everywhere: 9 reports kept the legacy label `SOSPECHA_IA`,
   the ORM raised `LookupError`, `GET /problems/{id}/submissions` answered 500 and `Biblioteca.tsx` swallowed it.
2. The report modal exposes too much technical detail to teachers, leads with Jaccard, has a separate XAI
   section, and its proportions are tall and narrow.

## Scope
- Backend: idempotent migration rewriting legacy labels. Local Postgres patched (backup in scratchpad).
- Frontend: no GitHub button in the header; semantic similarity (GraphCodeBERT) is the headline metric,
  Jaccard only as a tiny reference; percentages with one plain sentence and a "?" popover per metric
  (how it is computed + risks); XAI section removed, its evidence becomes a hover on suspicious lines;
  fewer labels; wider and shorter modal; the library warns when entregas fail to load.

## Constraints
- Frontend-only for the redesign; the backend decision logic (Jaccard + CharCNN flags) is untouched.
- `gcb_similarity` is null until references are reindexed: the UI must show "no disponible", never 0 %.
- UI copy in neutral Spanish; code and comments in English.

## Tasks
- [x] B1 Migration + test (RED: missing UPDATE statements; GREEN 15/15). Applied locally: 9 rows rewritten, ORM loads 14/14 reports. Commit `103d2cb`.
- [x] F1 Remove the GitHub button from `Header.tsx` (verified: lint/tsc/build green; no GitHub link left in the header)
- [x] F2 Redesign `SimilarityReportModal` (GraphCodeBERT-first, popovers, no XAI tab, hover evidence, proportions). Pure logic test-first (RED 29+2 failures, then GREEN): `gcbHeadline`, `plainVerdict`, `toComparison`, `evidenceByLine`. Visual check in demo mode (desktop + 375px): "?" popover opens/Escape closes only the popover, line hover tooltip shows evidence.
- [x] F3 `Biblioteca.tsx`: visible notice when loading entregas fails (banner with retry; not exercised against a failing API, only type/lint/build checked)
- [x] F4 Verify: vitest, lint, typecheck, build, visual check in the browser — parent re-run: lint, typecheck clean; vitest 72/72; build OK; demo-mode visual check at 1366x800 (two-column modal, metric cards with "?"). Not exercised: focus tooltip path, Biblioteca failure banner against a failing API.

## Route declaration
- B1 inline: one SQL file + one test, understood.
- F1-F3 delegated to one writer: 2+ non-trivial files and reading that prepares the write (mapping trigger).

