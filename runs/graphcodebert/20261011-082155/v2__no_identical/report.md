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
| roc_auc | 0.8834 | [0.8218, 0.9172] | 1846058 | 338 | 1845720 |  |
| pr_auc | 0.1277 | [0.0433, 0.2174] | 1846058 | 338 | 1845720 |  |
| ece | null | null | 1846058 | 338 | 1845720 | scores_not_probabilities |
| map_at_r | 0.4324 | [0.3192, 0.5463] |  |  |  |  |

## Operating points

| Point | Threshold | Source | Target FPR | View | Precision | Recall | FPR | F1 | Support |
|---|---|---|---|---|---|---|---|---|---|
| fpr_0.05 | 0.9979 | val_raw_score | 0.0500 | observed | 0.0946 [0.0558, 0.1988] | 0.2485 [0.1226, 0.3369] | 0.0004 [0.0001, 0.0012] | 0.1370 [0.0811, 0.1890] | ok |
| fpr_0.05 | 0.9979 | val_raw_score | 0.0500 | balanced | 0.9983 [0.9965, 0.9993] | 0.2485 [0.1226, 0.3369] | 0.0004 [0.0001, 0.0012] | 0.3980 [0.2184, 0.5037] | ok |
| fpr_0.01 | 1.0000 | val_raw_score | 0.0100 | observed | null null | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | null null | ok |
| fpr_0.01 | 1.0000 | val_raw_score | 0.0100 | balanced | null null | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | null null | ok |

## Plots

- ![roc.png](roc.png)
- ![pr.png](pr.png)
- confusion.png not produced: omitted (counts are in metrics.json operating_points)
- reliability.png not produced: scores_not_probabilities

## Warnings

- scores_not_probabilities: ECE and reliability are not computed

## Limitations

- Student overlap: the split unit is the block (course letter + Zx), not the student, so the same student can appear in train, val and test. Per-student style can leak across splits; treat results as optimistic for unseen students.
