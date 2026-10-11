# Run report: char_cnn_legacy on test

## Provenance

| Field | Value |
|---|---|
| Run | char_cnn_legacy/20261011-033124 |
| Split | test |
| Mode | legacy_contaminated |
| Seed | 42 |
| Manifest | C:/Users/edani/OneDrive/Documents/Proyectos/Graphito/data/splits/split_v1.json.gz |
| Manifest sha256 | e835362d2e7a4153ef97204d4b30e769759a0f8f54f7db67b9e1fb2639e5238f |
| Calibration sha256 | null |
| Threshold source | manual |
| Git | 9cce24adeacacda88d07f78564390cebef2139dd (dirty: True) |
| Created (UTC) | 2026-10-11T03:31:24.448110+00:00 |

## Threshold-free metrics (observed view)

| Metric | Value | CI95 | n | n_pos | n_neg | Note |
|---|---|---|---|---|---|---|
| roc_auc | 0.9991 | [0.9981, 0.9998] | 9649 | 331 | 9318 |  |
| pr_auc | 0.9888 | [0.9810, 0.9954] | 9649 | 331 | 9318 |  |
| ece | 0.0063 | [0.0055, 0.0084] | 9649 | 331 | 9318 |  |

## Operating points

| Point | Threshold | Source | Target FPR | View | Precision | Recall | FPR | F1 | Support |
|---|---|---|---|---|---|---|---|---|---|
| argmax_0.5 | 0.5000 | manual | null | observed | 0.9412 [0.9033, 0.9741] | 0.9668 [0.9475, 0.9848] | 0.0021 [0.0009, 0.0037] | 0.9538 [0.9316, 0.9733] | ok |
| argmax_0.5 | 0.5000 | manual | null | balanced | 0.9978 [0.9962, 0.9990] | 0.9668 [0.9475, 0.9848] | 0.0021 [0.0009, 0.0037] | 0.9820 [0.9722, 0.9914] | ok |

## Per group (ROC-AUC)

| Breakdown | Group | n | n_pos | AUC | Note |
|---|---|---|---|---|---|
| lang | c | 4338 | 140 | 0.9981 |  |
| lang | cpp | 5311 | 191 | 0.9996 |  |
| course | A2016 | 1428 | 60 | 0.9999 |  |
| course | A2017 | 2910 | 80 | 0.9974 |  |
| course | B2016 | 2817 | 71 | 0.9995 |  |
| course | B2017 | 2494 | 120 | 0.9997 |  |
| length_bucket | <512 | 1912 | 38 | 0.9952 |  |
| length_bucket | 512-1023 | 1494 | 85 | 0.9965 |  |
| length_bucket | 1024-2047 | 2050 | 141 | 1.0000 |  |
| length_bucket | 2048-4095 | 3037 | 56 | 1.0000 |  |
| length_bucket | >=4096 | 1156 | 11 | 1.0000 |  |

## Plots

- ![roc.png](roc.png)
- ![pr.png](pr.png)
- ![confusion.png](confusion.png)
- ![reliability.png](reliability.png)

## Warnings

- contaminated: the legacy checkpoint was trained on a split that overlaps split_v1 test, and its preprocessing (v1) differs from preprocess v2; these numbers are not comparable to a v2 run

## Limitations

- Student overlap: the split unit is the block (course letter + Zx), not the student, so the same student can appear in train, val and test. Per-student style can leak across splits; treat results as optimistic for unseen students.

## Legacy baseline (contaminated)

- contaminated: the legacy checkpoint was trained on a split that overlaps split_v1 test, and its preprocessing (v1) differs from preprocess v2; these numbers are not comparable to a v2 run; not comparable to the legacy 96% claim either.
- Checkpoint: `C:/Users/edani/OneDrive/Documents/Proyectos/Graphito/models/char_cnn/best_model.pth` (sha256 `d3692747d2767b56806964ba2a23e686aa5e8515994d449f6b5e3afb18cb19e7`, unchanged by the run).
- secondary: all non-broken test files (CI95 by dup_group) (n=9649, n_pos=331).
- Scores: uncalibrated `prob_sintetico` from the legacy facade; operating point `argmax_0.5` is manual.
- Legacy abstention (`insufficient_length`, scored with the 0.05 placeholder): test 9/4531 (human 8, ai 1), test_all 19/9649 (human 18, ai 1)

## Per generator (vs all humans)

Each group's AI files against every human file of the view; low_support when n_pos < 30.

| Breakdown | Group | n_pos | n_neg | ROC-AUC | PR-AUC | recall@argmax_0.5 | Support |
|---|---|---|---|---|---|---|---|
| model | codestral | 0 | 9318 | null | null | null | low_support |
| model | deepseek-chat | 228 | 9318 | 0.9990 | 0.9866 | 0.9781 | ok |
| model | gemini-flash | 1 | 9318 | 1.0000 | 1.0000 | 1.0000 | low_support |
| model | kimi | 1 | 9318 | 1.0000 | 1.0000 | 1.0000 | low_support |
| model | llama4 | 1 | 9318 | 1.0000 | 1.0000 | 1.0000 | low_support |
| model | mistral-small | 0 | 9318 | null | null | null | low_support |
| model | qwen3 | 100 | 9318 | 0.9994 | 0.9718 | 0.9400 | ok |
| profile | aplicado | 81 | 9318 | 0.9996 | 0.9852 | 0.9753 | ok |
| profile | comentado-basic | 26 | 9318 | 0.9997 | 0.9616 | 0.9615 | low_support |
| profile | comentado-bueno | 37 | 9318 | 1.0000 | 0.9986 | 1.0000 | ok |
| profile | comentado-malo | 32 | 9318 | 1.0000 | 0.9982 | 1.0000 | ok |
| profile | comentado-pro | 1 | 9318 | 1.0000 | 1.0000 | 1.0000 | low_support |
| profile | descuidado | 75 | 9318 | 0.9971 | 0.9475 | 0.9333 | ok |
| profile | kompaktan | 79 | 9318 | 0.9996 | 0.9677 | 0.9620 | ok |
