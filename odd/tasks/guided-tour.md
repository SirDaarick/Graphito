# Guided tour "Cómo usar"
Objective: interactive onboarding tour opened from a header button; two flows (own exercise / library), advancing on real user interaction.
Branch: feat/guided-tour · Delivery: ask-on-risk (3 slices, ~750 authored lines incl. tests) · Test runner: vitest (`npm run test` in frontend/, node env, `src/**/*.test.ts`)
Plan file: C:\Users\edani\.claude\plans\me-ayudas-a-hacer-mighty-axolotl.md

## Specs
- S1: Header shows a "Cómo usar" button; hidden when `IS_DEMO_MODE` is true (user decision: "Solo modo real").
- S2: Pressing it opens a chooser with two options: "Subir mi propio ejercicio" and "Usar un ejercicio de la biblioteca".
- S3: The tour darkens the UI, highlights the step target with a spotlight, an arrow and a short text.
- S4: A step advances when the user interacts with the highlighted element (click / fills field / route change).
- S5: Both flows end with the shared tail: compare -> submission -> "Iniciar Análisis" -> report -> verdict.
- S6: Design matches the existing interface (glass cards, graphito-blue/violet, Plus Jakarta Sans, dark/light), minimal text.
- S7: No new dependency; pure step/state logic lives in `src/lib/tour/` and is unit-tested.

## Tasks
- [x] T1 (S4,S7) pure types/steps/machine/geometry + tests — inline — commit 16a66dc (tests written after the code, no observed RED)
- [x] T2 (S2,S3,S6) provider, chooser, overlay, tooltip, CSS — inline — commit a0b4681
- [x] T3 (S1,S5) data-tour hooks, header button, App wiring — inline — commit e326a51

## Log
- L1 (2026-10-31): "me ayudas a hacer una planificacion para hacer una guia de usuario, donde arriba en el header aparezzca un boton que diga algo como "Como usar" y al pulsarlo se haga como una guia interactiva, donde como que se oscurezca un poco la interfaz y aparezcan indicaciones como alguna flecha y un texto simple indicando que hace, cuando el usuario interactue con la opcion mencionada en el paso, va al siguiente paso y asi hasta terminar con el flujo, pero al principio quiero que de como ambas opciones, tanto para subir su propio ejercicio, como para usar uno de la biblioteca de ejercicos precargados, quiero que tenga un buen diseño para el usuario para que sea agradable de ver apegandose al diseño de la interfaz como que sea facil de seguir, sin tanta informacion irrelevante"
- L2 (2026-10-31): Demo mode decision: "Solo modo real".
- Route declaration: all tasks inline (no Writer trigger: units are sequential and dependent).
- Verification (real backend, STUB engine, sqlite scratch DB on :8123): own flow 11/11 steps and library flow through step 6 observed in the browser pane; Esc exits; 768px OK.
- Bugs found while verifying and fixed before commit: (a) a step advanced twice when its effect saw stale `armed`/`missing` of the previous step -> state tagged per step id; (b) Header + App both call `navigate()` so one route change fired two events -> `next` is idempotent via `from: stepId` (pinned in machine.test.ts); (c) elements inside collapsed accordions counted as visible -> `isShown` checks zero-size clipping ancestors and opacity.
- Deviations from plan: CSS keyframes instead of GSAP for the tooltip entry; button hidden below `sm` because the header already overflowed at 375px before this change (503px vs 443px content width).
- Not covered: light theme visual pass, "Llévame ahí" fallback on a real narrow screen, `VITE_DEMO_MODE=true` hiding the button (code path only), library-flow tail past step 6 (identical steps to the own flow).
