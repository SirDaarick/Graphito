"""Unit tests for CharCNN v2 config, preprocessing, alphabet and leak guard (synthetic inputs only)."""

import dataclasses
import json

import numpy as np
import pytest

from models.char_cnn.v2 import preprocess as pp
from models.char_cnn.v2.config import (
    ALPHABET,
    ARCH_VERSION,
    PAD_IDX,
    PREPROC_VERSION,
    UNK_IDX,
    VOCAB_SIZE,
    CharCNNV2Config,
)


class TestConfig:
    def test_versions_and_alphabet_layout(self):
        assert PREPROC_VERSION == 2
        assert ARCH_VERSION == 2
        assert len(ALPHABET) == 96
        assert ALPHABET[0] == "\n"
        assert ALPHABET[1:] == "".join(chr(c) for c in range(0x20, 0x7F))
        assert (PAD_IDX, UNK_IDX, VOCAB_SIZE) == (0, 1, 98)

    def test_defaults(self):
        cfg = CharCNNV2Config()
        assert cfg.vocab_size == 98
        assert cfg.embedding_dim == 128
        assert cfg.conv_kernel_sizes == (3, 5, 7, 9)
        assert cfg.conv_filters == (64, 64, 64, 64)
        assert cfg.fc_units == 1024
        assert cfg.num_classes == 2
        assert cfg.dropout == 0.4
        assert (cfg.window, cfg.stride, cfg.max_windows) == (4096, 2048, 8)
        assert cfg.min_non_ws_chars == 60

    def test_construction_is_side_effect_free(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        CharCNNV2Config()
        CharCNNV2Config(embedding_dim=8, conv_kernel_sizes=(3,), conv_filters=(4,), fc_units=16)
        assert list(tmp_path.iterdir()) == []

    def test_frozen(self):
        cfg = CharCNNV2Config()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.window = 10  # type: ignore[misc]

    def test_round_trip_through_json(self):
        cfg = CharCNNV2Config(
            embedding_dim=8,
            conv_kernel_sizes=(3, 5),
            conv_filters=(4, 6),
            fc_units=16,
            dropout=0.1,
            window=256,
            stride=128,
            max_windows=3,
        )
        payload = json.loads(json.dumps(cfg.to_dict()))
        assert CharCNNV2Config.from_dict(payload) == cfg

    def test_to_dict_records_versions_and_alphabet(self):
        d = CharCNNV2Config().to_dict()
        assert d["arch_version"] == 2
        assert d["preproc_version"] == 2
        assert d["alphabet"] == ALPHABET
        assert (d["pad_idx"], d["unk_idx"], d["vocab_size"]) == (0, 1, 98)
        assert d["norm"] == "layernorm_channels"

    def test_from_dict_ignores_run_metadata(self):
        d = CharCNNV2Config().to_dict()
        d.update({"seed": 42, "manifest_sha256": "abc", "epoch": 3})
        assert CharCNNV2Config.from_dict(d) == CharCNNV2Config()

    @pytest.mark.parametrize(
        "key,value",
        [("arch_version", 1), ("preproc_version", 3), ("alphabet", "abc"), ("vocab_size", 99)],
    )
    def test_from_dict_rejects_incompatible_fields(self, key, value):
        d = CharCNNV2Config().to_dict()
        d[key] = value
        with pytest.raises(ValueError, match=key):
            CharCNNV2Config.from_dict(d)

    @pytest.mark.parametrize("key", ["arch_version", "preproc_version", "alphabet"])
    def test_from_dict_requires_version_and_alphabet_fields(self, key):
        d = CharCNNV2Config().to_dict()
        del d[key]
        with pytest.raises(ValueError, match=key):
            CharCNNV2Config.from_dict(d)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"conv_kernel_sizes": (3, 5), "conv_filters": (4,)},
            {"conv_kernel_sizes": (4,), "conv_filters": (4,)},
            {"window": 0},
            {"stride": 0},
            {"max_windows": 0},
            {"window": 8, "stride": 9},
        ],
    )
    def test_invalid_values_raise(self, kwargs):
        with pytest.raises(ValueError):
            CharCNNV2Config(**kwargs)


# Non-ASCII characters are written as escapes to keep the test source ASCII-only.
HEADER_FORMS = [
    "/\x01B\x0216/17 (Zada\u0107a 6, Zadatak 4)",
    "/B2017/2018: Zada\u0107a 4, Zadatak 2",
    "   B16/17 (Tutorijal 13, Zadatak 1)",
]

FIXTURES = [
    "a\r\nb\rc\x01d\x7fe\ufeff",
    "int x = 1'000; // c\r\n\tint  y;\r\n",
    "/*B 2017/2018, Zada\u0107a 2, Zadatak 1\n autotestovi */\n#include <stdio.h>\n",
    "int main() {\n\tprintf(\"Zada\u0107a 5, Zadatak 3\");\n\tputs(\"a    b\");\n}\n",
    "char c = '\"'; int y; // c\n\n\n  return   0;  \n",
    "Zada\u0107a \u0161\u0111 \u201cx\u201d \u2013 y z \u2713 \U0001F600",
    "",
    "   \n\t\n",
]


class TestSteps:
    def test_newlines_controls_and_zero_width(self):
        assert pp.preprocess_v2("a\r\nb\rc\x01d\x7fe\ufeff") == "a\nb\ncde"
        out = pp.preprocess_v2("int a;\r\nint\x0c b;\u200b\r\nint c;")
        for bad in ("\r", "\x0c", "\u200b"):
            assert bad not in out
        assert out == "int a;\nint b;\nint c;"

    def test_clean_controls_keeps_tab_and_lf(self):
        assert pp.clean_controls("x\u200c\u200d\u2060\ufffdy\tz\r\n") == "xy\tz\n"

    def test_cr_only_file_is_not_one_comment(self):
        assert pp.preprocess_v2("int a; // x\rint b;") == "int a;\nint b;"

    def test_fold_unicode(self):
        assert pp.fold_unicode("Zada\u0107a \u0161\u0111 \u201cx\u201d \u2013 y z") == 'Zadaca sd "x" - y z'
        assert pp.fold_unicode("\u0107\u010d\u0161\u0111\u017e\u00e1\u00f1\u0110") == "ccsdzanD"
        assert pp.fold_unicode("\u2018a\u2019 b\u2014c\u2212d\u00a0e\u3000f") == "'a' b-c-d e f"

    def test_non_ascii_is_dropped(self):
        assert pp.fold_unicode("a\u2713b\U0001F600c\u4e2d") == "abc"
        assert pp.preprocess_v2("int a\u2713b;") == "int ab;"

    @pytest.mark.parametrize(
        "src,expected",
        [
            ("int x = 1'000; // c", "int x = 1'000;"),
            ("char c = '\"'; int y; // c", "char c = '\"'; int y;"),
            ('puts("http://a"); /* b */', 'puts("http://a");'),
            # Digit separators inside hex/binary/suffixed literals (token starts with a digit).
            ("x = 0xDEAD'BEEF; // c", "x = 0xDEAD'BEEF;"),
            ("x = 0b1010'1010; // c", "x = 0b1010'1010;"),
            ("x = 1'000'000ull; // c", "x = 1'000'000ull;"),
            ("x = 0x1'Fu + 0XaB'cD; // c", "x = 0x1'Fu + 0XaB'cD;"),
            # Real char literals are untouched.
            ("c = 'a'; // c", "c = 'a';"),
            ("c = '\\''; // c", "c = '\\'';"),
            ("x = 'b'; // c", "x = 'b';"),
            ("c = '1'; d = '0'+n; // c", "c = '1'; d = '0'+n;"),
            ("s = u8'a'; t = v1; // c", "s = u8'a'; t = v1;"),
        ],
    )
    def test_comments(self, src, expected):
        assert pp.preprocess_v2(src) == expected

    def test_comment_marker_removed_with_comment(self):
        out = pp.preprocess_v2("// Zadaca 1, Zadatak 1\nint main(){}")
        assert out == "int main(){}"

    @pytest.mark.parametrize("header", HEADER_FORMS)
    def test_leading_header_lines_equal_body(self, header):
        body = "int main(){}"
        assert pp.preprocess_v2(header + "\n" + body) == pp.preprocess_v2(body)
        assert pp.preprocess_v2(header + "\r\n\r\n" + body) == pp.preprocess_v2(body)

    def test_header_print_line_removed_entirely(self):
        body_lines = ["int main() {", "    int n = 0;", "    return n;", "}"]
        with_print = body_lines[:2] + ['    printf("Zada\u0107a 5, Zadatak 3");'] + body_lines[2:]
        out = pp.preprocess_v2("\n".join(with_print))
        assert out == pp.preprocess_v2("\n".join(body_lines))
        assert "zadac" not in out.lower() and "zadat" not in out.lower()

    @pytest.mark.parametrize(
        "line",
        ['std::cout << "Tutorijal 3" << std::endl;', 'PUTS("ZADATAK br. 2");', 'printf("zadaa 1");'],
    )
    def test_print_line_variants_removed(self, line):
        assert pp.preprocess_v2("int a;\n" + line + "\nint b;") == "int a;\nint b;"

    def test_marker_tokens_removed_everywhere_else(self):
        out = pp.preprocess_v2('int a;\nchar *s = "Tutorijal 2 ok";')
        assert out == 'int a;\nchar *s = " ok";'

    def test_identifiers_preserved(self):
        assert pp.preprocess_v2("x = 1; /* Zadatak 2 */ int zadatak_count = 0;") == (
            "x = 1; int zadatak_count = 0;"
        )
        assert pp.preprocess_v2("int zadatak_count = 0;") == "int zadatak_count = 0;"
        assert pp.preprocess_v2("int x = printf_count;") == "int x = printf_count;"

    def test_whitespace_layout_is_removed(self):
        two = "int main() {\n  int a  =  1;\n\n  return a;\n}\n"
        four = "int main() {\n    int a = 1;\n    return a;   \n}"
        tab = "int main() {\n\tint a\t= 1;\n\n\n\treturn a;\n}\n"
        expected = "int main() {\nint a = 1;\nreturn a;\n}"
        assert pp.preprocess_v2(two) == pp.preprocess_v2(four) == pp.preprocess_v2(tab) == expected

    def test_literal_spacing_is_preserved(self):
        assert pp.preprocess_v2('printf("a    b\t c");   x  = 1;') == 'printf("a    b  c"); x = 1;'

    def test_empty_and_blank_inputs(self):
        assert pp.preprocess_v2("") == ""
        assert pp.preprocess_v2("   \n\t\n") == ""

    @pytest.mark.parametrize("text", FIXTURES + HEADER_FORMS)
    def test_idempotent(self, text):
        once = pp.preprocess_v2(text)
        assert pp.preprocess_v2(once) == once


HUMAN_TWIN = (
    "\ufeff   B16/17 (Tutorijal 13, Zadatak 1)\r\n"
    "/*B 2017/2018, Zada\u0107a 2, Zadatak 1\r\n autotestovi */\r\n"
    "#include <stdio.h>\r\n"
    "\r\n"
    "int main()  {\r\n"
    "\tint n;  // broj \u010d\r\n"
    "\tprintf(\"Zada\u0107a 4, Zadatak 4\");\r\n"
    "\tprintf(\u201cUnesite broj \u010d: \u201d);   \r\n"
    "\tscanf(\"%d\", &n);\r\n"
    "\r\n"
    "\treturn 0;\r\n"
    "}\r\n"
)
AI_TWIN = (
    "#include <stdio.h>\n"
    "\n"
    "int main() {\n"
    "    int n;\n"
    "    printf(\"Unesite broj c: \");\n"
    "    scanf(\"%d\", &n);\n"
    "    return 0;\n"
    "}\n"
)


class TestAlphabetSymmetryGuard:
    def test_encode_layout(self):
        out = pp.encode("abc")
        assert out.dtype == np.uint8
        assert 0 not in out
        assert out.tolist() == [ALPHABET.index(c) + 2 for c in "abc"]
        assert pp.encode(ALPHABET).tolist() == list(range(2, VOCAB_SIZE))
        assert PAD_IDX != UNK_IDX

    def test_empty_encodes_to_unk(self):
        assert pp.encode("").tolist() == [UNK_IDX]

    def test_out_of_alphabet_chars_map_to_unk(self):
        assert pp.encode("\t\x01\u2713").tolist() == [UNK_IDX] * 3

    def test_non_ascii_never_reaches_unk_after_preprocessing(self):
        out = pp.encode(pp.preprocess_v2("a\u2713b\U0001F600c"))
        assert out.tolist() == pp.encode("abc").tolist()
        assert UNK_IDX not in out

    def test_padding_is_distinct_from_real_chars(self):
        seqs = [pp.encode(pp.preprocess_v2(t)) for t in (AI_TWIN, "int a;", "x")]
        width = max(len(s) for s in seqs)
        batch = np.stack([np.pad(s, (0, width - len(s))) for s in seqs])
        for row, seq in zip(batch, seqs):
            assert (row[: len(seq)] != PAD_IDX).all()
            assert (row[len(seq):] == PAD_IDX).all()

    def test_effective_length(self):
        assert pp.effective_length_v2("int a;\nb c") == 7
        assert pp.effective_length_v2("") == 0

    def test_human_and_ai_twins_encode_identically(self):
        human = pp.preprocess_v2(HUMAN_TWIN)
        ai = pp.preprocess_v2(AI_TWIN)
        assert human == ai
        assert np.array_equal(pp.encode(human), pp.encode(ai))
        assert pp.leak_hits(human) == set()

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("int a;\nint b;", set()),
            ("int zadatak_count;", set()),
            ("Zadaca x", {"course_marker"}),
            ("TUTORIJAL", {"course_marker"}),
            ("autotestovi", {"course_marker"}),
            ("a\tb", {"non_alphabet"}),
            ("a\rb", {"non_alphabet"}),
            ("a\x01b", {"non_alphabet"}),
            ("caf\u00e9", {"non_alphabet"}),
            ("zadatak 1\t", {"course_marker", "non_alphabet"}),
        ],
    )
    def test_leak_hits(self, text, expected):
        assert pp.leak_hits(text) == expected

    def test_leak_patterns_names(self):
        assert set(pp.LEAK_PATTERNS) == {"non_alphabet", "course_marker"}

    def test_guard_passes_on_clean_texts(self):
        shares = pp.leak_guard(["int main(){return 0;}"] * 1000)
        assert shares == {"non_alphabet": 0.0, "course_marker": 0.0}

    def test_guard_passes_at_threshold(self):
        texts = ["int main(){return 0;}"] * 1000
        texts[5] = "int main(){puts(\"Zadatak 1\");}"
        shares = pp.leak_guard(texts)
        assert shares["course_marker"] == pytest.approx(0.001)

    def test_guard_raises_above_threshold(self):
        texts = ["int main(){return 0;}"] * 1000
        texts[3] = texts[7] = "int main(){puts(\"Zadatak 1\");}"
        with pytest.raises(pp.LeakGuardError, match="course_marker") as excinfo:
            pp.leak_guard(texts)
        assert excinfo.value.shares["course_marker"] == pytest.approx(0.002)
        assert excinfo.value.offending["course_marker"] == [3, 7]

    def test_guard_on_empty_input(self):
        assert pp.leak_guard([]) == {"non_alphabet": 0.0, "course_marker": 0.0}