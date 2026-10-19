"""Redraw the ROC/PR curves of an existing evaluation run, optionally with Spanish labels.

Reads only the run's ``roc.csv``, ``pr.csv`` and ``metrics.json``; no model is loaded and no
metric is recomputed. Example (thesis figures)::

    python scripts/replot_run_curves.py --run-dir runs/char_cnn/20261011-015734 \
        --out-dir Documentacion/Documento/figuras --prefix charcnn_v2_ --lang es
"""

import argparse
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from models.evaluation.report import CURVE_LABELS, replot_curves  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-dir", type=Path, required=True, help="runs/<channel>/<run> directory")
    parser.add_argument("--out-dir", type=Path, required=True, help="output directory for the PNGs")
    parser.add_argument("--prefix", default="", help="file name prefix, e.g. charcnn_v2_")
    parser.add_argument("--lang", default="en", choices=sorted(CURVE_LABELS), help="label language")
    args = parser.parse_args(argv)
    for path in replot_curves(args.run_dir, args.out_dir, lang=args.lang, prefix=args.prefix):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
