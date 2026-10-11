"""Backend Channel A Jaccard equals the SDD-3 evaluation Jaccard (spec AS2.1 parity; design testing).

The calibration in `models/deploy/channel_a/` was fitted on `SetSimilarity(jaccard_set(...))`
scores; the backend must compute the very same number. Skipped when the evaluation modules (which
pull in torch/scipy) cannot be imported.
"""

import pytest

from app.infrastructure.artifacts.models_path import ensure_on_path
from app.infrastructure.lexical.jaccard import JaccardSimilarity

ensure_on_path()
baselines = pytest.importorskip("models.graphcodebert.v2.baselines", reason="SDD-3 evaluation modules unavailable")
from models.evaluation.dedup import jaccard  # noqa: E402

PAIRS = [
    ("int main(){int a=1;return a;}", "int main(){int b=1;return b;}"),
    (
        "#include <stdio.h>\nint main(void){int n;scanf(\"%d\",&n);for(int i=0;i<n;i++)printf(\"%d\\n\",i);return 0;}",
        "#include <stdio.h>\n// otro\nint main(void){int k;scanf(\"%d\",&k);int i=0;while(i<k){printf(\"%d\\n\",i);i++;}return 0;}",
    ),
    ("x", "int main(void) { return 0; }"),
    ("int f(int x){return x*x;}", "double g(double y){return y+y;}"),
]


@pytest.mark.parametrize("a,b", PAIRS)
def test_backend_jaccard_equals_eval_jaccard(a, b):
    backend = JaccardSimilarity().similarity(a, b)
    expected = jaccard(baselines.jaccard_set(a), baselines.jaccard_set(b))
    block = baselines.SetSimilarity([baselines.jaccard_set(a), baselines.jaccard_set(b)])(0, 2)[0, 1]
    assert backend == pytest.approx(expected, abs=1e-12)
    assert backend == pytest.approx(block, abs=1e-12)


def test_empty_submission_stream_is_none():
    assert JaccardSimilarity().similarity("   ", "int main(void) { return 0; }") is None
