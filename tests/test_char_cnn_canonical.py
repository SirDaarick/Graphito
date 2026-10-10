"""CharCNN canonical whitespace mode, checkpoint mode persistence and manifest path rebasing."""

import json
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from models.char_cnn.config import CharCNNConfig
from models.char_cnn.dataset import CharCNNDataset, rebase_path
from models.char_cnn.preprocess import CharPreprocessor

COMPACT = '#include <stdio.h>\nint main(){int a,b;scanf("%d %d",&a,&b);\nif(a>b){printf("x");}\nreturn 0;}\n'
FORMATTED = """#include <stdio.h>

int main() {
    int a, b;
    scanf("%d %d", &a, &b);  // read input

    if (a > b) {
        printf("x");
    }
    return 0;
}
"""


def _pre(mode: str) -> CharPreprocessor:
    return CharPreprocessor(CharCNNConfig(whitespace_mode=mode))


def test_canonical_is_invariant_to_formatting_and_comments():
    pre = _pre("canonical")
    assert pre.normalize(COMPACT) == pre.normalize(FORMATTED)


def test_canonical_keeps_space_between_identifiers_and_literals_verbatim():
    out = _pre("canonical").normalize('int  a = 1;\nchar *s = "a  b";\nchar t = \'\\t\';  /* c */\n')
    assert out == 'int a=1;char*s="a  b";char t=\'\\t\';'


def test_trim_mode_is_unchanged_default():
    assert CharCNNConfig().whitespace_mode == "trim"
    out = _pre("trim").normalize("int a;   \n\n\n\nint b; // c\n")
    assert out == "int a;\n\nint b;\n"


def test_unknown_whitespace_mode_is_rejected():
    with pytest.raises(ValueError):
        CharPreprocessor(CharCNNConfig(whitespace_mode="bogus"))


def _fake_checkpoint(path: Path, extra: dict) -> None:
    from models.char_cnn.model import CharCNN

    config = CharCNNConfig()
    config.vocab_size = CharPreprocessor(config).vocab_size
    model = CharCNN(config)
    torch.save(
        {"model_state_dict": model.state_dict(),
         "config": {"alphabet": config.alphabet, "seq_length": config.seq_length, **extra}},
        path,
    )


def test_checkpoint_without_mode_loads_as_trim(tmp_path):
    from models.char_cnn.inference import CharCNNInference

    ckpt = tmp_path / "old.pth"
    _fake_checkpoint(ckpt, {})
    engine = CharCNNInference(ckpt, device=torch.device("cpu"))
    assert engine.preprocessor.config.whitespace_mode == "trim"


def test_checkpoint_mode_is_restored(tmp_path):
    from models.char_cnn.inference import CharCNNInference

    ckpt = tmp_path / "canon.pth"
    _fake_checkpoint(ckpt, {"whitespace_mode": "canonical"})
    engine = CharCNNInference(ckpt, device=torch.device("cpu"))
    assert engine.preprocessor.config.whitespace_mode == "canonical"


def test_rebase_maps_foreign_absolute_path_onto_local_data(tmp_path):
    local = tmp_path / "data" / "raw" / "src" / "A2016" / "Z1" / "Z1" / "s.c"
    local.parent.mkdir(parents=True)
    local.write_text("int a;", encoding="utf-8")
    foreign = "/home/x/Proyectos/Graphito/data/raw/src/A2016/Z1/Z1/s.c"
    assert rebase_path(foreign, tmp_path / "data") == local


def test_from_manifest_raises_when_files_are_missing(tmp_path):
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"splits": {"train": [
        {"file_path": "/home/x/Graphito/data/output/A/Z1/Z1/missing.c", "label": 1}
    ]}}), encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        CharCNNDataset.from_manifest(manifest, _pre("trim"), "train", data_root=tmp_path / "data")
