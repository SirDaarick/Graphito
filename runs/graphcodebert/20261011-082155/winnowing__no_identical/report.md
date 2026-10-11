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
| roc_auc | 0.9738 | [0.9659, 0.9820] | 1846058 | 338 | 1845720 |  |
| pr_auc | 0.0437 | [0.0205, 0.2686] | 1846058 | 338 | 1845720 |  |
| ece | 0.1731 | [0.1413, 0.2208] | 1846058 | 338 | 1845720 |  |
| map_at_r | 0.5569 | [0.4206, 0.6941] |  |  |  |  |

## Operating points

| Point | Threshold | Source | Target FPR | View | Precision | Recall | FPR | F1 | Support |
|---|---|---|---|---|---|---|---|---|---|
| fpr_0.05 | 0.6223 | val_raw_score | 0.0500 | observed | 0.0274 [0.0183, 0.0791] | 0.6065 [0.4444, 0.7095] | 0.0039 [0.0008, 0.0110] | 0.0524 [0.0356, 0.1371] | ok |
| fpr_0.05 | 0.6223 | val_raw_score | 0.0500 | balanced | 0.9935 [0.9844, 0.9983] | 0.6065 [0.4444, 0.7095] | 0.0039 [0.0008, 0.0110] | 0.7532 [0.6150, 0.8256] | ok |
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
