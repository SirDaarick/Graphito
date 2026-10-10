# Golden set

Benchmark corpus for `scripts/benchmark_suite.py`, rebuilt from the shared split manifest
(`data/splits/split_v1.json`, written by `scripts/build_split.py`).

## Why it was rebuilt (leakage in the previous version)

The previous golden set was assembled straight from `data/raw/src` and `data/output` and split
by `sha256(seed:problem_id)` per problem. It shared no split with model training: **1825 of its
2621 samples were CharCNN train/val samples**, so its metrics measured memorization as much as
generalization. Those manifests and every result computed from them are legacy and not
comparable with new runs.

## Provenance

The golden set is now built only from entries of one split of the split manifest:

| Corpus | Split | Use |
|---|---|---|
| `corpus/` | `test` | Benchmark (reported metrics) |
| `corpus_val/` | `val` | Only to fit calibration (`calibration_<channel>.json`); never reported as a result |

Train is refused. Excluded entries (`broken`, `cross_split_dup`) are never copied. Labels come
from the manifest `gt_status`; the ground truth is not re-parsed:

| class | source | role | label_copy | label_ai |
|---|---|---|---|---|
| `reference` | one honest human per problem (`negative`), held out | reference | false | false |
| `original` | other honest humans (`negative`) | submission | false | false |
| `copy` | humans in a static ground-truth cluster (`positive`) | submission | true | false |
| `ai` | every AI entry of the problem | submission | false | true |

Humans labelled `ambiguous` (dynamic/full ground truth only) or `unlabeled` (courses without
ground truth, e.g. B2017) are skipped. Problems without AI files or labelled humans are skipped.
Human classes are capped per problem with a seeded per-problem RNG (deterministic for a seed).

`<corpus>/provenance.json` maps every corpus file to its split id, split, class, model, profile,
dup_group, cluster and gt_status, and records `source_manifest_sha256` (the sha256 of the split
manifest file). The golden manifests carry the same hash.

## Build

```bash
python scripts/build_split.py                                       # data/splits/split_v1.json
python data/golden_set/build_corpus.py --split test --force         # -> data/golden_set/corpus
python data/golden_set/build_corpus.py --split val --force          # -> data/golden_set/corpus_val
python data/golden_set/build_manifest.py data/golden_set/corpus --out data/golden_set/manifest.json
python data/golden_set/build_manifest.py data/golden_set/corpus_val --out data/golden_set/manifest_val.json
```

`build_corpus.py` flags: `--split-manifest PATH` (default `data/splits/split_v1.json`),
`--split test|val`, `--repo-root PATH` (base of the manifest ids), `--out`, `--seed`, `--cap`,
`--expected-sha256`, `--force`.

`build_manifest.py` reads `provenance.json`: every corpus file must be listed there, a `train`
entry raises naming its id, and members of one `dup_group` are deduplicated (the first path in
sorted order is kept). The output has no wall-clock field, so rebuilding gives byte-identical
manifests. A corpus without provenance (a hand-written fixture) needs `--synthetic` and is
tagged `test`; there, byte-identical files of the same problem and class are deduplicated by
content sha256 instead (the first path in scan order is kept). Identical files in different
problems or classes are all kept: an exact copy of its original is a labelled positive.
`build_corpus.py` refuses manifest ids that resolve outside
`--repo-root`.

## Perturbed corpora (robustness check)

```bash
python data/golden_set/perturb_corpus.py --transform strip-comments \
    --split-manifest data/splits/split_v1.json --split test
```

The transform is applied to every class, `provenance.json` is copied, and `--split-manifest`
restricts the output to problems of that split (test or val; never train). With that filter the
copied provenance keeps only the selected problems' files and recounts `problems` and the
per-class totals from them.

## Run the benchmark

See `scripts/benchmark_suite.py --help` and the root `README.md`. `--engine stub` is only a
smoke test of the pipeline. Results on `tests/fixtures/golden_set_tiny/` or on the synthetic
factory tree are NOT evidence about the real models.
