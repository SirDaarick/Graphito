"""R4: the CharCNN length guard counts effective (non-comment, non-whitespace) characters."""

from pathlib import Path

import pytest

from models.char_cnn.preprocess import MIN_NON_WS_CHARS, CharPreprocessor

pp = CharPreprocessor()


def test_threshold_constant():
    assert MIN_NON_WS_CHARS == 60


def test_all_comment_file_is_insufficient():
    text = "// " + "x" * 497 + "\n"
    assert len(text) >= 500
    assert pp.effective_length(text) < MIN_NON_WS_CHARS


def test_short_code_with_big_comment_block_is_insufficient():
    code = "int main(){int a=1;return a;}"  # 29 non-ws chars
    text = code + "\n/* " + "padding " * 40 + "*/\n"
    assert pp.effective_length(text) < MIN_NON_WS_CHARS


def test_long_code_with_trailing_comment_is_sufficient():
    code = "int main(){int a=1;int b=2;int c=a+b;printf(\"%d\",c);int d=c*2;return d;}"
    assert len(code) >= 70
    text = code + " // trailing comment"
    assert pp.effective_length(text) >= MIN_NON_WS_CHARS


def test_comment_marker_inside_string_literal_is_counted():
    text = 'printf("// not a comment");'
    assert pp.effective_length(text) == len("".join(text.split()))


def test_block_comment_marker_inside_string_is_preserved():
    text = 'char *s = "/* keep */";'
    assert pp.effective_length(text) == len("".join(text.split()))


@pytest.mark.requires_charcnn_weights
def test_predict_text_flags_comment_only_file():
    pytest.importorskip("torch")
    from models.char_cnn.inference import CharCNNInference

    engine = CharCNNInference(Path("models/char_cnn/best_model.pth"))
    res = engine.predict_text("// " + "x" * 497 + "\n")
    assert res["insufficient_length"] is True
    assert res["ai_probability"] == 0.05
