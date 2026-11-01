# Example group "Ejemplo" + "Ver ejemplos" tour flow
Objective: every teacher account gets a preloaded group "Ejemplo" with ~5 problems and pre-analysed submissions (identical / similar / different problem / AI), plus a "Ver ejemplos" flow in "Cómo usar" that walks through those reports and the code view.
Branch: feat/example-group · Delivery: ask-on-risk · Test runners: pytest (`pytest tests/ backend/tests/ -v` from repo root), vitest (`npm run test` in frontend/)
Plan file: C:\Users\edani\.claude\plans\por-favor-ayudame-a-ticklish-swing.md

## Specs
- S1: "para todas las cuentas existan en su biblioteca problemas precargados en un grupo llamado ejemplo" — every account (new and existing) has a group named `Ejemplo` holding the example problems and their submissions.
- S2: "tomemos los mejores ejemplos que podamos (algunos pocos, unos 5 o asi) que sabemos que funcionan bien" — 5 problems chosen from `data/golden_set/corpus/`, measured with the REAL models; a problem is kept only if all four cases behave as described in S3.
- S3: "cuando son de IA si los detecta, cuando no pues no, que los codigos que son identicos si los detecta iguales en el canal A, cuando son del mismo problema son similares, y cuando son de otro problema si los detecta diferentes" — each problem has four submissions:
  - `identical`: Channel A flag true (calibrated >= umbral_a); Channel B flag false.
  - `similar` (same problem, own human solution): Channel A flag false; raw A > raw A of `different`; Channel B flag false.
  - `different` (another problem's code): Channel A flag false; lowest raw A of the four.
  - `ai`: Channel B flag true; Channel A flag false.
- S4: "en el de como usar, tener otro flujo que sea ver ejemplos, si le picas ahi te hace el flujo para que veas el codigo como se ve uno identico uno similar y otro distinto, de un recorrido por como ver el codigo" — third tour flow "Ver ejemplos": opens the identical, similar, different and AI reports of the showcase problem, shows the metric cards and the side-by-side code view.
- S5 (constraint, memory `graphito-no-verdicts`): UI copy describes what each metric measures and its value; no verdict words ("copia detectada", "sospechoso", severity labels).
- S6: numbers are frozen real measurements stored in a committed fixture; a STUB server shows the same numbers. Report rows keep `engine="real"`; the UI marks them with a neutral "Ejemplo" badge (not the `engine="demo"` "Datos de ejemplo" badge).
- S7: the tour button stays hidden in `VITE_DEMO_MODE` (guided-tour S1), so no demo-mode path is needed for the new flow.

## Contracts
### C1 Fixture `backend/app/data/examples/ejemplo_fixture.json`
```json
{
  "version": 1,
  "generated_at": "ISO-8601",
  "manifest_sha": "sha256 of models/deploy/manifest.json used",
  "engine": "real",
  "problems": [
    {
      "key": "A2016_Z1_Z1",
      "titulo": "Spanish title",
      "descripcion": "Spanish one-paragraph statement",
      "lenguaje": "c",
      "referencia": {"autor": "Referencia del ejemplo", "contenido": "..."},
      "entregas": [
        {
          "caso": "identical | similar | different | ai",
          "autor": "Ejemplo: copia de la referencia | Ejemplo: solución propia | Ejemplo: código de otro problema | Ejemplo: generado con IA",
          "origen": "data/golden_set/corpus/<task>/<kind>/<file>.c",
          "contenido": "...",
          "outcome": {
            "channel_a": {"estado": "...", "raw": 0.0, "calibrated": 0.0, "flag": true, "threshold": 0.0, "threshold_key": "...", "calibration_sha256": "..."},
            "channel_b": {"...same ChannelResult fields...": null},
            "gcb_similarity": 0.0,
            "engine": "real",
            "provenance": {"canal_a_metodo": "...", "manifest_sha": "...", "checkpoint_sha_b": "...", "gcb_estado": "...", "label": "..."}
          }
        }
      ]
    }
  ]
}
```
`channel_a`/`channel_b` are `dataclasses.asdict(ChannelResult)` (`backend/app/domain/scoring.py:52`); rebuild with `ChannelResult(**d)` and `ScoringOutcome.build(a, b, gcb_similarity=..., engine=..., provenance=...)`. `problems[0]` is the tour showcase. Every problem has exactly one entrega per caso, in the order identical, similar, different, ai. `provenance` drops `tiempos_ms`.

### C2 `POST /api/v1/examples/ensure` (authenticated teacher)
```json
{
  "grupo_id": 7,
  "creado": true,
  "problemas": [
    {"problema_id": 31, "titulo": "...", "casos": {"identical": 101, "similar": 102, "different": 103, "ai": 104}},
    {"problema_id": 32, "titulo": "...", "casos": {"identical": 201, "similar": 202, "different": 203}}
  ],
  "recorrido": {"problema_id": 31, "casos": {"identical": 101, "similar": 102, "different": 103, "ai": 104}}
}
```
`creado` is false when the group already existed. Report ids are `ReporteAnalisis.id` (int), openable at `/reporte/:id`. `problemas[].casos` (added by L4) holds only the cases that problem has (ESCOM catalog problems have no `ai`); `recorrido` is unchanged and equals `problemas[0]`.

### C3 Exposed flags
- Group schemas (list/get) include `es_ejemplo: bool`.
- The single-report response used by `api.analysis.getReport` includes `es_ejemplo: bool` (true when the submission's group is the example group).

## Tasks
- [x] T1 (S2,S3,S6,C1) fixture builder + fixture + test — delegated (Sonnet, user request) — RED 4 errors (no fixture) → GREEN 5 passed; GCB re-measured after review — commit —
- [x] T2 (S1,S6,C1,C2,C3) migration, ExampleService, hooks, endpoint, backfill, tests — delegated (Sonnet, user request) — RED ModuleNotFoundError → GREEN 12 passed, backend suite 358 passed — commit —
- [x] T3 (S4,S5,S6,S7,C2,C3) tour flow "Ver ejemplos", anchors, badge, tests — delegated (Sonnet, user request) — RED 7 failed → GREEN 150 passed, lint/build clean — commit —
- [x] T4 end-to-end check in browser preview — parent — observed (see Log)

## Log
- L1 (2026-11-01): "por favor ayudame a crear una cosa, quiero generar como un modo ejemplo dentro de graphito (no el demo), la idea es que para que los profesores puedan probar el sistema, ademas de la biblioteca precargada, para todas las cuentas existan en su biblioteca problemas precargados en un grupo llamado ejemplo, la idea es que tomemos los mejores ejemplos que podamos (algunos pocos, unos 5 o asi) que sabemos que funcionan bien y cargarle comparaciones que funcionen bien, para que se vea que cuando son de IA si los detecta, cuando no pues no, que los codigos que son identicos si los detecta iguales en el canal A, cuando son del mismo problema son similares, y cuando son de otro problema si los detecta diferentes, y despues en el de como usar, tener otro flujo que sea ver ejemplos, si le picas ahi te hace el flujo para que veas el codigo como se ve uno identico uno similar y otro distinto, de un recorrido por como ver el codigo y asi, me comprender?"
- L2 (2026-11-01): plan approved.
- L3 (2026-11-01): "por favor antes de que continues, quiero que delegues trabajo a agentes de sonnet y tu solo revises su trabajo"
- Route declaration: T1–T3 delegated to Sonnet writers in parallel per L3; contracts C1–C3 fixed up front so the units have disjoint edit surfaces. Parent reviews each diff and runs the seam check.
- Deviation from plan: demo-mode `examples.ensure()` dropped (S7).
- Fixture: 5 C tasks (A2017_Z4_Z1 showcase, A2017_Z3_Z3, A2017_Z1_Z1, A2017_Z4_Z2, A2016_Z3_Z3), REAL models, manifest 9baf2ec9…. `identical` is the reference file itself (corpus `copy/` files are student-to-student copies and never flag A against the reference). Raw A: identical 1.0, similar 0.31–0.42, different 0.05–0.10; B: ai ≈1.0, others ≤0.01; GCB: identical 1.0 > similar 0.75–0.90 > different 0.28–0.49 (ai 0.62–0.80). B2016_* tasks are C++ and were skipped.
- Review changes requested: (1) GCB was null (no vector store in the builder) → re-measured with an ephemeral Chroma; (2) tour showed code only for the identical case → added code steps for similar and different (L1 asks for all three); (3) layout-dependent "izquierda/derecha" copy → neutral.
- E2E (STUB backend, scratch SQLite, :8123/:3000): sign-up seeds group Ejemplo with 5×4 reports carrying fixture values and es_ejemplo=true; tour 11/11 steps observed incl. the code view of identical/similar/different and the AI style card; DELETE group → ensure restores it (creado=true, same 5 problems, 20 submissions relinked), second ensure creado=false.
- Bug found in E2E (pre-existing, exposed by the tour): a deep link to /reporte/:id left the modal at opacity 0 because the GSAP entrance ran while `comparison` was still null → animations now depend on `hasComparison`. No component test (vitest node env, no jsdom).
- L4 (2026-11-01): "para el modo guia, en lugar como de decir que de click en un problema especifico, le muestre la seccion y pueda elegir cualquiera de los problemas que mas le interese" → C2 gains `problemas[].casos`; the examples flow's first step highlights the list of example problems (`data-tour="example-problems"`, advance `pick`), the click on any problem card stores its id in `context.problemId` (action `pick`, the click is swallowed so Comparar/menu do not fire), later steps open that problem's reports (fallback `recorrido`), and the `ai` step (`requiresCase`) is skipped when the problem has no `ai` report (next/back/goTo/progress all use the filtered list).
- Known limits: seeding runs inside the sign-up request (REAL engine embeds 5 references); concurrent ensure calls for one teacher are not guarded; Google first-login hook is wired but untested; fixture code has Bosnian identifiers/comments (same corpus as the survey example).
