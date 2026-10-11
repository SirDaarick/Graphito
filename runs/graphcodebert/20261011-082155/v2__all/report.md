# Run report: graphcodebert on test

## Provenance

| Field | Value |
|---|---|
| Run | graphcodebert/20261011-082155 |
| Split | test |
| Mode | zero_shot |
| Seed | 42 |
| Manifest | data/splits/split_v1.json.gz |
| Manifest sha256 | e835362d2e7a4153ef97204d4b30e769759a0f8f54f7db67b9e1fb2639e5238f |
| Calibration sha256 | null |
| Threshold source | null |
| Git | 69a19d8a3ede60fce5247fe807e98c31657a076e (dirty: False) |
| Created (UTC) | 2026-10-11T08:21:55.689054+00:00 |

## Threshold-free metrics (observed view)

| Metric | Value | CI95 | n | n_pos | n_neg | Note |
|---|---|---|---|---|---|---|
| roc_auc | 0.8559 | [0.7960, 0.8925] | 1908545 | 338 | 1908207 |  |
| pr_auc | 0.0015 | [0.0003, 0.0051] | 1908545 | 338 | 1908207 |  |
| ece | null | null | 1908545 | 338 | 1908207 | scores_not_probabilities |
| map_at_r | 0.2946 | [0.1448, 0.4129] |  |  |  |  |

## Operating points

| Point | Threshold | Source | Target FPR | View | Precision | Recall | FPR | F1 | Support |
|---|---|---|---|---|---|---|---|---|---|
| fpr_0.05 | 0.9979 | val_raw_score | 0.0500 | observed | 0.0013 [0.0003, 0.0046] | 0.2485 [0.1226, 0.3369] | 0.0332 [0.0168, 0.0471] | 0.0026 [0.0006, 0.0090] | ok |
| fpr_0.05 | 0.9979 | val_raw_score | 0.0500 | balanced | 0.8823 [0.7622, 0.9412] | 0.2485 [0.1226, 0.3369] | 0.0332 [0.0168, 0.0471] | 0.3878 [0.2131, 0.4933] | ok |
| fpr_0.01 | 1.0000 | val_raw_score | 0.0100 | observed | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | 0.0001 [0.0001, 0.0001] | 0.0000 [0.0000, 0.0000] | ok |
| fpr_0.01 | 1.0000 | val_raw_score | 0.0100 | balanced | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | 0.0001 [0.0001, 0.0001] | 0.0000 [0.0000, 0.0000] | ok |

## Plots

- ![roc.png](roc.png)
- ![pr.png](pr.png)
- confusion.png not produced: omitted (counts are in metrics.json operating_points)
- reliability.png not produced: scores_not_probabilities

## Warnings

- scores_not_probabilities: ECE and reliability are not computed

## Limitations

- Student overlap: the split unit is the block (course letter + Zx), not the student, so the same student can appear in train, val and test. Per-student style can leak across splits; treat results as optimistic for unseen students.
