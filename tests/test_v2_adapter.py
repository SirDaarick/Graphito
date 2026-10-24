"""`models.graphcodebert.v2.adapter`: adapter identity, file-embedder cache key and merged-model loading."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from models.graphcodebert.v2 import adapter as ad


def _fake_adapter(tmp_path: Path, name: str = "adapter", weights: bytes = b"weights", config: str = '{"r": 16}') -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / "adapter_model.safetensors").write_bytes(weights)
    (d / "adapter_config.json").write_text(config, encoding="utf-8")
    return d


def test_adapter_sha256_depends_on_weights_and_config(tmp_path):
    base = ad.adapter_sha256(_fake_adapter(tmp_path))
    assert len(base) == 64
    assert base == ad.adapter_sha256(_fake_adapter(tmp_path, name="copy"))  # same content, same identity
    assert base != ad.adapter_sha256(_fake_adapter(tmp_path, name="w", weights=b"different"))
    assert base != ad.adapter_sha256(_fake_adapter(tmp_path, name="c", config='{"r": 8}'))


def test_adapter_sha256_is_stable_hex(tmp_path):
    d = _fake_adapter(tmp_path)
    expected = hashlib.sha256()
    for name in ("adapter_config.json", "adapter_model.safetensors"):
        expected.update(name.encode())
        expected.update((d / name).read_bytes())
    assert ad.adapter_sha256(d) == expected.hexdigest()


def test_adapter_sha256_requires_the_weights_file(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    with pytest.raises(FileNotFoundError):
        ad.adapter_sha256(d)


def test_parse_adapter_specs_validates_names_and_paths(tmp_path):
    d = _fake_adapter(tmp_path)
    assert ad.parse_adapter_specs([f"ft_B_s1={d}"]) == {"ft_B_s1": d}
    with pytest.raises(ValueError):
        ad.parse_adapter_specs([f"B_s1={d}"])  # name must start with ft_
    with pytest.raises(ValueError):
        ad.parse_adapter_specs(["ft_x"])  # missing =PATH
    with pytest.raises(ValueError):
        ad.parse_adapter_specs([f"ft_a={d}", f"ft_a={d}"])  # duplicated name


def test_file_embedder_key_fields_change_with_the_adapter():
    class Cfg:
        def to_dict(self):
            return {"code_length": 384, "pooling": "mean", "use_dfg": True}

    class Emb:
        config = Cfg()
        model_revision = "rev"

    one = ad.AdapterFileEmbedder(Emb(), adapter_sha="a" * 64).key_fields()
    two = ad.AdapterFileEmbedder(Emb(), adapter_sha="b" * 64).key_fields()
    assert one != two
    assert one["adapter_sha256"] == "a" * 64
    assert json.dumps(one, sort_keys=True)  # JSON-friendly for the cache key


def test_prefix_helper():
    assert ad.is_adapter_method("ft_B_s1") and not ad.is_adapter_method("v2_norm")


def test_adapter_methods_get_canonicalized_texts_like_v2_norm():
    from models.robustness.scoring import texts_for_method

    code = "int suma(int a, int b) { return a + b; }\nint main() { return suma(1, 2); }\n"
    renamed = code.replace("suma", "mezcla").replace("a +", "x +").replace("int a", "int x")
    raw, _ = texts_for_method("v2", [code], [renamed], ["cpp"])
    assert raw == [code]  # v2 gets the text unchanged
    for method in ("v2_norm", "ft_B_s1"):
        orig, trans = texts_for_method(method, [code], [renamed], ["cpp"])
        assert orig == trans != [code]


@pytest.mark.skipif(not Path(r"C:\Users\edani\datasets\codenet\f3\B_s1\adapter\adapter_model.safetensors").exists(), reason="trained adapter not on this machine")
def test_merged_adapter_embedding_matches_the_training_path():
    """Embedding a CodeNet val program through the windowed v2 embedder (what E1/E2/robustness use)
    equals the single-window cached features the adapter was trained and validated on."""
    import pickle

    import torch

    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import contrastive_f1 as f1

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    adapter_dir = Path(r"C:\Users\edani\datasets\codenet\f3\B_s1\adapter")
    rows = pickle.loads(Path(r"C:\Users\edani\datasets\codenet\f0\cache_val.pkl").read_bytes())[:6]
    embedder = ad.build_embedder(adapter_dir, device=device)
    roberta = embedder.encoder.roberta
    via_cache = f1.embed_rows(roberta, rows, device)
    codenet = Path(r"C:\Users\edani\datasets\codenet")
    manifest = [json.loads(line) for line in (codenet / "f0" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    by_id = {(m["problem"], m["submission_id"]): m for m in manifest}
    from models.logic_eval.canonical import canonicalize_code

    cos = []
    for r, v in zip(rows, via_cache):
        code = (codenet / by_id[(r["problem"], r["submission_id"])]["path"]).read_text(encoding="utf-8", errors="replace")
        res = embedder.embed(canonicalize_code(code, "cpp"), "cpp")
        assert res.success and res.n_windows == 1
        m = np.asarray(res.mean, dtype=np.float64)
        cos.append(float(m @ v / (np.linalg.norm(m) * np.linalg.norm(v))))
    assert min(cos) > 0.9999
