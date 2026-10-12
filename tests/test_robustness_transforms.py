"""Unit tests for semantic-preserving code transformations and validity checks."""

import shutil
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import pytest

from models.graphcodebert.v2.baselines import jaccard_set
from models.graphcodebert.v2.dfg import parse_source
from models.robustness.transforms import (
    TRANSFORMS,
    TransformResult,
    apply_condition,
    derive_seed,
    t0_identity,
    t1_rename_identifiers,
    t2_for_while,
    t3_reorder_stmts,
    t4_operators,
    t5_dead_code,
    t6_invert_if,
    t7_combined,
)
from models.robustness.validity import (
    count_error_nodes,
    syntax_check,
    token_edit_ratio,
    abstract_edit_ratio,
)

C_SAMPLE = """
#include <stdio.h>

struct Point {
    int x;
    int y;
};

int compute(int n) {
    int acc = 0;
    int step = 1;
    for (int i = 0; i < n; i++) {
        acc = acc + step;
    }
    if (acc > 10) {
        acc += 2;
    } else {
        acc -= 1;
    }
    return acc;
}

int main(void) {
    struct Point pt;
    pt.x = 5;
    pt.y = 10;
    int res = compute(pt.x);
    printf("Result: %d\\n", res);
    return 0;
}
"""

CPP_SAMPLE = """
#include <iostream>

class Counter {
public:
    int count;
    Counter() : count(0) {}
};

int process(int limit) {
    int total = 0;
    int inc = 1;
    for (int idx = 0; idx < limit; ++idx) {
        total = total + inc;
    }
    if (total > 5) {
        total += 10;
    } else {
        total -= 2;
    }
    return total;
}

int main() {
    Counter c;
    c.count = 4;
    int val = process(c.count);
    std::cout << "Value: " << val << std::endl;
    return 0;
}
"""


@pytest.mark.parametrize("lang,code", [("c", C_SAMPLE), ("cpp", CPP_SAMPLE)])
@pytest.mark.parametrize("trans_name", ["T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7"])
@pytest.mark.parametrize("intensity", [0.25, 0.5, 1.0])
def test_transforms_parse_validity_and_no_new_errors(lang, code, trans_name, intensity):
    """All transforms across C/C++ at various intensities must parse without introducing new AST errors."""
    cond = f"{trans_name}@{intensity}" if trans_name == "T7" else trans_name
    seed = derive_seed(42, "dummy_hash", trans_name, intensity)
    res = apply_condition(code, lang, cond, seed=seed)

    assert isinstance(res, TransformResult)
    orig_tree = parse_source(code.encode("utf-8"), lang)
    trans_tree = parse_source(res.code.encode("utf-8"), lang)

    orig_errors = count_error_nodes(orig_tree.root_node)
    trans_errors = count_error_nodes(trans_tree.root_node)
    assert trans_errors <= orig_errors, f"{trans_name} introduced new AST error nodes"

    if shutil.which("gcc" if lang == "c" else "g++"):
        assert syntax_check(res.code, lang) is True


def test_t0_identity_is_byte_identical():
    """T0 must preserve the original text untouched, including comments and whitespace."""
    commented = "// Header comment\nint main() { /* body */ return 0; }\n"
    res = t0_identity(commented, "c", p=1.0, seed=42)
    assert res.code == commented
    assert res.n_eligible == 0
    assert res.n_applied == 0


def test_t1_identifier_renaming_preserves_jaccard_and_safe_symbols():
    """T1: jaccard_set(orig) == jaccard_set(T1(orig)) (H2 proof); main, printf, and struct fields kept."""
    res_c = t1_rename_identifiers(C_SAMPLE, "c", p=1.0, seed=42)
    assert res_c.n_applied > 0

    # H2 core proof: Jaccard set must be 100% identical
    s_orig = jaccard_set(C_SAMPLE)
    s_trans = jaccard_set(res_c.code)
    assert np.array_equal(s_orig, s_trans), "T1 altered Jaccard shingle set!"

    # main and printf must not be renamed
    assert "main" in res_c.code
    assert "printf" in res_c.code
    # struct fields x and y must remain intact
    assert ".x" in res_c.code
    assert ".y" in res_c.code
    assert "int x;" in res_c.code
    assert "int y;" in res_c.code

    # Same check for C++
    res_cpp = t1_rename_identifiers(CPP_SAMPLE, "cpp", p=1.0, seed=42)
    s_orig_cpp = jaccard_set(CPP_SAMPLE)
    s_trans_cpp = jaccard_set(res_cpp.code)
    assert np.array_equal(s_orig_cpp, s_trans_cpp), "T1 altered C++ Jaccard shingle set!"
    assert "main" in res_cpp.code
    assert "count" in res_cpp.code


def test_t2_for_while_conversion():
    """T2 converts for <-> while, but leaves loops with continue untouched."""
    snippet_for = "void f(int n) { int s = 0; for (int i = 0; i < n; i++) { s += i; } }"
    res_for = t2_for_while(snippet_for, "c", p=1.0, seed=42)
    assert res_for.n_applied == 1
    assert "while" in res_for.code
    assert "for" not in res_for.code

    snippet_while = "void g(int x) { while (x > 0) x /= 2; }"
    res_while = t2_for_while(snippet_while, "c", p=1.0, seed=42)
    assert res_while.n_applied == 1
    assert "for" in res_while.code
    assert "while" not in res_while.code

    # Loop with continue belonging to it must NOT be converted
    snippet_continue = "void h(int n) { for (int i = 0; i < n; i++) { if (i == 2) continue; } }"
    res_cont = t2_for_while(snippet_continue, "c", p=1.0, seed=42)
    assert res_cont.n_applied == 0
    assert res_cont.code == snippet_continue

    # Inner loop with continue should allow outer loop to convert
    snippet_nested = "void k(int n) { for (int i = 0; i < n; i++) { for (int j = 0; j < 5; j++) { continue; } } }"
    res_nested = t2_for_while(snippet_nested, "c", p=1.0, seed=42)
    # At least the outer loop is eligible
    assert res_nested.n_eligible >= 1


def test_t3_statement_reordering_read_write_sets():
    """T3 swaps independent statements; dependent stmts and consecutive calls are not swapped."""
    # Dependent statements: a = 1; b = a; -> must NOT swap
    dep_snippet = "void f() { int a = 1; int b = a; }"
    res_dep = t3_reorder_stmts(dep_snippet, "c", p=1.0, seed=42)
    assert res_dep.n_applied == 0
    assert res_dep.code == dep_snippet

    # Independent statements: x = 1; y = 2; -> must swap
    indep_snippet = "void f() { int x = 1; int y = 2; }"
    res_indep = t3_reorder_stmts(indep_snippet, "c", p=1.0, seed=42)
    assert res_indep.n_applied == 1
    assert "int y = 2;\n    int x = 1;" in res_indep.code or "int y = 2; int x = 1;" in res_indep.code

    # Consecutive function calls (I/O): printf("A"); printf("B"); -> must NOT swap
    calls_snippet = 'void f() { printf("A"); printf("B"); }'
    res_calls = t3_reorder_stmts(calls_snippet, "c", p=1.0, seed=42)
    assert res_calls.n_applied == 0
    assert res_calls.code == calls_snippet


def test_t4_equivalent_operators():
    """T4 rewrites operators between equivalent forms."""
    snippet = "void f() { int x = 0; x = x + 1; x = x * 2; x += 3; }"
    res = t4_operators(snippet, "c", p=1.0, seed=42)
    assert res.n_applied >= 1
    # x = x + 1 can become x += 1 or x++
    # x = x * 2 can become x *= 2
    # x += 3 can become x = x + 3
    assert res.code != snippet


def test_t5_dead_code_insertion():
    """T5 inserts benign dead code blocks without breaking syntax."""
    snippet = "void f(int n) { int x = n + 1; x = x * 2; }"
    res = t5_dead_code(snippet, "c", p=1.0, seed=42)
    assert res.n_applied >= 1
    assert "if (0)" in res.code or "(void)0;" in res.code
    assert count_error_nodes(parse_source(res.code.encode("utf-8"), "c").root_node) == 0


def test_t6_branch_inversion():
    """T6 inverts if/else branches using !(cond)."""
    snippet = "void f(int x) { int pos = 0, neg = 0; if (x > 0) { pos++; } else { neg++; } }"
    res = t6_invert_if(snippet, "c", p=1.0, seed=42)
    assert res.n_applied == 1
    assert "!(x > 0)" in res.code or "!((x > 0))" in res.code
    # Inverted body should place neg++ in if and pos++ in else
    assert "neg++" in res.code

    # Multiple chained else if
    chain = "void g(int a) { if (a) { int x = 1; } else if (a == 2) { int y = 2; } else { int z = 3; } }"
    res_chain = t6_invert_if(chain, "c", p=1.0, seed=42)
    assert res_chain.n_applied >= 1
    assert count_error_nodes(parse_source(res_chain.code.encode("utf-8"), "c").root_node) == 0


def test_t7_combined_pipeline():
    """T7 applies T2 -> T3 -> T4 -> T5 with derived seeds."""
    res_100 = t7_combined(C_SAMPLE, "c", p=1.0, seed=42)
    res_050 = t7_combined(C_SAMPLE, "c", p=0.5, seed=42)
    res_025 = t7_combined(C_SAMPLE, "c", p=0.25, seed=42)

    assert res_100.n_applied >= res_025.n_applied
    assert count_error_nodes(parse_source(res_100.code.encode("utf-8"), "c").root_node) == 0
    assert count_error_nodes(parse_source(res_050.code.encode("utf-8"), "c").root_node) == 0
    assert count_error_nodes(parse_source(res_025.code.encode("utf-8"), "c").root_node) == 0


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not available")
def test_execution_equivalence_with_gcc():
    """Transformed programs compile and produce identical stdout when executed."""
    exec_c = """
#include <stdio.h>

int run(int n) {
    int sum = 0;
    int step = 1;
    for (int i = 0; i < n; i++) {
        sum = sum + step;
    }
    if (sum > 5) {
        sum += 2;
    } else {
        sum -= 1;
    }
    return sum;
}

int main(void) {
    int v = run(5);
    printf("OUTPUT=%d\\n", v);
    return 0;
}
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        orig_src = tmp_path / "orig.c"
        orig_bin = tmp_path / "orig.exe"
        orig_src.write_text(exec_c, encoding="utf-8")

        res_build_orig = subprocess.run(
            ["gcc", "-O0", str(orig_src), "-o", str(orig_bin)],
            capture_output=True,
            text=True,
        )
        assert res_build_orig.returncode == 0, f"Orig build failed: {res_build_orig.stderr}"
        orig_run = subprocess.run([str(orig_bin)], capture_output=True, text=True)
        assert orig_run.returncode == 0

        # Test T1..T7 transformations for execution equivalence
        for cond in ["T1", "T2", "T3", "T4", "T5", "T6", "T7@1.0"]:
            trans = apply_condition(exec_c, "c", cond, seed=42)
            trans_src = tmp_path / f"trans_{cond.replace('@', '_')}.c"
            trans_bin = tmp_path / f"trans_{cond.replace('@', '_')}.exe"
            trans_src.write_text(trans.code, encoding="utf-8")

            res_build_trans = subprocess.run(
                ["gcc", "-O0", str(trans_src), "-o", str(trans_bin)],
                capture_output=True,
                text=True,
            )
            assert res_build_trans.returncode == 0, f"{cond} build failed: {res_build_trans.stderr}\nCode:\n{trans.code}"
            trans_run = subprocess.run([str(trans_bin)], capture_output=True, text=True)
            assert trans_run.returncode == 0
            assert trans_run.stdout == orig_run.stdout, f"{cond} produced different stdout!"
