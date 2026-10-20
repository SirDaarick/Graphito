"""v2_norm robustness method: canonical renaming applied to both sides before embedding."""

import pytest

from models.logic_eval.canonical import canonicalize_code
from models.robustness.scoring import texts_for_method
from models.robustness.transforms import apply_condition, t1_rename_identifiers

SNIPPETS_C = [
    "#include <stdio.h>\nint sumar(int a, int b) {\n  int total = a + b;\n  return total;\n}\n"
    "int main() {\n  int x = 3;\n  int y = 4;\n  printf(\"%d\\n\", sumar(x, y));\n  return 0;\n}\n",
    "#include <stdio.h>\nint main() {\n  int n, i, acc = 0;\n  scanf(\"%d\", &n);\n"
    "  for (i = 0; i < n; i++) {\n    acc += i;\n  }\n  printf(\"%d\", acc);\n  return 0;\n}\n",
    "#include <stdio.h>\nint fact(int k) {\n  if (k <= 1) return 1;\n  return k * fact(k - 1);\n}\n"
    "int main() {\n  int m = 5;\n  printf(\"%d\", fact(m));\n  return 0;\n}\n",
]
SNIPPET_CPP = (
    "#include <iostream>\nusing namespace std;\nint doble(int valor) {\n  int res = valor * 2;\n  return res;\n}\n"
    "int main() {\n  int dato = 7;\n  cout << doble(dato) << endl;\n  return 0;\n}\n"
)


@pytest.mark.parametrize("code,lang", [(s, "c") for s in SNIPPETS_C] + [(SNIPPET_CPP, "cpp")])
def test_canonicalize_absorbs_t1(code, lang):
    renamed = t1_rename_identifiers(code, lang, p=1.0, seed=42)
    assert renamed.code != code  # T1 actually changed something
    assert canonicalize_code(renamed.code, lang) == canonicalize_code(code, lang)


def test_v2_norm_canonicalizes_both_sides():
    code = SNIPPETS_C[0]
    trans = apply_condition(code, "c", "T1", seed=42).code
    o, t = texts_for_method("v2_norm", [code], [trans], ["c"])
    assert o == [canonicalize_code(code, "c")]
    assert t == [canonicalize_code(trans, "c")]
    assert o == t


def test_other_methods_leave_texts_untouched():
    code = SNIPPETS_C[1]
    trans = apply_condition(code, "c", "T1", seed=42).code
    for m in ("v2", "jaccard", "v2_nodfg"):
        o, t = texts_for_method(m, [code], [trans], ["c"])
        assert o == [code] and t == [trans]


def test_v2_norm_deterministic():
    code = SNIPPETS_C[2]
    a = texts_for_method("v2_norm", [code], [code], ["c"])
    b = texts_for_method("v2_norm", [code], [code], ["c"])
    assert a == b


def test_length_mismatch_rejected():
    with pytest.raises(ValueError):
        texts_for_method("v2_norm", ["int x;"], [], ["c"])


def test_canonicalize_tolerates_broken_code_and_is_stable():
    broken = "int f(int a){ int b = a +; return b; } int g(){return f(1)}"
    assert canonicalize_code(broken, "c") == canonicalize_code(broken, "c")
