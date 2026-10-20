# Report modal: metrics-first view, code comparison optional

**Branch:** `feat/report-metrics-first-view` (from `origin/main` `c149b99`).

## Problem
The redesign in PR #1 put metrics and the code comparison in one crowded two-column screen. The teacher wants
the previous structure back: the metrics view is the main screen and the code comparison is an optional view,
keeping the simplified content (GraphCodeBERT-first, plain language, "?" popovers, hover evidence, few labels).

## Scope
- Frontend only. Restore the two view modes of the old modal (`report` by default, `code_diff` on demand),
  using `git show 90f8676:frontend/src/pages/SimilarityReportModal.tsx` as the reference for layout/behavior.
- Keep from PR #1: `gcbHeadline`, `plainVerdict`, `evidenceByLine`, `ReportMetrics`/`MetricCard`/`InfoPopover`,
  hover evidence on code lines, no XAI drawer, no provenance chips, library notice.

## Tasks
- [x] V1 Metrics view as the default screen (compact modal, simplified content) - observed in demo preview, desktop and 375px
- [x] V2 Code comparison as an optional second view with a clear way in and out - lazy fetch, Esc layering, retry state; error state not exercised in browser
- [x] V3 Verify: lint, typecheck, vitest (72 passed), build all green; visual check done (desktop + 375px)
