"""CharCNN inference facade: legacy golden snapshot (CPU only).

The golden values in `fixtures/charcnn_legacy_golden.json` were captured with the pre-change
facade. The seeded v1 fixture checkpoint (weights drawn with numpy's legacy `RandomState`, so
they do not depend on torch's init) is the always-running guard; the real `best_model.pth`
cases only run when the checkpoint on disk has the sha256 they were captured with.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN_PATH = FIXTURES / "charcnn_legacy_golden.json"
REAL_CHECKPOINT = ROOT / "models" / "char_cnn" / "best_model.pth"
TOL = 1e-6

LEGACY_KEYS = (
    "prediction",
    "class_id",
    "confidence",
    "prob_humano",
    "prob_sintetico",
    "ai_probability",
    "embedding",
    "insufficient_length",
)

# Inputs (non-ASCII written as escapes). `crlf_tabs_diacritics` covers CRLF, tabs and Bosnian text.
SNIPPETS = {
    "c_program": (
        "#include <stdio.h>\n\n"
        "int main() {\n"
        "    int n, i, sum = 0;\n"
        "    scanf(\"%d\", &n);  // read n\n"
        "    for (i = 1; i <= n; i++) {\n"
        "        sum += i * i;\n"
        "    }\n"
        "    printf(\"%d\\n\", sum);\n"
        "    return 0;\n"
        "}\n"
    ),
    "crlf_tabs_diacritics": (
        "/* Zadaća 2, Zadatak 1 */\r\n"
        "#include <iostream>\r\n"
        "using namespace std;\r\n"
        "int main() {\r\n"
        "\tint a, b;\r\n"
        "\tcout << \"Unesite članove niza (šđž): \";\r\n"
        "\tcin >> a >> b;\r\n"
        "\tif (a > b)\tcout << a - b << endl;\r\n"
        "\telse\t\tcout << b - a << endl;\r\n"
        "\treturn 0;\r\n"
        "}\r\n"
    ),
    "short": "int x;",
    "long_program": "#include <stdio.h>\nint main(void) {\n"
    + "".join(f"    int v{k} = {k} * {k + 3} % 7; printf(\"%d\\n\", v{k});\n" for k in range(40))
    + "    return 0;\n}\n",
}

PREPROCESS_INPUTS = {
    "crlf": "int a;\r\nint b;   \r\n\r\n\r\n\r\nint c; // x\r\n",
    "tabs": "int main() {\n\tint  a\t= 1;\n\t\treturn a;\t\n}\n",
    "diacritics": "printf(\"Zadaća šđčž áñ\"); /* Đ */\n",
}

# Seeded random v1 fixture checkpoints: (name, numpy seed, extra checkpoint config).
FIXTURE_CHECKPOINTS = {
    "trim_default": (11, {}),
    "canonical_512": (12, {"whitespace_mode": "canonical", "seq_length": 512}),
}
FIXTURE_CASES = [
    ("trim_default", "c_program", False),
    ("trim_default", "crlf_tabs_diacritics", False),
    ("trim_default", "short", False),
    ("trim_default", "c_program", True),
    ("canonical_512", "c_program", False),
    ("canonical_512", "crlf_tabs_diacritics", False),
    ("canonical_512", "long_program", False),
]
REAL_CASES = ["c_program", "crlf_tabs_diacritics", "short"]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_v1_checkpoint(path: Path, seed: int, extra_config: dict) -> Path:
    """Write a legacy-format checkpoint (no version fields) with seeded random v1 weights.

    The legacy `CharCNNConfig` creates `weights/` and `logs/` relative to cwd, so callers run
    this from a temporary directory.
    """
    from models.char_cnn.config import CharCNNConfig
    from models.char_cnn.model import CharCNN
    from models.char_cnn.preprocess import CharPreprocessor

    config = CharCNNConfig()
    config.vocab_size = CharPreprocessor(config).vocab_size
    rs = np.random.RandomState(seed)
    state = {}
    for name, tensor in CharCNN(config).state_dict().items():
        if name.endswith("num_batches_tracked"):
            state[name] = torch.tensor(100, dtype=torch.long)
            continue
        arr = rs.standard_normal(tuple(tensor.shape))
        if name.endswith("running_var"):
            arr = 0.5 + 0.5 * np.abs(arr)
        elif name.endswith("running_mean"):
            arr = 0.1 * arr
        elif name == "embedding.weight":
            pass
        elif arr.ndim >= 2:
            arr = arr / np.sqrt(np.prod(arr.shape[1:]))
        elif name.endswith("weight"):  # BatchNorm affine weight
            arr = 1.0 + 0.1 * arr
        else:
            arr = 0.1 * arr
        state[name] = torch.from_numpy(arr.astype(np.float32))
    torch.save(
        {
            "model_state_dict": state,
            "config": {"alphabet": config.alphabet, "seq_length": config.seq_length, **extra_config},
        },
        path,
    )
    return path


def run_case(engine, text: str, pad: bool) -> dict:
    return engine.predict_text(text, pad=pad)


def snapshot(result: dict) -> dict:
    """The recorded part of a legacy `predict_text` result."""
    out = {k: result[k] for k in LEGACY_KEYS}
    out["embedding"] = [float(x) for x in result["embedding"]]
    return out


def assert_matches(result: dict, expected: dict) -> None:
    for key in ("prediction", "class_id", "insufficient_length"):
        assert result[key] == expected[key], key
    for key in ("confidence", "prob_humano", "prob_sintetico", "ai_probability"):
        assert isinstance(result[key], float), key
        assert result[key] == pytest.approx(expected[key], abs=TOL), key
    np.testing.assert_allclose(
        np.asarray(result["embedding"], dtype=np.float64), expected["embedding"], rtol=TOL, atol=TOL
    )


def _load_golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


GOLDEN = _load_golden() if GOLDEN_PATH.exists() else None


@pytest.fixture
def in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestLegacyGolden:
    def test_golden_file_matches_inputs(self):
        assert GOLDEN is not None, f"missing {GOLDEN_PATH}"
        assert GOLDEN["snippets"] == SNIPPETS
        assert GOLDEN["preprocess_inputs"] == PREPROCESS_INPUTS
        assert [c["case"] for c in GOLDEN["fixture_cases"]] == [
            f"{ck}/{name}/pad={pad}" for ck, name, pad in FIXTURE_CASES
        ]

    @pytest.mark.parametrize("mode", ["trim", "canonical"])
    @pytest.mark.parametrize("name", sorted(PREPROCESS_INPUTS))
    def test_v1_preprocess_and_encode_table(self, in_tmp, mode, name):
        from models.char_cnn.config import CharCNNConfig
        from models.char_cnn.preprocess import CharPreprocessor

        pre = CharPreprocessor(CharCNNConfig(whitespace_mode=mode))
        text = PREPROCESS_INPUTS[name]
        expected = GOLDEN["preprocess"][mode][name]
        assert pre.normalize(text) == expected["normalized"]
        assert pre.encode(text, pad=False) == expected["encoded"]
        assert pre.effective_length(text) == expected["effective_length"]
        assert pre.vocab_size == GOLDEN["preprocess"]["vocab_size"]

    def test_fixture_checkpoint_matches_golden(self, in_tmp):
        from models.char_cnn.inference import CharCNNInference

        engines = {
            name: CharCNNInference(
                make_v1_checkpoint(in_tmp / f"{name}.pth", seed, extra), device=torch.device("cpu")
            )
            for name, (seed, extra) in FIXTURE_CHECKPOINTS.items()
        }
        for (ck, name, pad), expected in zip(FIXTURE_CASES, GOLDEN["fixture_cases"]):
            assert_matches(run_case(engines[ck], SNIPPETS[name], pad), expected["result"])

    @pytest.mark.requires_charcnn_weights
    def test_real_checkpoint_matches_golden(self, in_tmp):
        recorded = GOLDEN["real_checkpoint"]["sha256"]
        current = sha256_file(REAL_CHECKPOINT)
        if current != recorded:
            pytest.skip(
                f"best_model.pth sha256 {current[:12]} differs from the golden capture "
                f"{recorded[:12]}; real-weight golden cases only apply to that checkpoint"
            )
        from models.char_cnn.inference import CharCNNInference

        engine = CharCNNInference(REAL_CHECKPOINT, device=torch.device("cpu"))
        for name in REAL_CASES:
            assert_matches(run_case(engine, SNIPPETS[name], False), GOLDEN["real_checkpoint"]["cases"][name])
