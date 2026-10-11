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
| roc_auc | 0.9747 | [0.9667, 0.9832] | 1846058 | 338 | 1845720 |  |
| pr_auc | 0.0466 | [0.0212, 0.3029] | 1846058 | 338 | 1845720 |  |
| ece | 0.1955 | [0.1635, 0.2429] | 1846058 | 338 | 1845720 |  |
| map_at_r | 0.5492 | [0.4162, 0.6862] |  |  |  |  |

## Operating points

| Point | Threshold | Source | Target FPR | View | Precision | Recall | FPR | F1 | Support |
|---|---|---|---|---|---|---|---|---|---|
| fpr_0.05 | 0.6491 | val_raw_score | 0.0500 | observed | 0.0300 [0.0199, 0.0845] | 0.6095 [0.4653, 0.7019] | 0.0036 [0.0008, 0.0096] | 0.0573 [0.0386, 0.1462] | ok |
| fpr_0.05 | 0.6491 | val_raw_score | 0.0500 | balanced | 0.9941 [0.9862, 0.9984] | 0.6095 [0.4653, 0.7019] | 0.0036 [0.0008, 0.0096] | 0.7557 [0.6347, 0.8210] | ok |
| fpr_0.01 | null | val_raw_score | 0.0100 | - | - | - | - | - | ok; no_threshold_meets_target |

## Plots

- ![roc.png](roc.png)
- ![pr.png](pr.png)
- confusion.png not produced: omitted (counts are in metrics.json operating_points)
- reliability.png not produced: scores_not_probabilities

## Warnings

- unachievable: operating point fpr_0.01 has no threshold (no_threshold_meets_target)

## Limitations

- Student overlap: the split unit is the block (course letter + Zx), not the student, so the same student can appear in train, val and test. Per-student style can leak across splits; treat results as optimistic for unseen students.
