# UI/UX audit improvements
Objective: fix the usability and accessibility issues found in the 2026-10-31 audit (demo mode, 1366px and 375px), keeping Graphito as metrics-only decision support with no verdicts about students.
Branch: `feat/ui-ux-audit` · Delivery: ask-on-risk · Test runner: vitest (`npm run test` in frontend/, `src/**/*.test.ts`) · Status: implemented (commits 0ee844b, fdc3df4, 40decdd); partial items noted in the Log.

## Specs
- S1: Improve the app's interface and usability: "Me ayudas con una auditoria para mejorar la aplicacion tanto en interfaz y usabilidad?"
- S2: Metrics only, never verdicts: "graphito es un sistema de apoyo a la evaluacion docente, no hace veredictos, solo da metricas y el profesor es el que decide que significa eso para el, ya que si falla no queremos comprometer a ningun alumno"
- S3 (assumption, derived from S2): no screen, color, label or export may present a judgment, a severity level (BAJA/MEDIA/ALTA/CRITICA) or a suggested action about a student. Descriptive labels such as those in `lib/dictamen.ts:53-58` stay.

## Tasks
Phase 1: remove judgments that leak into the UI (S2, S3)
- [x] T1 (S2,S3) Neutral metric encoding — the list colors 97% red and the report shows the same 97% in blue; `flagged: true` in `lib/dictamen.ts:53-56` drives rose/amber vs emerald. Use one neutral scale, and label what each % measures ("Similitud lógica 97%"). Route: inline.
- [x] T2 (S2,S3) Export wording — `lib/api.ts:478-492` (demo export) prints "REPORTE DE INTEGRIDAD ACADÉMICA", "Estudiante Evaluado" and `[${i.severidad}]`. Rewrite as a metrics report without severity. Also check the real backend PDF for the same wording. Risk: item 3 if the backend PDF format changes.
- [x] T3 (S2,S3) Severity in evidence — `lib/evidence.ts:44` carries `severidad` into line evidence; check whether it reaches the side-by-side view as color or icon and neutralize it. Update `lib/evidence.test.ts`.

Phase 2: blocking issues (S1)
- [x] T4 (S1) Modal focus management — `components/ui/Modal.tsx` only handles Escape: on open, focus stays on the element behind (verified for the report and catalog modals). Add initial focus, focus trap and focus restore; check which modals do not use `Modal.tsx` (the report modal sets its own `role=dialog`).
- [x] T5 (S1) Mobile navigation — below `sm` the Biblioteca/Catálogo nav is hidden and the user menu only has "Cerrar sesión", so Catálogo is unreachable; "+ Nuevo código" wraps into 3 lines and covers the logo. The header already overflowed at 375px (see `guided-tour.md` L-log).
- [x] T6 (S1) Report header on mobile — "Reporte de similitud" overlaps the "1 de 1" pager at 375px; the student name is truncated on desktop.

Phase 3: helping the teacher interpret and decide (S1, S2)
- [x] T7 (S2) Context instead of conclusion — explain what each metric measures and what it does not (high similarity to the reference is expected for a correct solution), a visible note that the models can fail and are not conclusive evidence, and optionally where the submission sits relative to its group, shown as data.
- [x] T8 (S1,S2) Teacher decision controls — "Marcar sin observaciones" / "Marcar para aclarar" are icon-only in the footer; give them visible text. The single-key `A`/`R` shortcuts record the decision and advance with no undo; add confirmation or an undo toast.
- [x] T9 (S1) Deep link keeps the list — opening `/reporte/:id` directly shows "1 de 1", so the teacher cannot move to other submissions of the same problem.
- [x] T10 (S1) Side-by-side evidence — renamed identifiers (`NODOS`↔`V`, `obtener_minimo`↔`minDistance`) are not linked visually and the highlighting has no legend. Needs investigation: whether the backend exposes identifier mappings.

Phase 4: forms and visual polish (S1)
- [x] T11 (S1) Forms — every input in "Agregar código de referencia" and "Nueva comparación" has no associated label (`label=null`); no required markers. In demo mode the primary submit buttons look enabled although the feature is disabled.
- [x] T12 (S1) Hierarchy and targets — three competing gradient CTAs ("+ Nuevo código", "Carga Masiva", "Comparar" per card); the "+" of "Comparar" wraps onto its own line at 1366px; "Asignar grupo" is 100×21px and the C/C++ chips ~30px tall (target 44px); no `h1` (page starts at `h2`); emoji ℹ️ used as icon; redundant "demo" + "Datos de ejemplo" badges.
- [x] T13 (S1) Catalog — cards have no visible "Agregar" action; demo data lacks accents ("Busqueda binaria", "memoizacion") and "Búsqueda binaria" sits under "Unidad 2: Listas".

Not audited: file upload, bulk upload, groups and the guided tour (disabled in demo mode); React performance (renders, bundle) beyond a quick check. Already good: skip link, aria-labels on icon buttons, `prefers-reduced-motion` support, report deep links, documented shortcuts, light theme contrast.

## Log
- L1 (2026-10-31): "Me ayudas con una auditoria para mejorar la aplicacion tanto en interfaz y usabilidad? por favor haz uso de skills para ver como mejorarla"
- L2 (2026-10-31): Audit run in the browser pane with the `ui-ux-pro-max` checklist (accessibility, interaction, layout, forms, navigation) and `vercel-react-best-practices`; findings verified via DOM inspection and screenshots.
- L3 (2026-10-31): User correction: "solo recuerda que graphito es un sistema de apoyo a la evaluacion docente, no hace veredictos, solo da metricas y el profesor es el que decide que significa eso para el, ya que si falla no queremos comprometer a ningun alumno". Withdrawn: the earlier proposal to show severity and a suggested action in the report; replaced by T7. Judgment leaks (T1-T3) moved to Phase 1.
- L4 (2026-10-31): "ajusta el plan primero y dejalo en un md por favor". Plan written; no Engram mirror yet (created when implementation starts).
- Next step: user picks the phase to start; route per task to be declared then (all expected inline).
- L5 (2026-10-31): User: "implementa @ui-ux-audit.md". Implemented inline on `feat/ui-ux-audit`. Checks: vitest 123/123, `npm run build`, `npm run lint`, backend `pytest backend/tests` 333 passed (before the final frontend-only commits). Verified in the browser pane (demo mode): deep link `/reporte/101` shows "1 de 3", focus lands inside the dialog, A/R show the undo toast and Deshacer restores the previous decision, 375px header fits and the user menu lists Biblioteca/Catálogo.
- L6 (2026-10-31): Deviations from the plan. T1: list % is one neutral color with "Similitud lógica" label; `flagged`, `color` and `plainVerdict` removed from `lib/dictamen.ts`. T2: the backend PDF (`pdf_service.py`) also changed (neutral banner colors, severity column removed, "Estudiante Evaluado" renamed) — Risk: item 3 (PDF layout consumed by teachers; no test pins the old wording). T3: `LineEvidence` no longer carries severity and is no longer sorted by it. T7: replaced the simulated "Interpretación con IA" card (it had hardcoded text like "94%") with a context card and the validation label; "position relative to the group" NOT done. T8: footer labels are visible from `sm` up, icon-only (with aria-label) below `sm`; undo window 5 s, the last submission now closes after the window instead of 1 s. T10: the backend does not expose identifier mappings, so only a legend was added (highlight meaning + "renamed names are not linked"); linking needs backend work. T12: Carga Masiva and Comparar are no longer gradient CTAs; the "Datos de ejemplo" badge shows only for the demo engine and the raw calibration pill is hidden for stub/demo. T13: card hint is now always visible ("Ver y agregar →"); demo accents and unit fixed.
- Next step: manual review on the real backend (focus trap with the tour open, PDF look), then PR.