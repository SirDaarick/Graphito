"""CharCNN inference facade: legacy golden snapshot and version-dispatch contract (CPU only).

The golden values in `fixtures/charcnn_legacy_golden.json` were captured with the pre-change
facade. The seeded v1 fixture checkpoint (weights drawn with numpy's legacy `RandomState`, so
they do not depend on torch's init) is the always-running guard; the real `best_model.pth`
cases only run when the checkpoint on disk has the sha256 they were captured with.
"""

import hashlib
import json
import warnings
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


NEW_KEYS = ("score", "abstained", "n_windows", "preproc_version", "arch_version")
PROB_KEYS = ("confidence", "prob_humano", "prob_sintetico", "ai_probability")

# Non-default v2 architecture, so rebuilding from the checkpoint config is actually exercised.
TINY_V2 = dict(
    embedding_dim=8,
    conv_kernel_sizes=(3, 7),
    conv_filters=(5, 3),
    fc_units=16,
    dropout=0.2,
    window=64,
    stride=32,
    max_windows=4,
)


def make_v2_checkpoint(path: Path, seed: int = 5, **config_overrides):
    """Write a v2-format checkpoint (primitives only) and return (path, source model)."""
    from models.char_cnn.v2.config import CharCNNV2Config
    from models.char_cnn.v2.model import CharCNNV2

    cfg = CharCNNV2Config(**TINY_V2)
    torch.manual_seed(seed)
    model = CharCNNV2(cfg).eval()
    config = {**cfg.to_dict(), "seed": seed, "run_id": "fixture", **config_overrides}
    torch.save(
        {"format": "graphito.charcnn_checkpoint/v2", "model_state_dict": model.state_dict(), "config": config},
        path,
    )
    return path, model


def _engine(path: Path, **kwargs):
    from models.char_cnn.inference import CharCNNInference

    return CharCNNInference(path, device=torch.device("cpu"), **kwargs)


def assert_contract(result: dict, *, embedding_dim: int) -> None:
    for key in LEGACY_KEYS + NEW_KEYS:
        assert key in result, key
    for key in PROB_KEYS:
        assert type(result[key]) is float, key
        assert 0.0 <= result[key] <= 1.0, key
    assert isinstance(result["embedding"], list)
    assert len(result["embedding"]) == embedding_dim
    assert all(type(x) is float for x in result["embedding"])
    assert type(result["class_id"]) is int
    assert type(result["n_windows"]) is int
    assert result["abstained"] is result["insufficient_length"]
    json.dumps(result)  # backend/API contract: JSON-serializable


LONG_TEXT = SNIPPETS["long_program"]


class TestLegacyContract:
    def test_legacy_checkpoint_adds_new_keys(self, in_tmp):
        engine = _engine(make_v1_checkpoint(in_tmp / "v1.pth", 11, {}))
        res = engine.predict_text(SNIPPETS["c_program"])
        assert_contract(res, embedding_dim=1024)
        assert (res["arch_version"], res["preproc_version"], res["n_windows"]) == (1, 1, 1)
        assert res["abstained"] is False
        assert res["score"] == res["prob_sintetico"] == res["ai_probability"]

    def test_legacy_abstention_keeps_placeholders(self, in_tmp):
        engine = _engine(make_v1_checkpoint(in_tmp / "v1.pth", 11, {}))
        res = engine.predict_text("int x;")
        assert_contract(res, embedding_dim=1024)
        assert res["abstained"] is True and res["insufficient_length"] is True
        assert res["score"] is None
        assert (res["prob_humano"], res["prob_sintetico"], res["ai_probability"]) == (0.95, 0.05, 0.05)
        assert (res["arch_version"], res["preproc_version"], res["n_windows"]) == (1, 1, 1)

    def test_absent_preproc_version_selects_v1(self, in_tmp):
        from models.char_cnn.preprocess import CharPreprocessor

        engine = _engine(make_v1_checkpoint(in_tmp / "v1.pth", 11, {}))
        assert isinstance(engine.preprocessor, CharPreprocessor)
        assert (engine.arch_version, engine.preproc_version) == (1, 1)

    def test_explicit_v1_versions_are_legacy(self, in_tmp):
        engine = _engine(make_v1_checkpoint(in_tmp / "v1.pth", 11, {"arch_version": 1, "preproc_version": 1}))
        assert (engine.arch_version, engine.preproc_version) == (1, 1)

    def test_legacy_checkpoint_with_non_tensor_payload_still_loads(self, in_tmp):
        path = make_v1_checkpoint(in_tmp / "v1.pth", 11, {})
        ckpt = torch.load(path, weights_only=True)
        ckpt["metrics"] = np.float64(0.5)  # legacy trainers pickled numpy scalars
        torch.save(ckpt, path)
        with pytest.warns(UserWarning, match="weights_only"):
            engine = _engine(path)
        expected = GOLDEN["fixture_cases"][0]["result"]
        assert_matches(engine.predict_text(SNIPPETS["c_program"]), expected)

    @pytest.mark.requires_charcnn_weights
    def test_real_checkpoint_loads_as_legacy(self, in_tmp):
        res = _engine(REAL_CHECKPOINT).predict_text(SNIPPETS["c_program"])
        assert_contract(res, embedding_dim=1024)
        assert (res["arch_version"], res["preproc_version"], res["n_windows"]) == (1, 1, 1)


class TestV2Contract:
    def _expected(self, model, text):
        from models.char_cnn.v2.preprocess import encode, preprocess_v2
        from models.char_cnn.v2.scoring import window_starts

        arr = encode(preprocess_v2(text))
        starts = window_starts(len(arr), model.config)
        with torch.no_grad():
            windows = [
                model(torch.from_numpy(arr[s : s + model.config.window]).long().unsqueeze(0)).double()
                for s in starts
            ]
        logits = torch.cat(windows).mean(dim=0)
        return torch.softmax(logits, dim=0), len(starts)

    def test_rebuilds_model_from_checkpoint_config(self, tmp_path):
        from models.char_cnn.v2.config import CharCNNV2Config

        path, source = make_v2_checkpoint(tmp_path / "v2.pth")
        engine = _engine(path)
        assert engine.config == CharCNNV2Config(**TINY_V2)
        assert (engine.arch_version, engine.preproc_version) == (2, 2)
        x = torch.randint(2, 98, (3, 50), generator=torch.Generator().manual_seed(0))
        with torch.no_grad():
            torch.testing.assert_close(engine.model(x), source(x), atol=1e-6, rtol=0)

    def test_normal_input_contract(self, tmp_path):
        path, source = make_v2_checkpoint(tmp_path / "v2.pth")
        res = _engine(path).predict_text(LONG_TEXT)
        assert_contract(res, embedding_dim=TINY_V2["fc_units"])
        probs, n_windows = self._expected(source, LONG_TEXT)
        assert n_windows > 1
        assert res["n_windows"] == n_windows
        assert res["prob_sintetico"] == pytest.approx(probs[1].item(), abs=1e-6)
        assert res["prob_humano"] == pytest.approx(probs[0].item(), abs=1e-6)
        assert res["class_id"] == int(probs.argmax())
        assert res["prediction"] == {0: "humano", 1: "sint\u00e9tico"}[res["class_id"]]
        assert res["confidence"] == pytest.approx(probs.max().item(), abs=1e-6)
        assert res["score"] == res["ai_probability"] == res["prob_sintetico"]
        assert res["abstained"] is False and res["insufficient_length"] is False
        assert (res["arch_version"], res["preproc_version"]) == (2, 2)

    def test_pad_argument_is_ignored(self, tmp_path):
        engine = _engine(make_v2_checkpoint(tmp_path / "v2.pth")[0])
        assert engine.predict_text(LONG_TEXT, pad=True) == engine.predict_text(LONG_TEXT)

    def test_short_input_abstains(self, tmp_path):
        res = _engine(make_v2_checkpoint(tmp_path / "v2.pth")[0]).predict_text("int x;")
        assert_contract(res, embedding_dim=TINY_V2["fc_units"])
        assert res["abstained"] is True and res["insufficient_length"] is True
        assert res["score"] is None
        assert (res["prediction"], res["class_id"], res["confidence"]) == ("humano", 0, 0.95)
        assert (res["prob_humano"], res["prob_sintetico"], res["ai_probability"]) == (0.95, 0.05, 0.05)
        assert res["n_windows"] == 1
        assert any(x != 0.0 for x in res["embedding"])

    def test_empty_normalized_input_abstains_with_zero_embedding(self, tmp_path):
        res = _engine(make_v2_checkpoint(tmp_path / "v2.pth")[0]).predict_text("  // only a comment\n\t\n")
        assert_contract(res, embedding_dim=TINY_V2["fc_units"])
        assert res["abstained"] is True and res["score"] is None
        assert res["n_windows"] == 0
        assert res["embedding"] == [0.0] * TINY_V2["fc_units"]

    def test_predict_file(self, tmp_path):
        engine = _engine(make_v2_checkpoint(tmp_path / "v2.pth")[0])
        src = tmp_path / "a.c"
        src.write_bytes(LONG_TEXT.encode("utf-8"))
        res = engine.predict(src)
        assert res["file"] == str(src)
        assert res["prob_sintetico"] == engine.predict_text(LONG_TEXT)["prob_sintetico"]

    def test_config_argument_is_ignored_with_warning(self, tmp_path):
        from models.char_cnn.v2.config import CharCNNV2Config

        path, _ = make_v2_checkpoint(tmp_path / "v2.pth")
        with pytest.warns(UserWarning, match="ignored"):
            engine = _engine(path, config=CharCNNV2Config())
        assert engine.config == CharCNNV2Config(**TINY_V2)

    def test_no_warning_without_config_argument(self, tmp_path):
        path, _ = make_v2_checkpoint(tmp_path / "v2.pth")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            _engine(path)

    def test_v2_checkpoint_must_be_weights_only(self, tmp_path):
        path, _ = make_v2_checkpoint(tmp_path / "v2.pth", extra=np.float64(1.0))
        with pytest.raises(ValueError, match="weights_only"):
            _engine(path)


class TestVersionDispatch:
    @pytest.mark.parametrize(
        "arch,preproc",
        [(3, 3), (2, 1), (1, 2), (None, 2), (2, None), (3, None), ("2", "2")],
    )
    def test_unsupported_versions_raise(self, tmp_path, arch, preproc):
        overrides = {"arch_version": arch, "preproc_version": preproc}
        path, _ = make_v2_checkpoint(tmp_path / "bad.pth")
        ckpt = torch.load(path, weights_only=True)
        for key, value in overrides.items():
            if value is None:
                ckpt["config"].pop(key)
            else:
                ckpt["config"][key] = value
        torch.save(ckpt, path)
        with pytest.raises(ValueError, match="version"):
            _engine(path)

    @pytest.mark.parametrize(
        "config,expected",
        [
            ({}, (1, 1)),
            ({"alphabet": "abc"}, (1, 1)),
            ({"arch_version": 1, "preproc_version": 1}, (1, 1)),
            ({"arch_version": 2, "preproc_version": 2}, (2, 2)),
        ],
    )
    def test_checkpoint_versions(self, config, expected):
        from models.char_cnn.v2.checkpoint import checkpoint_versions

        assert checkpoint_versions(config) == expected

    def test_make_checkpoint_round_trip(self, tmp_path):
        from models.char_cnn.v2.checkpoint import CHECKPOINT_FORMAT, load_checkpoint, make_checkpoint, load_v2_model
        from models.char_cnn.v2.config import CharCNNV2Config
        from models.char_cnn.v2.model import CharCNNV2

        torch.manual_seed(0)
        model = CharCNNV2(CharCNNV2Config(**TINY_V2)).eval()
        ckpt = make_checkpoint(model, seed=3, run_id="r1", epoch=2)
        assert ckpt["format"] == CHECKPOINT_FORMAT
        assert ckpt["config"]["seed"] == 3 and ckpt["config"]["arch_version"] == 2
        torch.save(ckpt, tmp_path / "best.pth")
        loaded = torch.load(tmp_path / "best.pth", weights_only=True)
        assert load_checkpoint(tmp_path / "best.pth")["config"] == loaded["config"]
        rebuilt = load_v2_model(loaded, "cpu")
        x = torch.randint(2, 98, (2, 40), generator=torch.Generator().manual_seed(1))
        with torch.no_grad():
            torch.testing.assert_close(rebuilt(x), model(x), atol=1e-6, rtol=0)
